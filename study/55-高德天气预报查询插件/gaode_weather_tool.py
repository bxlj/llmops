"""
@Time    : 2026-03-23 14:12
@AUthor  : jiachengjie
@File    : gaode_weather_tool.py
"""
import json
import os
from typing import Any, Type

import dotenv
import requests
from langchain_core.tools import BaseTool
from langchain_core.utils.pydantic import BaseModel, Field

dotenv.load_dotenv()


# 构建参数模型

class WeatherData(BaseModel):
    city: str = Field(description="这是一个城市名称")


# 实现BaseTool接口
class WeatherTool(BaseTool):
    """根据传入的城市名查询天气"""
    name: str = "weather_tool"
    description: str = "当你想查询天气或者与天气相关的问题时可以使用的工具"
    args_schema: Type[BaseModel] = WeatherData

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


gaode_weather = WeatherTool()

print(gaode_weather.invoke({"city": "深圳"}))
