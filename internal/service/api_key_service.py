"""
@Time    : 2026-07-22 16:02
@Author  : JiaChengJie
@File    : api_key_service.py
"""
import secrets
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.exception import ForbiddenException
from internal.model import Account, ApiKey
from internal.schema.api_key_schema import CreateAPIKeyReq, UpdateApiKeyIsActiveReq
from pkg.paginator import PaginatorReq, Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class ApiKeyService(BaseService):
    """apiKey密钥管理器"""
    db: SQLAlchemy

    def create_api_key(self, req: CreateAPIKeyReq, account: Account) -> ApiKey:
        """新增apikey密钥"""
        return self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.generate_api_key(),
            is_active=req.is_active.data,
            remark=req.remark.data,
        )

    def update_api_key(self, api_key_id: UUID, req: CreateAPIKeyReq, account: Account) -> ApiKey:
        """该接口用于修改指定API秘钥的基础信息，涵盖是否激活 和备注信息"""
        # 1. 获取APIKey信息
        api_key = self.get_api_key(api_key_id, account)
        # 2.修改对应的信息
        self.update(
            api_key,
            is_active=req.is_active.data,
            remark=req.remark.data,
        )
        return api_key

    def delete_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """根据传递的id删除API秘钥"""
        # 1. 获取api_key信息
        api_key = self.get_api_key(api_key_id, account)
        self.delete(api_key)
        return api_key

    def update_api_key_is_active(self, api_key_id: UUID, account: Account, req: UpdateApiKeyIsActiveReq) -> ApiKey:
        """该接口用于修改指定API秘钥的状态信息"""
        # 1. 获取api_key信息
        api_key = self.get_api_key(api_key_id, account)
        # 2.修改对应的信息
        self.update(
            api_key,
            is_active=req.is_active.data,
        )
        return api_key

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """根据api_key_id和account_id获取数据"""
        api_key = self.get(ApiKey, api_key_id)
        if not api_key or account.id != api_key.account_id:
            raise ForbiddenException("数据不存在或没有权限")
        return api_key

    def get_api_keys_with_page(self, req: PaginatorReq, account: Account) -> tuple[list[ApiKey], Paginator]:
        """获取API秘钥分页列表数据"""

        # 构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 查询数据
        api_keys = paginator.paginate(
            self.db.session.query(ApiKey).
            filter(ApiKey.account_id == account.id).
            order_by(desc("created_at")),
        )

        return api_keys, paginator

    def get_api_keys_by_credential(self, api_key: UUID) -> ApiKey:
        """根据密钥获取Api密钥完整信息"""
        return self.db.session.query(ApiKey).filter(
            ApiKey.api_key == api_key,
        ).one_or_none()

    @classmethod
    def generate_api_key(cls, api_key_prefix: str = "llmops-v1/") -> str:
        """生成一个长度为48的API秘钥，并携带前缀"""
        return api_key_prefix + secrets.token_urlsafe(48)
