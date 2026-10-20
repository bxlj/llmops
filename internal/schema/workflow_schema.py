"""
@Time    : 2026-10-12 14:34
@Author  : JiaChengJie
@File    : workflow_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import Optional, AnyOf, DataRequired, Length, Regexp, URL

from internal.core.workflow.entities.workflow_entity import WORKFLOW_CONFIG_NAME_PATTERN
from internal.entity.workflow_entity import WorkflowStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import Workflow
from pkg.paginator import PaginatorReq


class CreateWorkflowReq(FlaskForm):
    """创建工作流请求数据"""
    name = StringField('name', validators=[
        DataRequired(message="工作流名称不能为空"),
        Length(max=50, message="工作流名称长度不能超过50")
    ])
    tool_call_name = StringField('tool_call_name', validators=[
        DataRequired(message="工作流工具调用名字不能为空"),
        Length(max=50, message="工作流工具调用名称长度不能超过50"),
        Regexp(WORKFLOW_CONFIG_NAME_PATTERN, message="英文名称仅支持字母、数字和下划线，且以字母/下划线为开头")
    ])
    icon = StringField("icon", validators=[
        DataRequired("工作流图标不能为空"),
        URL(message="工作流图标必须是图片URL地址"),
    ])
    description = StringField("description", validators=[
        DataRequired("工作流描述不能为空"),
        Length(max=1024, message="工作流描述不能超过1024个字符")
    ])


class GetWorkflowResp(Schema):
    """根据workflow_id获取工作流信息"""
    """获取账号下的工作流分页返回数据"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    tool_call_name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    is_debug_passed = fields.Boolean(dump_default=False)
    node_count = fields.Integer(dump_default=0)
    published_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Workflow, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "tool_call_name": data.tool_call_name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "is_debug_passed": data.is_debug_passed,
            "node_count": len(data.graph.get("nodes", [])),
            "published_at": datetime_to_timestamp(data.published_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }


class UpdateWorkflowReq(FlaskForm):
    """修改工作流请求数据"""
    name = StringField('name', validators=[
        DataRequired(message="工作流名称不能为空"),
        Length(max=50, message="工作流名称长度不能超过50")
    ])
    tool_call_name = StringField('tool_call_name', validators=[
        DataRequired(message="工作流工具调用名字不能为空"),
        Length(max=50, message="工作流工具调用名称长度不能超过50"),
        Regexp(WORKFLOW_CONFIG_NAME_PATTERN, message="英文名称仅支持字母、数字和下划线，且以字母/下划线为开头")
    ])
    icon = StringField("icon", validators=[
        DataRequired("工作流图标不能为空"),
        URL(message="工作流图标必须是图片URL地址"),
    ])
    description = StringField("description", validators=[
        DataRequired("工作流描述不能为空"),
        Length(max=1024, message="工作流描述不能超过1024个字符")
    ])


class GetDatasetWithPageReq(PaginatorReq):
    """获取账号下的工作流分页数据"""
    status = StringField('status', default="", validators=[
        Optional(),
        AnyOf(WorkflowStatus.__members__.values(), message="工作流状态错误")
    ])
    search_word = StringField('search_word', default="", validators=[Optional()])


class GetWorkflowsWithPageResp(Schema):
    """获取账号下的工作流分页返回数据"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    tool_call_name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    is_debug_passed = fields.Boolean(dump_default=False)
    node_count = fields.Integer(dump_default=0)
    published_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Workflow, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "tool_call_name": data.tool_call_name,
            "icon": data.icon,
            "description": data.description,
            "status": data.status,
            "is_debug_passed": data.is_debug_passed,
            "node_count": len(data.graph.get("nodes", [])),
            "published_at": datetime_to_timestamp(data.published_at),
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
