"""
@Time    : 2026-11-23 16:19
@Author  : JiaChengJie
@File    : conversation_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.conversation_schema import GetConversationWithPageReq, GetConversationWithPageResp, \
    UpdateConversationNameReq, UpdateConversationIsPinnedReq
from internal.service.conversation_service import ConversationService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class ConversationHandler:
    """会话控制器"""
    conversation_service: ConversationService

    @login_required
    def get_conversation_messages_with_page(self, conversation_id: UUID):
        """获取指定会话的消息列表"""
        # 1. 校验请求体信息
        req = GetConversationWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. 获取数据信息
        messages, paginator = self.conversation_service.get_conversations_with_page(conversation_id, req, current_user)

        # 3. 构建返回值结构体
        resp = GetConversationWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_conversation(self, conversation_id: UUID):
        """删除特定的会话,同时删除指定下的消息"""
        self.conversation_service.delete_conversation(conversation_id, current_user)

        return success_message("删除会话成功")

    @login_required
    def delete_message(self, conversation_id: UUID, message_id: UUID):
        """删除特定的会话下特定的消息"""
        self.conversation_service.delete_message(conversation_id, message_id, current_user)

        return success_message("删除会话消息成功")

    @login_required
    def get_conversation_name(self, conversation_id: UUID):
        """获取指定会话名称"""
        name = self.conversation_service.get_conversation_name(conversation_id, current_user)

        return success_json({"name": name})

    @login_required
    def update_conversation_name(self, conversation_id: UUID):
        """修改指定会话的名称"""
        req = UpdateConversationNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.conversation_service.update_conversation_name(conversation_id, req.name.data, current_user)

        return success_message("修改会话名称成功")

    @login_required
    def update_conversation_is_pinned(self, conversation_id: UUID):
        """置顶或取消置顶某个会话"""
        req = UpdateConversationIsPinnedReq()
        if not req.validate():
            return validate_error_json(req.errors)
        self.conversation_service.update_conversation_is_pinned(conversation_id, req.is_pinned.data, current_user)
        return success_message("修改会话置顶状态成功")
