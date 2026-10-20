"""
@Time    : 2026-04-13 17:18
@Author  : jiachengjie
@File    : tool_entity.py
"""
from pydantic import BaseModel, Field


class ToolEntity(BaseModel):
    """API工具实体类，记录langchain里面所需要的参数描述"""
    id: str = Field(default="", description="API工具提供者主键")
    name: str = Field(default="", description="API工具名称")
    url: str = Field(default="", description="API工具访问路径")
    method: str = Field(default="", description="API工具方法类型")
    description: str = Field(default="", description="API工具描述")
    parameters: list[dict] = Field(default_factory=list, description="参数列表")
    headers: list[dict] = Field(default_factory=list, description="API工具的请求头信息")
