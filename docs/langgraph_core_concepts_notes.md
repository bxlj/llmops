# LangGraph 图程序详解——核心元素、主要属性与执行原理

> 源码：`internal/core/workflow/workflow.py`（`_build_workflow`）、`internal/core/workflow/entities/workflow_entity.py`（`WorkflowState`）
> 姊妹篇：[workflow_tool_design_notes.md](workflow_tool_design_notes.md)（设计思想）、[tool_four_elements_notes.md](tool_four_elements_notes.md)（Tool 四要素）
> 环境版本：langgraph 1.2.11
> 整理日期：2026-10-16

---

## 0. 一句话总纲

> **LangGraph = 一台"共享状态驱动的流水线引擎"：你把节点注册进去、用边接好线，它负责按线调度、并行执行、把各节点的产出合并进一份共享状态。**

它只解决一个问题：**多个节点（函数）怎么有序、并行、可靠地协作。**
剩下的一切——`compile()`、`invoke()`、`stream()`、chunk 格式——都是这个问题的衍生品。

---

## 1. 为什么需要 LangGraph（先看没有它会怎样）

假设没有 LangGraph，你要手工执行那张 5 分支的工作流：

```python
def 手工执行(inputs):
    start_result = start(inputs)
    retrieve = dataset_retrieval(start_result)
    llm_result = llm(retrieve)
    # 接下来 5 条分支：模板、代码、谷歌、高德、HTTP —— 先跑谁？一起跑怎么写？
    # 线程池？5个结果怎么汇合？谁先完成谁先算？
    # end 要等所有分支到齐 —— 怎么判断"到齐"？
```

你会发现要自己写：**调度顺序、并行管理、结果汇合、状态传递**——每一项都不难，但每一项都容易出错。

LangGraph 就是把这四件事做成现成引擎。你只需要提供三样东西：**状态模板、节点、边**——这就是三大核心元素。

---

## 2. 核心元素一：State（状态）——共享黑板

### 2.1 它是什么

整张图**只有一份**共享状态，所有节点都从它取数、往它写数。你项目的定义：

```python
class WorkflowState(TypedDict):
    inputs: Annotated[dict[str, Any], _process_dict]                  # 全图共用的输入
    outputs: Annotated[dict[str, Any], _process_dict]                 # 最终输出
    node_results: Annotated[list[NodeResult], _process_node_results]  # 各节点运行结果
```

**打个比方**：这是一块挂在工厂墙上的大白板。每个工位（节点）干活前看一眼白板，干完活把成果写回白板。工位之间不直接对话，全靠白板交流——这就是"黑板模式"。

### 2.2 最精妙的设计：归纳函数（reducer）

注意每个字段都长这样：`Annotated[类型, 函数]`。第二个位置的函数叫 **reducer（归纳函数）**，它回答一个问题：

> **当两个节点同时往同一个字段写时，听谁的？**

你项目里的两个 reducer：

```python
def _process_dict(left, right):
    """字典字段：覆盖式合并（新key加入，旧key被覆盖）"""
    left = left or {}
    right = right or {}
    return {**left, **right}

def _process_node_results(left, right):
    """列表字段：追加（新老结果都保留）"""
    left = left or []
    right = right or []
    return left + right
```

### 2.3 为什么必须有 reducer（并行写冲突问题）

你的工作流里，llm 节点跑完后，**模板、代码、谷歌、高德、HTTP 五个节点并行执行**。它们完成后都会往 `node_results` 写自己的结果——五个几乎同时到达！

如果没有合并规则：后写的把先写的**覆盖**，白板上只剩最后一个节点的结果——你的 5 分支图会丢 4 个结果。

有了 `left + right`：引擎把 5 份结果**追加**成一份长列表，一个不丢。

> **这就是之前问过的"并行结果怎么汇合"的最终答案——藏在这两行小函数里。**

### 2.4 reducer 的通用套路

| 数据形态 | 常见 reducer | 语义 |
|---|---|---|
| 数值（计数、累加） | `left + right` | 累加 |
| 列表（日志、结果集） | `left + right` | 追加 |
| 字典（配置、输出） | `{**left, **right}` | 新盖旧 |
| "只要最新值" | `return right` | 直接覆盖 |
| 自定义逻辑 | 任意函数 | 比如取 max、去重合并 |

LangGraph 的灵活性大半来自这里：**同一个节点注册到不同图里，换个 reducer 就换一种协作方式。**

---

## 3. 核心元素二：Node（节点）——工位

### 3.1 节点的本质：一个"state 进、state 增量出"的函数

