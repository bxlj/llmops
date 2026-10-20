"""
@Time    : 2026-10-08 16:03
@Author  : JiaChengJie
@File    : http_request_entity.py
"""
from enum import Enum

from pydantic import HttpUrl, Field, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType, VariableType
from internal.exception import ValidateErrorException


class HttpRequestMethod(str, Enum):
    """http请求方式"""
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


class HttpRequestInputType(str, Enum):
    """Http请求输入变量类型"""
    PARAMS = "params"  # query参数
    HEADERS = "headers"  # header请求头
    BODY = "body"  # body参数


class HttpRequestNodeData(BaseNodeData):
    """http请求结果数据"""
    url: HttpUrl = ""  # 请求路径
    method: HttpRequestMethod = HttpRequestMethod.GET  # http请求方式
    inputs: list[VariableEntity] = Field(default_factory=list)
    outputs: list[VariableEntity] = Field(
        exclude=True,
        default_factory=lambda: [
            VariableEntity(
                name="status_code",
                type=VariableType.INT,
                value={"type": VariableValueType.GENERATED, "content": 0},
            ),
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED}),
        ],

    )

    @field_validator("inputs")
    def validate_inputs(cls, inputs: list[VariableEntity]):
        """校验输入列表数据"""
        # 1.校验判断输入变量列表中的类型信息
        for input in inputs:
            if input.meta.get("type") not in HttpRequestInputType.__members__.values():
                raise ValidateErrorException("Http请求参数结构出错")

        return inputs
