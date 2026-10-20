"""
@Time    : 2026-03-04 14:36
@AUthor  : jiachengjie
@File    : prompt组件使用技巧.py
"""

from langchain_core.messages import AIMessage
from langchain_core.prompts import (PromptTemplate,
                                    ChatPromptTemplate,
                                    MessagesPlaceholder,
                                    HumanMessagePromptTemplate)

tem = PromptTemplate.from_template("请讲一个关于{cont}的笑话")
print((tem.format(cont="演员")))
tem_invoke = tem.invoke({"cont": "程序员"})
print(tem_invoke.to_string())
print(tem_invoke.to_messages())

print("==================")

# 聊天模板使用

chat_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个房地产资深研究者，现在根据用户提问，进行回答问题",),
    MessagesPlaceholder("chat_history"),
    HumanMessagePromptTemplate.from_template("请给我说一个{housue}的建议"),
])

chat_prompt_value = chat_prompt.invoke({
    "chat_history": [
        ("human", "我叫小木"),
        AIMessage("你好，我是ChatGPT，有什么可以帮到您")
    ],
    "housue": "买房"
})

print(chat_prompt_value)
print("==================")
print(chat_prompt_value.to_messages())
print("==================")
print(chat_prompt_value.to_string())
