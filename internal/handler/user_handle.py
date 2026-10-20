"""
@Time    : 2026-05-25 9:47
@Author  : jiachengjie
@File    : user_handle.py
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from injector import inject

from internal.schema.user_schema import CreateUserReq, UpdateUserReq
from internal.service.user_service import UserService
from pkg.response.response import success_message
from pkg.response.response import validate_error_json


@inject
@dataclass
class UserHandler:
    user_service: UserService

    def create_user(self):
        """创建用户信息"""
        req = CreateUserReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.user_service.create_user(req)

        return success_message("保存数据成功")

    def update_user(self, user_id: UUID):
        """修改用户信息"""
        logging.info("这是第一步，我进来了")
        req = UpdateUserReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.user_service.update_user(user_id, req)

        return success_message("修改数据成功")
