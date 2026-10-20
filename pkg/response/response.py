"""
@Time    : 2026/3/3 11:42
@AUthor  : jiachengjie
@File    : response.py
"""
import dataclasses
from dataclasses import field
from typing import Any, Union, Generator

from flask import Response as FlaskResponse, stream_with_context
from flask import jsonify

from pkg.response.http_code import HttpCode


@dataclasses.dataclass
class Response:
    """基础HTTP接口响应格式"""
    code: HttpCode = HttpCode.SUCCESS
    message: str = ''
    data: Any = field(default_factory=dict)


def json(data: Response = None):
    """基础响应接口"""
    response = jsonify(data)
    response.headers['Access-Control-Allow-Origin'] = 'http://localhost:5173'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    return response, 200


def success_json(data: Response = None):
    """成功数据响应"""
    return json(Response(code=HttpCode.SUCCESS, message="", data=data))


def fail_json(data: Response = None):
    """失败数据响应"""
    return json(Response(code=HttpCode.FAIL, message="", data=data))


def validate_error_json(errors: dict = None):
    """数据验证错误响应"""
    first_key = next(iter(errors))
    if first_key is not None:
        msg = errors.get(first_key)[0]
    else:
        msg = ""
    return json(Response(code=HttpCode.VALIDATE_ERROR, message=msg, data=errors))


def message(code: HttpCode = None, msg: str = ""):
    """基础的消息响应，固定返回消息提示，数据固定为空字典"""
    return json(Response(code=code, message=msg, data={}))


def success_message(msg: str = ""):
    """成功的消息响应"""
    return message(code=HttpCode.SUCCESS, msg=msg)


def fail_message(msg: str = ""):
    """失败的消息响应"""
    return message(code=HttpCode.FAIL, msg=msg)


def not_found_message(msg: str = ""):
    """未找到消息响应"""
    return message(code=HttpCode.NOT_FOUND, msg=msg)


def unauthorized_message(msg: str = ""):
    """未授权消息响应"""
    return message(code=HttpCode.UNAUTHORIZED, msg=msg)


def forbidden_message(msg: str = ""):
    """无权限消息响应"""
    return message(code=HttpCode.FORBIDDEN, msg=msg)


def compact_generate_response(response: Union[Response, Generator]) -> FlaskResponse:
    """统一合并处理块输出以及流式事件输出"""
    # 1.检测下是否为块输出(Response)
    if isinstance(response, Response):
        return json(response)
    else:
        # 2.response格式为生成器，代表本次响应需要执行流式事件输出
        def generate() -> Generator:
            yield from response

        # 3.返回携带上下文的流式事件输出
        return FlaskResponse(
            stream_with_context(generate()),
            status=200,
            mimetype='text/event-stream'
        )
