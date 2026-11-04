#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/01 20:33
@Author  : thezehui@gmail.com
@File    : chat.py
"""
import os
from typing import Optional

from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """月之暗面聊天模型，走Moonshot的OpenAI兼容端点（langchain_community的MoonshotChat未实现bind_tools，挂载工具会抛NotImplementedError）"""

    openai_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.environ.get("MOONSHOT_API_KEY") or ""),
    )
    openai_api_base: str = "https://api.moonshot.cn/v1"
