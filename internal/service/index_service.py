"""
@Time    : 2026-05-11 15:41
@Author  : jiachengjie
@File    : index_service.py
"""
import logging
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED
from internal.entity.dataset_entity import DocumentStatus, SegmentStatus
from internal.exception import NotFoundException
from internal.lib.helper import generate_text_hash
from internal.model import Document
from internal.model.dataset import ProcessRule, Segment, KeywordTable, DatasetQuery
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .process_rule_service import ProcessRuleService
from .vector_database_service import VectorDatabaseService


@inject
@dataclass
class IndexService(BaseService):
    db: SQLAlchemy
    redis_client: Redis
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_db_service: VectorDatabaseService

    def build_documents(self, document_ids: list[UUID]):
        """根据传递的文档id列表构建知识库文档，涵盖了加载、分割、索引构建、数据存储等内容"""
        # 1. 根据传入的文档列表id获取文档数据
        documents = self.db.session.query(Document).filter(Document.id.in_(document_ids)).all()

        # 2. 遍历文档，进行处理
        for document in documents:
            # 3. 更新知识库文档表状态
            self.update(
                document,
                status=DocumentStatus.PARSING,
                processing_started_at=datetime.now(),
            )

            # 4. 将普通document文档转化为langchain能识别的document,
            # 执行文档加载步骤，并更新文档的状态与时间
            lc_documents, document = self._parsing(document)

            # 5.执行文档分割步骤，并更新文档状态与时间，涵盖了片段的信息
            lc_segments = self._splitting(document, lc_documents)

            # 6. 构建索引
            self._indexing(document, lc_segments)

            # 7.存储操作，涵盖文档状态更新，以及向量数据库的存储
            self._completed(document, lc_segments)

    def _parsing(self, document: Document) -> tuple[list[LCDocument], Document]:
        """将普通document文档转化为langchain能识别的document"""
        # 1. 获取该文档下的所有upload_file文件
        upload_file = document.upload_file
        # 2. 将upload_file转换为langchain类型的document
        lc_documents = self.file_extractor.load(upload_file, False, True)

        # 3. 清除document里面的空字符串，空格
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # ==========================================
        # 【修复】关键代码：重新合并到会话
        # ==========================================
        document = self.db.session.merge(document)

        # 4. 更新知识库文档表状态
        self.update(
            document,
            character_count=sum([len(lc_document.page_content) for lc_document in lc_documents]),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now(),
        )

        return lc_documents, document

    def _splitting(self, document: Document, lc_documents: list[LCDocument]) -> list[LCDocument]:
        """根据传递的信息进行文档分割，拆分成小块片段"""
        # 双重保险：确保 document 是被会话跟踪的对象
        document = self.db.session.merge(document)

        # 1. 获取分割规则
        process_rule = self.db.session.query(ProcessRule).filter(
            ProcessRule.id == document.process_rule_id
        ).one_or_none()

        # 2.获取分割器对象
        text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
            process_rule,
            self.embeddings_service.calculate_token_count
        )

        # 3. 按照规则清除文档里面的空格等
        for lc_document in lc_documents:
            lc_document.page_content = (
                self.process_rule_service.clean_text_by_process_rule(
                    lc_document.page_content,
                    process_rule
                )
            )

        # 4. 把文档列表切分成片段列表
        lc_segments = text_splitter.split_documents(lc_documents)

        # 5. 获取文档下最大的片段位置
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
            Segment.document_id == document.id).scalar()

        # 6. 补齐元数据以及将片段数据入库
        segments = []
        for lc_segment in lc_segments:
            position += 1
            content = lc_segment.page_content
            segment = self.create(
                Segment,
                account_id=document.account_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                node_id=uuid.uuid4(),
                position=position,
                content=content,
                character_count=len(content),
                token_count=self.embeddings_service.calculate_token_count(content),
                hash=generate_text_hash(content),
                status=SegmentStatus.WAITING,
            )
            lc_segment.metadata = {
                "account_id": str(document.account_id),
                "dataset_id": str(document.dataset_id),
                "document_id": str(document.id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": False,
                "segment_enabled": False,
            }
            segments.append(segment)

        # 7. 更新文档信息
        self.update(
            document,
            status=DocumentStatus.INDEXING,
            splitting_completed_at=datetime.now(),
            token_count=sum([segment.token_count for segment in segments]), )

        return lc_segments

    # def _indexing(self, document: Document, lc_segments: list[LCDocument]) -> None:
    #     """根据传递的信息构建索引"""
    #
    #     # 1. 获取每个片段的关键词
    #     for lc_segment in lc_segments:
    #         keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)
    #
    #         # 2. 更新文档分片表里面的关键词数组keywords
    #         self.db.session.query(Segment).filter(
    #             Segment.id == lc_segment.metadata["segment_id"]
    #         ).update({
    #             "keywords": keywords,
    #             "status": SegmentStatus.INDEXING,
    #             "indexing_completed_at": datetime.now(),
    #         })
    #
    #         # 3. 获取关键词表
    #         keyword_table_record = (self.keyword_table_service.
    #                                 get_keyword_table_from_dataset_id(document.dataset_id))
    #
    #         keyword_table_record = self.db.session.merge(keyword_table_record)
    #
    #         keyword_table = {
    #             field: set(value) for field, value in keyword_table_record.keyword_table.items()
    #         }
    #
    #         # 4.循环将新关键词添加到关键词表中
    #         for keyword in keywords:
    #             if keyword not in keyword_table:
    #                 keyword_table[keyword] = set()
    #             keyword_table[keyword].add(lc_segment.metadata["segment_id"])
    #
    #         # 5. 更新关键词表
    #         self.update(
    #             keyword_table_record,
    #             keyword_table={field: list(value) for field, value in keyword_table.items()}
    #         )
    #
    #     # 6.更新文档状态
    #     self.update(
    #         document,
    #         indexing_completed_at=datetime.now(),
    #     )

    def _indexing(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """根据传递的信息构建索引（带完整日志追踪）"""
        logging.info(f"[INDEXING] 开始处理文档: {document.id}")
        try:
            for idx, lc_segment in enumerate(lc_segments):
                logging.info(
                    f"[INDEXING] 处理片段 {idx + 1}/{len(lc_segments)}, segment_id: {lc_segment.metadata.get('segment_id')}")
                try:
                    # 1. 提取关键词
                    keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)
                    logging.info(f"[INDEXING] 提取关键词成功: {keywords}")

                    # 2. 更新 Segment
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.id == lc_segment.metadata["segment_id"]
                        ).update({
                            "keywords": keywords,
                            "status": SegmentStatus.INDEXING,
                            "indexing_completed_at": datetime.now(),
                        })
                    logging.info(f"[INDEXING] 更新 Segment 成功")

                    # 3. 获取关键词表
                    keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(
                        document.dataset_id)
                    keyword_table_record = self.db.session.merge(keyword_table_record)
                    logging.info(f"[INDEXING] 获取关键词表成功")

                    keyword_table = {
                        field: set(value) for field, value in keyword_table_record.keyword_table.items()
                    }

                    # 4. 添加关键词
                    for keyword in keywords:
                        keyword_table.setdefault(keyword, set()).add(lc_segment.metadata["segment_id"])

                    # 5. 更新关键词表
                    self.update(
                        keyword_table_record,
                        keyword_table={field: list(value) for field, value in keyword_table.items()}
                    )
                    logging.info(f"[INDEXING] 更新关键词表成功")

                except Exception as e:
                    logging.exception(f"[INDEXING] 片段 {idx + 1} 处理失败: {str(e)}")
                    continue

            logging.info(f"[INDEXING] 所有片段处理完成，准备更新 document")
            # 6.更新文档状态
            self.update(
                document,
                indexing_completed_at=datetime.now(),
            )
            logging.info(f"[INDEXING] document 更新成功，indexing_completed_at 已写入")

        except Exception as e:
            logging.exception(f"[INDEXING] 整体处理失败: {str(e)}")

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """存储文档片段到向量数据库，并完成状态更新"""
        # 1.循环遍历片段列表数据，将文档状态及片段状态设置成True
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True

        # 2.调用向量数据库，每次存储10条数据，避免一次传递过多的数据
        def thread_func(flask_app: Flask, chunks: list[LCDocument], ids: list[UUID]) -> None:
            """线程函数，执行向量数据库与postgres数据的存储"""
            with flask_app.app_context():
                try:
                    self.vector_db_service.vector_store.add_documents(
                        chunks, ids=ids,
                    )
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.COMPLETED,
                            "completed_at": datetime.now(),
                            "enabled": True,
                        })
                except Exception as e:
                    logging.exception(f"构建文档片段索引发生异常，错误信息： {str(e)}")
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id.in_(ids)
                        ).update({
                            "status": SegmentStatus.ERROR,
                            "completed_at": None,
                            "stopped_at": datetime.now(),
                            "enabled": False,
                        })

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                futures.append(executor.submit(thread_func, current_app._get_current_object(), chunks, ids))

            for future in futures:
                future.result()

        # 6.更新文档的状态数据
        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True,
        )

    # def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
    #     """将文档片段保存在向量数据库"""
    #     # 更改状态，表示该片段可以存入向量数据库，正常让外部使用
    #     for lc_segment in lc_segments:
    #         lc_segment.metadata["document_enabled"] = True
    #         lc_segment.metadata["segment_enabled"] = True
    #
    #     # 2.调用向量数据库，每次存储10条数据，避免一次传递过多的数据
    #     def thread_func(flask_app: Flask, chunks: list[LCDocument], ids: list[UUID]) -> None:
    #         """线程函数，执行pg库和向量数据库的存储"""
    #         with flask_app.app_context():
    #             try:
    #                 # 存储数据到向量数据库
    #                 self.vector_db_service.vector_store.add_documents(
    #                     chunks, ids=ids,
    #                 )
    #                 with self.db.auto_commit():
    #                     self.db.session.query(Segment).filter(
    #                         Segment.node_id.in_(ids)
    #                     ).update({
    #                         "status": SegmentStatus.COMPLETED,
    #                         "completed_at": datetime.now(),
    #                         "enabled": True
    #                     })
    #             except Exception as e:
    #                 logging.exception(f"构建文档片段索引发生异常，错误信息： {str(e)}")
    #                 with self.db.auto_commit():
    #                     self.db.session.query(Segment).filter(
    #                         Segment.node_id.in_(ids)
    #                     ).update({
    #                         "status": SegmentStatus.ERROR,
    #                         "completed_at": datetime.now(),
    #                         "enabled": False,
    #                         "stopped_at": datetime.now()
    #                     })
    #
    #     # 构建线程池
    #     with ThreadPoolExecutor(max_workers=5) as executor:
    #         futures = []
    #         for i in range(0, len(lc_segments), 10):
    #             chunks = lc_segments[i:i + 10]
    #             ids = [chunk.metadata["node_id"] for chunk in chunks]
    #             futures.append(executor.submit(thread_func, current_app._get_current_object(), chunks, ids))
    #
    #             for future in futures:
    #                 future.result()
    #
    #     self.update(
    #         document,
    #         completed_at=datetime.now(),
    #         status=DocumentStatus.COMPLETED,
    #         enabled=True
    #     )

    def update_document_enabled(self, document_id: UUID) -> None:
        """根据文档id更新向量数据库对应的状态"""
        print("=== 我进来了，执行了 ===")
        # 1. 构建cache_key
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)

        # 2. 根据document_id获取文档信息
        document = self.get(Document, document_id)
        if document is None:
            logging.exception(f"Document {document_id} not found")
            raise NotFoundException("文档不存在")

        # 3.查询归属于当前文档的所有片段的节点id
        segments = self.db.session.query(Segment).with_entities(Segment.id, Segment.node_id, Segment.enabled).filter(
            Segment.document_id == document_id,
            Segment.status == SegmentStatus.COMPLETED,
        ).all()

        # 列表推导式
        segment_ids = [id for id, _, _ in segments]
        node_ids = [node_id for _, node_id, _ in segments]

        try:
            print("=== 开始更新向量库 ===")
            print("vector_db_service:", self.vector_db_service)
            # 便利更新所有node_ids并更新向量数据库
            collection = self.vector_db_service.collection
            for node_id in node_ids:
                try:
                    collection.data.update(
                        uuid=node_id,
                        properties={
                            "document_enabled": document.enabled,
                        }
                    )
                except Exception as e:
                    with self.db.session.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id == node_id,
                        ).update({
                            "error": str(e),
                            "status": SegmentStatus.ERROR,
                            "enabled": False,
                            "disabled_at": datetime.now(),
                            "stopped_at": datetime.now(),
                        })
            # 根据文档状态来判断关键词新增还是删除，如果文档状态修改为ture，则需要新增关键词，否则删除关键词
            if document.enabled is True:
                # 根据片段获取关键词
                enabled_segment_ids = [id for id, _, enable in segments if enable is True]
                self.keyword_table_service.add_keyword_table_from_ids(document.dataset_id, enabled_segment_ids)

            else:
                # 删除对应的关键词信息
                self.keyword_table_service.delete_keyword_table_from_ids(document.dataset_id, segment_ids)

        except Exception as e:
            # 5.记录日志并将状态修改回原来的状态
            logging.exception(f"修改向量数据库状态失败，文档id为：{document.id},错误信息是：{str(e)}")
            origin_enabled = not document.enabled
            self.update(
                document,
                enabled=origin_enabled,
                disabled_at=None if origin_enabled else datetime.now(),
            )
        finally:
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """删除向量数据库存储的文档信息"""
        segment_ids = [str(id) for id, in (self.db.session.query(Segment).with_entities(Segment.id).filter(
            Segment.document_id == document_id,
        ).all())]

        # 2.调用向量数据库删除其关联记录
        collection = self.vector_db_service.collection
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(document_id)
        )

        # 3. 删除pg数据库中segement片段文档
        with self.db.auto_commit():
            self.db.session.query(Segment).filter(
                Segment.document_id == document_id,
            ).delete()

        # 4. 删除关键词表里面对应的片段文档id
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segment_ids)

    def delete_dataset(self, dataset_id: UUID):
        """根据传递的知识库id执行相应的删除操作"""
        try:
            with self.db.auto_commit():
                # 1. 删除相关文档信息
                self.db.session.query(Document).filter(
                    Document.dataset_id == dataset_id,
                ).delete()

                # 2. 删除相关片段信息
                self.db.session.query(Segment).filter(
                    Segment.dataset_id == dataset_id,
                ).delete()

                # 3. 删除相关关键字表字表信息
                self.db.session.query(KeywordTable).filter(
                    KeywordTable.dataset_id == dataset_id,
                ).delete()

                # 4. 删除相关查询记录表
                self.db.session.query(DatasetQuery).filter(
                    DatasetQuery.dataset_id == dataset_id,
                ).delete()

                # 5. 删除向量数据库相关字段
                self.vector_db_service.collection.data.delete_many(
                    where=Filter.by_property("dataset_id").equal(str(dataset_id))
                )

        except Exception as e:
            logging.exception(f"异步删除知识库关联内容出错, dataset_id: {dataset_id}, 错误信息: {str(e)}")

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """清除过滤传递的多余空白字符串"""
        text = re.sub(r'<\|', '<', text)
        text = re.sub(r'\|>', '>', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]', '', text)
        text = re.sub('\uFFFE', '', text)  # 删除零宽非标记字符
        return text
