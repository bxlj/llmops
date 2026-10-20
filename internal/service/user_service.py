"""
@Time    : 2026-05-25 9:58
@Author  : jiachengjie
@File    : user_service.py
"""
import json
import logging
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from redis import Redis
from sqlalchemy.exc import SQLAlchemyError

from internal.entity.cache_entity import USER_INFO
from internal.exception.exception import FailException
from internal.model.user import User
from internal.schema.user_schema import CreateUserReq, UpdateUserReq
from internal.service import BaseService
from pkg.sqlalchemy.sqlalchemy import SQLAlchemy


@inject
@dataclass
class UserService(BaseService):
    db: SQLAlchemy
    redis_client: Redis

    def create_user(self, req: CreateUserReq) -> User:
        """创建用户信息"""
        try:
            id_card = req.id_card.data.strip()
            # 0. 判断用户信息是否已经存在
            user_redis = self.redis_client.get(USER_INFO.format(id_card=id_card))
            if user_redis:
                raise FailException("人员信息已经存在")

            user_db = self.db.query(User).filter(User.id_card == id_card).first()
            if user_db:
                self.redis_client.set(
                    USER_INFO.format(id_card=id_card),
                    json.dumps(user_db.to_dict(), ensure_ascii=False),
                    ex=86400 * 7
                )
                raise FailException("人员信息已经存在")

            # 1.保存用户信息
            user = self.create(
                User,
                name=req.name.data.strip(),
                nike_name=req.nike_name.data.strip(),
                sex=req.sex.data.strip(),
                age=req.age.data,
                id_card=id_card,
                address=req.address.data.strip(),
            )

            user_dict = self.user_to_dict(user)

            # 存储redis中
            self.redis_client.set(
                USER_INFO.format(id_card=user.id_card),
                json.dumps(user_dict, ensure_ascii=False),
                ex=86400 * 7
            )

            return user
        except SQLAlchemyError as e:
            logging.error(f"保存人员信息创建数据库异常，人员名称是：{req.name.data.strip()}")
            self.db.session.rollback()
            raise FailException("创建用户失败，请稍后重试")

    def update_user(self, user_id: UUID, req: UpdateUserReq) -> User:
        """修改用户信息，修改那些字段，数据就更新哪些字段"""
        # 1. 判断要修改用户是否存在
        logging.info("===================== 我进来了 =====================")

        user = self.get(User, user_id)
        if not user:
            raise FailException("用户不存在")

        # 2. 构建更新数据（只传要改的）
        update_data = {}
        for field, value in req.data.items():
            logging.info(f"里面的字段有：{field}")
            if value is not None:
                update_data[field] = value

        if not update_data:
            raise FailException("没有要修改的字段")

        # 3. 更新数据库
        self.update(user, **update_data)

        # 4. 更新redis
        new_user = self.get(User, user_id)

        user_dict = self.user_to_dict(new_user)

        self.redis_client.set(
            USER_INFO.format(id_card=user.id_card),
            json.dumps(user_dict, ensure_ascii=False),
            ex=86400 * 7
        )

        return new_user

    @staticmethod
    def user_to_dict(user: User) -> dict:
        return {
            "id": str(user.id),
            "name": user.name,
            "nike_name": user.nike_name,
            "sex": user.sex,
            "age": user.age,
            "address": user.address,
            "id_card": user.id_card,
            "created_at": int(user.created_at.timestamp()) if user.created_at else 0,
            "updated_at": int(user.updated_at.timestamp()) if user.updated_at else 0,
        }
