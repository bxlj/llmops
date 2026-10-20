"""
@Time    : 2026-04-02 0:15
@AUthor  : jiachengjie
@File    : dalle3.py
"""
import os
from typing import Type

import dotenv
from langchain_core.tools import BaseTool
from langchain_core.utils.pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

from internal.lib.helper import add_attribute

dotenv.load_dotenv()


class Dalle3ArgsSchema(BaseModel):
    query: str = Field(description="输入应该是生成图像的文本提示(prompt)")


class MoonshotImageGenerationTool(BaseTool):
    name: str = 'moonshot_image'
    description: str = "使用月之暗面模型生成图像"
    args_schema: Type[BaseModel] = Dalle3ArgsSchema

    def _run(self, query: str):
        client = ChatOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),  # 从外部传入
            base_url=os.getenv("OPENAI_API_BASE"),
        )

        response = client.images.generate(
            model=os.getenv("OPENAI_MODEL_MULTIMODAL_NAME"),
            prompt=query,
            n=1,
            size="1024x1024"
        )
        return response.data[0].url


@add_attribute("args_schema", Dalle3ArgsSchema)
def dalle3(**kwargs) -> BaseTool:
    """返回dalle3绘图的LangChain工具"""
    return MoonshotImageGenerationTool(
        args_schema=Dalle3ArgsSchema,
    )
