"""
@Time    : 2026-05-28 14:46
@Author  : jiachengjie
@File    : segment_service.py
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Tuple
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func

from internal.entity.cache_entity import LOCK_SEGMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from internal.entity.dataset_entity import SegmentStatus, DocumentStatus
from internal.exception.exception import ForbiddenException, FailException, ValidateErrorException
from internal.lib.helper import generate_text_hash
from internal.model import Account
from internal.model.dataset import Segment, Document
from internal.schema.segment_schema import GetSegmentWithPageReq, CreateSegmentReq, UpdateSegmentReq
from internal.service import BaseService
from internal.service.embeddings_service import EmbeddingsService
from internal.service.jieba_service import JiebaService
from internal.service.keyword_table_service import KeywordTableService
from internal.service.vector_database_service import VectorDatabaseService
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class SegmentService(BaseService):
    db: SQLAlchemy
    redis_client: Redis
    keyword_table_service: KeywordTableService
    vector_db_service: VectorDatabaseService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService

    def create_segment(self, dataset_id: UUID, document_id: UUID, req: CreateSegmentReq, account: Account) -> Segment:
        """保存片段信息"""
        # 该接口主要用于在指定文档下新增 文档片段信息，添加的片段位置会处于该文档的最后，并且由于每次只能新增一个文档片段，
        # 相对来说并不会这么耗时(无需加载分割，直接并行执行关键问提取+文本转向量)，所以该接口是同步的，
        # 接口会等待处理完毕后再返回，该接口如果任意一个dataset_id或document_id 出错，都会抛出对应的错误。

        # 1.获取文档信息并校验
        document = self.get(Document, document_id)
        if (
                document is None or
                document.id != document_id or
                document.account_id != account.id
        ):
            raise ForbiddenException("文档不存在或无权限给当前文档新增片段信息")

        # 2. 校验上传内容的token长度总数，不能超过1000
        token_count = self.embeddings_service.calculate_token_count(req.content.data)
        if token_count > 1000:
            raise ValidateErrorException("token长度总数，不能超过1000")

        # 3.判断文档的状态是否可以新增片段数据，只有completed才可以新增
        if document.status != DocumentStatus.COMPLETED:
            raise FailException("当前文档状态不能新增文档片段")
        # 4.提取文档片段的最大位置
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
            Segment.document_id == document_id
        ).scalar()

        # 5.检测是否传递了keywords，如果没有传递的话，调用jieba服务生成关键词
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data, 10)

        # 6.往postgres数据库中新增记录
        segment = None
        try:
            #  7.位置+1并且新增segment记录
            segment = self.create(
                Segment,
                account_id=account.id,
                dataset_id=dataset_id,
                document_id=document_id,
                position=position + 1,
                node_id=uuid.uuid4(),
                character_count=len(req.content.data),
                token_count=token_count,
                content=req.content.data,
                keywords=req.keywords.data,
                hash=generate_text_hash(req.content.data),
                enabled=True,
                status=SegmentStatus.COMPLETED,
                processing_started_at=datetime.now(),
                indexing_completed_at=datetime.now(),
                completed_at=datetime.now(),
            )
            # 8.往向量数据库中新增数据
            self.vector_db_service.vector_store.add_documents(
                [LCDocument(
                    page_content=req.content.data,
                    metadata={
                        "account_id": str(account.id),
                        "dataset_id": str(dataset_id),
                        "document_id": str(document_id),
                        "segment_id": str(segment.id),
                        "node_id": segment.node_id,
                        "document_enabled": document.enabled,
                        "segment_enabled": True
                    }
                )],
                ids=[str(segment.node_id)]
            )
            # 9.重新计算片段的字符总数以及token总数
            document_character_count, document_token_count = self.db.session.query(
                func.coalesce(func.sum(Segment.character_count), 0),
                func.coalesce(func.sum(Segment.token_count), 0),
            ).filter(Segment.document_id == document_id).first()

            # 10.更新文档的对应信息
            self.update(
                document,
                character_count=document_character_count,
                token_count=document_token_count,
            )

            # 11.更新关键词表信息
            if document.enabled is None:
                self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment.id])

        except Exception as e:
            logging.exception(f"SegmentService.create_segment error: {str(e)}")
            if segment:
                self.update(
                    segment,
                    enable=False,
                    error=str(e),
                    disabled_at=datetime.now(),
                    status=SegmentStatus.ERROR,
                    stopped_at=datetime.now(),
                )
            raise FailException("新增文档片段失败，请稍后尝试")

    def update_segment(
            self,
            dataset_id: UUID,
            document_id: UUID,
            segment_id: UUID,
            req: UpdateSegmentReq,
            account: Account
    ) -> Segment:
        """修改片段信息"""

        # 1. 片段当前用户是否可以修改当前片段信息
        segment = self.get(Segment, segment_id)

        if (
                segment is None or
                segment.document_id != document_id or
                segment.account_id != account.id
        ):
            raise ForbiddenException("当前片段信息不存在或无权限修改")

        # 2. 判断文档状态，只要状态是complite时才能修改
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当天片段状态无法修改")

        # 3. 判断是否传进来关键词，如果没有则调用结巴分词器进行分词
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data, 10)

        # 4.计算新内容hash值，用于判断是否需要更新向量数据库以及文档详情
        new_hash = generate_text_hash(req.content.data)
        required_update = segment.hash != new_hash

        # 判断当前是否有锁
        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(segment_id=segment_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("当前片段信息正在被修改，请稍后重试")

        # 计算token数量
        token_count = self.embeddings_service.calculate_token_count(req.content.data)

        # 5. 加锁修改数据信息和向量数据库信息
        try:
            self.update(
                segment,
                content=req.content.data,
                keywords=req.keywords.data,
                character_count=len(req.content.data),
                token_count=token_count

            )
            # 6.修改关键词表.先删除，在添加新的
            self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment.id])
            self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment.id])

            if required_update:
                document = segment.document

                # 8. 更新文档的总字符数，总Token数量
                document_character_count, document_token_count = self.db.session.query(
                    func.coalesce(func.sum(Segment.character_count), 0),
                    func.coalesce(func.sum(Segment.token_count), 0)
                ).filter(Segment.document_id == document_id).first()

                self.update(
                    document,
                    character_count=document_character_count,
                    token_count=document_token_count
                )
                # 9. 修改向量数据信息
                self.vector_db_service.collection.data.update(
                    uuid=str(segment.node_id),
                    properties={
                        "text": req.content.data,
                    },
                    vector=self.embeddings_service.embeddings.embed_query(req.content.data)
                )

        except Exception as e:
            logging.exception(f"更新文档片段记录失败, segment_id: {segment}, 错误信息: {str(e)}")
            raise FailException("更新文档片段记录失败，请稍后尝试")

        return segment

    def get_segment_with_page(
            self, dataset_id: UUID, document_id: UUID, req: GetSegmentWithPageReq, account: Account
    ) -> Tuple[list[Segment], Paginator]:
        """分页获取片段信息"""

        document = self.get(Document, document_id)

        if document is None or document.account_id != account.id:
            raise ForbiddenException("当前用户无权限或文件不存在")

        # 构建分页器
        paginator = Paginator(db=self.db, req=req)
        # 配置过滤器
        filters = [
            Segment.dataset_id == dataset_id,
            Segment.document_id == document_id,
        ]

        if req.search_word.data:
            filters.append(Segment.content.ilike(f"%{req.search_word.data}%"))

        # 查询数据
        segments = paginator.paginate(
            self.db.session.query(Segment).filter(*filters).order_by("position")
        )

        return segments, paginator

    def update_segment_enabled(self, dataset_id: UUID, document_id: UUID, segment_id: UUID,
                               enabled: bool, account: Account):

        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
                or account.id != segment.account_id
        ):
            raise ForbiddenException("当前用户无权限或文件不存在")

        # 2.判断文档片段是否处于可启用/禁用的环境
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当前状态无法操作文档")

        # 3.判断更新的片段启用状态和数据库的数据是否一致，如果是则抛出错误
        if segment.enabled == enabled:
            raise FailException("修改状态不能和数据库状态一致")

        # 4.获取更新片段启用状态锁并上锁检测
        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(segment_id=segment_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("当前文档正在修改，请稍后修改")

        # 5.上锁并更新对应的数据，涵盖postgres记录、weaviate、关键词表
        with self.redis_client.lock(cache_key, LOCK_EXPIRE_TIME):
            try:
                # 6.修改postgres数据库里的文档片段状态
                self.update(
                    segment,
                    enabled=enabled,
                    disabled_at=None if enabled else datetime.now(),
                )
                # 7.更新关键词表的对应信息，有可能新增，也有可能删除
                document = segment.document
                if enabled is True and document.enabled is True:
                    self.keyword_table_service.add_keyword_table_from_ids(dataset_id, [segment.id])
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment.id])

                # 8.同步处理weaviate向量数据库里的数据
                self.vector_db_service.collection.data.update(
                    uuid=segment.node_id,
                    properties={
                        "segment_enabled": enabled
                    }
                )
            except Exception as e:
                logging.exception(f"修改片段信息出错，片段编号是：{segment_id}")
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(),
                    stopped_at=datetime.now(),
                )
                raise FailException("更新文档片段启用状态失败，请稍后重试")

    def delete_segment(
            self, dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account
    ) -> Segment:
        """根据传递的信息更新指定的文档片段启用状态"""
        # 该接口主要用于更新文档片段的启用状态，例如启用或禁用，
        # 该接口会同步更新业务数据库和向量数据库，并且耗时较短，所以无需执行异步任务。
        # enabled ->bool:对应片段的状态，true为开启，false为关闭，只有当文档片段处理完成后，
        # 才可以修改，文档如果没有执行完毕，将enabled修改为true，会抛出错误信息。

        segment = self.get(Segment, segment_id)
        if (
                segment is None
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
                or account.id != segment.account_id
        ):
            raise ForbiddenException("当前用户无权限或文件不存在")

        # 2.判断文档是否处于可以删除的状态，只有COMPLETED/ERROR才可以删除
        if segment.status not in [SegmentStatus.COMPLETED, SegmentStatus.ERROR]:
            raise FailException("当前文档片段处于不可删除状态，请稍后尝试")

        # 3.删除文档片段信息
        document = segment.document
        self.delete(segment)

        # 4. 删除该片段在关键字表中信息
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])

        # 5. 删除在向量数据库中的片段信息
        try:
            self.vector_db_service.collection.data.delete_by_id(str(segment.node_id))
        except Exception as e:
            logging.exception(e)(f"删除文档片段记录失败, segment_id: {segment_id}, 错误信息: {str(e)}")

        # 6. 查询当前 document 下所有分段（Segment）的总字符数、总 token 数
        document_character_count, document_token_count = self.db.session.query(
            func.coalesce(func.sum(Segment.character_count), 0),
            func.coalesce(func.sum(Segment.token_count), 0),
        ).filter(Segment.document_id == document.id).first()

        self.update(
            document,
            document.character_count == document_character_count,
            document.token_count == document_token_count
        )

        return segment

    def get_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account) -> Segment:
        """查询文档片段信息"""

        segment = self.get(Segment, segment_id)

        if (
                segment is None
                or segment.dataset_id != dataset_id
                or segment.account_id != account.id
                or segment.document_id != document_id
        ):
            raise ForbiddenException("文档不存在或无权限操作该文档")

        return segment
