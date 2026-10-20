"""
@Time    : 2026-04-27 17:06
@Author  : jiachengjie
@File    : document_handle.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.document_schema import CreateDocumentRep, CreateDocumentResp, GetDocumentResp, \
    UpdateDocumentNameRep, UpdateDocumentEnabledRep, GetDocumentsWithPageResp, \
    GetDocumentWithPageReq
from internal.service import DocumentService
from pkg.paginator import PageModel
from pkg.response.response import validate_error_json, success_json, success_message


@inject
@dataclass
class DocumentHandler:
    document_service: DocumentService

    @login_required
    def create_documents(self, dataset_id: UUID):
        """知识库新增/上传文档列表"""
        # 1.提取请求并校验
        rep = CreateDocumentRep()
        if not rep.validate():
            raise validate_error_json(rep.errors)
        # 2.调用服务并创建文档，返回文档列表信息+处理批次
        documents, batch = self.document_service.create_document(dataset_id, **rep.data, account=current_user)

        # 3.生成响应结构并返回
        resp = CreateDocumentResp()

        return success_json(resp.dump((documents, batch)))

    @login_required
    def get_document(self, dataset_id: UUID, document_id: UUID):
        """根据dataset_id + document_id 获取文档信息"""
        document = self.document_service.get_document(dataset_id, document_id, current_user)

        resp = GetDocumentResp()

        return success_json(resp.dump((document)))

    @login_required
    def update_document_name(self, dataset_id: UUID, document_id: UUID):
        """根据dataset_id + document_id更新文档名称"""
        rep = UpdateDocumentNameRep()
        if not rep.validate():
            raise validate_error_json(rep.errors)

        self.document_service.update_document_name(dataset_id, document_id, current_user, name=rep.data["name"])

        return success_message("更新文档名称成功")

    @login_required
    def update_document_enabled(self, dataset_id: UUID, document_id: UUID):
        """根据dataset_id + document_id更新文档状态"""
        req = UpdateDocumentEnabledRep()
        if not req.validate():
            raise validate_error_json(req.errors)

        self.document_service.update_document_enable(dataset_id, document_id, req.enabled.data, current_user)

        return success_message("修改状态成功")

    @login_required
    def delete_document(self, dataset_id: UUID, document_id: UUID):
        """根据dataset_id + document_id删除文档"""
        self.document_service.delete_document(dataset_id, document_id, current_user)

        return success_message("删除文档成功")

    @login_required
    def get_documents_with_page(self, dataset_id: UUID):
        """分页获取文档信息"""
        req = GetDocumentWithPageReq(request.args)
        if not req.validate():
            raise validate_error_json(req.errors)

        documents, paginator = self.document_service.get_document_with_page(dataset_id, req, current_user)

        # 3.构建响应结构并映射
        resp = GetDocumentsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(documents), paginator=paginator))

    @login_required
    def get_documents_status(self, dataset_id: UUID, batch: str):
        """根据传递的知识库id+批处理标识获取文档的状态"""
        documents_status = self.document_service.get_documents_status(dataset_id, batch, current_user)

        return success_json(documents_status)
