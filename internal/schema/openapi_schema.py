"""
@Time    : 2026-07-24 17:25
@Author  : JiaChengJie
@File    : openapi_schema.py
"""
import uuid

from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField, BooleanField
from wtforms.validators import DataRequired, UUID, Optional, ValidationError


class OpenAPIChatReq(FlaskForm):
    app_id = StringField('app_id', validators=[
        DataRequired("会话应用id,不能为空"),
        UUID("应用id格式必须为UUID")
    ])
    end_user_id = StringField('end_user_id', validators=[
        Optional(),
        UUID("终端用户id格式必须为UUID")
    ])

    conversation_id = StringField('conversation_id', default="")

    query = StringField('query', validators=[
        DataRequired("用户的提问为必填"),
    ])

    stream = BooleanField('stream', default=True)

    def validate_conversation_id(self, field: StringField) -> None:
        """用于校验conversation_id字段"""
        # 1. conversation_id 格式是否准确
        if field.data:
            try:
                uuid.UUID(field.data)
            except Exception as e:
                raise ValidationError("会话id格式必须为UUID")

            # 2. 判断end_user_id终端用户不能为空
            if not self.end_user_id.data:
                raise ValidationError("传递会话id则终端用户id不能为空")
