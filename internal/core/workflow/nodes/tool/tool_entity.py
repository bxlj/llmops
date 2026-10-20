"""
@Time    : 2026-10-07 12:02
@Author  : JiaChengJie
@File    : tool_entity.py
"""
from typing import Literal, Any

from pydantic import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType


class ToolNodeData(BaseNodeData):
    """工具节点数据"""
    tool_type: Literal["builtin_tool", "api_tool"] = Field(alias="type")  # type
    provider_id: str  # 工具提供者
    tool_id: str  # 工具id
    params: dict[str, Any] = Field(default_factory=dict)  # 内置工具参数
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ],
    )
