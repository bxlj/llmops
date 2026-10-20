"""
@Time    : 2026-04-20 15:41
@Author  : jiachengjie
@File    : dataset_handle.py
"""
from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.core.file_extractor.file_extractor import FileExtractor
from internal.model import UploadFile
from internal.schema.dataset_schema import (ValidateCreateDatasetReq,
                                            GetDatasetResp,
                                            GetDatasetWithPageRep,
                                            GetDatasetsWithPageResp,
                                            UpdateDatasetReq, HitReq, GetDatasetQueriesResp)
from internal.service.dataset_service import DatasetService
from internal.service.embeddings_service import EmbeddingsService
from internal.service.jieba_service import JiebaService
from internal.service.vector_database_service import VectorDatabaseService
from pkg.paginator import PageModel
from pkg.response import validate_error_json, success_message, success_json
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DatasetHandler:
    dataset_service: DatasetService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    db: SQLAlchemy
    file_extractor: FileExtractor
    vector_database_service: VectorDatabaseService

    @login_required
    def embeddings_query(self):
        # query = request.args.get("query")
        # vectors = self.embeddings_service.embeddings.embed_query(query)
        # return success_json({"vectors": vectors})

        upload_file = self.db.session.query(UploadFile).get("ad2b72eb-979f-44c2-9e56-0fba9771cb40")
        content = self.file_extractor.load(upload_file, True)
        return success_json({"content": content})

        # query = request.args.get("query")
        # keywords = self.jieba_service.extract_keywords(query)
        # return success_json({"keywords": keywords})

    @login_required
    def create_dataset(self):
        """创建知识库"""
        rep = ValidateCreateDatasetReq()
        if not rep.validate():
            raise validate_error_json(rep.errors)

        self.dataset_service.create_dataset(rep, current_user)

        return success_message("保存数据成功")

    @login_required
    def get_dataset(self, dataset_id: UUID):
        """根据知识库id获取详情信息"""
        rep = self.dataset_service.get_dataset(dataset_id, current_user)

        result = GetDatasetResp()

        return success_json(result.dump(rep))

    @login_required
    def update_dataset(self, dataset_id: UUID):
        """根据知识库id修改信息"""
        rep = UpdateDatasetReq()
        if not rep.validate():
            raise validate_error_json(rep.errors)

        self.dataset_service.update_dataset(dataset_id, rep, current_user)

        return success_message("修改数据成功")

    @login_required
    def get_datasets_with_page(self):
        """获取知识库列表分页"""
        # 1.提取query数据并校验
        rep = GetDatasetWithPageRep(request.args)

        if not rep.validate():
            raise validate_error_json(rep.errors)

        datasets, paginator = self.dataset_service.get_dataset_with_page(rep, current_user)

        # 3.构建响应
        resp = GetDatasetsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(datasets), paginator=paginator))

    @login_required
    def hit(self, dataset_id: UUID):
        """根据传递的知识库id+检索参数执行召回测试"""
        req = HitReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        hit_result = self.dataset_service.hit(dataset_id, req, current_user)

        return success_json(hit_result)

    @login_required
    def get_dataset_queries(self, dataset_id: UUID):
        """获取指定知识库最近的查询列表"""
        dataset_queries = self.dataset_service.get_dataset_queries(dataset_id, current_user)
        resp = GetDatasetQueriesResp(many=True)
        return success_json(resp.dump(dataset_queries))

    @login_required
    def delete_dataset(self, dataset_id: UUID):
        """删除指定的知识库"""
        self.dataset_service.delete_dataset(dataset_id, current_user)
        return success_message("删除知识库成功")
