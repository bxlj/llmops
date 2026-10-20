"""
@Time    : 2026-07-14 16:34
@Author  : JiaChengJie
@File    : ai_schema.py
"""
from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Length, UUID


class OptimizePromptReq(FlaskForm):
    prompt = StringField('Prompt', validators=[
        DataRequired("提示词模板不能为空"),
        Length(max=2000, message="提示词模板长度最多2000")
    ])


class GenerateSuggestedQuestionsReq(FlaskForm):
    """根据传递的消息id获取建议问题列表"""
    message_id = StringField('message_id', validators=[
        DataRequired("消息ID不能为空"),
        UUID(message="消息id格式必须为uuid")
    ])
