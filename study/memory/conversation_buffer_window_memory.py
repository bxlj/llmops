"""
@Time    : 2026-03-06 16:30
@AUthor  : jiachengjie
@File    : conversation_buffer_window_memory.py
"""

import os

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

# ====================== 1. 彻底禁用追踪器 + 环境配置 ======================
# 多重保障：禁用所有LangChain追踪/日志
os.environ["LANGCHAIN_TRACING"] = "false"
os.environ["LANGCHAIN_VERBOSE"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
# 初始化提示词模板
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是AI聊天机器人，请帮助用户解决问题"),
    # 历史对话占位符：会被记忆组件中的历史对话填充
    MessagesPlaceholder("history"),
    ("human", "{query}")
])

# 初始化LLM模型
llm = ChatOpenAI(
    api_key="sk-f0IfbwLmAWocLLP3ku3VWcErPgexDTDl9kAiHpej9HkY2OF5",
    base_url="https://api.moonshot.cn/v1",
    model="moonshot-v1-8k",
    temperature=0.1,  # 回答更稳定
    max_tokens=2000  # 限制单次响应长度

)

# 构建对话链
base_chain = prompt | llm | StrOutputParser()

# 初始化会话存储（按session_id隔离，支持持久化扩展）
store = {}


# 获取会话历史的函数
def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    # 窗口记忆：只保留最近2轮（4条消息：用户+AI为1轮）
    history = store[session_id]
    if len(history.messages) > 4:
        history.messages = history.messages[-4:]
    return history


# 封装带记忆的对话链
chain = RunnableWithMessageHistory(
    runnable=base_chain,
    get_session_history=get_session_history,
    input_messages_key="query",
    history_messages_key="history"
)

# ====================== 3. 交互式对话循环（修复流式打印重复问题） ======================
# 固定会话ID（本地测试用，生产环境替换为用户唯一标识）
SESSION_ID = "java_dev_agent_转型"
while True:
    query = input("Human:")

    if query == "exit":
        exit(0)

    # 构造链的输入参数（需和memory的input_key一致）
    chat_input = {"query": query}

    # 2. 构造config（必须包含session_id，这是错误的核心修复点）
    config = {
        "configurable": {
            "session_id": SESSION_ID  # 必须与get_session_history的入参对应
        }
    }

    # 打印AI响应的前缀（flush=True确保立即输出，end=""不换行，适配流式输出）
    print("AI:", flush=True, end="")
    # 流式调用对话链：逐块返回响应（提升用户体验）
    result = chain.stream(chat_input, config=config)

    output = ""

    # 3. 流式调用：必须传入config参数（核心！）
    try:
        for chunk in chain.stream(chat_input, config=config):
            output += chunk
            # 只打印当前chunk，避免重复输出
            print(chunk, flush=True, end="")
    except Exception as e:
        print(f"\n调用出错：{str(e)}")
        continue

    # 打印当前记忆（格式化输出，方便查看）
    history_messages = get_session_history(SESSION_ID).messages
    print(f"\n\n当前记忆内容（最近2轮）：")
    for msg in history_messages:
        role = "用户" if msg.type == "human" else "AI"
        print(f"{role}: {msg.content}")
    print("-" * 80)
