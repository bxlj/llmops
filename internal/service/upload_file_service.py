"""
@Time    : 2026-04-16 12:34
@Author  : jiachengjie
@File    : upload_file_service.py
"""
from dataclasses import dataclass

from injector import inject

from internal.model import UploadFile
from internal.service import BaseService
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class UploadFileService(BaseService):
    """文件上传服务类"""
    db: SQLAlchemy

    def upload_file(self, **kwargs) -> UploadFile:
        return self.create(UploadFile, **kwargs)
