"""
@Time    : 2026-06-05 14:36
@Author  : jiachengjie
@File    : dataset_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def delete_dataset(dataset_id: UUID):
    """根据传递的知识库id删除特定的知识库信息"""
    from app.http.model import injector
    from internal.service import IndexService

    indexing_service = injector.get(IndexService)
    indexing_service.delete_dataset(dataset_id)
