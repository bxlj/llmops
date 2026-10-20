"""
@Time    : 2026-03-19 13:50
@AUthor  : jiachengjie
@File    : 3-LLM与stream使用技巧.py
"""
import os

import dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 创建prompt
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是OpenAI开发的聊天机器人，请回答用户的问题"),
    ("human", "{query}")

])

# 初始化大模型
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=os.getenv("OPENAI_TEMPERATURE")
)

# 调用大模型
messages = llm.stream(chat_prompt.invoke({"query": "你能介绍一下LLM和LLMOps吗？"}))

for message in messages:
    print(message.content, flush=True, end="")
