"""
@Time    : 2026-05-25 11:01
@Author  : jiachengjie
@File    : user_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.numeric import IntegerField
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Length, Regexp, NumberRange, Optional

from internal.model.user import User


class CreateUserReq(FlaskForm):
    """创建用户校验"""
    name = StringField('name', validators=[
        DataRequired(message="姓名不能为空"),
        Length(max=255, message="姓名长度不能超过255")
    ])
    nike_name = StringField('nike_name', validators=[
        Length(max=255, message="昵称长度不能超过255")
    ])
    sex = StringField("sex", validators=[
        Length(max=10, message="性别长度不超过10")
    ])
    age = IntegerField("age", validators=[
        NumberRange(min=0, max=130, message="年龄最小是0岁，最大不能超过130岁"),
    ])
    id_card = StringField('id_card', validators=[
        DataRequired(message="身份证号码不能为空"),
        Length(min=15, max=18, message="身份证号码长度为15或18位"),
        Regexp(r'^\d{15}$|^\d{17}[\dXx]$', message="身份证号格式不正确")
    ])
    address = StringField('address')


class UpdateUserReq(FlaskForm):
    """修改用户校验"""
    name = StringField('name', validators=[
        Optional(),
        Length(max=255, message="姓名长度不能超过255")
    ])
    nike_name = StringField('nike_name', validators=[
        Optional(),
        Length(max=255, message="昵称长度不能超过255")
    ])
    sex = StringField("sex", validators=[
        Optional(),
        Length(max=10, message="性别长度不超过10")
    ])
    age = IntegerField("age", validators=[
        Optional(),
        NumberRange(min=0, max=130, message="年龄最小是0岁，最大不能超过130岁"),
    ])
    id_card = StringField('id_card', validators=[
        Optional(),
        Length(min=15, max=18, message="身份证号码长度为15或18位"),
        Regexp(r'^\d{15}$|^\d{17}[\dXx]$', message="身份证号格式不正确")
    ])
    address = StringField('address', validators=[
        Optional(),
    ])


class GetUserWithPageResp(Schema):
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    nike_name = fields.String(dump_default="")
    sex = fields.String(dump_default="")
    age = fields.Integer(dump_default=0)
    id_card = fields.String(dump_default="")
    address = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: User, **kwargs):
        return {
            
        }
