# 从 `Workflow(BaseTool)` 看工作流引擎的设计思想

> 源码：`internal/core/workflow/workflow.py` 的 `class Workflow(BaseTool)`
> 关联代码：`internal/service/workflow_service.py` 的 `debug_workflow` / `_validate_graph`
> 整理日期：2026-10-15

---

## 0. 一句话总纲

这个类同时是 **编译器** 和 **适配器**：

- **编译器**：把数据库里的声明式图数据（nodes/edges JSON）编译成可执行程序（LangGraph `CompiledStateGraph`）
- **适配器**：把这张图包装成 LangChain 的 Tool，让它进入"一切可调用物"的生态

理解了这两层，就理解了 Dify / Coze / n8n 这类工作流产品的核心抽象。

---

## 1. 现象层：一个类，三种身份

```python
class Workflow(BaseTool):
    # 身份一：BaseTool —— 对 Agent 而言"它是个工具"
    # 身份二：CompiledStateGraph —— 对内部而言"它是个可执行的状态图"
    # 身份三：数据快照的消费者 —— 对数据库而言"它是 nodes/edges JSON 的唯一解释者"
```

三个身份对应三种消费者：

| 消费者 | 看到的身份 | 走的入口 |
|---|---|---|
| Agent（function calling） | 一个有 name/description/args_schema 的工具 | `_run` |
| 调试接口（SSE 推给前端画布） | 逐节点吐进度的流式程序 | `stream` |
| 数据库里的 draft_graph | JSON 图数据的编译产物 | `__init__` → `_build_workflow` |

**设计启示**：当一个对象需要被多种消费者使用时，不要写三套逻辑，而是找到每种消费者的"原生协议"，把核心逻辑包进协议要求的接口里。

---

## 2. 核心思想一：声明式与命令式分离（数据 → 程序的编译）

### 2.1 代码证据

```python
def _build_workflow(self) -> CompiledStateGraph:
    graph = StateGraph(WorkflowState)          # 空状态机
    for node in nodes:                         # 数据 → 节点注册
        graph.add_node(node_flag, NodeClasses[NodeType.XXX](node_data=node))
    for edge in edges:                         # 数据 → 接线
        ...
    graph.set_entry_point(start_node)          # 数据 → 入口/出口
    graph.set_finish_point(end_node)
    return graph.compile()                     # 编译产物，可反复执行
```

数据库里存的是**声明**（"有哪些点、哪些边、谁连谁"），`_build_workflow` 把它**编译**成**程序**（沿边调度的可执行状态机）。

### 2.2 这个思想在计算机科学里无处不在

| 声明式数据 | 编译产物 | 执行者 |
|---|---|---|
| 正则表达式字符串 | 有限状态机 | 字符串匹配引擎 |
| SQL 语句 | 查询计划树 | 数据库执行器 |
| Kubernetes YAML | 集群实际状态 | 控制器循环 |
| HTML/CSS | 渲染树 | 浏览器排版引擎 |
| **画布上的流程图（JSON）** | **StateGraph** | **LangGraph 调度器** |

### 2.3 为什么要把"编译"单独拎出来

1. **校验前移**：图对不对（孤岛节点、类型错误）在编译期就能发现，不用等到运行时。你项目里 `_validate_graph` 在入库前做校验，`_build_workflow` 在构造时再校验一次，双保险。
2. **优化前移**：`parallel_edges` 分组合并——多条边汇聚同一终点时合并注册，LangGraph 才能识别出你的 5 条分支可以并行。这类优化做一次，N 次运行受益。
3. **成本前移**：`__init__` 里 `self._workflow = self._build_workflow()` **构造时编译一次并缓存**，之后每次调用（`_run`/`stream`）直接用编译产物，零重复开销。这就是"解释执行"和"编译执行"的差别。

### 2.4 数据与行为分离带来的架构自由

