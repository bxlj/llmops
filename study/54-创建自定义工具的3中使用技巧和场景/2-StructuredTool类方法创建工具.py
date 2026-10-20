"""
@Time    : 2026-03-20 16:16
@AUthor  : jiachengjie
@File    : 2-StructuredTool类方法创建工具.py
"""
from langchain_core.tools import StructuredTool
#
from langchain_core.utils.pydantic import BaseModel, Field


# 定义参数模型
class MultiplyInput(BaseModel):
    a: int = Field(description="这是第一个数字")
    b: int = Field(description="这是第二个数字")


def multiply(a: int, b: int) -> int:
    """将传递的两个数字相乘"""
    return a * b


async def multiply_async(a: int, b: int) -> int:
    """将传递的两个数字相乘"""
    return a * b


calculator = StructuredTool.from_function(
    func=multiply,  # 同步函数：工具的核心功能
    coroutine=multiply_async,  # 异步函数：工具的异步版本
    name='multiply_tool',  # 工具唯一名称：Agent调用时用这个名字
    description="两个数字相乘",  # 工具描述：Agent判断是否调用的依据
    return_direct=True,  # 直接返回结果：跳过Agent后续思考
    args_schema=MultiplyInput,  # 参数校验：强制a/b为float类型，校验必填项
)

# 打印下该工具的相关信息
print("名字", calculator.name)
print("描述", calculator.description)
print("直接返回", calculator.return_direct)
print("参数", calculator.args)

# 调用工具
print(calculator.invoke({"a": 2, "b": 3}))
