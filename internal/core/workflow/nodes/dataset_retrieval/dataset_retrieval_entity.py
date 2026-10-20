"""
@Time    : 2026-09-30 16:24
@Author  : JiaChengJie
@File    : dataset_retrieval_entity.py
"""
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType, VariableType
from internal.entity.dataset_entity import RetrievalStrategy
from internal.exception import FailException


class RetrievalConfig(BaseModel):
    """检索配置数据"""
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC  # 检索策略
    k: int = 4
    score: float = 0


class DatasetRetrievalNodeData(BaseNodeData):
    """知识库检索节点数据"""
    dataset_ids: list[UUID]  # 知识库检索相关文档id
    retrieval_config: RetrievalConfig = RetrievalConfig()  # 检索配置信息
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入信息
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("inputs")
    def validator_inputs(cls, value: list[VariableEntity]):
        """校验inputs字段属性"""
        if len(value) != 1:
            raise FailException("知识库节点输入变量信息出错")

        # 判断输入的字段类型以及字段名字是否准确
        input_entity = value[0]
        if input_entity.name != "query" or input_entity.type != VariableType.STRING or input_entity.required is False:
            raise FailException("输入字段名称/类型/必填属性出错")

        return value
