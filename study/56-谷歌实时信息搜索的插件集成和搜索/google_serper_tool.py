"""
@Time    : 2026-03-23 16:11
@AUthor  : jiachengjie
@File    : google_serper_tool.py
"""
import os

import dotenv
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.utils.pydantic import BaseModel, Field

dotenv.load_dotenv()


# 定义模型参数

class GoogleSerperModel(BaseModel):
    query: str = Field(description="执行谷歌搜索查询")


serper_api_wrapper = GoogleSerperAPIWrapper(
    serper_api_key=os.environ.get("SERPER_API_KEY"),  # 关键：从环境变量读取 Key
    gl="cn",  # 搜索地区：中国
    hl="zh-CN",  # 搜索语言：中文
    num=5,  # 返回结果数量
)

# 实例化工具
search_tool = GoogleSerperRun(
    name="google_search",
    description="用于查询实时/最新信息，比如黄金价格、大盘指数、天气等",
    args_schema=GoogleSerperModel,
    api_wrapper=serper_api_wrapper
)

print(search_tool.invoke("今天黄金大盘价格是多少"))
