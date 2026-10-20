"""
@Time    : 2026-03-19 15:45
@AUthor  : jiachengjie
@File    : RunnableParallel使用技巧.py
"""
import os

import dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

# 初始化prompt模板
joke_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是数学老师，请回答用户的问题"),
    ("human", "{joke_query}")
])

poem_prompt = ChatPromptTemplate.from_template("给我写一下{poem_query}")

# 初始化大模型
llm = ChatOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
    model=os.getenv("OPENAI_MODEL_NAME"),
    temperature=os.getenv("OPENAI_TEMPERATURE"),
)

# 编排链
joke_chain = joke_prompt | llm | StrOutputParser()
poem_chain = poem_prompt | llm | StrOutputParser()

map_chain = RunnableParallel(
    joke_answer=lambda x: joke_chain.invoke({"joke_query": x["joke_query"]}),
    poem_answer=lambda x: poem_chain.invoke({"poem_query": x["poem_query"]}),

)

# 定义要传递的参数
input_params = {
    "joke_query": "解释勾股定理的公式",
    "poem_query": "《沁园春·雪》全文"
}

# 传参调用
result = map_chain.stream(input_params)

for chunk in result:
    if chunk.get("joke_answer"):
        print(f"【数学回答】: {chunk['joke_answer']}", flush=True, end="")
    if chunk.get("poem_answer"):
        print(f"【诗词回答】: {chunk['poem_answer']}", flush=True, end="")
