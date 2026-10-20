"""
@Time    : 2026-06-10 14:26
@Author  : jiachengjie
@File    : token_buffer_memory.py
"""
from dataclasses import dataclass

from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, trim_messages, get_buffer_string
from sqlalchemy import desc

from internal.entity.conversation_entity import MessageStatus
from internal.model import Conversation, Message
from pkg.sqlalchemy import SQLAlchemy


@dataclass
class TokenBufferMemory:
    """基于token计数的缓冲记忆组件"""
    db: SQLAlchemy
    conversation: Conversation
    model_instance: BaseLanguageModel  # LLM大语言模型

    def get_history_prompt_message(
            self,
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> list[AnyMessage]:
        """根据传递的token限制+消息条数限制获取指定会话模型的历史消息列表"""
        # 1. 判断会话模型是否为空，如果为空直接返回
        if self.conversation is None:
            return []

        # 2. 查找会话模型表
        messages = self.db.session.query(Message).filter(
            Message.conversation_id == self.conversation.id,
            Message.is_deleted == False,
            Message.status.in_([MessageStatus.NORMAL, MessageStatus.STOP, MessageStatus.TIMEOUT]),
            Message.answer != "",
        ).order_by(desc("created_at")).limit(message_limit).all()

        if not messages:
            return []

        messages = list(reversed(messages))

        # 3. messages转化为LangChain 模型需要的格式
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                HumanMessage(content=message.query),
                AIMessage(content=message.answer),
            ])

        # 4.调用LangChain继承的trim_messages函数剪切消息列表
        return trim_messages(
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.token_counter,
            strategy="last",
        )

    def get_history_prompt_text(
            self,
            human_prefix: str,
            ai_prefix: str,
            max_token_limit: int = 2000,
            message_limit: int = 10,
    ) -> str:
        """根据传递的数据获取指定会话历史消息提示文本(短期记忆的文本形式，用于文本生成模型)"""
        # 1.根据传递的信息获取历史消息列表
        messages = self.get_history_prompt_message(max_token_limit, message_limit)
        # 2. 使用LangChain里面的get_buffer_string函数将消息列表转为文本格式
        return get_buffer_string(messages, human_prefix, ai_prefix)

    @staticmethod
    def token_counter(messages):
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")

        text = ""

        for message in messages:
            text += message.content

        return len(
            encoding.encode(text)
        )
