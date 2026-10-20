# 一个东西要成为 LangChain Tool，需要什么？——四要素与"点菜-炒菜"模型

> 源码：`internal/core/workflow/workflow.py`（`Workflow(BaseTool)`）、`internal/core/agent/agents/function_call_agent.py`（`_tools_node` / `_tools_condition`）
> 姊妹篇：[workflow_tool_design_notes.md](workflow_tool_design_notes.md)（工作流引擎的设计思想）
> 整理日期：2026-10-15

---

## 0. 一句话总纲

**成为一个 Tool 只需要"三份说明书 + 一双手"：**

- `name`、`description`、`args_schema` —— 三份说明书，**说给模型听**（模型据此"点菜"）
- `_run` —— 一双手，**做给运行时跑**（运行时负责"炒菜"）

而"Agent 调用工具"的真相是：**大模型在点菜，Python 运行时在炒菜。模型从头到尾没有执行任何东西**——它只是在响应里输出一段结构化 JSON，说"我想调叫 X 的工具，参数是 Y"。

---

## 1. 四要素总表

| 要素 | 谁在用 | 作用 | 在 `Workflow(BaseTool)` 里的落点 |
|---|---|---|---|
| `name` | 模型 + 运行时 | 工具的身份证号。模型在 `tool_calls` 里报这个名字；运行时靠 `tools_by_name[name]` 找到它 | `name=workflow_config.name`（数据库里的 `tool_call_name`） |
| `description` | 只给模型 | **广告词**。模型判断"什么时候该用这个工具"的唯一依据 | `description=workflow_config.description` |
| `args_schema` | 模型 + 运行时 | **使用说明书**。pydantic 模型 → JSON Schema 塞进 prompt 告诉模型传什么；运行时用它自动校验参数 | `args_schema=self._build_args_schema(...)`（从 start 节点动态推导） |
| `_run` | 只给运行时 | **双手**。真正干活的方法 | `return self._workflow.invoke({"inputs": kwargs})` |

记忆法：**前三个是模型的使用前提（点菜依据），最后一个是运行时的执行入口（炒菜动作）**。`_run` 根本不会发给模型——模型不知道也不需要知道工具背后是 requests、数据库还是一整张图。

---

## 2. 四要素上线时的样子（wire format）

调用 `llm.bind_tools(tools)` 时，LangChain 把**前三样**转成 OpenAI function calling 格式发出去：

```json
{
  "type": "function",
  "function": {
    "name": "gaode_weather",
    "description": "查询中国城市的实时天气",
    "parameters": {
      "type": "object",
      "properties": {
        "city": { "type": "string", "description": "城市名" }
      },
      "required": ["city"]
    }
  }
}
```

要点：

- `parameters` 就是 `args_schema`（pydantic 模型）调 `model_json_schema()` 转出来的东西
- 模型的响应里若要调工具，只会输出 `tool_calls: [{name, args, id}]` 这样的 JSON
- 参数校验在运行时由 pydantic 兜底——模型传错了类型会报错，错误信息再喂回模型让它自己纠正

---

## 3. "点菜-炒菜"模型：Agent 调用工具的完整闭环

以本项目 `function_call_agent.py` 为例（`_tools_node` 就是后厨）：

```python
def _tools_node(self, state):
    tools_by_name = {tool.name: tool for tool in self.agent_config.tools}  # 菜单→后厨对照表
    tool_calls = state["messages"][-1].tool_calls      # 模型递来的"点菜单"（纯JSON）
    for tool_call in tool_calls:
        tool = tools_by_name[tool_call["name"]]        # 按名字找工具
        tool_result = tool.invoke(tool_call["args"])   # ★ 真正执行的只有这一行Python
        messages.append(ToolMessage(tool_call_id=..., content=json.dumps(tool_result)))
```

完整闭环（假设工具箱里挂着我们的工作流工具）：

```
1. llm.bind_tools(tools)             四要素的前三样被序列化进请求
2. 模型响应: tool_calls=[            ← 模型只产出"点菜单"
     {name: "工作流工具", args: {query: "上海天气"}}]
3. _tools_node: tool.invoke(args)    ← 运行时炒菜：
       Workflow._run → graph.invoke → 沿边调度节点
4.     └─ 图里的 LLMNode.invoke → ChatOpenAI.stream()
                                     ← 图内部还有一次独立的"点菜+炒菜"
5. ToolMessage(结果) 塞回 messages    ← 菜端上桌，模型才能"看到"结果
6. _tools_condition: 检查最后一条AI消息
     还有 tool_calls → 回到 "tools" 节点继续循环
     没有             → END，产出最终回答
```

两个关键推论：

1. **模型是决策者，运行时是执行者**。整条链路上真正调大模型 API 的只有 `ChatOpenAI.stream()` 那一处（或 Agent 层每轮对话的那一次响应），其余全是 Python。
2. **`ToolMessage` 是模型看到工具结果的唯一通道**。工具执行完必须把结果塞回 messages，否则模型永远不知道"菜做好了没有"——这是初学者最容易漏掉的一环。

---

## 4. Agent 与 Workflow 的分界线：一个 if

```python
def _tools_condition(self, state) -> Literal["tools", "__end__"]:
    ai_message = state["messages"][-1]
    if hasattr(ai_message, "tool_calls") and len(ai_message.tool_calls) > 0:
        return "tools"        # 模型说继续 → 继续调工具
    return END                # 模型说够了 → 结束
```

**"要不要继续"的判断权在谁手里，就是二者的分界线：**

