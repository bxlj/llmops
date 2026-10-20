"""
@Time    : 2026-03-23 17:03
@AUthor  : jiachengjie
@File    : 1.GPT模型绑定函数.py
"""
import json
import os
from typing import Any, Type

import dotenv
import requests
from langchain_community.tools import GoogleSerperRun
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.tools import BaseTool
from langchain_core.utils.pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()


# 定义天气查询工具
class weatherData(BaseModel):
    city: str = Field(description="需要查询天气预报的目标城市，例如：广州")


class weatherTool(BaseTool):
    """根据传入的城市名称查询天气"""
    name: str = "weather_tool"
    description: str = "当你想询问天气或与天气相关的问题时的工具。"
    args_schema: Type[BaseModel] = weatherData

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """根据传入的城市名称运行调用api获取城市对应的天气预报信息"""
        try:
            # 1.获取高德API秘钥
            gaode_key = os.environ['GAODE_API_KEY']
            if not gaode_key:
                return f"高德API KEY没有配置"

            # 2.从参数中获取city城市名字
            city = kwargs.get("city", "")
            api_domain = f"https://restapi.amap.com/v3"
            session = requests.session()

            # 3. 发起行政区域编码查询，根据city获取ad_code
            city_response = session.request(
                method="GET",
                url=f"{api_domain}/config/district?key={gaode_key}&keywords={city}&subdistrict=0",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

            city_response.raise_for_status()
            city_data = city_response.json()
            if city_data.get("info") == "OK":
                ad_code = city_data["districts"][0]["adcode"]

            # 4.根据得到的ad_code调用天气预报API接口，获取天气信息
            weather_response = session.request(
                method="GET",
                url=f"{api_domain}/weather/weatherInfo?key={gaode_key}&city={ad_code}&extensions=all",
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

            weather_response.raise_for_status()
            weather_data = weather_response.json()
            if weather_data.get("info") == "OK":
                # 5.返回最后的结果字符串
                return json.dumps(weather_data)

            return f"获取{city}天气预报信息失败"

        except Exception as e:
            return f"获取{kwargs.get('city', '')}天气预报信息失败"


# 定义谷歌搜索
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

# 1.定义工具列表
gaode_weather = weatherTool()
google_serper = search_tool

tool_dict = {
    gaode_weather.name: gaode_weather,
    google_serper.name: google_serper,
}

tools = list(tool_dict.values())

# 2.创建Prompt
prompt = ChatPromptTemplate.from_messages([
    ("system",
     "你是由OpenAI开发的聊天机器人，可以帮助用户回答问题，必要时刻请调用工具帮助用户解答，如果问题需要多个工具回答，请一次性调用所有工具，不要分步调用"),
    ("human", "{query}"),

])

# 3.创建大语言模型并绑定工具
llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=os.environ.get("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=os.getenv("OPENAI_TEMPERATURE"),

)

llm_with_tool = llm.bind_tools(tools=tools)

# 4. 创建链应用
chain = {"query": RunnablePassthrough()} | prompt | llm_with_tool

# 5.调用链应用，并获取输出响应
query = "上海现在天气怎样，并且请用谷歌搜索工具查询一下现在的金价？"
resp = chain.invoke(query)
tool_calls = resp.tool_calls

# 6.判断是工具调用还是正常输出结果
if len(tool_calls) <= 0:
    print("生成内容: ", resp.content)
else:
    # 7.将历史的系统消息、人类消息、AI消息组合
    messages = prompt.invoke(query).to_messages()
    messages.append(resp)

    # 8.循环遍历所有工具调用信息
    for tool_call in tool_calls:
        tool = tool_dict.get(tool_call.get("name"))  # 获取需要执行的工具
        print("正在执行工具: ", tool.name)
        content = tool.invoke(tool_call.get("args"))  # 工具执行的内容/结果
        print("工具返回结果: ", content)
        tool_call_id = tool_call.get("id")
        messages.append(ToolMessage(
            content=content,
            tool_call_id=tool_call_id,
        ))
    print("输出内容: ", llm.invoke(messages).content)
