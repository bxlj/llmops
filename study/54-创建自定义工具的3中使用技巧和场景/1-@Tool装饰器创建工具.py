"""
@Time    : 2026-03-20 13:36
@AUthor  : jiachengjie
@File    : 1-@Tool装饰器创建工具.py
"""
from langchain_core.tools import tool
from langchain_core.utils.pydantic import BaseModel, Field


# 定义参数模型
class MultiplyInput(BaseModel):
    a: int = Field(description="第一个数字")
    b: int = Field(description="第二个数字")


# 装饰器定义工具
@tool("multiply_tool", return_direct=True, args_schema=MultiplyInput)
def multiply(a: int, b: int) -> int:
    """将传递的两个数字相乘"""
    return a * b


print("名称：", multiply.name)
print("描述：", multiply.description)
print("参数：", multiply.args)
print("直接返回：", multiply.return_direct)
