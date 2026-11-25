#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2026/11/03 17:30
@Author  : jiachengjie
@File    : chat.py
"""
import os
from typing import Optional, Tuple

import tiktoken
from langchain_openai import ChatOpenAI
from pydantic import Field, SecretStr

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    """智谱聊天模型，走智谱BigModel的OpenAI兼容端点（实测glm-5.3支持工具调用，endpoint与openai SDK完全兼容）"""
    openai_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.environ.get("ZHIPU_API_KEY") or ""),
    )
    openai_api_base: str = "https://open.bigmodel.cn/api/paas/v4"

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写词表模型获取逻辑，智谱模型名不在tiktoken字典中，固定使用gpt-3.5-turbo的分词器防止token统计报错"""
        # 1.将词表模型设置为gpt-3.5-turbo（对应cl100k_base编码器）
        model = "gpt-3.5-turbo"

        # 2.返回模型名字+编码器
        return model, tiktoken.encoding_for_model(model)
