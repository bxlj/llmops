"""
@Time    : 2026-05-28 14:45
@Author  : jiachengjie
@File    : segment_handle.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.segment_schema import GetSegmentWithPageReq, GetSegmentWithPageResp, UpdateSegmentEnabledReq, \
    GetSegmentResp, CreateSegmentReq, UpdateSegmentReq
from internal.service.segment_service import SegmentService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_json, success_message


@inject
@dataclass
class SegmentHandler:
    segment_service: SegmentService

    @login_required
    def create_segment(self, dataset_id: UUID, document_id: UUID):
        """新增文档片段信息"""
        req = CreateSegmentReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.segment_service.create_segment(dataset_id, document_id, req, current_user)

        return success_message("保存片段信息成功")

    @login_required
    def update_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """修改片段信息"""
        req = UpdateSegmentReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.segment_service.update_segment(dataset_id, document_id, segment_id, req, current_user)

        return success_message("修改片段信息成功")

    @login_required
    def get_segment_with_page(self, dataset_id: UUID, document_id: UUID):
        """获取指定文档的片段列表"""
        req = GetSegmentWithPageReq(request.args)
        if req is None:
            raise validate_error_json("参数错误")

        segments, paginator = self.segment_service.get_segment_with_page(dataset_id, document_id, req, current_user)

        resp = GetSegmentWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(segments), paginator=paginator))

    @login_required
    def update_segment_enabled(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """更新文档片段的启用状态"""
        req = UpdateSegmentEnabledReq()
        if not req:
            raise validate_error_json(req.errors)

        self.segment_service.update_segment_enabled(dataset_id, document_id, segment_id,
                                                    req.enabled.data, current_user)

        return success_message("修改状态成功")

    @login_required
    def delete_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """删除片段信息"""
        self.segment_service.delete_segment(dataset_id, document_id, segment_id, current_user)
        return success_message("删除文档片段信息成功")

    @login_required
    def get_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID):
        """查询文档片段信息"""
        segment = self.segment_service.get_segment(dataset_id, document_id, segment_id, current_user)
        resp = GetSegmentResp()
        return success_json(resp.dump(segment))
