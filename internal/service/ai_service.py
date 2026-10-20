"""
@Time    : 2026-07-20 9:26
@Author  : JiaChengJie
@File    : ai_service.py
"""
import json
import os
from dataclasses import dataclass
from typing import Generator
from uuid import UUID

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.exception import ForbiddenException
from internal.model import Account, Message
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService


@inject
@dataclass
class AIService(BaseService):
    """ai辅助模块"""
    db: SQLAlchemy
    conversation_service: ConversationService

    @classmethod
    def optimize_prompt(cls, prompt: str) -> Generator[str, None, None]:
        """使用AI优化提示词模板"""
        # 1.构建优化prompt的提示词模板
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE,),
            ("human", f"{prompt}")
        ])

        # 2. 构建llm
        llm = ChatOpenAI(
            base_url=os.getenv("OPENAI_API_BASE"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL_NAME"),
            temperature=os.getenv("OPENAI_TEMPERATURE"),
        )

        # 3. 构建应用链
        chain = prompt_template | llm | StrOutputParser()

        for optimize_prompt in chain.stream({"prompt": prompt}):
            data = {"optimize_prompt": optimize_prompt}
            yield f"event: optimize_prompt\ndata: {json.dumps(data)}\n\n"

    def generate_suggested_questions(
            self,
            message_id: UUID,
            account: Account
    ) -> list[str]:
        """根据传递的消息id获取建议问题列表"""
        # 1.查询消息并校验权限信息
        message = self.get(Message, message_id)
        if not message or message.created_by != account.id:
            raise ForbiddenException("当前用户无法查看或无权限")

        # 2.构建对话历史列表
        history = f"Human: {message.query}\nAI: {message.answer}"

        # 3.调用服务生成建议问题
        questions = self.conversation_service.generate_suggested_questions(history)
        return questions
