"""
@Time    : 2026-04-07 11:02
@AUthor  : jiachengjie
@File    : api_tool_service.py
"""
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.core.tool.api_tools.entities import ToolEntity
from internal.core.tool.api_tools.providers import ApiProviderManager
from internal.core.tool.builtin_tools.enytities import OpenAPISchema
from internal.exception import ValidateErrorException, NotFoundException
from internal.model import ApiToolProvider, ApiTool, Account
from internal.schema import ValidateCreateAPISchemaReq, GetToolProviderWithPageReq, UpdateAPISchemaReq
from internal.service import BaseService
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class ApiToolService(BaseService):
    db: SQLAlchemy
    api_provider_manager: ApiProviderManager

    def get_api_tool_provider_with_page(
            self,
            req: GetToolProviderWithPageReq,
            account: Account,
    ) -> tuple[list[Any], Paginator]:
        """获取API工具提供者详情，并分页"""

        # 构建分页查询器
        paginator = Paginator(self.db, req=req)

        # 构建筛选器
        filters = [ApiToolProvider.account_id == account.id]
        # 先判断有没有 keyword，有才加过滤条件
        if req.search_word.data:
            filters.append(ApiToolProvider.name.ilike(f"%{req.search_word.data}%"))
        # 执行分页并获取数据
        api_tool_providers = paginator.paginate(
            self.db.session.query(ApiToolProvider).filter(*filters).order_by(desc("created_at"))
        )

        return api_tool_providers, paginator

    def create_api_tool(
            self,
            req: ValidateCreateAPISchemaReq,
            account: Account
    ) -> None:
        """根据传递的请求创建自定义API工具"""

        # 1.检验并提取openapi_schema对应的数据
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)
        # 2.查询当前登录的账号是否已经创建了同名的工具提供者，如果是则抛出错误
        api_tool_provider = self.db.session.query(ApiToolProvider).filter_by(
            account_id=account.id,
            name=req.name.data
        ).one_or_none()
        if api_tool_provider:
            raise ValidateErrorException(f"Api tool already exists: {api_tool_provider}")
        # 3.首先创建工具提供者，并获取工具提供者的id信息，然后在创建工具信息
        api_tool_provider = self.create(
            ApiToolProvider,
            account_id=account.id,
            name=req.name.data,
            icon=req.icon.data,
            description=openapi_schema.description,
            openapi_schema=openapi_schema.model_dump_json(),
            headers=req.headers.data,
        )

        # 4.创建api工具并关联api_tool_provider
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account.id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def update_api_tool_provider(self, provider_id: UUID, req: UpdateAPISchemaReq, account: Account):
        """修改工具提供者信息"""

        # 1. 根据provider_id获取根据提供者信息
        api_tool_provider = self.get(ApiToolProvider, provider_id)

        if api_tool_provider is None or api_tool_provider.account_id != account.id:
            raise ValidateErrorException(f"Api tool provider does not exist: {api_tool_provider}")

        # 2. 校验openapi_schema
        openapi_schema = self.parse_openapi_schema(req.openapi_schema.data)

        # 3.检测当前账号是否已经创建了同名的工具提供者，如果是则抛出错误
        check_api_tool_provider = self.db.session.query(ApiToolProvider).filter(
            ApiToolProvider.id != api_tool_provider.id,
            ApiToolProvider.account_id == account.id,
            ApiToolProvider.name == req.name.data,
        ).one_or_none()

        if check_api_tool_provider:
            raise ValidateErrorException(f"Api tool provider already exists: {check_api_tool_provider}")

        # 开启数据库自动提交
        with self.db.auto_commit():
            # 5.先删除该工具提供者下的所有工具
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account.id,
            ).delete()

        # 6.修改工具提供者信息
        self.update(
            api_tool_provider,
            name=req.name.data,
            icon=req.icon.data,
            headers=req.headers.data,
            openapi_schema=json.dumps(req.openapi_schema.data),
        )

        # 7.新增工具信息从而完成覆盖更新
        for path, path_item in openapi_schema.paths.items():
            for method, method_item in path_item.items():
                self.create(
                    ApiTool,
                    account_id=account.id,
                    provider_id=api_tool_provider.id,
                    name=method_item.get("operationId"),
                    description=method_item.get("description"),
                    url=f"{openapi_schema.server}{path}",
                    method=method,
                    parameters=method_item.get("parameters", []),
                )

    def delete_api_provider_tool(self, provider_id: UUID, account: Account):
        """删除数据"""
        # 1.先查找数据，检测下provider_id对应的数据是否存在，权限是否正确
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or api_tool_provider.account_id != account.id:
            raise NotFoundException("该工具提供者不存在")

        # 2.开启数据库的自动提交
        with self.db.auto_commit():
            self.db.session.query(ApiTool).filter(
                ApiTool.provider_id == provider_id,
                ApiTool.account_id == account.id
            ).delete()

            self.db.session.delete(api_tool_provider)

    def get_api_tool(self, provider_id: UUID, name: str, account: Account) -> ApiTool:
        """根据传递的请求获取API工具"""
        api_tool = self.db.session.query(ApiTool).filter_by(
            provider_id=provider_id,
            name=name).one_or_none()
        if api_tool is None or api_tool.account_id != account.id:
            raise ValidateErrorException(f"Api tool does not exist: {name}")

        return api_tool

    def get_api_tool_provider(self, provider_id: UUID, account: Account) -> ApiToolProvider:
        """根据传递的请求创建自定义API工具"""

        # 1.查询数据库获取对应的数据
        api_tool_provider = self.get(ApiToolProvider, provider_id)
        if api_tool_provider is None or api_tool_provider.account_id != account.id:
            raise ValidateErrorException(f"Api tool does not exist: {api_tool_provider}")

        return api_tool_provider

    @classmethod
    def parse_openapi_schema(cls, data) -> OpenAPISchema:
        """解析传递的openapi_schema（支持字符串或字典）"""
        try:
            # 如果是字符串，解析成字典
            if isinstance(data, str):
                data = json.loads(data.strip())
            # 必须是字典
            if not isinstance(data, dict):
                raise ValidateErrorException("数据必须是JSON对象或字符串")

            return OpenAPISchema(**data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise ValidateErrorException(f"OpenAPI数据错误：{str(e)}")

    def api_tool_invoke(self):
        provider_id = "e1069411-b5df-477f-95e7-c4597a9bf031"
        tool_name = "YoudaoSuggest"

        api_tool = self.db.session.query(ApiTool).filter(
            ApiTool.provider_id == provider_id,
            ApiTool.name == tool_name,
        ).one_or_none()
        api_tool_provider = api_tool.provider

        tool = self.api_provider_manager.get_tool(ToolEntity(
            id=provider_id,
            name=tool_name,
            url=api_tool.url,
            method=api_tool.method,
            description=api_tool.description,
            headers=api_tool_provider.headers,
            parameters=api_tool.parameters,
        ))
        return tool.invoke({"q": "love", "doctype": "json"})
