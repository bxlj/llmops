"""
@Time    : 2026-05-13 10:21
@Author  : jiachengjie
@File    : keyword_table_service.py
"""
import logging
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from redis import Redis

from internal.entity.cache_entity import LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE, LOCK_EXPIRE_TIME
from internal.model.dataset import KeywordTable, Segment
from internal.service import BaseService
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class KeywordTableService(BaseService):
    db: SQLAlchemy
    redis_client: Redis

    def get_keyword_table_from_dataset_id(self, dataset_id: UUID) -> KeywordTable:
        """根据传递的知识库id获取关键词表"""
        keyword_table = self.db.session.query(KeywordTable).filter(
            KeywordTable.dataset_id == dataset_id
        ).one_or_none()
        if keyword_table is None:
            keyword_table = self.create(
                KeywordTable,
                dataset_id=dataset_id,
                keyword_table={}
            )
        return keyword_table

    def add_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]) -> None:
        try:
            """根据传递的知识库id+片段id列表，在关键词表中添加关键词"""
            cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
            with (self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME)):
                keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)
                keyword_table = {
                    field: set(value) for field, value in keyword_table_record.keyword_table.items()
                }

                # 获取片段里面的关键字
                segments = self.db.session.query(Segment).with_entities(Segment.id, Segment.keywords).filter(
                    Segment.id.in_(segment_ids)
                ).all()

                # 判断keyword_table里面是否有segments里面的关键字，如果没有，则进行添加
                for id, keywords in segments:
                    for keyword in keywords:
                        if keyword not in keyword_table:
                            keyword_table[keyword] = set()
                        keyword_table[keyword].add(str(id))

                # 更新关键词表
                self.update(
                    keyword_table_record,
                    keyword_table={field: list(value) for field, value in keyword_table.items()}
                )
        except Exception as e:
            import traceback
            print("=== [关键词添加] 报错 ===")
            traceback.print_exc()
            logging.error(f"关键词添加失败: {str(e)}")
            raise  # 抛出异常让上层捕获

    def delete_keyword_table_from_ids(self, dataset_id: UUID, segment_ids: list[UUID]):
        try:
            """根据传递的知识库id+片段id列表删除对应关键词表中多余的数据"""
            cache_key = LOCK_KEYWORD_TABLE_UPDATE_KEYWORD_TABLE.format(dataset_id=dataset_id)
            with self.redis_client.lock(cache_key, timeout=LOCK_EXPIRE_TIME):
                keyword_table_record = self.get_keyword_table_from_dataset_id(dataset_id)

                keyword_table = keyword_table_record.keyword_table.copy()

                # 3.将片段id列表转换成集合，并创建关键词集合用于清除空关键词
                # 我要删除的集合
                segment_ids_to_delete = set([str(segment_id) for segment_id in segment_ids])
                # 存储的是在取差集之后，关键字没有在关联片段的关键字
                keywords_to_delete = set()

                # 分离数据
                for keyword, ids in keyword_table.items():
                    ids_set = set(ids)
                    if segment_ids_to_delete.intersection(ids_set):
                        keyword_table[keyword] = list(ids_set.difference(segment_ids_to_delete))
                        if not keyword_table[keyword]:
                            keywords_to_delete.add(keyword)

                # 检测空关键词数据并删除（关键词并没有映射任何字段id的数据）
                for keyword in keywords_to_delete:
                    del keyword_table[keyword]

                # 更新关键词表
                self.update(
                    keyword_table_record,
                    keyword_table=keyword_table
                )
        except Exception as e:
            import traceback
            print("=== [关键词添加] 报错 ===")
            traceback.print_exc()
            logging.error(f"关键词添加失败: {str(e)}")
            raise  # 抛出异常让上层捕获
