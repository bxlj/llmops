"""
@Time    : 2026-05-11 15:35
@Author  : jiachengjie
@File    : document_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def build_documents(document_ids: list[UUID]) -> None:
    """根据传递的文档id列表，构建文档"""
    from app.http.model import injector
    from internal.service.index_service import IndexService

    index_service = injector.get(IndexService)
    index_service.build_documents(document_ids)


@shared_task
def update_document_enabled(document_id: UUID) -> None:
    """根据文档id更新文档状态"""
    from app.http.model import injector
    from internal.service.index_service import IndexService

    index_service = injector.get(IndexService)
    index_service.update_document_enabled(document_id)


@shared_task
def delete_document(dataset_id: UUID, document_id: UUID) -> None:
    """根据文档id更新文档状态"""
    from app.http.model import injector
    from internal.service.index_service import IndexService

    index_service = injector.get(IndexService)
    index_service.delete_document(dataset_id, document_id)
