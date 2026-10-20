"""
@Time    : 2026-04-27 17:12
@Author  : jiachengjie
@File    : document_service.py
"""
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from injector import inject
from redis import Redis
from sqlalchemy import asc, func, desc

from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from internal.entity.dataset_entity import ProcessType, SegmentStatus, DocumentStatus
from internal.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from internal.exception.exception import ForbiddenException, FailException, NotFoundException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Account
from internal.model.dataset import Dataset, Document, ProcessRule, Segment
from internal.model.upload_file import UploadFile
from internal.schema.document_schema import GetDocumentWithPageReq
from internal.service import BaseService
from internal.task.document_task import build_documents, update_document_enabled, delete_document
from pkg.paginator import Paginator
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DocumentService(BaseService):
    db: SQLAlchemy
    redis_client: Redis

    def create_document(
            self,
            dataset_id: UUID,
            upload_file_ids: list[UUID],
            process_type: str = ProcessType.AUTOMATIC,
            rule: dict = None,
            account: Account = None,
    ) -> tuple[list[Document], str]:
        """创建知识库文档表信息"""

        # 1.判断dataset_id知识库数据是否存在
        dataset = self.get(Dataset, dataset_id)

        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("无权限操作当前文档")

        # 2. 判断上传的文件是否存在
        upload_files = self.db.session.query(UploadFile).filter(
            UploadFile.account_id == account.id,
            UploadFile.id.in_(upload_file_ids),
        ).all()

        upload_files = [
            upload_file for upload_file in upload_files
            if upload_file.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]

        if len(upload_files) == 0:
            logging.warning(
                f"上传文档列表未解析到合法文件，account_id: {account.id}, dataset_id: {dataset_id}, upload_file_ids: {upload_file_ids}")
            raise FailException("暂未解析到合法文件，请重新上传")

        # 3. 保存数据到文档解析切片处理规则表
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        process_rule = self.create(
            ProcessRule,
            account_id=account.id,
            dataset_id=dataset_id,
            mode=process_type,
            rule=rule
        )

        position = self.get_latest_document_position(dataset_id, account.id)

        # 4.保存数据在知识库文档表
        documents = []
        for upload_file in upload_files:
            position += 1
            document = self.create(
                Document,
                account_id=account.id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                name=upload_file.name,
                process_rule_id=process_rule.id,
                position=position,
                batch=batch
            )
            documents.append(document)

        # 6.调用异步任务，完成后续操作
        build_documents.delay([document.id for document in documents])

        # 7.返回文档列表与处理批次
        return documents, batch

    def get_documents_status(self, dataset_id: UUID, batch: str, account: Account) -> list[dict]:
        """根据知识库表id和批次号获取文档状态信息"""

        # 判断当前账户下是否有文档
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("当前用户没有该知识库的权限或当前用户下没有文档")

        documents = self.db.session.query(Document).filter(
            Document.account_id == account.id,
            Document.batch == batch
        ).order_by(asc("position")).all()

        if documents is None or len(documents) == 0:
            raise NotFoundException("文档不存在")

        documents_status = []
        for document in documents:
            segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
            ).scalar()

            completed_segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
                Segment.status == SegmentStatus.COMPLETED
            ).scalar()

            upload_file = document.upload_file

            documents_status.append({
                "id": document.id,
                "name": document.name,
                "size": upload_file.size,
                "extension": upload_file.extension,
                "mime_type": upload_file.mime_type,
                "position": document.position,
                "segment_count": segment_count,
                "completed_segment_count": completed_segment_count,
                "processing_started_at": datetime_to_timestamp(document.processing_started_at),
                "parsing_completed_at": datetime_to_timestamp(document.parsing_completed_at),
                "splitting_completed_at": datetime_to_timestamp(document.splitting_completed_at),
                "indexing_completed_at": datetime_to_timestamp(document.indexing_completed_at),
                "completed_at": datetime_to_timestamp(document.completed_at),
                "stopped_at": datetime_to_timestamp(document.stopped_at),
                "created_at": datetime_to_timestamp(document.created_at),
            })

        return documents_status

    def get_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:

        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("文档不存在")
        if document.account_id != account.id or document.dataset_id != dataset_id:
            raise ForbiddenException("当前用户获取该文档，请核实后重试")

        return document

    def update_document_name(self, dataset_id: UUID, document_id: UUID, account: Account, **kwargs) -> Document:
        """根据知识库id和文档id修改文档名称"""
        # todo:等待授权认证模块完成进行切换调整
        account_id = "46db30d1-3199-4e79-a0cd-abf12fa6858f"

        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("文档信息不存在")
        if str(document.account_id) != account_id or document.dataset_id != dataset_id:
            raise ForbiddenException("当前用户获取该文档，请核实后重试")

        document = self.update(document, **kwargs)

        return document

    def update_document_enable(self, dataset_id: UUID, document_id: UUID, enabled: bool, account: Account) -> Document:
        """根据知识库id和文档id修改文档状态"""
        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("文档信息不存在")
        if document.account_id != account.id or document.dataset_id != dataset_id:
            raise ForbiddenException("当前用户获取该文档，请核实后重试")

        # 2. 判断文档是否处于可以修改的状态，只有构建完成才可以修改enabled
        if document.status != DocumentStatus.COMPLETED:
            raise ForbiddenException("当前文档状态不支持修改")

        # 3. 更新文档状态必须和当前状态不一致
        if document.enabled == enabled:
            raise FailException(f"文档状态修改错误，当前状态已经是{'启用' if enabled else '禁用'}状态")

        # 4. 防止在并发下多个用户操作同一个文档导致状态错误，使用redis分布式锁去实现
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document.id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("该文档正在修改启用状态，请稍后重试")

        # 5. 在数据库中修改文档启用状态
        self.update(
            document,
            enabled=enabled,
            disabled_at=None if enabled else datetime.now()
        )

        # 使用分布式锁，锁定该文档10分钟
        self.redis_client.setex(cache_key, LOCK_EXPIRE_TIME, 1)

        # 6. 启用异步任务完成后续操作
        # update_document_enable.delay(document.id)

        update_document_enabled.delay(document.id)

        return document

    def delete_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """根据dataset_id + document_id删除文档数据"""

        document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("文档不存在")

        if document.account_id != account.id or document.dataset_id != dataset_id:
            raise ForbiddenException("当前用户权限无法，删除该文挡")

        # 2.判断文档是否处于可删除状态，只有构建完成/出错的时候才可以删除，其他情况需要等待构建完成
        if document.status not in [DocumentStatus.COMPLETED, DocumentStatus.ERROR]:
            raise ForbiddenException("当前文档状态不能删除")

        self.delete(document)

        delete_document.delay(dataset_id, document_id)

        return document

    def get_document_with_page(self, dataset_id: UUID, req: GetDocumentWithPageReq, account: Account) -> tuple[
        list[Document],]:
        """分页查询数据"""

        dataset = self.get(Dataset, dataset_id)

        if dataset is None or dataset.account_id != account.id:
            raise ForbiddenException("无权限获取列表信息")

        # 获取分页器
        paginator = Paginator(db=self.db, req=req)

        # 构建筛选器
        filters = [
            Document.dataset_id == dataset_id,
            Document.account_id == account.id,
        ]

        if req.search_word.data:
            filters.append(Document.name.ilike(f"%{req.search_word.data}%"))

        # 执行分页并获取数据
        documents = paginator.paginate(
            self.db.session.query(Document).filter(*filters).order_by(desc("created_at"))
        )

        return documents, paginator

    def get_latest_document_position(self, dataset_id: UUID, account_id: UUID) -> int:
        doc = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.account_id == account_id,
        ).order_by(Document.position.desc()).first()

        return doc.position if doc else 0
