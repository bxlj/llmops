"""
@Time    : 2026-04-03 17:12
@AUthor  : jiachengjie
@File    : api_tool_schema.py
"""

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import Field
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Length, URL, ValidationError, Optional

from pkg.paginator import PaginatorReq
from .schema import ListField
from ..model import ApiToolProvider, ApiTool


class JSONField(Field):
    """wtforms 自定义JSON字段，支持直接传JSON对象/字符串"""


class ValidateOpenAPISchemaReq(FlaskForm):
    """校验OpenAPI规范字符串请求"""
    openapi_schema = StringField("openapi_schema", validators=[
        DataRequired(message="openapi_schema字符串不能为空")
    ])


class GetToolProviderWithPageReq(PaginatorReq):
    """校验获取API列表信息参数"""
    search_word = StringField("search_word", validators=[
        Optional()
    ])


class ValidateCreateAPISchemaReq(FlaskForm):
    """检验创建自定义插件接口参数"""
    name = StringField("name", validators=[
        DataRequired(message="工具提供者名字不能为空"),
        Length(min=1, max=30, message="工具提供者名字范围1-30")
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="工具提供商icon不能为空"),
        URL(message="工具提供者的图标必须是URL")
    ])
    openapi_schema = JSONField("openapi_schema", validators=[
        DataRequired(message="openapi_schema不能为空")
    ])
    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """校验headers请求的数据是否正确，涵盖列表校验，列表元素校验"""
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("headers里的每一个元素都必须是字典")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("headers里的每一个元素都必须包含key/value两个属性，不允许有其他属性")


class UpdateAPISchemaReq(FlaskForm):
    """检验修改自定义插件接口参数"""
    name = StringField("name", validators=[
        DataRequired(message="工具提供者名字不能为空"),
        Length(min=1, max=30, message="工具提供者名字范围1-30")
    ])
    icon = StringField("icon", validators=[
        DataRequired(message="工具提供商icon不能为空"),
        URL(message="工具提供者的图标必须是URL")
    ])
    openapi_schema = JSONField("openapi_schema", validators=[
        DataRequired(message="openapi_schema不能为空")
    ])
    headers = ListField("headers", default=[])

    @classmethod
    def validate_headers(cls, form, field):
        """校验headers请求的数据是否正确，涵盖列表校验，列表元素校验"""
        for header in field.data:
            if not isinstance(header, dict):
                raise ValidationError("headers里的每一个元素都必须是字典")
            if set(header.keys()) != {"key", "value"}:
                raise ValidationError("headers里的每一个元素都必须包含key/value两个属性，不允许有其他属性")


class GetApiToolResp(Schema):
    """获取tool工具信息"""
    id = fields.UUID()
    name = fields.String()
    description = fields.String()
    inputs = fields.List(fields.Dict(), load_default=list, dump_default=list)
    provider = fields.Dict()

    @pre_dump
    def process_data(self, data: ApiTool, **kwargs):
        provider = data.provider
        return {
            "id": data.id,
            "name": data.name,
            "description": data.description,
            "inputs": [{k: v for k, v in param.items() if k != "in"} for param in data.parameters],
            "provider": {
                "id": provider.id,
                "name": provider.name,
                "description": provider.description,
                "icon": provider.icon,
                "headers": provider.headers,
            }
        }


class GetApiToolProviderResp(Schema):
    """获取API工具提供者响应信息"""
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    openapi_schema = fields.String()
    headers = fields.List(fields.Dict, load_default=list, dump_default=list)
    created_at = fields.Integer(load_default=0, dump_default=0)

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "openapi_schema": data.openapi_schema,
            "headers": data.headers,
            "created_at": int(data.created_at.timestamp())
        }


class GetApiToolProvidersWithPageResp(Schema):
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    openapi_schema = fields.String()
    headers = fields.List(fields.Dict, load_default=list, dump_default=list)
    created_at = fields.Integer(load_default=0, dump_default=0)
    tools = fields.List(fields.Dict, load_default=list, dump_default=list)

    @pre_dump
    def process_data(self, data: ApiToolProvider, **kwargs):
        tools = data.tools
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "headers": data.headers,
            "created_at": int(data.created_at.timestamp()),
            "tools": [{
                "id": tool.id,
                "description": tool.description,
                "name": tool.name,
                "inputs": [{k: v for k, v in parameter.items() if k != "in"} for parameter in tool.parameters]

            } for tool in tools],
        }
