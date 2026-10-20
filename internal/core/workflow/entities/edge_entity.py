"""
@Time    : 2026-08-23 21:36
@Author  : JiaChengJie
@File    : edge_entity.py
"""
from uuid import UUID

from pydantic.main import BaseModel

from internal.core.workflow.entities.node_entity import NodeType


class BaseEdgeData(BaseModel):
    """基础边数据"""
    id: UUID  # 边记录id
    source: UUID  # 边起点对应的节点id
    source_type: NodeType  # 边起点类型
    target: UUID  # 边目标对应的节点id
    target_type: NodeType  # 边目标类型