```python
graph.add_node("llm_eba75e0b-...", LLMNode(node_data=...))
#              ↑ 旗标（唯一名字）      ↑ 可调用体
```

LangGraph 对节点函数的要求只有一条：**接收当前 state，返回 state 的增量（部分更新）**。你的 8 种节点全部遵守：

```python
# LLMNode.invoke 的返回（简化）
return {"node_results": [NodeResult(...)]}   # ← 增量：只包含"我要更新"的字段
```

引擎拿到增量后，**按 reducer 合并**进共享状态——不是整体替换。

### 3.2 节点的"肚子"里装着配置

构造图时，你 Postman 里发的节点 dict 被装进节点对象：

```python
NodeClasses[NodeType.LLM](node_data=node)
# dict{prompt, model_config, inputs...} → LLMNode实例的 self.node_data
```

运行时节点从自己肚子里掏配置干活：

```python
def invoke(self, state, ...):
    prompt = self.node_data.prompt        # ← 构造时存进来的
    llm = ChatOpenAI(model=self.node_data.language_model_config.get("model"))
    ...
```

**所以原始 nodes/edges 列表在 `_build_workflow` 结束后就"退休"了——它们的信息已全部长进节点对象和图里。**

### 3.3 节点的旗标名

`_build_workflow` 用 `f"{node.node_type.value}_{node.id}"` 做旗标（如 `llm_eba75e0b-21b7-...`）。这个旗标后来在两个地方露脸：

1. `stream` 的 chunk 的 key：`{"llm_eba75e0b-...": {...}}`——`debug_workflow` 里 `next(iter(chunk))` 拆的就是它
2. 前端画布用 `node_data.id` 对号入座点亮节点

---

## 4. 核心元素三：Edge（边）——调度规则

边回答"**一个节点跑完之后，下一个跑谁**"。三种：

| 边类型 | API | 调度语义 | 你项目在哪用 |
|---|---|---|---|
| 固定边 | `add_edge("a", "b")`；列表形式 `add_edge(["b","c","d","e","f"], "end")` 表达汇聚 | A 完 → 必跑 B | `_build_workflow`（工作流图全是这种） |
| 入口/出口 | `set_entry_point(x)` / `set_finish_point(y)`（新版本等价于连 `START`/`END` 特殊节点） | 从哪开始、到哪算完 | `_build_workflow` 第 7 步 |
| **条件边** | `add_conditional_edges("a", 路由函数)` | A 完 → **运行时动态**决定去 B 还是 C | **Agent 图！** `_tools_condition` |

### 4.1 汇聚边 = 并行的开关

`add_edge(["b","c","d","e","f"], "end")` 的含义：**end 要等 b/c/d/e/f 全部完成才开始**。同时 b/c/d/e/f 之间没有先后约束——引擎会**并行**执行它们。你的 5 分支并行，就是"llm 的出边指向 5 个节点 + 这 5 个节点的边共同指向 end"表达出来的。

### 4.2 条件边：工作流和 Agent 的分水岭

看 Agent 里那个路由函数：

```python
def _tools_condition(self, state) -> Literal["tools", "__end__"]:
    if len(state["messages"][-1].tool_calls) > 0:
        return "tools"      # 模型还想调工具 → 继续循环
    return END              # 模型说完了 → 结束
```

固定边的图：路线**编译期定死**（工作流，可控）；
条件边的图：路线**运行时由数据/模型决定**（Agent，灵活）。

> **"工作流 vs Agent"的区别，在 LangGraph 层面就是"你用了哪种边"。**

---

## 5. 编译：从图纸到机器

```python
graph = StateGraph(WorkflowState)   # ① 拿着"状态模板"造一张空图
graph.add_node(...)                 # ② 注册节点（8种）
graph.add_edge(...)                 # ③ 接线（含入口/出口/汇聚合并）
graph.compile()                     # ④ 编译 → CompiledStateGraph
```

### 5.1 CompiledStateGraph 的主要属性

| 属性 | 是什么 | 对应你项目的东西 |
|---|---|---|
| `nodes` | 旗标名 → 节点可调用体 的字典 | `"llm_eba75e0b-...": LLMNode实例` |
| state schema | 状态的字段 + reducer 契约 | `WorkflowState` 的 3 个字段 |
| channels | 内部"传输通道"，每个 state 字段一条，负责按 reducer 合并写入 | `inputs` / `outputs` / `node_results` 三条 |
| 入口/出口 | 调度从哪开始、到哪停 | start / end 节点旗标 |

### 5.2 最重要的性质：它是一个 Runnable

