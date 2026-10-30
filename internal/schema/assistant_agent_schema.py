"""
@Time    : 2026-10-29 14:56
@Author  : JiaChengJie
@File    : assistant_agent_schema.py
"""

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange

from internal.model import Message
from lib.helper import datetime_to_timestamp
from pkg.paginator import PaginatorReq


class AssistantAgentChatReq(FlaskForm):
    """与辅助 Agent 进行 Chat 对话请求参数"""
    query = StringField("query", validators=[DataRequired()])


class GetAssistantAgentWithPageReq(PaginatorReq):
    """获取当前登录账号的辅助Agent对话历史列表请求参数"""
    created_at = IntegerField("created_at", default=0, validators=[
        Optional(),
        NumberRange(min=0, message="created_at游标最小值为0")
    ])


class GetAssistantAgentWithPageResp(Schema):
    """获取当前登录账号的辅助Agent对话历史列表返回参数"""
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
            } for agent_thought in data.agent_thoughts],
        }
