"""
@Time    : 2026-04-03 9:03
@AUthor  : jiachengjie
@File    : category_entity.py
"""
from langchain_core.utils.pydantic import BaseModel
from pydantic import field_validator

from internal.exception import FailException


class CategoryEntity(BaseModel):
    name: str
    icon: str
    category: str

    @field_validator("icon")
    def check_icon_extension(cls, icon: str):
        """校验icon的扩展名是不是.svg，如果不是则抛出错误"""
        if not icon.endswith('.svg'):
            raise FailException('icon must end with .svg')
        return icon
