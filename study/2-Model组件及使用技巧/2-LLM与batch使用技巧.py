"""
@Time    : 2026-03-19 13:31
@AUthor  : jiachengjie
@File    : 2-LLM与batch使用技巧.py
"""
import os

import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 编排模板
chat_prompt = ChatPromptTemplate([
    ("system", "你是OpenAI开发的聊天机器人，请回答用户的问题"),
    ("human", "{query}",)

])

# 初始化大模型
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=0
)

# 调用大模型

messages = llm.batch([
    chat_prompt.invoke({"query": "你好，你是"}),
    chat_prompt.invoke({"query": "请说出王铮亮的歌曲名字"}),

])

for message in messages:
    print(message.content)
    print("===========================")
