"""
@Time    : 2026-03-23 11:33
@AUthor  : jiachengjie
@File    : 3-BaseTool子类创建工具.py
"""
from typing import Any, Type

from langchain_core.tools import BaseTool
from langchain_core.utils.pydantic import BaseModel, Field


# d定义参数模型
class Base(BaseModel):
    a: int = Field(description="这是第一个参数")
    b: int = Field(description="这是第二个参数")


class MultiplyTool(BaseTool):
    """这是一个乘法计算器"""
    name: str = "multiply_tool"
    description: str = "传递两个数字相乘后返回"
    args_schema: Type[BaseModel] = Base

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """将传入的a和b相乘后返回"""
        return kwargs["a"] * kwargs["b"]


calculator = MultiplyTool()

# 打印下该工具的相关信息
print("name", calculator.name)
print("description", calculator.description)
print("args_schema", calculator.args_schema)

print(calculator.invoke({"a": 2, "b": 8}))
