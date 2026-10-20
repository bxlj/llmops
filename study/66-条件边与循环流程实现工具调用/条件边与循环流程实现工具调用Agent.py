"""
@Time    : 2026-03-30 9:38
@AUthor  : jiachengjie
@File    : 条件边与循环流程实现工具调用Agent.py
"""
import json
import os
from typing import TypedDict, Annotated, Any, Literal

import dotenv
import requests
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langchain_core.utils.pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langgraph.graph import add_messages, StateGraph

dotenv.load_dotenv()


# ====================== 【接入高德天气工具】 ======================
class GaodeWeatherArgsSchema(BaseModel):
    city: str = Field(description="需要查询天气预报的城市，例如：广州")


class GaodeWeatherTool(BaseTool):
    name: str = "gaode_weather"
    description: str = "查询城市的实时天气，需要传入城市名称"
    args_schema: type[BaseModel] = GaodeWeatherArgsSchema

    def _run(self, city: str) -> str:
        try:
            gaode_api_key = os.getenv("GAODE_API_KEY")
            if not gaode_api_key:
                return "高德API密钥未配置"

            api_domain = "https://restapi.amap.com/v3"
            city_res = requests.get(
                f"{api_domain}/config/district?keywords={city}&key={gaode_api_key}"
            )
            city_data = city_res.json()

            if city_data.get("info") == "OK" and city_data["districts"]:
                ad_code = city_data["districts"][0]["adcode"]
                weather_res = requests.get(
                    f"{api_domain}/weather/weatherInfo?city={ad_code}&key={gaode_api_key}"
                )
                weather_data = weather_res.json()
                return json.dumps(weather_data, ensure_ascii=False)

            return f"未找到 {city} 的天气信息"
        except Exception as e:
            return f"查询天气失败：{str(e)}"


# ====================== 状态定义 ======================

class State(TypedDict):
    messages: Annotated[list, add_messages,]


# ====================== 工具列表：加入你的天气工具 ======================

toos = [GaodeWeatherTool()]

llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=os.getenv("OPENAI_TEMPERATURE"),
)

llm_with_tool = llm.bind_tools(tools=toos)


# ====================== 聊天机器人节点 ======================

def chatbot(state: State, config: RunnableConfig = None) -> Any:
    ai_message = llm_with_tool.invoke(state["messages"])
    return {"messages": ai_message}


# def 执行工具(状态):
#     # 拿到AI想调用的工具
#     要调用的工具列表 = 状态.消息最后一条.tool_calls
#
#     # 遍历并执行
#     结果消息列表 = []
#     for 工具 in 要调用的工具列表:
#         结果 = 执行对应工具(参数)
#         结果消息列表.append(工具消息(结果))
#
#     # 返回结果给AI
#     return {"messages": 结果消息列表}

# ====================== 工具执行器 ======================

# state["messages"] = 所有消息列表（你说的、AI 说的、工具记录）
# [-1] = 取最后一条消息
# 最后一条消息，就是 AI 刚刚发出的 “我要调用工具” 的指令
# .tool_calls = AI 想调用什么工具？参数是什么？

def tool_executor(state: State, config: RunnableConfig = None) -> Any:
    tool_calls = state["messages"][-1].tool_calls
    tool_by_name = {tool.name: tool for tool in toos}

    messages = []
    for call in tool_calls:
        tool = tool_by_name[call["name"]]
        messages.append(ToolMessage(
            tool_call_id=call["id"],
            content=tool.invoke(call["args"]),
            name=call["name"],
        ))
    return {"messages": messages}


# ====================== 路由 ======================
def router(state: State, config: RunnableConfig = None) -> Literal["tool_executor", "__end__"]:
    # 1. 拿到AI最后发的消息
    ai_message = state["messages"][-1]

    # 2. 判断：AI是不是想调用工具？
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tool_executor"

    return "__end__"


# ====================== 构建图 ======================

graph_builder = StateGraph(State)

graph_builder.add_node("llm", chatbot)
graph_builder.add_node("tool_executor", tool_executor)

graph_builder.set_entry_point("llm")
graph_builder.add_conditional_edges("llm", router)
graph_builder.add_edge("tool_executor", "llm")

graph = graph_builder.compile()

# ====================== 测试 ======================
if __name__ == "__main__":
    state = graph.invoke({
        "messages": [("human", "广州天气怎么样？")]
    })

    for msg in state["messages"]:
        print(f"类型：{msg.type}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print("工具调用：", msg.tool_calls)
        print("内容：", msg.content)
        print("=" * 50)
