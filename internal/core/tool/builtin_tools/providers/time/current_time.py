"""
@Time    : 2026-04-01 22:58
@AUthor  : jiachengjie
@File    : current_time.py
"""
from datetime import datetime

from langchain_core.tools import tool


@tool('current_time')
def current_time() -> str:
    """
       获取当前系统日期和时间
       返回格式：YYYY-MM-DD HH:MM:SS ±时区
       无需传入参数
       """
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S %z')
