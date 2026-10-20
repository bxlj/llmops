"""
@Time    : 2026-03-11 9:33
@AUthor  : jiachengjie
@File    : weaviate使用.py
"""
import os

import dotenv
from langchain_community.embeddings import ZhipuAIEmbeddings
from langchain_weaviate import WeaviateVectorStore

import weaviate_view

dotenv.load_dotenv()

# 连接weaviate向量数据库
client = weaviate_view.connect_to_local("192.168.127.151", "8080")

# 初始化Embedding模型
embeddings = ZhipuAIEmbeddings(
    model='embedding-2',
    api_key=os.environ['ZHIPU_API_KEY'],
)

# 实例化WeaviateVectorStore
db = WeaviateVectorStore(client=client, index_name="DatasetTest", text_key="text", embedding=embeddings)

# 3.新增数据
ids = db.add_texts([
    "笨笨是一只很喜欢睡觉的猫咪",
    "我喜欢在夜晚听音乐，这让我感到放松。",
    "猫咪在窗台上打盹，看起来非常可爱。",
    "学习新技能是每个人都应该追求的目标。",
    "我最喜欢的食物是意大利面，尤其是番茄酱的那种。",
    "昨晚我做了一个奇怪的梦，梦见自己在太空飞行。",
    "我的手机突然关机了，让我有些焦虑。",
    "阅读是我每天都会做的事情，我觉得很充实。",
    "他们一起计划了一次周末的野餐，希望天气能好。",
    "我的狗喜欢追逐球，看起来非常开心。",
])

# 4.检索数据
print(db.similarity_search_with_score("笨笨"))
