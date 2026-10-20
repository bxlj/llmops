"""
@Time    : 2026-04-03 9:23
@AUthor  : jiachengjie
@File    : builtin_category_manager.py
"""
import os.path
from typing import Any

import yaml
from injector import inject, singleton
from langchain_core.utils.pydantic import BaseModel, Field

from internal.core.tool.builtin_tools.enytities.category_entity import CategoryEntity
from internal.exception import NotFoundException


@inject
@singleton
class BuiltinCategoryManager(BaseModel):
    """内置的工具分类管理器"""
    category_map: dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._init_categories()

    def get_category_map(self) -> dict[str, Any]:
        return self.category_map

    def _init_categories(self):
        """初始化分类数据"""
        # 1.检测数据是否已经处理
        if self.category_map:
            return
        # 2.获取yaml数据路径并加载
        current_path = os.path.abspath(__file__)
        category_path = os.path.dirname(current_path)
        category_yaml_path = os.path.join(category_path, 'categories.yaml')

        with open(category_yaml_path, encoding='utf-8') as f:
            categories = yaml.safe_load(f)

        # 3.循环遍历所有分类，并且将分类加载成实体信息
        for category in categories:
            category_entity = CategoryEntity(**category)

            # 获取icon图标信息
            icon_svg_path = os.path.join(category_path, 'icons', category_entity.icon)

            if not os.path.exists(icon_svg_path):
                raise NotFoundException(f"icons path {icon_svg_path} does not exist")

            with open(icon_svg_path, encoding='utf-8') as f:
                icon_svg = f.read()

            # 将数据映射到字典中
            self.category_map[category_entity.category] = {
                "icon": icon_svg,
                "entity": category_entity,
            }
