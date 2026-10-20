"""
@Time    : 2026-03-19 11:01
@AUthor  : jiachengjie
@File    : 1-LLM与ChatModel使用技巧.py
"""
import os

import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 编排prompt模板
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是新闻咨询专家，请回答用户的问题"),
    ("human", "{query}")
])

# 创建大语言模型
llm = ChatOpenAI(
    base_url=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    model="moonshot-v1-32k",
    temperature=0)

ai_message = llm.invoke(chat_prompt.invoke({"query": "给我查找目前黄金的大盘价格"}))

print(ai_message)
print("==================")
print(ai_message.content)
print("==================")
print(ai_message.response_metadata)
