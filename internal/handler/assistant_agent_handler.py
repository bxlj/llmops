"""
@Time    : 2026-10-29 14:49
@Author  : JiaChengJie
@File    : assistant_agent_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.assistant_agent_schema import AssistantAgentChatReq, GetAssistantAgentWithPageReq, \
    GetAssistantAgentWithPageResp
from internal.service import AssistantAgentService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, compact_generate_response, success_json, success_message


@inject
@dataclass
class AssistantAgentHandler:
    """辅助智能体处理器"""
    assistant_agent_service: AssistantAgentService

    @login_required
    def assistant_agent_chat(self):
        """与辅助 Agent 进行 Chat 对话"""
        req = AssistantAgentChatReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        response = self.assistant_agent_service.chat(req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def get_assistant_agent_messages_with_page(self):
        """获取当前登录账号的辅助Agent对话历史列表"""
        req = GetAssistantAgentWithPageReq(request.args)
        if not req.validate():
            raise validate_error_json(req.errors)

        messages, paginator, = self.assistant_agent_service.get_assistant_agent_with_page(req, current_user)

        response = GetAssistantAgentWithPageResp(many=True)

        return success_json(PageModel(list=response.dump(messages), paginator=paginator))

    @login_required
    def delete_assistant_agent_conversation(self):
        """清空当前登录账号与辅助Agent的对话列表"""
        self.assistant_agent_service.delete_assistant_agent_conversation(current_user)
        return success_message("清空辅助Agent会话成功")

    @login_required
    def stop_assistant_agent_chat(self, task_id: UUID):
        """停止与辅助智能体的对话聊天"""
        self.assistant_agent_service.stop_chat(task_id)
        return success_message("停止辅助Agent会话成功")
