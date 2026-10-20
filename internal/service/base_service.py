"""
@Time    : 2026-04-07 16:29
@Author  : jiachengjie
@File    : base_service.py
"""
from typing import Any, Optional
from uuid import UUID

from internal.exception import FailException
from pkg.sqlalchemy import SQLAlchemy


class BaseService:
    """基础服务，完善数据库基础增删改查"""
    db: SQLAlchemy

    def create(self, model: Any, **kwargs) -> Any:
        with self.db.auto_commit():
            model_instance = model(**kwargs)
            self.db.session.add(model_instance)
        return model_instance

    def delete(self, model_instance: Any) -> Any:
        with self.db.auto_commit():
            self.db.session.delete(model_instance)
        return model_instance

    def update(self, model_instance: Any, **kwargs) -> Any:
        """根据传递的模型实例+键值对信息更新数据库记录"""
        with self.db.auto_commit():
            for key, value in kwargs.items():
                if hasattr(model_instance, key):
                    setattr(model_instance, key, value)
                else:
                    raise FailException("更新数据失败")
        return model_instance

    def query(self, model: Any, primary_key: Any) -> Optional[Any]:
        """根据传递的模型类+主键的信息获取唯一数据"""
        with self.db.auto_commit():
            return self.db.session.query(model).get(primary_key)

    def get(self, model: Any, primary_key: UUID) -> Optional[Any]:
        """根据传递的模型类+主键的信息获取唯一数据"""
        return self.db.session.query(model).get(primary_key)
