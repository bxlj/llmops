"""
@Time    : 2026-07-22 15:52
@Author  : JiaChengJie
@File    : api_key_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.api_key_schema import CreateAPIKeyReq, UpdateAPIKeyReq, UpdateApiKeyIsActiveReq, \
    GetApiKeysWithPageResp
from internal.service import ApiKeyService
from pkg.paginator import PaginatorReq, PageModel
from pkg.response import validate_error_json, success_message, success_json


@inject
@dataclass
class ApiKeyHandler:
    """ApiKey密钥管理器"""
    api_key_service: ApiKeyService

    @login_required
    def create_api_key(self):
        """新增apikey密钥"""
        req = CreateAPIKeyReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_key_service.create_api_key(req, current_user)

        return success_message("创建API秘钥成功")

    @login_required
    def delete_api_key(self, api_key_id: UUID):
        """根据api_key_id删除密钥信息"""
        self.api_key_service.delete_api_key(api_key_id, current_user)

        return success_message("删除API秘钥成功")

    @login_required
    def update_api_key(self, api_key_id: UUID):
        """该接口用于修改指定API秘钥的基础信息，涵盖是否激活 和备注信息"""
        req = UpdateAPIKeyReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_key_service.update_api_key(api_key_id, req, current_user)

        return success_message("修改API秘钥成功")

    @login_required
    def update_api_key_is_active(self, api_key_id: UUID):
        """该接口用于修改指定API秘钥的状态信息"""
        req = UpdateApiKeyIsActiveReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_key_service.update_api_key_is_active(api_key_id, current_user, req)

        return success_message("修改API秘钥状态成功")

    @login_required
    def get_api_keys_with_page(self):
        """该接口主要用于获取当前登录账号的API秘钥分页列表数据，接口支持分页"""
        req = PaginatorReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        api_keys, paginator = self.api_key_service.get_api_keys_with_page(req, current_user)

        resp = GetApiKeysWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(api_keys), paginator=paginator))
