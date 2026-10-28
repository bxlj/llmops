"""
@Time    : 2026-10-26 14:47
@Author  : JiaChengJie
@File    : language_model_handle.py
"""
import io
from dataclasses import dataclass

from flask import send_file
from flask_login import login_required
from injector import inject

from internal.service.language_model_service import LanguageModelService
from pkg.response import success_json


@inject
@dataclass
class LanguageModelHandel:
    """多LLM接口集成开发"""
    language_model_service: LanguageModelService

    @login_required
    def get_language_models(self):
        """获取LLMOps语言模型列表"""
        language_models = self.language_model_service.get_language_models()

        return success_json(language_models)

    @login_required
    def get_language_model(self, provider_name: str, model_name: str):
        """获取指定模型的详细信息"""
        return success_json(self.language_model_service.get_language_model(provider_name, model_name))

    def get_language_model_icon(self, provider_name: str):
        """获取指定模型对应icon图标"""
        icon, mimetype = self.language_model_service.get_language_model_icon(provider_name)
        return send_file(io.BytesIO(icon), mimetype=mimetype)
