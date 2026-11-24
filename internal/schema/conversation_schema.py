"""
@Time    : 2026-11-23 16:31
@Author  : JiaChengJie
@File    : conversation_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, pre_dump, fields
from wtforms import IntegerField, StringField, BooleanField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from internal.lib.helper import datetime_to_timestamp
from internal.model.conversation import Message
from pkg.paginator import PaginatorReq


class GetConversationWithPageReq(PaginatorReq):
    """获取指定会话列表请求体"""
    created_at = IntegerField("created_at", default=0, validators=[
        Optional(),
        NumberRange(min=0, message="created_at游标最小值为0")
    ])


class GetConversationWithPageResp(Schema):
    """获取指定会话列表的返回体"""
    id = fields.String(dump_default="")
    conversation_id = fields.String(dump_default="")
    query = fields.String(dump_default="")
    answer = fields.String(dump_default="")
    total_token_count = fields.Integer(dump_default=0)
    latency = fields.Float(dump_default=0)
    agent_thoughts = fields.List(fields.Dict, dump_default=[])
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Message, **kwargs):
        message_agent_thoughts = data.agent_thoughts
        return {
            "id": data.id,
            "conversation_id": data.conversation_id,
            "query": data.query,
            "answer": data.answer,
            "total_token_count": data.total_token_count,
            "latency": data.latency,
            "created_at": datetime_to_timestamp(data.created_at),
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
            } for agent_thought in message_agent_thoughts],

        }


class UpdateConversationNameReq(FlaskForm):
    """修改会话名称请求体"""
    name = StringField(validators=[
        DataRequired(message="会话名称不能为空"),
        Length(max=100, message="会话名称最长不能超过100个字符")
    ])


class UpdateConversationIsPinnedReq(FlaskForm):
    """置顶或取消置顶某个会话请求结构体"""
    is_pinned = BooleanField("is_pinned", default=False)
