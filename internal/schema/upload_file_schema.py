"""
@Time    : 2026-04-15 12:26
@AUthor  : jiachengjie
@File    : upload_file_schema.py
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileSize, FileAllowed
from marshmallow import Schema, fields, pre_dump

from internal.entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION, ALLOWED_IMAGE_EXTENSION
from internal.model import UploadFile


class UploadFileReq(FlaskForm):
    """文件上传数据校验"""
    file = FileField("file", validators=[
        FileRequired("文件不能为空"),
        FileSize(max_size=15 * 1024 * 1024, message="文件最大不能超过15M"),
        FileAllowed(ALLOWED_DOCUMENT_EXTENSION, message=f"仅允许上传{'/'.join(ALLOWED_DOCUMENT_EXTENSION)}文件")

    ])


class UploadImageFileReq(FlaskForm):
    """文件上传数据校验"""
    file = FileField("file", validators=[
        FileRequired("文件不能为空"),
        FileSize(max_size=15 * 1024 * 1024, message="图片最大不能超过15M"),
        FileAllowed(ALLOWED_IMAGE_EXTENSION, message=f"仅允许上传{'/'.join(ALLOWED_IMAGE_EXTENSION)}图片")

    ])


class UploadFileResp(Schema):
    id = fields.UUID(dump_default="")
    account_id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    key = fields.String(dump_default="")
    size = fields.Integer(dump_default=0)
    extension = fields.String(dump_default="")
    mime_type = fields.String(dump_default="")
    created_at = fields.Integer(dump_default="")

    @pre_dump
    def process_data(self, data: UploadFile, **kwargs):
        return {
            "id": data.id,
            "account_id": data.account_id,
            "name": data.name,
            "key": data.key,
            "extension": data.extension,
            "size": data.size,
            "mime_type": data.mime_type,
            "created_at": int(data.created_at.timestamp()),
        }


class UploadImageReq(FlaskForm):
    """上传图片进行数据校验"""
    field = FileField("field", validators=[
        FileRequired("上传图片不能为空"),
        FileSize(max_size=15 * 1024 * 1024, message="上传图片最大不能超过15MB"),
        FileAllowed(ALLOWED_IMAGE_EXTENSION, message=f"仅允许上传{'/'.join(ALLOWED_IMAGE_EXTENSION)}文件")

    ])
