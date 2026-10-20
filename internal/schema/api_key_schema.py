"""
@Time    : 2026-07-22 16:21
@Author  : JiaChengJie
@File    : api_key_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.simple import BooleanField, StringField
from wtforms.validators import DataRequired, Optional, Length

from internal.lib.helper import datetime_to_timestamp
from internal.model import ApiKey


class CreateAPIKeyReq(FlaskForm):
    """创建API秘钥请求"""
    is_active = BooleanField('is_active')
    remark = StringField('remark', validators=[
        Optional(),
        Length(max=100, message="接口备注信息,长度最大不能超过100")
    ])


class UpdateAPIKeyReq(FlaskForm):
    """修改API秘钥请求"""
    is_active = BooleanField('is_active')
    remark = StringField('remark', validators=[
        Optional(),
        Length(max=100, message="接口备注信息,长度最大不能超过100")
    ])


class UpdateApiKeyIsActiveReq(FlaskForm):
    is_active = BooleanField('is_active', validators=[
        DataRequired("请选择秘钥是否激活")])


class GetApiKeysWithPageResp(Schema):
    id = fields.UUID(dump_default="")
    api_key = fields.String(dump_default="")
    is_active = fields.Boolean(dump_default=False)
    remark = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: ApiKey, **kwargs):
        return {
            "id": data.id,
            "api_key": data.api_key,
            "is_active": data.is_active,
            "remark": data.remark,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at)
        }
