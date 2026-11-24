"""
@Time    : 2026-11-22 15:28
@Author  : JiaChengJie
@File    : web_app_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.web_app_schema import GetAppByTokenResp, WebAppChatReq, GetConversationReq, GetConversationResp
from internal.service.web_app_service import WebAppService
from pkg.response import success_json, validate_error_json, compact_generate_response, success_message


@inject
@dataclass
class WebAppHandler:
    web_app_service: WebAppService

    @login_required
    def get_app_by_token(self, token: str):
        """根据token获取app信息"""
        # 1.获取app信息
        app = self.web_app_service.get_app_by_token(token)
        # 2. 构建响应结构并返回
        resp = GetAppByTokenResp()

        return success_json(resp.dump(app))

    @login_required
    def web_app_chat(self, token: str):
        """根据传递的token凭证+请求与指定的WebApp进行对话 """
        # 1. 获取请求信息
        req = WebAppChatReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        # 2. 调用服务获取对应响应内容
        response = self.web_app_service.web_app_chat(token, req.conversation_id.data, req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_web_app_chat(self, token: str, task_id: UUID):
        """停止与指定WebApp进行对话"""
        self.web_app_service.stop_web_app_chat(token, task_id, current_user)

        return success_message("停止应用会话调试成功")

    @login_required
    def get_conversation(self, token: str):
        """获取指定应用的会话列表"""
        # 1，获取指定参数
        req = GetConversationReq(request.args)
        if not req.validate():
            raise validate_error_json(req.errors)

        # 2. 获取符合要求的会话信息
        conversations = self.web_app_service.get_conversation(token, req.is_pinned.data, current_user)

        # 3. 构建返回体
        resp = GetConversationResp(many=True)

        return success_json(resp.dump(conversations))
