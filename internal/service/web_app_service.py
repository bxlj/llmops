"""
@Time    : 2026-11-22 15:27
@Author  : JiaChengJie
@File    : web_app_service.py
"""
import json
from dataclasses import dataclass
from threading import Thread
from typing import Generator
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.messages import HumanMessage

from internal.core.agent.agents import FunctionCallAgent
from internal.core.agent.agents.react_agent import ReACTAgent
from internal.core.agent.entities.agent_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.memory.token_buffer_memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.model.account import Account
from internal.model.app import App
from internal.model.conversation import Conversation, Message
from internal.service.app_config_service import AppConfigService
from internal.service.language_model_service import LanguageModelService
from internal.service.retrieval_service import RetrievalService
from language_model.entities.model_entity import ModelFeature
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class WebAppService(BaseService):
    db: SQLAlchemy
    app_config_service: AppConfigService
    retrieval_service: RetrievalService
    language_model_service: LanguageModelService

    def get_app_by_token(self, token: str) -> App:
        """根据token获取app信息"""
        app = self.db.session.query(App).filter(App.token == token).one_or_none()

        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("当前应用信息不存在")

        return app

    def web_app_chat(self, token: str, conversation_id: UUID, query: str, account: Account) -> Generator:
        """根据传递的token凭证+请求与指定的WebApp进行对话"""
        # 1. 获取app信息
        app = self.get_app_by_token(token)
        # 2. 根据是否传递了会话id，判断会话归属信息
        if conversation_id:
            conversation = self.get(Conversation, conversation_id)
            if (
                    not conversation
                    or app.id != conversation.id
                    or conversation.invoke_from != InvokeFrom.WEB_APP
                    or conversation.created_by != account.id
                    or conversation.is_deleted is True
            ):
                raise ForbiddenException("该会话不存在，或者不属于/用户/调用方式")
        else:
            # 3. 如果没有传递会话id,则创建一个新的会话
            self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.WEB_APP,
                "created_by": account.id,
            })

        # 4. 获取校验后的运行时配置
        app_config = self.app_config_service.get_app_config(app)

        # 5. 新建一条消息信息
        message = self.create(
            Message,
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.WEB_APP,
            created_by=account.id,
            query=query,
        )

        # 6. 根据配置信息创建llm对象
        llm = self.language_model_service.load_language_model(app_config.get("model_config"), {})

        # 7. 实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )

        history = token_buffer_memory.get_history_prompt_message(
            message_limit=app_config["dialog_round"]
        )

        # 8. 将草稿配置中的tool转换为langchain工具
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"])

        # 9. 检测是否关联了知识库
        if app_config["datasets"]:
            # 10. 构建langchain知识库检索工具
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrieval_strategy=RetrievalSource.APP,
                **app_config["retrieval_strategy"],
            )
            tools.append(dataset_retrieval)

        # 11. 检索是否关联工作流，如果关联工作流，则将工作信息构建成工具添加到tools中
        if app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow.id for workflow in app_config["workflows"]],
            )
            tools.extend(workflow_tools)

        # 12. 根据LLM是否支持tool_call决定使用不同的Agent
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReACTAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.WEB_APP,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
            ),
        )

        # 13. 定义字典存储推理过程，并调用智能体获取消息
        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [HumanMessage(query)],
            "history": history,
            "long_term_memory": conversation.summary,
        }):
            # 14.提取thought以及answer
            event_id = str(agent_thought.id)

            # 15.将数据填充agent_thought, 便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING:
                # 16.除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                    if event_id not in agent_thoughts:
                        # 17. 初始化智能体消息时间
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 18. 叠加智能体信息
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            # 消息相关数据
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            # 答案相关数据
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            # Agent推理统计相关
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 19.处理其他类型事件的消息
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 20.将消息以及推理过程添加到数据库
        thread = Thread(
            target=self.conversation_service.save_agent_thoughts,
            kwargs={
                "flask_app": current_app._get_current_object(),
                "account_id": account.id,
                "app_id": app.id,
                "app_config": app_config,
                "conversation_id": conversation.id,
                "message_id": message.id,
                "agent_thoughts": [agent_thought for agent_thought in agent_thoughts.values()],
            }
        )
        thread.start()
