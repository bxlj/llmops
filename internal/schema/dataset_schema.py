"""
@Time    : 2026-04-20 15:44
@Author  : jiachengjie
@File    : dataset_schema.py
"""
from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.numeric import IntegerField, FloatField
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, Optional, Length, AnyOf, NumberRange

from internal.entity.dataset_entity import RetrievalStrategy
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset
from pkg.paginator import PaginatorReq


class ValidateCreateDatasetReq(FlaskForm):
    name = StringField('Name', validators=[DataRequired(message="Name is required")])
    icon = StringField('Icon', validators=[DataRequired(message="Icon is required")])
    description = StringField('Description', validators=[DataRequired(message="Description is required")])


class GetDatasetResp(Schema):
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    hit_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "hit_count": data.hit_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "created_at": int(data.created_at.timestamp()),
            "updated_at": int(data.updated_at.timestamp()),
        }


class GetDatasetWithPageRep(PaginatorReq):
    search_word = StringField('search_word', validators=[
        Optional()
    ])


class GetDatasetsWithPageResp(Schema):
    """获取知识库分页列表响应数据"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    document_count = fields.Integer(dump_default=0)
    related_app_count = fields.Integer(dump_default=0)
    character_count = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "document_count": data.document_count,
            "related_app_count": data.related_app_count,
            "character_count": data.character_count,
            "updated_at": int(data.updated_at.timestamp()),
            "created_at": int(data.created_at.timestamp()),
        }


class UpdateDatasetReq(FlaskForm):
    name = StringField('name', validators=[DataRequired(message="name is required")])
    icon = StringField('icon', validators=[DataRequired(message="icon is required")])
    description = StringField('description', validators=[DataRequired(message="description is required")])


class HitReq(FlaskForm):
    query = StringField('query', validators=[
        DataRequired(message="召回测试的查询语句,不能为空"),
        Length(min=1, max=200, message="召回测试的查询语句,长度最小为1个字符，最大不超过200个字符"),
    ])
    retrieval_strategy = StringField('retrieval_strategy', validators=[
        DataRequired(message="检索策略不能为空"),
        AnyOf([item.value for item in RetrievalStrategy], message="检索策略格式错误")
    ])
    k = IntegerField('k', validators=[
        DataRequired(message="最大召回数量不能为空"),
        NumberRange(min=1, max=10, message="最大召回数量范围在1-10")
    ])
    score = FloatField('score', validators=[
        NumberRange(min=0, max=0.99, message="最小匹配度范围在0-0.99")
    ])


class GetDatasetQueriesResp(Schema):
    id = fields.UUID(dump_default="")
    dataset_id = fields.UUID(dump_default="")
    query = fields.String(dump_default="")
    source = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Dataset, **kwargs):
        return {
            "id": data.id,
            "dataset_id": data.dataset_id,
            "query": data.query,
            "source": data.source,
            "created_at": datetime_to_timestamp(data.created_at),
        }
