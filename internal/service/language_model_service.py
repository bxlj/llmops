"""
@Time    : 2026-10-26 18:24
@Author  : JiaChengJie
@File    : language_model_service.py
"""
import mimetypes
import os
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject

from internal.core.language_model import LanguageModelManager
from internal.exception import NotFoundException
from internal.service import BaseService


@inject
@dataclass
class LanguageModelService(BaseService):
    """多LLM接口集成开发"""
    language_model_manager: LanguageModelManager

    def get_language_models(self) -> list[dict[str, Any]]:
        """获取LLMOps语言模型列表"""
        # 1. 获取provide列表
        providers = self.language_model_manager.get_providers()

        # 2.构建语言模型列表，循环读取数据
        language_models = []
        for provider in providers:
            # 3. 获取providerEntity,modelEntity
            provider_entity = provider.provider_entity
            model_entities = provider.get_model_entities()

            language_model = {
                "name": provider_entity.name,
                "position": provider.position,
                "label": provider_entity.label,
                "icon": provider_entity.icon,
                "description": provider_entity.description,
                "background": provider_entity.background,
                "support_model_types": provider_entity.supported_model_types,
                "models": [{
                    "model": model_entity.model_name,
                    "label": model_entity.label,
                    "model_type": model_entity.model_type,
                    "context_window": model_entity.context_window,
                    "max_output_tokens": model_entity.max_output_tokens,
                    "features": model_entity.features,
                    "metadata": model_entity.metadata,
                    "attributes": model_entity.attributes,
                    "parameters": [{
                        "name": parameter.name,
                        "label": parameter.label,
                        "type": parameter.type,
                        "help": parameter.help,
                        "required": parameter.required,
                        "default": parameter.default,
                        "min": parameter.min,
                        "max": parameter.max,
                        "precision": parameter.precision,
                        "options": [{"label": option.label, "value": option.value} for option in parameter.options],
                    } for parameter in model_entity.parameters]
                } for model_entity in model_entities]
            }
            language_models.append(language_model)

        return language_models

    def get_language_model(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """获取指定模型的详细信息"""
        # 1.根据provider_name获取提供者信息
        provider = self.language_model_manager.get_provider(provider_name)

        if not provider:
            raise NotFoundException("该服务提供者不存在")
        model_entity = provider.get_model_entity(model_name)
        if not model_entity:
            raise NotFoundException("该模型不存在")

        language_model = {
            "models": {
                "model": model_entity.model_name,
                "label": model_entity.label,
                "model_type": model_entity.model_type,
                "context_window": model_entity.context_window,
                "max_output_tokens": model_entity.max_output_tokens,
                "features": model_entity.features,
                "metadata": model_entity.metadata,
                "attributes": model_entity.attributes,
                "parameters": [{
                    "name": parameter.name,
                    "label": parameter.label,
                    "type": parameter.type,
                    "help": parameter.help,
                    "required": parameter.required,
                    "default": parameter.default,
                    "min": parameter.min,
                    "max": parameter.max,
                    "precision": parameter.precision,
                    "options": [{"label": option.label, "value": option.value} for option in parameter.options],
                } for parameter in model_entity.parameters]
            }
        }
        return language_model

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """获取指定模型对应icon图标"""
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("该服务提供者不存在")

        # 2. 获取项目根路径
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3.拼接得到提供者所在的文件夹
        provider_path = os.path.join(root_path, "internal", "core", "language_model", "providers", provider_name)

        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)

        if not os.path.exists(icon_path):
            raise NotFoundException("当前图标不存在")

        # 6.读取icon的类型
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7.读取icon的字节数据
        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype
