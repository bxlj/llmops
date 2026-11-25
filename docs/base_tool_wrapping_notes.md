# 把向量数据库查询包装成 LangChain BaseTool —— 详解与项目实战

> 日期：2026-11-02
> 项目：llmops（`internal/service/retrieval_service.py` / `function_call_agent.py`）
> 关联：`docs/agent_core_module_notes.md`、`docs/tool_four_elements_notes.md`

---

## 1. 一句话理解 BaseTool

**BaseTool 就是给一个普通 Python 函数套上"说明书"——名字、描述、参数表——让 LLM 看得懂它、Agent 框架调得动它。**

LLM 从来不执行函数。它读完说明书后只做一件事："点单"（发出 `tool_calls`），真正执行的是你的 Python 代码。三者关系：

```
LLM     →  读说明书（name / description / args_schema）→ 决定何时调用、传什么参数
BaseTool →  数据契约（pydantic 校验）→ 路由到真正的实现
你的代码 →  _run() 真正执行（查向量库、调 API……）
```

这个设计的本质：**把"LLM 的选择"和"代码的执行"用一个数据契约隔离开**——所以参数校验错误能安全地回传给模型自愈，而不是炸掉整个程序。

---

## 2. 三种创建方式（按封装程度从低到高）

### 2.1 `@tool` 装饰器（最快）

```python
from langchain_core.tools import tool

@tool
def get_weather(city: str, date: str = "今天") -> str:
    """查询指定城市指定日期的天气。date格式为YYYY-MM-DD"""
    return f"{city}{date}：晴，25℃"

get_weather.name          # get_weather
get_weather.description   # docstring 原文
get_weather.invoke({"city": "广州"})   # Agent 内部就这么调
```

- **docstring 就是 prompt 的一部分**——LLM 靠它决定何时用这个工具，含糊的描述 = LLM 乱点单；
- 适合无状态的单个函数。

### 2.2 子类化 `BaseTool`（最完整）

```python
from typing import Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

class WeatherArgs(BaseModel):
    """工具的参数表——LLM 据此生成 tool_calls 的 args"""
    city: str = Field(description="城市名，如：广州")
    date: str = Field(default="今天", description="日期，YYYY-MM-DD")

class WeatherTool(BaseTool):
    name: str = "get_weather"                    # 点单菜名
    description: str = "查询城市天气"              # 菜单描述
    args_schema: Type[BaseModel] = WeatherArgs   # 菜品规格

    def _run(self, city: str, date: str = "今天") -> str:
        return f"{city}{date}：晴"

    # async 支持：不写则框架自动 fallback 到 _run 的线程池
    # async def _arun(self, ...) -> str: ...

tool = WeatherTool()
tool.invoke({"city": "广州"})
```

三个部件各司其职；`invoke` 时 pydantic 先校验参数，**LLM 传错参在这里被拦下**，不会进入业务代码。项目里的 builtin 工具（dalle3、gaode、serper 等）全部是这条路的变体：构造时注入凭证，`_run` 调外部 API。

### 2.3 `StructuredTool.from_function`（中间态）

```python
from langchain_core.tools import StructuredTool

def search_db(sql: str) -> str: ...

tool = StructuredTool.from_function(
    func=search_db,
    name="search_db",
    description="执行只读SQL查询",
)
```

---

## 3. 实战：把 Weaviate 向量库查询包装成 BaseTool

### 3.1 项目里的现成实现（`retrieval_service.py`）

```python
def create_langchain_tool_from_search(
        self,
        flask_app: Flask,
        dataset_ids: list[UUID],
        account_id: UUID,
        retrieval_strategy: str = RetrievalStrategy.SEMANTIC,
        k: int = 4,
        score: float = 0,
        retrival_source: str = RetrievalSource.HIT_TESTING,
) -> BaseTool:
    """根据传递的参数构建一个LangChain知识库搜索工具"""

    class DatasetRetrievalInput(BaseModel):                 # ① 参数表（给LLM看）
        """知识库检索工具输入结构"""
        query: str = Field(description="知识库搜索query语句，类型为字符串")

    @tool(DATASET_RETRIEVAL_TOOL_NAME, args_schema=DatasetRetrievalInput)   # ② 装饰成BaseTool
    def dataset_retrieval(query: str) -> str:
        """如果需要搜索扩展的知识库内容，当你觉得用户的提问超过你的知识范围时，
        可以尝试调用该工具，输入为搜索query语句，返回数据为检索内容字符串"""
        with flask_app.app_context():                       # ③ 手动补应用上下文
            documents = self.search_in_datasets(            # ④ 真正的向量库查询
                datasets=dataset_ids,
                query=query,
                account_id=account_id,
                retrieval_strategy=retrieval_strategy,
                k=k,
                score=score,
                retrival_source=retrival_source,
            )

        if documents is None or len(documents) == 0:
            return "知识库内没有检索到对应内容"

        return combine_documents(documents)                 # ⑤ 结果序列化成字符串

    return dataset_retrieval                                # ⑥ 返回BaseTool实例
```

### 3.2 五个关键设计点

#### ① 闭包解决"工具需要携带状态"——这是整个模式的灵魂

`search_in_datasets` 需要知道：查**哪些知识库**（dataset_ids）、**替谁查**（account_id）、用**哪个 app 的资源**（flask_app）。但 BaseTool 的执行签名里只能有 LLM 传的参数（query）。

**解法：工厂函数的参数被内层函数闭包捕获**——工具实例创建的那一刻，"查谁的哪些库"就焊死在里面了。之后 Agent 调用时只传 query，LLM 无从指定账号或知识库。

