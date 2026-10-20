"""
@Time    : 2026-09-18 10:58
@Author  : JiaChengJie
@File    : end_entity.py
"""
from pydantic import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity


class EndNodeData(BaseNodeData):
    """输出节点数据"""
    outputs: list[VariableEntity] = Field(default_factory=list)
