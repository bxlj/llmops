"""
@Time    : 2026-04-03 16:56
@Author  : jiachengjie
@File    : api_tool_handle.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.api_tool_schema import ValidateOpenAPISchemaReq, ValidateCreateAPISchemaReq, \
    GetApiToolProviderResp, GetApiToolResp, GetToolProviderWithPageReq, GetApiToolProvidersWithPageResp, \
    UpdateAPISchemaReq
from internal.service.api_tool_service import ApiToolService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_message, success_json


@inject
@dataclass
class ApiToolHandler:
    """自定义api处理器"""
    api_tool_service: ApiToolService

    @login_required
    def create_api_tool(self):
        """创建自定义插件"""
        req = ValidateCreateAPISchemaReq()
        if not req.validate:
            return validate_error_json(req.errors)

        self.api_tool_service.create_api_tool(req, current_user)

        return success_message("数据保存成功")

    @login_required
    def update_api_tool_provider(self, provider_id: UUID):
        """修改数据信息"""
        req = UpdateAPISchemaReq()
        if not req.validate:
            return validate_error_json(req.errors)

        self.api_tool_service.update_api_tool_provider(provider_id, req, current_user)

        return success_message("数据修改成功")

    @login_required
    def get_api_tool_provider_with_page(self):
        """获取API提供者信息列表，支持分页"""
        req = GetToolProviderWithPageReq(request.args)
        if not req.validate:
            return validate_error_json(req.errors)

        api_tool_providers, paginator = self.api_tool_service.get_api_tool_provider_with_page(req, current_user)

        resp = GetApiToolProvidersWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_tool_providers), paginator=paginator))

    @login_required
    def delete_api_tool_provider(self, provider_id: UUID):
        """删除提供者工具信息"""
        self.api_tool_service.delete_api_provider_tool(provider_id, current_user)

        return success_message("删除数据成功")

    @login_required
    def get_api_tool(self, provider_id: UUID, tool_name: str):
        """根据传入的provider_id,name获取工具信息"""
        api_tool = self.api_tool_service.get_api_tool(provider_id, tool_name, current_user)

        tool = GetApiToolResp()

        return success_json(tool.dump(api_tool))

    @login_required
    def get_api_tool_provider(self, provider_id: UUID):
        """根据传入的provider_id获取工具提供者信息"""
        api_tool_provider = self.api_tool_service.get_api_tool_provider(provider_id, current_user)
        # 将对象转为字典给前端
        provider = GetApiToolProviderResp()

        return success_json(provider.dump(api_tool_provider))

    @login_required
    def validate_openapi_schema(self):
        """校验传递的openapi_schema字符串是否正确"""
        req = ValidateOpenAPISchemaReq()

        if not req.validate():
            return validate_error_json(req.errors)

        self.api_tool_service.parse_openapi_schema(req.openapi_schema.data)

        return success_message("数据校验成功")
