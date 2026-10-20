"""
@Time    : 2026-04-15 12:23
@Author  : jiachengjie
@File    : upload_file_handle.py
"""
from dataclasses import dataclass

from flask_login import current_user, login_required
from injector import inject

from internal.schema.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageFileReq
from internal.service.cos_service import CosService
from pkg.response import validate_error_json, success_json


@inject
@dataclass
class UploadFileHandler:
    cos_service: CosService

    @login_required
    def upload_file(self):
        """上传文件/文档"""
        # 1.构建请求并校验
        req = UploadFileReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 上传文件,并保存记录
        upload_file = self.cos_service.upload_file(req.file.data, False, current_user)

        # 构建返回值
        resp = UploadFileResp()

        return success_json(resp.dump(upload_file))

    @login_required
    def upload_image(self):
        """上传图片"""
        req = UploadImageFileReq()
        if not req.validate():
            raise validate_error_json(req.errors)

        upload_image_file = self.cos_service.upload_file(req.file.data, True, current_user)

        # 获取图片路径
        image_url = self.cos_service.get_file_url(upload_image_file.key)

        return success_json({"image_url": image_url})
