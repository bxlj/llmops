"""
@Time    : 2026-04-20 15:41
@Author  : jiachengjie
@File    : dataset_service.py
"""
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from internal.exception.exception import ValidateErrorException, NotFoundException, ForbiddenException, FailException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, AppDatasetJoin, Account
from internal.model import DatasetQuery
from internal.model.dataset import Segment
from internal.schema.dataset_schema import ValidateCreateDatasetReq, GetDatasetWithPageRep, UpdateDatasetReq, HitReq
from internal.service import BaseService
from internal.service.retrieval_service import RetrievalService
from internal.task.dataset_task import delete_dataset
from pkg.paginator import PaginatorReq, Paginator
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DatasetService(BaseService):
    db: SQLAlchemy
    retrieval_service: RetrievalService

    def create_dataset(self, req: ValidateCreateDatasetReq, account: Account) -> Dataset:
        """创建知识库"""

        # 1.判断当前用户下知识库是否存在（根据account_id，name去查询数据）
        data_set = self.db.session.query(Dataset).filter_by(
            account_id=account.id,
            name=req.name.data,
        ).one_or_none()

        if data_set:
            return ValidateErrorException(f"Dataset {req.name} already exists")

        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name.data)

        return self.create(Dataset,
                           account_id=account.id,
                           name=req.name.data,
                           description=req.description.data,
                           icon=req.icon.data, )

    def get_dataset(self, dataset_id: UUID, account: Account) -> Dataset:
        """根据知识库id获取"""

        dataset = self.query(Dataset, dataset_id)

        if dataset is None or dataset.account_id != account.id:
            return NotFoundException(f"Dataset {dataset_id} does not exist")

        return dataset

    def update_dataset(self, dataset_id: UUID, req: UpdateDatasetReq, account: Account) -> Dataset:
        """修改知识库信息"""

        # 1. 判断该知识库是否存在
        dataset = self.query(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            return NotFoundException(f"Dataset {dataset_id} does not exist")

        # 2.判断修改之后，知识库名称是否重名
        check_dataset = self.db.session.query(Dataset).filter(
            Dataset.account_id == account.id,
            Dataset.name == req.name.data,
            Dataset.id != dataset_id,
        ).one_or_none()

        if check_dataset:
            return ValidateErrorException(f"Dataset {dataset_id} already exists")

        # 3.校验描述信息是否为空，如果为空则人为设置
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name.data)

        self.update(
            dataset,
            icon=req.icon.data,
            name=req.name.data,
            description=req.description.data)

        return dataset

    def get_dataset_with_page(self, req: GetDatasetWithPageRep, account: Account) -> tuple[list[Any], PaginatorReq]:
        """获取知识库列表，分页"""

        # 构建分页查询器
        paginator = Paginator(self.db, req=req)

        # 构建筛选器
        filters = [Dataset.account_id == account.id]
        # 先判断有没有 keyword，有才加过滤条件
        if req.search_word.data:
            filters.append(Dataset.name.ilike(f"%{req.search_word.data}%"))
        # 执行分页并获取数据
        dataset_entity = paginator.paginate(
            self.db.session.query(Dataset).filter(*filters).order_by(desc("created_at"))
        )

        return dataset_entity, paginator

    def hit(self, dataset_id: UUID, req: HitReq, account: Account) -> list[dict]:
        """召回测试"""

        dataset = self.query(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("当前知识库不存在或无权限操作")

        # 2.调用检索服务执行检索
        lc_documents = self.retrieval_service.search_in_datasets(
            datasets=[dataset_id],
            account_id=account.id,
            **req.data,
        )
        lc_document_dict = {str(lc_document.metadata["segment_id"]): lc_document for lc_document in lc_documents}

        # 3.根据检索到的数据查询对应的片段信息
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([str(lc_document.metadata["segment_id"]) for lc_document in lc_documents])
        ).all()

        segment_dict = {str(segment.id): segment for segment in segments}
        # 4.排序片段数据
        sorted_segments = [
            segment_dict[str(lc_document.metadata["segment_id"])]
            for lc_document in lc_documents
            if str(lc_document.metadata["segment_id"]) in segment_dict
        ]
        # 5.组装响应数据
        hit_result = []
        for segment in sorted_segments:
            document = segment.document
            upload_file = document.upload_file
            hit_result.append({
                "id": segment.id,
                "document": {
                    "id": document.id,
                    "name": document.name,
                    "extension": upload_file.extension,
                    "mime_type": upload_file.mime_type,
                },
                "dataset_id": segment.dataset_id,
                "score": lc_document_dict[str(segment.id)].metadata["score"],
                "position": segment.position,
                "content": segment.content,
                "keywords": segment.keywords,
                "character_count": segment.character_count,
                "token_count": segment.token_count,
                "hit_count": segment.hit_count,
                "enabled": segment.enabled,
                "disabled_at": datetime_to_timestamp(segment.disabled_at),
                "status": segment.status,
                "error": segment.error,
                "updated_at": datetime_to_timestamp(segment.updated_at),
                "created_at": datetime_to_timestamp(segment.created_at),
            })

        return hit_result

    def get_dataset_queries(self, dataset_id: UUID, account: Account) -> list[DatasetQuery]:
        """获取指定知识库最近的查询列表"""
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("该知识库不存在")

        # 用于获取指定知识库最近的查询列表，该接口会返回最近的10条记录，没有分页+搜索功能，
        # 返回的数据是按照created_at进行倒序，即数据越新越靠前。
        dataset_queries = self.db.session.query(DatasetQuery).filter(
            DatasetQuery.dataset_id == dataset_id,
        ).order_by(desc("created_at")).limit(10).all()

        return dataset_queries

    def delete_dataset(self, dataset_id: UUID, account: Account):
        """删除指定的知识库"""
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise NotFoundException("知识库不存在")

        try:
            self.delete(dataset)
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(
                    AppDatasetJoin.dataset_id == dataset_id,
                ).delete()

            delete_dataset.delay(dataset_id)
        except Exception as e:
            logging.exception(f"删除知识库失败, dataset_id: {dataset_id}, 错误信息: {str(e)}")
            raise FailException("删除知识库失败，请稍后重试")
