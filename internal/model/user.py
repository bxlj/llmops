"""
@Time    : 2026-05-25 9:41
@Author  : jiachengjie
@File    : user_handle.py
"""

# !/usr/bin/env python
# -*- coding: utf-8 -*-
from sqlalchemy import Column, String, Integer, Text, DateTime, PrimaryKeyConstraint, text
from sqlalchemy.dialects.postgresql import UUID

from internal.extension.database_extension import db


class User(db.Model):
    """用户表模型"""
    __tablename__ = "user"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_user_id"),
    )

    id = Column(UUID, nullable=False, server_default=text("uuid_generate_v4()"))
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    nike_name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    sex = Column(String(10), nullable=False, server_default=text("''::character varying"))
    age = Column(Integer, nullable=False, server_default=text("0"))
    id_card = Column(String(18), nullable=False, server_default=text("''::character varying"))
    address = Column(Text, nullable=False, server_default=text("''::text"))
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        server_onupdate=text('CURRENT_TIMESTAMP(0)'),
    )
