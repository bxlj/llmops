"""
@Time    : 2026-06-25 11:08
@Author  : jiachengjie
@File    : jwt_service.py
"""
import os
from dataclasses import dataclass
from typing import Any, Optional, Dict

import jwt
from injector import inject

from internal.exception import UnauthorizedException


@inject
@dataclass
class JwtService:
    """jwt服务"""

    @classmethod
    def generate_token(cls, data: dict[str, Any]) -> str:
        """
        生成 JWT Token
        :param data: 载荷数据，如 {"user_id": 1, "username": "test"}
        :param expires_delta: 过期时间
        :return: token字符串
        """
        jwt_secret_key = os.getenv("JWT_SECRET_KEY")
        alembic = os.getenv("ALGORITHM")

        return jwt.encode(data, jwt_secret_key, alembic)

    @classmethod
    def verify_token(cls, token: str) -> Optional[Dict]:
        """
        校验 Token 并返回载荷
        :param token: jwt token
        :return: 载荷dict，校验失败返回None
        """
        jwt_secret_key = os.getenv("JWT_SECRET_KEY")
        alembic = os.getenv("ALGORITHM")

        try:
            payload = jwt.decode(token, jwt_secret_key, algorithms=[alembic])
            return payload
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("授权认证凭证已过期请重新登陆")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("解析token出错，请重新登陆")
        except Exception as e:
            raise UnauthorizedException(str(e))

    @classmethod
    def parse_token(cls, token: str) -> dict[str, Any]:
        """解析传入的token信息得到载荷"""
        secret_key = os.getenv("JWT_SECRET_KEY")
        alembic = os.getenv("ALGORITHM")
        try:
            return jwt.decode(token, secret_key, algorithms=[alembic])
        except jwt.ExpiredSignatureError:
            raise UnauthorizedException("授权认证凭证已过期请重新登陆")
        except jwt.InvalidTokenError:
            raise UnauthorizedException("解析token出错，请重新登陆")
        except Exception as e:
            raise UnauthorizedException(str(e))