- 换执行引擎（LangGraph → 自研调度器）：只重写 `_build_workflow`，存储格式不动、上层接口不动
- 换存储格式（JSON → 表结构）：只改数据来源，编译逻辑不动
- 版本管理：图就是数据，可以存快照（`WorkflowResult.graph`）、可以做 diff、可以回滚重跑

> **金句**：把"程序"降格为"数据"，才能对它做版本管理、可视化编辑和平台化运营。

---

## 3. 核心思想二：面向协议编程（接口是生态的通行证）

### 3.1 为什么继承 `BaseTool`

LangChain 生态里"可以被调用的东西"统一遵循 **Runnable / Tool 协议**：有 `invoke`/`stream`/`batch`，Tool 还要求 `name` + `description` + `args_schema` + `_run`。

```python
def _run(self, *args, **kwargs) -> Any:            # 履行 BaseTool 的合同
    return self._workflow.invoke({"inputs": kwargs})
```

`_run` 的全部实现就一行——因为 `_workflow` 本身也是 Runnable，**协议对协议，直接转手**。

### 3.2 统一协议 → 自由组合

协议统一后，Agent 做选择时不需要知道工具背后是什么：

```
Agent 的工具箱:
  [google_serper 搜索]  [gaode 天气]  [我的工作流 ← 里面也藏着模型、HTTP、代码节点]
```

三种粒度完全不同的东西在 Agent 眼里地位平等。更进一步，**工作流里可以再嵌工作流**——图编译成工具，工具又成为更大的图的节点，递归组合。

### 3.3 和"调大模型"的区分（容易混淆的点）

`invoke`/`stream` 是**协议方法**，语义是"执行眼前这个对象"：

- 对象是 `ChatOpenAI` → 恰好是发 HTTP 请求调模型
- 对象是 `StateGraph` → 是走一遍图，内部可能调 0~N 次模型

嵌套关系（以本项目为例）：

```
workflow_tool.stream()            图的 stream（协议层）
  └─ LLMNode.invoke()             节点的 invoke（协议层）
       └─ ChatOpenAI.stream()     模型的 stream（★ 唯一真正调模型的地方）
```

> **金句**：协议让"怎么调"被统一，实现让"调了发生什么"各不相同。

---

## 4. 核心思想三：Schema 自描述（单一事实来源，SSOT）

### 4.1 代码证据

```python
@classmethod
def _build_args_schema(cls, workflow_config) -> type[BaseModel]:
    # 从开始节点的 inputs 现场推导工具的参数 schema
    inputs = next((node.inputs for node in nodes if node.node_type == NodeType.START), [])
    for input in inputs:
        fields[input.name] = (
            field_type if input.required else Optional[field_type],
            Field(description=input.description),
        )
    return create_model("DynamicModel", **fields)   # 运行时动态造类
```

### 4.2 为什么这是关键设计

**function calling 的工作原理**：Agent 调工具前，LangChain 会把 `args_schema` 转成 JSON Schema 塞进 prompt，模型照着 schema 决定传什么参数。所以 schema 就是"模型的使用说明书"。

这份说明书**不是另写的，是从图推导的**：

- 画布上给开始节点加一个输入变量 → 工具 schema 自动多一个字段 → Agent 自动知道要传它
- 图改了，说明书**不可能**忘改，因为它根本不存在"第二份"

这就是 **DRY（Don't Repeat Yourself）** 的严格版：**知识的每一个片段，在系统里有且只有一个权威表示（Single Source of Truth），其余全是派生**。

### 4.3 对手写两份的方案推演一遍

| 方案 | 图改动后 | 后果 |
|---|---|---|
| 手写 schema + 手写图 | 两处都要改 | 忘改一处 → Agent 传错参数 → 运行时才炸 |
| 从图推导 schema（本项目） | 只改图 | schema 永远同步，pydantic 还在运行时兜底校验 |

`create_model("DynamicModel", **fields)` 是 pydantic 的**运行时元编程**：每个工作流参数集不同，类必须现场造。这招在"动态表单""动态配置"场景通用。

---

