"""
@Time    : 2026-04-02 10:02
@AUthor  : jiachengjie
@File    : builtin_tool_service.py
"""
import mimetypes
import os.path
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject
from langchain_core.utils.pydantic import BaseModel

from internal.core.tool.builtin_tools.categories import BuiltinCategoryManager
from internal.core.tool.builtin_tools.providers import BuiltinProviderManager
from internal.exception import NotFoundException


@inject
@dataclass
class BuiltinToolService:
    """内置工具服务"""
    builtin_provider_manager: BuiltinProviderManager
    builtin_category_manager: BuiltinCategoryManager

    def get_builtin_tools(self) -> list:
        """获取LLMOps项目中的所有内置提供商+工具对应的信息"""
        # 1.获取所有的提供商
        providers = self.builtin_provider_manager.get_providers()
        # 2.遍历所有的提供商并提取工具信息
        builtin_tools = []
        for provider in providers:
            provider_entity = provider.provider_entity
            builtin_tool = {
                # 对象转为字典
                **provider_entity.model_dump(exclude=["icon"]),
                "tools": [],
            }
            # 3.循环遍历提取提供者的所有工具实体
            for tool_entity in provider.get_tool_entitys():
                # 4.从提供者中获取工具函数
                tool = provider.get_tool(tool_entity.name)
                # 5.构建工具实体信息
                tool_dict = {
                    **tool_entity.model_dump(),
                    "inputs": self.get_tool_inputs(tool),
                }
                builtin_tool["tools"].append(tool_dict)
            builtin_tools.append(builtin_tool)

        return builtin_tools

    def get_provider_tool(self, provider_name: str, tool_name: str) -> dict:
        provider = self.builtin_provider_manager.get_provider(provider_name)

        if provider is None:
            raise NotFoundException(f"该提供商{provider_name}不存在")

        # 2.获取该提供商下对应的工具
        tool_entity = provider.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(f"该工具{tool_name}不存在")

        # 3.组装提供商和工具实体信息
        provider_entity = provider.provider_entity
        tool = provider.get_tool(tool_name)
        print(tool)

        builtin_tool = {
            "providers": {**provider_entity.model_dump(exclude=["icon", "created_at"])},
            **tool_entity.model_dump(),
            "created_at": provider_entity.created_at,
            "inputs": self.get_tool_inputs(tool),
        }

        return builtin_tool

    def get_provider_icon(self, provider_name: str) -> tuple[bytes, str]:
        """根据供应商名称获取图标"""
        # 1. 根据provider_name获取供应商实体
        provider = self.builtin_provider_manager.get_provider(provider_name)
        if provider is None:
            raise NotFoundException(f"没有{provider_name}供应商")

        # 2.获取项目的根路径信息
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        provider_path = os.path.join(root_path, "internal", "core", "tool", "builtin_tools", "providers", provider_name)

        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)
        #
        if not os.path.exists(icon_path):
            raise NotFoundException("图标不存在")

        # 6.读取icon的类型
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype

    def get_categories(self) -> list[str, Any]:
        category_map = self.builtin_category_manager.get_category_map()
        return [{
            "name": category["entity"].name,
            "category": category["entity"].category,
            "icon": category["icon"],
        } for category in category_map.values()]

    @classmethod
    def get_tool_inputs(cls, tool) -> list:
        """根据传入的工具获取inputs信息"""
        inputs = []
        if hasattr(tool, "args_schema") and issubclass(tool.args_schema, BaseModel):
            for field_name, model_field in tool.args_schema.__fields__.items():
                inputs.append({
                    "name": field_name,
                    "description": model_field.description or "",
                    "required": model_field.repr,
                    "type": model_field.annotation.__name__,
                })
        return inputs