> 安全意义：**权限边界在实例化时封死**，LLM 永远接触不到 dataset_ids / account_id 这类敏感参数。

#### ② `@tool` 装饰器做了什么

把内层函数转成 `StructuredTool` 实例：函数名 → `name`，docstring → `description`，`args_schema` → LLM 生成 tool_calls 时的参数模板。**返回值必须是 `str`**——工具结果要变成 `ToolMessage` 的 content 喂回模型。

#### ③ `with flask_app.app_context()` —— 最容易漏的坑

这个工具会在 **Agent 的流式执行**中被调用，运行线程不是普通 HTTP 请求线程。而 `search_in_datasets` 里用了 `self.db.session`（Flask-SQLAlchemy）和 `self.vector_database_service`（Weaviate 客户端）——**没有 app context 会直接报 "Working outside of application context"**。

工厂把 `flask_app` 闭包进来、执行时手动 push 上下文，就是在补这个环境。调用方传的是 `current_app._get_current_object()`（真实 app 对象，而不是代理）。

#### ④ 查询细节全部下沉到 `search_in_datasets`

| 检索策略 | 实现 |
|---|---|
| 语义检索 | Weaviate 向量检索（`SemanticRetriever`，k + score_threshold） |
| 全文检索 | jieba 分词 + 数据库（`FullTextRetriever`） |
| 混合检索 | `EnsembleRetriever` 0.5/0.5 加权合并 |

工具层完全不关心这些，只认"传 query 回来字符串"。**换向量库、改检索策略，工具层零改动**——这就是包装带来的解耦。

#### ⑤ `combine_documents`：LLM 不吃 Document 对象

检索返回 `list[LCDocument]`（带 metadata、score），必须拼成纯字符串再返回。这里同时是**成本闸门**：`k=4` 限制条数，防止把几万 token 塞回 prompt（模型账单暴涨的常见源头之一）。

### 3.3 接进 Agent 的完整链路

```python
# assistant_agent_service.py，TODO 第 6 步的位置
tools = []
tools.append(self.retrieval_service.create_langchain_tool_from_search(
    flask_app=current_app._get_current_object(),   # 真实app对象，不是LocalProxy
    dataset_ids=绑定给Agent的知识库id列表,
    account_id=account.id,
))
```

工具实例在 FunctionCallAgent 里的一生：

```
bind_tools(tools)      → 说明书（name/description/args_schema）发给 LLM
LLM 返回 tool_calls    → {"name": "dataset_retrieval", "args": {"query": "..."}}
_tools_node 执行       → tools_by_name["dataset_retrieval"].invoke(args)
                         args_schema 校验 → 闭包内查 Weaviate → 字符串结果
ToolMessage 回传       → LLM 读到检索内容 → 组织最终回答
```

### 3.4 工具名的特殊约定

```python
event = (QueueEvent.AGENT_ACTION
         if tool_call["name"] != DATASET_RETRIEVAL_TOOL_NAME   # 名字对上 → 专属事件
         else QueueEvent.DATASET_RETRIEVAL)
```

工具名叫 `DATASET_RETRIEVAL_TOOL_NAME` 不是随便起的——**前端靠这个事件类型把"知识库检索"渲染成独立面板**，和普通工具动作区分开。业务协议层对特定工具的"白名单"识别，是 Dify 同构设计的一部分。

---

## 4. 常见坑与要点清单

| # | 坑 | 说明 |
|---|---|---|
| 1 | docstring 写成给人看的注释 | 它是 LLM 的决策依据，要写成"使用说明"：什么时候用、输入是什么、返回什么 |
| 2 | 返回值不是字符串 | ToolMessage.content 需要 str；复杂数据先 `json.dumps` 或拼文本 |
| 3 | 忘记 app_context | 流式/子线程里访问 db.session / vector store 直接报上下文错误 |
| 4 | 闭包变量被循环变量覆盖 | 循环里创建多个工具时，晚绑定陷阱会让所有工具共享最后一次的值（必要时用默认参数固化） |
| 5 | 不控制返回体积 | k 不限制、原文不截断 → prompt 爆炸、费用暴涨 |
| 6 | 敏感参数暴露给 LLM | dataset_ids / account_id 必须走闭包，不能出现在 args_schema 里 |
| 7 | `_run` 里抛裸异常 | 会被 Agent 的错误兜底包成 ToolMessage 回传模型自愈——这是特性不是 bug，但要在内容里带上可读的错误描述 |

---

## 5. 面试话术（30 秒版）

> "包装向量库查询成 BaseTool 的核心是**工厂 + 闭包**：工厂参数注入运行时状态（知识库 id、账号、app 上下文），闭包把它们焊进工具实例；装饰器负责生成 LLM 可见的 name/description/args_schema；执行时手动 push Flask 上下文调检索服务，结果序列化成字符串回传。LLM 只见说明书不见实现，权限边界在实例化时封死。"

追问预案：

- **为什么用闭包而不是把参数放进 args_schema？** —— dataset_ids/account_id 是权限信息，不能让 LLM 决定；闭包让它们在实例化时固定，LLM 的调用面里根本不存在这些参数。
- **工具执行出错怎么办？** —— Agent 的 tools 节点把异常包成错误 ToolMessage 回传，模型看到错误后自己换参数重试或放弃，任务不中断。
- **怎么控制成本？** —— k 限制召回条数 + 结果拼接时截断，检索内容是 prompt 的一部分，体积直接决定 token 费用。