## 5. 核心思想四：一次封装，多种消费

同一个 `WorkflowTool` 实例，三种消费路径：

```
                    ┌→ stream() ─→ debug_workflow ─→ SSE 逐节点推前端（给人看）
WorkflowTool 实例 ──┼→ _run() ───→ 发布后的应用同步调用（给程序用）
                    └→ 作为 BaseTool 挂进 Agent 的工具箱（给模型选）
```

配套的可观测性设计也值得注意（`debug_workflow` 里）：

- 运行前先落一条 `WorkflowResult`（RUNNING），**快照当时的 draft_graph** → 事后能回答"那次跑的是哪个版本的图"
- 每个节点的 `NodeResult`（状态/输入/输出/latency）逐条留存 → 可定位挂在哪个节点
- `is_debug_passed` 门禁 → 调试通过才允许发布

> **金句**：平台化的本质是"一个内核，多个门面"；可观测性是门面的地基。

---

## 6. 状态机视角：`WorkflowState` 是共享黑板

所有节点的输入输出都通过 `{"inputs": kwargs}` 这个约定进出的 `WorkflowState` 传递：

- **节点之间不直接调用**，只读写共享 state——这是 **Blackboard（黑板）模式**
- 好处一：**天然支持并行**（你的 5 条分支各自读写自己的 key，互不干扰）
- 好处二：**可恢复/可重放**——state 是纯数据，快照下来就能断点续跑
- 好处三：**解耦**——删掉一条分支，别的分支毫无感知

对比：如果节点之间互相传参（A 的返回值直接作 B 的入参），就变成了硬编码的调用链，画布上"拖根线"这种产品形态就不存在了。

---

## 7. 动手练习（把思想变成肌肉记忆）

### 练习 1（入门）：观察 schema 推导

建一个只含 start + end 的工作流，开始节点分别加 1 个、2 个、3 个输入变量，POST 保存后打印 `_build_args_schema` 生成的 `model_json_schema()`，确认字段随图变化。

### 练习 2（进阶）：写一个 100 行以内的迷你 StateGraph

不依赖 LangGraph，用 dict + 拓扑排序实现：`add_node` / `add_edge` / `compile` / `invoke`，支持并行分支汇聚。写完再回头看 `_build_workflow`，每一行都会有新的体会。

### 练习 3（实战）：让 Agent 真的调用这个工具

用 LangChain 的 `create_tool_calling_agent` 挂上这个 WorkflowTool，问"上海天气怎么样"，观察三件事：

1. 模型传的参数是否严格遵守 args_schema（schema 自描述生效）
2. Agent 的 function call 日志里 name 是 `tool_call_name`（数据库字段，不是类名）
3. 把工作流里某个节点删掉重存，Agent 无需任何改动（协议隔离生效）

### 练习 4（架构）：对照同类产品

读 Dify 开源版的 `WorkflowService`（或 Coze 的公开资料），找出它对应"编译、适配、SSOT、快照"四件事的代码位置，体会不同团队对同一抽象的不同取舍。

---

## 8. 复盘用的一页纸

| 思想 | 在代码里的落点 | 一句话 |
|---|---|---|
| 声明式→命令式 | `_build_workflow` | 图是数据，编译成程序，才能平台化 |
| 面向协议 | `BaseTool` 继承 + `_run` 一行实现 | 接口是生态的通行证 |
| SSOT | `_build_args_schema` 从 start 节点推导 | 说明书不写第二份 |
| 多种消费 | `_run` / `stream` / Agent 工具箱 | 一个内核，多个门面 |
| 黑板模式 | `WorkflowState` 共享状态 | 节点互不调用，只读写共享黑板 |
| 可观测性 | `WorkflowResult` 快照 + NodeResult 留痕 | 留下证据链，问题可回溯 |

**最容易混淆的概念修正**：`invoke`/`stream` ≠ 调大模型。它们是"执行"协议——对象是模型时恰好是调模型，对象是图时是跑一遍图。