`compile()` 的产物实现了 LangChain 的 Runnable 协议——**自带 `invoke` / `stream` / `batch`**。这就是为什么 `WorkflowTool` 能"协议对协议"直接转手：

```python
def _run(self, **kwargs):        # 同步：一口气跑完
    return self._workflow.invoke({"inputs": kwargs})

def stream(self, input, ...):    # 流式：一拍一拍吐
    return self._workflow.stream({"inputs": input})
```

---

## 6. 怎么执行：一"拍"一拍地走（superstep 模型）

### 6.1 引擎主循环

`invoke`/`stream` 内部是同一个循环，每走一**拍**（superstep）做三件事：

```
① 取出当前待跑的节点集合 → 并行执行（各自基于当前state干活）
② 把所有结果按 reducer 合并进共享状态
③ 沿边算出下一拍该跑谁 → 没有了 → 结束
```

### 6.2 拿你的图实走一遍

```
第0拍: inputs={query, location} 写入白板
       待跑: [start]

第1拍: start 执行（把inputs原样放进state）
       node_results 追加 start 的结果
       沿边 → 待跑: [dataset_retrieval]

第2拍: dataset_retrieval 执行（查知识库）
       沿边 → 待跑: [llm]

第3拍: llm 执行（渲染prompt、调大模型，耗时几秒）
       llm的出边指向5个节点 → 待跑: [template, code, 谷歌, 高德, http]
       ↑ 5个节点进入同一拍 → 引擎【并行】执行它们

第4拍: 5个节点陆续返回 → node_results 按 left+right 追加 → 一份不丢
       5条边共同指向end → 待跑: [end]

第5拍: end 执行，收集outputs → 连到END → 循环结束
```

### 6.3 stream 的 chunk = 每一拍的增量

`stream` 模式下，**每拍产生一个 chunk**：

```python
{"llm_eba75e0b-...": {"node_results": [NodeResult(...)]}}
#  ↑ 节点旗标         ↑ 该节点写入state的增量
```

`handle_stream` 里的两行拆包对应关系：

```python
first_key = next(iter(chunk))              # "llm_eba75e0b-..."（旗标）
node_result = chunk[first_key]["node_results"][0]   # 这个节点的运行结果
```

> 注：并行拍如果多个节点同拍完成，一个 chunk 里可能有多组更新；单节点拍就是一组。你的图 5 分支同拍完成，实际收到的 chunk 顺序以引擎实际执行为准。

### 6.4 "拉一下走一格"的最终解释

`stream()` 返回的生成器内部**就是这个 superstep 循环**：

- 第一次 next → 执行第 1 拍 → yield 增量 → 暂停
- 第二次 next → 第 2 拍 → yield → 暂停
- ……
- 循环结束 → 生成器枯竭

之前文档里的"拉拽链"（Flask → generate → handle_stream → 图引擎）推的就是这个循环的曲柄。**节点执行的时间（比如 llm 的几秒钟）就消耗在两次拉之间。**

---

## 7. 与项目代码的完整对应总表

| LangGraph 概念 | 概念含义 | 你项目的落点 |
|---|---|---|
| State 模板 | 黑板 + 合并规则 | `WorkflowState`（3 字段 + 2 reducer） |
| Node | 工位函数 | 8 种 `XxxNode.invoke`，旗标 `类型_id` |
| 固定边 | 编译期定死的路线 | `_build_workflow` 翻译 edges 的产物 |
| 条件边 | 运行时动态路由 | Agent 的 `_tools_condition` |
| 汇聚边 | 并行 + 等全部完成 | 5 分支共同指向 end |
| `compile()` | 图纸 → 机器，执行一次 | `WorkflowTool.__init__` 里 |
| `invoke` | 一口气跑完 | `WorkflowTool._run`（Agent 用） |
| `stream` | 一拍一拍吐 | `WorkflowTool.stream`（debug 用） |
| chunk | 每拍的状态增量 | `{旗标: 增量}`，debug 逐个推前端 |
| reducer | 并行写合并规则 | `_process_dict` / `_process_node_results` |

---

## 8. 常见迷惑 Q&A（本篇知识点的实战沉淀）

**Q1：调用 `workflow_tool.stream(inputs)` 时，节点执行了吗？**
没有。那一刻只做了三件事：把 inputs 打包成 `{"inputs": ...}`、引擎建初始状态并排好第一批任务、返回迭代器。第一次被"拉"才执行第一拍。

