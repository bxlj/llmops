"""
@Time    : 2026/3/3 10:30
@AUthor  : jiachengjie
@File    : app_schema.py
"""
from uuid import UUID

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.numeric import IntegerField
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Length, URL, ValidationError, Optional, NumberRange

from internal.entity.app_entity import AppStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import App, Message
from pkg.paginator import PaginatorReq


class CompletionReq(FlaskForm):
    """基础聊天接口请求验证"""
    # 必填
    query = StringField('query', validators=[
        DataRequired(message="用户提问必填"),
        Length(max=2000, message="输入字段过长")
    ])


class CreateAppReq(FlaskForm):
    """在个人空间下新增应用"""
    name = StringField('name', validators=[
        DataRequired(message="Agent应用的名称必填"),
        Length(max=40, message="长度不超过40个字符")
    ])
    icon = StringField('icon', validators=[
        DataRequired(message="Agent应用的图标URL地址必填"),
        URL(message="应用图标必须是图片URL链接")
    ])
    description = StringField('description', validators=[
        Length(max=800, message="描述信息，长度不超过800个字符")
    ])


class GetAppResp(Schema):
    id = fields.UUID(dump_default="")
    debug_conversation_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    status = fields.String(dump_default="")
    create_at = fields.Integer(dump_default=0)
    update_at = fields.Integer(dump_default=0)
    draft_updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, app: App, **kwargs):
        return {
            "id": app.id,
            "debug_conversation_id": app.debug_conversation_id if app.debug_conversation_id else "",
            "name": app.name,
            "icon": app.icon,
            "description": app.description,
            "status": app.status,
            "draft_updated_at": datetime_to_timestamp(app.draft_app_config.updated_at),
            "create_at": datetime_to_timestamp(app.draft_app_config.updated_at),
            "update_at": datetime_to_timestamp(app.draft_app_config.updated_at),
        }


class GetPublishHistoriesWithPage(PaginatorReq):
    """获取应用发布历史配置分页列表请求"""
    ...


class GetPublishHistoriesWithPageResp(Schema):
    id = fields.UUID(dump_default="")
    version = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        return {
            "id": data.id,
            "version": data.version,
            "created_at": datetime_to_timestamp(data.created_at),
        }


class FallbackHistoryToDraftReq(FlaskForm):
    """回退指定的历史配置到草稿"""
    """回退历史版本到草稿请求结构体"""
    app_config_version_id = StringField("app_config_version_id", validators=[
        DataRequired("回退配置版本id不能为空")
    ])

    def validate_app_config_version_id(self, field: StringField) -> None:
        """校验回退配置版本id"""
        try:
            UUID(field.data)
        except Exception as e:
            raise ValidationError("回退配置版本id必须为UUID")


class UpdateDebugConversationSummary(FlaskForm):
    summary = StringField('summary', validators=[
        DataRequired("更新的长记忆内容不能为空")
    ])


class DebugChatReq(FlaskForm):
    query = StringField('query', validators=[
        DataRequired("用户发起的提问信息不能为空")
    ])


class GetDebugConversationMessagesWithPageReq(PaginatorReq):
    created_at = IntegerField('created_at', validators=[
        Optional(),
        NumberRange(min=0, message="created_at游标最小值为0")
    ])


class GetDebugConversationMessagesWithPageResp(Schema):
    """获取调试会话消息列表分页响应结构体"""
    id = fields.UUID(dump_default="")
    conversation_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    answer = fields.String(dump_default="")
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs):
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "answer": data.answer,
            "total_token_count": data.total_token_count,
            "latency": data.latency,
            "agent_thoughts": [{
                "id": agent_thought.id,
                "position": agent_thought.position,
                "event": agent_thought.event,
                "thought": agent_thought.thought,
                "observation": agent_thought.observation,
                "tool": agent_thought.tool,
                "tool_input": agent_thought.tool_input,
                "latency": agent_thought.latency,
                "created_at": datetime_to_timestamp(agent_thought.created_at),
            } for agent_thought in data.agent_thoughts],
            "created_at": datetime_to_timestamp(data.created_at),
        }


class GetAppWithPageReq(PaginatorReq):
    search_word = StringField('search_word', validators=[
        Optional()
    ])


class GetAppWithPageResp(Schema):
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    preset_prompt = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    status = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    create_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config if data.status == AppStatus.PUBLISHED else data.draft_app_config
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "preset_prompt": app_config.preset_prompt,
            "model_config": {
                "provider": app_config.model_config.get("provider", ""),
                "model": app_config.model_config.get("model", ""),
            },
            "status": data.status,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "create_at": datetime_to_timestamp(data.created_at),
        }


class UpdateAppReq(FlaskForm):
    """更新Agent应用请求结构体"""
    name = StringField("name", validators=[
        DataRequired("应用名称不能为空"),
        Length(max=40, message="应用名称长度最大不能超过40个字符"),
    ])
    icon = StringField("icon", validators=[
        DataRequired("应用图标不能为空"),
        URL(message="应用图标必须是图片URL链接"),
    ])
    description = StringField("description", validators=[
        Length(max=800, message="应用描述的长度不能超过800个字符")
    ])