| | 判断权 | 判断时机 | 结果 |
|---|---|---|---|
| Workflow | 开发者（画布上的边） | 编译期定死 | 可控、可审计、路径固定 |
| Agent | 模型（每轮响应里的 tool_calls） | 运行时临时决定 | 灵活、开放、路径不可预知 |

这段 if 是"可控性 vs 灵活性"取舍在代码里的**确切物理位置**。

---

## 5. 造一个 Tool 的三种写法（四要素不变）

```python
# 写法一：继承 BaseTool —— 本项目 Workflow 用的，适合复杂逻辑/需要构造参数
class WeatherTool(BaseTool):
    name: str = "gaode_weather"
    description: str = "查询中国城市的实时天气"
    args_schema: type[BaseModel] = WeatherInput      # 一个pydantic模型

    def _run(self, city: str) -> str:
        return requests.get(f"https://...?city={city}").text

# 写法二：@tool 装饰器 —— 函数签名自动推导 name/args_schema，docstring 即 description
@tool
def gaode_weather(city: str) -> str:
    """查询中国城市的实时天气"""
    return requests.get(...).text

# 写法三：StructuredTool.from_function —— 已有现成函数时包一层
tool = StructuredTool.from_function(
    func=some_func, name="...", description="...", args_schema=SomeModel,
)
```

无论哪种写法，最终在 Agent 眼里地位完全平等——`function_call_agent.py` 里那个 `tools_by_name` 字典能一视同仁调度内置工具、API 工具和工作流工具，正是因为**大家都履行同一份四要素合同**。

---

## 6. 本项目的三种工具来源（殊途同归）

| 来源 | 四要素从哪来 | 注册到哪 |
|---|---|---|
| 内置工具（谷歌搜索、高德天气） | yaml 声明文件（provider/tool 目录下的配置） | `BuiltinProviderManager` |
| API 工具（用户在平台上创建的） | 数据库 `api_tool` 表 | `ApiTool` 记录 → 包装成 Tool |
| 工作流（整张图） | `tool_call_name` / `description` 字段 + start 节点 inputs 动态推导 | `Workflow(BaseTool)` 实例 |

> 注意区分：工作流**类名**（`Workflow`/`WorkflowTool`，随便起）只是 Python 标识符；工具对外的 `name` 来自 `tool_call_name` 数据库字段。改名类不影响 Agent 看到的工具名。

---

## 7. 两个最容易踩的坑

### 坑 1：description 写不好 = 模型不会用

模型选工具全靠 description。含糊的描述（"这是一个工具"）会让 Agent 要么不选、要么乱选。写清楚三件事：

- **什么时候用**（触发条件："当用户询问中国城市的实时天气时"）
- **输入是什么**（配合 args_schema 的字段 description）
- **返回什么**（结果的形式："返回温度、湿度、风向的 JSON"）

### 坑 2：args_schema 和 _run 签名漂移

schema 里声明了 `city` 而 `_run` 参数叫 `city_name` → 运行时校验直接报错。这也是为什么 `Workflow` 用 `_build_args_schema` 从 start 节点**统一推导**——schema 和执行体同源，天然不会漂移（单一事实来源思想的又一次应用）。

### 附：其他可选要素（进阶再用）

- `_arun`：异步执行体（高并发服务端建议实现）
- `return_direct`：结果直接作为最终回答，不再让模型加工
- `handle_tool_error`：工具报错时返回可读信息而不是直接抛异常（让模型有机会自行纠正）

---

## 8. 动手练习

### 练习 1（入门）：手写一个 Tool 并观察 wire format

用写法二写一个"单词翻译"工具，挂到 Agent 上，然后打印 `llm.bind_tools([tool]).kwargs["tools"]`（或抓包看请求体），对照第 2 节的 JSON 找到四要素分别变成了哪个字段。

### 练习 2（进阶）：故意写坏 description

把某个工具的 description 改成"工具"，同时工具箱里放两个功能不同的工具，问一个明确属于其中一个的问题，观察模型的选错率；再写回完整描述（何时用/输入/输出），对比。**这是体会"description 是模型唯一决策依据"最直接的方法。**

### 练习 3（实战）：追踪一次完整的点菜-炒菜循环

在 `_tools_node` 的 `tool.invoke` 前后加 print（调试环境），跑一次带工具的 Agent 对话，把打印顺序记下来，和第 3 节的闭环图逐条对应。重点确认：`ToolMessage` 塞回后，下一轮模型请求的 messages 里多了什么。

### 练习 4（架构）：给 WorkflowTool 加异步

给 `Workflow(BaseTool)` 补一个 `_arun`（内部调 `await self._workflow.ainvoke(...)`），思考：哪些节点天然可异步（http_request、llm），哪些必须保持同步（code 节点里用户写的 Python）。

---

## 9. 复盘用的一页纸

| 概念 | 一句话 |
|---|---|
| Tool 四要素 | name/description/args_schema 给模型看，_run 给运行时跑 |
| function calling | 模型输出 tool_calls JSON（点菜单），运行时执行（炒菜） |
| 结果回传 | ToolMessage 是模型看到工具结果的唯一通道 |
| 循环与否 | `_tools_condition`：有 tool_calls 就继续，没有就结束 |
| Agent vs Workflow | "要不要继续"的判断权：模型手里 vs 画布的边手里 |
| 万物皆 Tool | yaml 声明、Python 函数、整张工作流图，履行同一份合同 |

**和上一篇的衔接**：上一篇讲了"工作流如何伪装成 Tool"（适配器+编译器）；本篇讲"Tool 的合同具体长什么样"（四要素）以及"模型如何按合同点菜"（function calling 闭环）。两篇合起来 = 你项目里从画布到 Agent 的完整链路。
