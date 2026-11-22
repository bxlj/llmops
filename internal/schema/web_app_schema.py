"""
@Time    : 2026-11-22 15:59
@Author  : JiaChengJie
@File    : web_app_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Optional, UUID

from internal.model.app import App


class GetAppByTokenResp(Schema):
    """根据token获取app返回体"""
    id = fields.UUID(dump_default="")
    icon = fields.String(dump_default="")
    name = fields.String(dump_default="")
    description = fields.String(dump_default="")
    app_config = fields.Dict(dump_default={})

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config
        return {
            "id": data.id,
            "icon": data.icon,
            "name": data.name,
            "description": data.description,
            "app_config": {
                "opening_statement": app_config.opening_statement,
                "opening-questions": app_config.opening_questions,
                "suggested_after_answer": app_config.suggested_after_answer,
            },
        }


class WebAppChatReq(FlaskForm):
    """webapp请求对话结构体"""
    conversation_id = StringField("conversation_id", default="", validators=[
        Optional(),
        UUID(message="格式必须为UUID")
    ])
    query = StringField("query", default="", validators=[
        DataRequired(message="用户提问的问题不能为空")
    ])
