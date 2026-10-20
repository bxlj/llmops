"""
@Time    : 2026-04-02 9:24
@AUthor  : jiachengjie
@File    : builtin_tool_handler.py
"""
import io
from dataclasses import dataclass

from flask import send_file
from flask_login import login_required
from injector import inject

from internal.service.builtin_tool_service import BuiltinToolService
from pkg.response import success_json


@inject
@dataclass
class BuiltinToolHandler:
    """内置插件处理器"""
    builtin_service: BuiltinToolService

    @login_required
    def get_builtin_tools(self):
        """获取LLMOps所有内置工具信息+提供商信息"""
        builtin_tools = self.builtin_service.get_builtin_tools()
        return success_json(builtin_tools)

    @login_required
    def get_provider_tool(self, provider_name: str, tool_name: str):
        """根据传递的提供商名字+工具名字获取指定工具的信息"""
        builtin_tool = self.builtin_service.get_provider_tool(provider_name, tool_name)
        return success_json(builtin_tool)

    def get_provider_icon(self, provider_name: str):
        """根据供应商名称获取对应图标"""
        icon, mimetype = self.builtin_service.get_provider_icon(provider_name)
        return send_file(io.BytesIO(icon), mimetype=mimetype)

    @login_required
    def get_categories(self):
        categories = self.builtin_service.get_categories()
        return success_json(categories)
