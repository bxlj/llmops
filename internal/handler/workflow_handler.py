"""
@Time    : 2026-10-12 14:22
@Author  : JiaChengJie
@File    : workflow_handler.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.model import Workflow
from internal.schema.workflow_schema import GetDatasetWithPageReq, GetWorkflowsWithPageResp, CreateWorkflowReq, \
    GetWorkflowResp, UpdateWorkflowReq
from internal.service import WorkflowService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message, compact_generate_response


@inject
@dataclass
class WorkflowHandler:
    """工作流控制器"""
    workflow_service: WorkflowService

    @login_required
    def create_workflow(self):
        """创建工作流数据"""
        req = CreateWorkflowReq()
        if not req.validate():
            return validate_error_json(req.errors)

        workflow = self.workflow_service.create_workflow(req, current_user)

        return success_json({"id": workflow.id})

    @login_required
    def get_workflow(self, workflow_id: UUID) -> Workflow:
        """根据workflow_id获取工作流信息"""
        workflow = self.workflow_service.get_workflow(workflow_id, current_user)
        resp = GetWorkflowResp()
        return success_json(resp.dump(workflow))

    @login_required
    def update_workflow(self, workflow_id: UUID):
        """修改工作流信息"""
        req = UpdateWorkflowReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.workflow_service.update_workflow(workflow_id, req, current_user)

        return success_message("修改工作流基础信息成功")

    @login_required
    def get_workflows_with_page(self):
        """获取账号下的工作流分页数据"""
        # 1.提取请求并校验
        req = GetDatasetWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        workflows, paginator = (
            self.workflow_service.get_workflows_with_page(req, current_user))

        resp = GetWorkflowsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(workflows), paginator=paginator))

    @login_required
    def delete_workflow(self, workflow_id: UUID):
        """根据workflow_id删除指定工作流信息"""
        self.workflow_service.delete_workflow(workflow_id, current_user)
        return success_message("删除工作流成功")

    @login_required
    def update_draft_graph(self, workflow_id: UUID):
        """修改工作流草稿配置信息（节点+边配置）"""
        draft_graph_dict = request.get_json(force=True, silent=True) or {
            "nodes": [],
            "edges": []
        }

        self.workflow_service.update_draft_graph(workflow_id, draft_graph_dict, current_user)

        return success_message("修改工作流草稿配置信息成功")

    @login_required
    def get_draft_graph(self, workflow_id: UUID):
        """获取指定工作流的graph图草稿配置"""
        draft_graph = self.workflow_service.get_draft_graph(workflow_id, current_user)
        return success_json(draft_graph)

    @login_required
    def debug_workflow(self, workflow_id: UUID):
        """调试工作流"""
        inputs = request.get_json(force=True, silent=True)

        response = self.workflow_service.debug_workflow(workflow_id, inputs, current_user)

        return compact_generate_response(response)

    @login_required
    def publish_workflow(self, workflow_id: UUID):
        """发布工作流信息"""
        self.workflow_service.publish_workflow(workflow_id, current_user)

        return success_message("发布工作流成功")

    @login_required
    def cancel_publish_workflow(self, workflow_id: UUID):
        """取消发布工作流信息"""
        self.workflow_service.cancel_publish_workflow(workflow_id, current_user)
        return success_message("取消发布工作流成功")
