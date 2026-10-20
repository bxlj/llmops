"""
@Time    : 2026-03-19 14:17
@AUthor  : jiachengjie
@File    : 1-LCEL表达式.py
"""
import os

import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 构建prompt模板
chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是OpenAI开发的聊天机器人，请回答用户的问题"),
    ("human", "{query}"),
])

# 初始化大模型
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_URL"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=os.getenv("OPENAI_TEMPERATURE"),
)

# 创建链

chain = chat_prompt | llm | StrOutputParser()

# 调用链返回结果
messages = chain.stream({"query": "今天陕西西安的天气怎么样，温度多少"})

for message in messages:
    print(message, flush=True, end="")
