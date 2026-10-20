"""
@Time    : 2026-04-16 11:17
@Author  : jiachengjie
@File    : cos_service.py
"""
import datetime
import hashlib
import os
import uuid
from dataclasses import dataclass

from injector import inject
from qcloud_cos import CosS3Client, CosConfig
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception.exception import FailException
from internal.model.upload_file import UploadFile
from .upload_file_service import UploadFileService
from ..model import Account


@inject
@dataclass
class CosService:
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, only_image: bool, account: Account) -> UploadFile:
        """文件上传接口"""

        # 获取文件名称
        filename = file.filename
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        if extension.lower() not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"该.{extension}扩展名文件不支持上传，请上传符合要求的文件")
        elif only_image and extension.lower() not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"该.{extension}扩展名文件不支持上传，请上传符合要求的照片")

        # 2.获取客户端+存储桶名字
        client = self.get_cos_client()
        bucket = self._get_bucket()

        # 3.生成一个随机的名字
        random_filename = str(uuid.uuid4()) + "." + extension
        now = datetime.datetime.now()
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"
        # 4.流式读取上传的数据并将其上传到cos中
        file_content = file.stream.read()
        try:
            client.put_object(Bucket=bucket,
                              Key=upload_filename,
                              Body=file_content
                              )
        except Exception as e:
            raise FailException("上传文件失败，请稍后重试")

        # 保存文件信息到数据
        return self.upload_file_service.upload_file(
            account_id=account.id,
            name=filename,
            extension=extension,
            size=len(file_content),
            mime_type=file.mimetype,
            key=upload_filename,
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    def download_file(self, key: str, target_file_path: str):
        client = self.get_cos_client()

        bucket = self._get_bucket()

        client.download_file(Bucket=bucket, Key=key, DestFilePath=target_file_path)

    @classmethod
    def get_file_url(cls, key: str) -> str:
        """获取文件完整路径"""
        cos_domain = os.getenv("COS_DOMAIN")
        if not cos_domain:
            scheme = os.getenv("COS_SCHEME")
            bucket = os.getenv("COS_BUCKET")
            region = os.getenv("COS_REGION")
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

        return f"{cos_domain}/{key}"

    @classmethod
    def get_cos_client(cls) -> CosS3Client:
        """获取CosS3Client客户端"""
        config = CosConfig(
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Region=os.getenv("COS_REGION"),
            Scheme=os.getenv("COS_SCHEME", "https"),
            Token=None,
        )
        return CosS3Client(config)

    @classmethod
    def _get_bucket(cls) -> str:
        return os.getenv("COS_BUCKET")
