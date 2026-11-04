"""
@Time    : 2026-11-02 15:41
@Author  : JiaChengJie
@File    : app_task.py
"""
from uuid import UUID

from celery import shared_task


@shared_task
def auto_create_app(account_id: UUID, name: str, description: str) -> None:
    """根据用户输入的agent名称和描述信息，异步创建Agent"""
    from app.http.model import injector
    from internal.service import AppService

    app_service = injector.get(AppService)
    app_service.auto_create_app(account_id, name, description)
