#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/01 22:55
@Author  : thezehui@gmail.com
@File    : chat.py
"""
import os
from typing import Optional, Tuple

import tiktoken
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """通义千问聊天模型，走DashScope的OpenAI兼容端点（qwen3.8系列新模型仅在兼容端点提供服务）"""
    openai_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.environ.get("DASHSCOPE_API_KEY") or ""),
    )
    openai_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写词表模型获取逻辑，通义模型名不在tiktoken字典中，固定使用gpt-3.5-turbo的分词器防止token统计报错"""
        # 1.将词表模型设置为gpt-3.5-turbo（对应cl100k_base编码器）
        model = "gpt-3.5-turbo"

        # 2.返回模型名字+编码器
        return model, tiktoken.encoding_for_model(model)