**Q2：什么时候"拉"？**
从 handler `return FlaskResponse` 之后、Flask 往网络写响应正文的整个期间——写完一块就拉下一块，直到生成器枯竭（正常结束）或连接断开（火熄半路）。用户只调用了一次；"拉"是 Flask 在同一条连接上分段写正文，不是用户多次调用。

**Q3：nodes/edges 什么时候被用掉？**
`_build_workflow` 执行的那一刻，一次性消化：nodes 变成节点对象（配置装进 `node_data`），edges 变成图里的线和入口出口。`compile()` 完成后原始列表退休，运行时引擎只认编译后的图。

**Q4：`Workflow` 都继承 `BaseTool` 了，为什么还要在类里建图？**
BaseTool 只是合同（name/description/args_schema/`_run` 空方法），回答"别人怎么调我"；图程序是发动机，回答"调了之后活怎么干"。`_run` 那一行就是把外壳收到的调用转手交给发动机。

**Q5：并行分支的结果会不会互相覆盖？**
不会——`node_results` 字段挂了 `left + right` 追加型 reducer，5 个节点的结果全部追加保留。覆盖只发生在"没挂 reducer 或 reducer 写成 return right"的字段上。

**Q6：为什么 chunk 的 key 是 `llm_eba75e0b-...` 这种格式？**
构造时 `add_node(旗标, 节点)` 用的名字是 `f"{node_type.value}_{id}"`，stream 的 chunk 就用这个旗标做 key。前端靠 `node_data.id` 对号入座。

---

## 9. 动手实验

### 实验 1：亲眼看见 reducer 的作用（5 分钟）

把 `_process_node_results` 临时改成 `return right`，重启服务，跑一次 5 分支工作流的调试，观察 `state` 里的 `node_results`——只剩最后完成的那个节点的结果，其他 4 个丢了。改回 `left + right`，5 个全在。**这就是并行写冲突与合并规则的现场。**

### 实验 2：50 行手写 mini-LangGraph（半天，强烈推荐）

只支持固定边，理解型代码：

```python
import threading

class MiniGraph:
    def __init__(self, state_schema): self.nodes = {}; self.edges = {}; self.state = {}

    def add_node(self, name, fn): self.nodes[name] = fn
    def add_edge(self, sources, target):
        for s in (sources if isinstance(sources, list) else [sources]):
            self.edges.setdefault(s, []).append(target)

    def invoke(self, inputs):
        current = ["start"]
        while current:
            results = {}
            threads = []
            for name in current:                       # 同一拍：并行执行
                t = threading.Thread(
                    target=lambda n=name: results.update({n: self.nodes[n](self.state)}))
                t.start(); threads.append(t)
            for t in threads: t.join()
            self.state.update(results)                 # 简化版"reducer合并"
            nxt = []                                   # 沿边推下一拍
            for name in current: nxt += self.edges.get(name, [])
            current = [n for n in nxt if n != "end"]
        return self.state
```

写完这个，回头看 `_build_workflow` 的每一行都会有"原来如此"的感觉——它做的是同样的事，只是把并行调度、reducer、错误处理做得工业级健壮。

### 实验 3：观察 superstep（可选）

在两个节点的 `invoke` 开头各加一行 `print(f"{time.time()} {self.node_data.title} 开始")`，跑调试看打印顺序：start → 知识库检索 → 大模型 → 然后五个节点的时间戳几乎相同（并行）→ 结束。

---

## 10. 复盘用的一页纸

| 要点 | 一句话 |
|---|---|
| LangGraph 是什么 | 共享状态驱动的流水线引擎：调度、并行、合并 |
| State | 全图一块黑板；每个字段挂 reducer 定义"并行写听谁的" |
| Node | state进、增量出的函数；配置装在自己肚子里（node_data） |
| Edge | 固定边=定死路线；条件边=运行时路由（工作流/Agent的分水岭）；汇聚边=并行 |
| compile | 图纸→机器；产物是 Runnable（invoke/stream 自带） |
| 执行 | superstep 循环：并行执行一拍 → reducer 归纳 → 沿边推下一拍 |
| stream chunk | 每拍增量 `{旗标: 增量}`；拉拽链的最终目的地 |
| 三个元素的关系 | State 决定"怎么共享"，Node 决定"干什么"，Edge 决定"什么顺序" |

**与前两篇的衔接**：第一篇讲"图怎么变成工具"（编译+适配），第二篇讲"工具的合同与 function calling"（四要素+点菜炒菜），本篇拆开最里面那台机器——**"发动机"的内部构造与运转原理**。三篇合起来，从画布 JSON 到浏览器亮灯的整条链路全部打通。
