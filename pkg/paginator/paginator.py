"""
@Time    : 2026-04-09 8:49
@Author  : jiachengjie
@File    : paginator.py
"""
import math
from dataclasses import dataclass
from typing import Any

from flask_wtf import FlaskForm
from wtforms.fields.numeric import IntegerField
from wtforms.validators import Optional, NumberRange

from pkg.sqlalchemy import SQLAlchemy


class PaginatorReq(FlaskForm):
    current_page = IntegerField('current_page', validators=[
        Optional(),
        NumberRange(min=1, max=9999, message='Current Page must be greater than or equal to 1.'),
    ])

    page_size = IntegerField('page_size', validators=[
        Optional(),
        NumberRange(min=1, max=50, message='Page size must be greater than or equal to 1.'),
    ])


@dataclass
class Paginator:
    """分页器"""
    total_page: int = 0  # 总页数
    total_record: int = 0  # 总条数
    current_page: int = 0  # 当前页数
    page_size: int = 20  # 每条页数

    def __init__(self, db: SQLAlchemy, req: PaginatorReq = None):
        if req is not None:
            self.current_page = req.current_page.data
            self.page_size = req.page_size.data
        self.db = db

    def paginate(self, select) -> list[Any]:
        """对传入的查询进行分页"""
        # 1. 调用db.paginate进行数据分页
        p = self.db.paginate(select, page=self.current_page, per_page=self.page_size, error_out=False)

        # 2.计算总页数 + 总条数
        self.total_record = p.total
        self.total_page = math.ceil(p.total / self.page_size)

        # 3. 返回分页后的数据
        return p.items


@dataclass
class PageModel:
    list: list[Any]
    paginator: Paginator
