"""
@Time    : 2026-09-30 11:02
@Author  : JiaChengJie
@File    : template_transform_entity.py
"""
from pydantic import Field

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableValueType
from internal.core.workflow.entities.workflow_entity import VariableEntity


class TemplateTransformNodeData(BaseNodeData):
    """模板转换节点"""
    template: str  # 画布上配的模板
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(name="output", value={"type": VariableValueType.GENERATED})
        ]
    )
