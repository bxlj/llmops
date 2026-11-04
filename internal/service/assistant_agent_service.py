"""
@Time    : 2026-10-29 14:51
@Author  : JiaChengJie
@File    : assistant_agent_service.py
"""
import datetime
import json
from dataclasses import dataclass
from threading import Thread
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sqlalchemy import desc

from internal.core.agent.agents import AgentQueueManager
from internal.core.agent.agents import FunctionCallAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.language_model.providers.moonshot.chat import Chat
from internal.core.memory.token_buffer_memory import TokenBufferMemory
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.model.account import Account
from internal.model.conversation import Message
from internal.schema.assistant_agent_schema import GetAssistantAgentWithPageReq
from internal.service.conversation_service import ConversationService
from internal.service.faiss_service import FaissService
from internal.task.app_task import auto_create_app
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class AssistantAgentService(BaseService):
    """辅助智能体业务层"""
    db: SQLAlchemy
    faiss_service: FaissService
    conversation_service: ConversationService

    def chat(self, query: str, account: Account) -> Generator:
        """辅助agent与chat多轮次对话"""

        # 1.获取辅助Agent对应的id
        assistant_agent_id = current_app.config.get("ASSISTANT_AGENT_ID")
        # 2.获取当前应用的调试会话信息
        conversation = account.assistant_agent_conversation
        # 3.新建一条消息记录
        message = self.create(
            Message,
            app_id=assistant_agent_id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.ASSISTANT_AGENT,
            query=query,
            created_by=account.id,
            status=MessageStatus.NORMAL
        )

        # 4.使用GPT模型作为辅助Agent的LLM大脑
        llm = Chat(
            model="kimi-k2.6",
            temperature=1,
            features=[ModelFeature.TOOL_CALL, ModelFeature.AGENT_THOUGHT],
            metadata={}
        )

        # 5.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm
        )
        history = token_buffer_memory.get_history_prompt_message(message_limit=3)

        # TODO 6.将草稿配置中的tools转换成LangChain工具
        tools = [
            self.faiss_service.convert_faiss_to_tool(),
            self.convert_create_app_to_tools(account.id),
        ]

        # 7.构建Agent智能体，使用FunctionCallAgent
        agent = FunctionCallAgent(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.ASSISTANT_AGENT,
                enable_long_term_memory=True,
                tools=tools
            ),
        )

        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(query)],
            "history": history,
            "long_term_memory": conversation.summary
        }):
            # 8.提取thought以及answer
            event_id = str(agent_thought.id)

            # 9.将数据填充到agent_thought，便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING:
                # 10.除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 11.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 12.叠加智能体消息
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "latency": agent_thought.latency
                        })
                else:
                    # 13.处理其他类型事件的消息
                    agent_thoughts[event_id] = agent_thought

            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata: {json.dumps(data)}\n\n"

        # 14.将消息以及推理过程添加到数据库
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": assistant_agent_id,
                "app_config": {
                    "long_term_memory": {"enable": True},
                },
                "conversation_id": conversation.id,
                "message_id": message.id,
                "agent_thoughts": [agent_thought for agent_thought in agent_thoughts.values()],
                "invoke_from": InvokeFrom.ASSISTANT_AGENT,
            }
        )

        thread.start()

    def get_assistant_agent_with_page(self, req: GetAssistantAgentWithPageReq, account: Account) -> tuple[
        list[Message], Paginator]:
        """获取当前登录账号的辅助Agent对话历史列表"""
        # 1.获取应用的调试会话
        conversation = account.assistant_agent_conversation
        print(f"conversation值是：{conversation.id}")
        # 2. 构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 3. 构建筛选器
        filters = []
        if req.created_at.data:
            # 3.将时间戳转换成DateTime
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        # 4. 执行分页并获取数据
        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters,
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def delete_assistant_agent_conversation(self, account: Account):
        """清空当前登录账号与辅助Agent的对话列表"""
        self.update(account, assistant_agent_conversation_id=None)

    def stop_chat(self, task_id: UUID, account: Account) -> None:
        """根据传递的任务id+账号停止某次响应会话"""
        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.ASSISTANT_AGENT, account.id)

    @classmethod
    def convert_create_app_to_tools(cls, account_id: UUID) -> BaseTool:
        """定义自动创建Agent应用LangChain工具"""

        class CreateAppTools(BaseModel):
            name: str = Field(description="需要创建的Agent/应用名称,长度最多50个字符")
            description: str = Field(description="需要创建的Agent/描述信息，请详细概括该应用的功能")

        @tool("create_app", args_schema=CreateAppTools)
        def create_app(name: str, description: str) -> str:
            """如果用户提出要创建一个Agent应用，你可以调用此工具，参数的输入是应用的名称 + 描述，返回的提示是创建后的成功提示"""
            # 1.提交celery任务并同步等待结果。
            # 工具执行夹在Agent的两次LLM调用之间：此刻Flask侧没有在途的Moonshot请求，
            # 任务内两次顺序调用不会与最终回答的流式响应争抢组织并发=1的配额；
            # 同时任务异常会在这里抛出，避免"实际失败却告诉用户创建成功"。更换为质谱多并发访问
            auto_create_app.delay(account_id, name, description)

            return f"已调用后端服务创建Agent应用成功，名字是：{name}，描述信息为：{description}"

        return create_app
