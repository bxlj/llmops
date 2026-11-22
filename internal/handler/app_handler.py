"""
@Time    : 2026/3/2 13:19
@Author  : jiachengjie
@File    : app_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.core.language_model import LanguageModelManager
from internal.schema.app_schema import CreateAppReq, GetAppResp, GetPublishHistoriesWithPage, \
    GetPublishHistoriesWithPageResp, FallbackHistoryToDraftReq, UpdateDebugConversationSummary, \
    DebugChatReq, GetDebugConversationMessagesWithPageResp, \
    GetDebugConversationMessagesWithPageReq, GetAppWithPageReq, GetAppWithPageResp, UpdateAppReq
from internal.service import (AppService)
from pkg.paginator import PageModel
from pkg.response import (success_message,
                          validate_error_json, success_json, compact_generate_response)


@inject
@dataclass
class AppHandler:
    """应用控制器"""
    app_service: AppService
    language_model_manager: LanguageModelManager

    @login_required
    def create_app(self):
        """在个人空间下新增应用"""
        req = CreateAppReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        app = self.app_service.create_app(req, current_user)

        return success_message(f"应用服务创建成功,id为{app.id}")

    @login_required
    def get_app(self, app_id: UUID):
        app = self.app_service.get_app(app_id, current_user)
        resp = GetAppResp()
        return success_json(resp.dump(app))

    @login_required
    def get_draft_app_config(self, app_id: UUID):
        """根据传递的应用id获取应用的最新草稿配置"""
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)
        return success_json(draft_config)

    @login_required
    def update_draft_app_config(self, app_id: UUID):
        """根据传递的应用id+草稿配置更新应用的最新草稿配置"""
        # 1.获取草稿请求json数据
        draft_app_config = request.get_json(force=True, silent=True) or {}

        # 2.调用服务更新应用的草稿配置
        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message("更新应用草稿配置成功")

    @login_required
    def publish(self, app_id: UUID):
        """发布/更新应用发布信息"""
        self.app_service.publish_draft_app_config(app_id, current_user)
        return success_message("发布/更新应用发布信息成功")

    @login_required
    def cancel_publish(self, app_id: UUID):
        """取消发布信息"""
        self.app_service.cancel_publish_draft_app_config(app_id, current_user)
        return success_message("取消发布信息成功")

    @login_required
    def get_publish_histories_with_page(self, app_id: UUID):

        """获取应用的发布历史列表"""
        req = GetPublishHistoriesWithPage(request.args)
        if not req.validate():
            raise validate_error_json(req.errors)

        # 2.调用服务获取分页列表数据
        app_config_versions, paginator = self.app_service.get_publish_histories_with_page(app_id, current_user, req)

        # 3.创建响应结构并返回
        resp = GetPublishHistoriesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(app_config_versions), paginator=paginator))

    @login_required
    def fallback_history_to_draft(self, app_id: UUID):
        """回退指定的历史配置到草稿"""
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.app_service.fallback_history_to_draft(app_id, req.app_config_version_id.data, current_user)

        return success_message("回退历史版本成功")

    @login_required
    def get_debug_conversation_summary(self, app_id: UUID):
        """获取应用调试长记忆"""
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)

        return success_json({"summary": summary})

    @login_required
    def update_debug_conversation_summary(self, app_id: UUID):
        """更新应用调试长记忆"""
        req = UpdateDebugConversationSummary()
        if not req.validate():
            raise validate_error_json(req.errors)

        summary = self.app_service.update_debug_conversation_summary(app_id, req.summary.data, current_user)

        return success_message("更新AI应用长记忆成功")

    @login_required
    def delete_debug_conversation(self, app_id: UUID):
        """清空应用的调试会话记录"""
        self.app_service.delete_debug_conversation(app_id, current_user)

        return success_message("清空应用调试长记录成功")

    @login_required
    def debug_chat(self, app_id: UUID):
        """根据传递的应用id+query，发起调试对话"""
        # 1.提取数据并校验数据
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务发起会话调试
        response = self.app_service.debug_chat(app_id, req.query.data, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID):
        """根据传递的应用id+任务id停止某个应用的指定调试会话"""
        self.app_service.stop_debug_chat(app_id, task_id, current_user)
        return success_message("停止应用调试会话成功")

    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID):
        """根据传递的应用id，获取该应用的调试会话分页列表记录"""
        # 1.提取请求并校验数据
        req = GetDebugConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        messages, paginator = self.app_service.get_debug_conversation_messages_with_page(app_id, req, current_user)

        resp = GetDebugConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_app(self, app_id: UUID):
        """删除指定的应用"""
        self.app_service.delete_app(app_id, current_user)
        return success_message("删除Agent智能体应用成功")

    @login_required
    def get_apps_with_page(self):
        """获取应用分页列表"""
        req = GetAppWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        apps, paginator = self.app_service.get_app_with_page(req, current_user)

        resp = GetAppWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    @login_required
    def update_app(self, app_id: UUID):
        """修改应用基础信息"""
        req = UpdateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_app(app_id, current_user, **req.data)

        return success_message("修改Agent智能体应用成功")

    @login_required
    def copy_app(self, app_id: UUID):
        """创建应用副本API"""
        app = self.app_service.copy_app(app_id, current_user)
        return success_json({"app_id": app.id})

    @login_required
    def get_published_token(self, app_id: UUID):
        """获取指定发布应用的token"""
        token = self.app_service.get_published_token(app_id, current_user)
        return success_json(token)

    @login_required
    def regenerate_web_app_token(self, app_id: UUID):
        """重新生成web凭证标识"""
        token = self.app_service.regenerate_web_app_token(app_id, current_user)
        return success_json(token)

    @login_required
    def ping(self):
        provider = self.language_model_manager.get_provider("tongyi")
        model_entity = provider.get_model_entity("qwen3.8-flash")
        model_class = provider.get_model_class(model_entity.model_type)

        llm = model_class(**{
            **model_entity.attributes,
            "features": model_entity.features,
            "metadata": model_entity.metadata,
        })
        return success_json({
            "content": llm.invoke("你好，你是？").content,
            "features": llm.features,
            "metadata": llm.metadata,
        })
