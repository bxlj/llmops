# Agent 核心模块解读笔记

> 对应代码:`internal/core/agent/`
> 日期:2026-10-30

---

## 一、总览:这个包解决什么问题

Agent 模块是整个 LLMOps 平台的"执行引擎":用户在应用编排里配置好 LLM、工具、知识库、预设提示词之后,**真正跑一次对话、产生答案**的就是这个包。

它要同时解决三个问题:

1. **怎么跑**:用 LangGraph 把"预处理 → 记忆召回 → LLM → 工具"组织成一个可循环的状态图;
2. **怎么吐**:LLM 是流式输出的,工具调用是分步的,中间每个事件都要实时推给前端(SSE);
3. **怎么停/怎么保命**:超时、用户手动停止、报错、超过最大迭代次数,都要能干净地终止。

解决思路一句话:**生产者-消费者模式** —— LangGraph 图在一个子线程里跑(生产者),把每一步都包装成 `AgentThought` 事件塞进队列;主线程 `listen` 队列(消费者),`yield` 给上层做 SSE 推流。

### 文件地图

```
internal/core/agent/
├── __init__.py                    # 空文件
├── agents/
│   ├── __init__.py                # 导出 BaseAgent / FunctionCallAgent / AgentQueueManager
│   ├── base_agent.py              # 智能体基类:线程+队列的骨架,invoke/stream 的公共实现
│   ├── function_call_agent.py     # 具体实现:基于 Function Call 的 LangGraph 状态图
│   └── agent_queue_manager.py     # 队列管理器:事件的生产/消费/停止/超时/心跳
└── entities/
    ├── agent_entity.py            # AgentConfig(配置)、AgentState(图状态)、系统提示词模板
    └── queue_entity.py            # QueueEvent(事件枚举)、AgentThought(事件实体)、AgentResult(最终结果)
```

依赖方向:`agents/` 依赖 `entities/`,外部通过 `from internal.core.agent.agents import FunctionCallAgent` 使用。

---

## 二、entities 层:数据结构先行

### 2.1 `queue_entity.py` —— 流式过程中的三种数据

**`QueueEvent`(事件枚举)** —— 队列里流动的每一种消息类型:

| 事件 | 含义 | 产生位置 |
|---|---|---|
| `LONG_TERM_MEMORY_RECALL` | 长期记忆召回完成 | 记忆召回节点 |
| `AGENT_THOUGHT` | LLM 决定调用工具(推理过程) | llm 节点 |
| `AGENT_MESSAGE` | LLM 生成的文本 token(**增量,靠 id 叠加**) | llm 节点 |
| `AGENT_ACTION` | 普通工具执行完成 | tools 节点 |
| `DATASET_RETRIEVAL` | 知识库检索工具执行完成 | tools 节点 |
| `AGENT_END` | 智能体正常结束 | 各节点 |
| `STOP` / `ERROR` / `TIMEOUT` | 三种异常终止 | 队列管理器 |
| `PING` | 心跳保活 | 队列管理器 |

**`AgentThought`(单次事件)** —— 队列里流动的最小单元。关键字段:

- `id`:事件 id。**同一个事件的多次发布共用同一个 id**(如 AGENT_MESSAGE 的每个 token 片段都用同一个 id),不同事件 id 不同——这是后面"增量叠加"的依据;
- `event` + `thought`/`observation`:事件类型 + 对应内容;
- `tool`/`tool_input`:工具事件专用;
- `message`:当前推理使用的完整消息列表(快照);
- token 数/单价/`latency`:计费与耗时统计,`AgentThought` 层是单步的,`AgentResult` 层是汇总的。

**`AgentResult`(最终结果)** —— 一次性调用结束后返回的聚合体:`query`(原始提问)、`answer`(完整答案)、`agent_thoughts`(全部推理步骤)、`status`/`error`(终止状态)、总耗时与总 token。

### 2.2 `agent_entity.py` —— 配置与图状态

**`AgentConfig`** —— 创建一个 Agent 需要的全部配置:

```python
user_id: UUID                          # 谁在调用(用于停止权限校验)
invoke_from: InvokeFrom                # 调用来源:WEB_APP / DEBUGGER / API
max_iteration_count: int = 5           # 工具调用循环的最大轮数
preset_prompt: str                     # 用户编排时写的预设提示词
enable_long_term_memory: bool          # 是否开启长期记忆
tools: list[BaseTool]                  # 绑定的工具列表
review_config: dict                    # 输入/输出敏感词审核配置
```

**`AgentState`(继承 `MessagesState`)** —— LangGraph 图的全局状态。`MessagesState` 自带 `messages: list[AnyMessage]` 且对 messages 做**追加合并**(Annotated reducer);在此基础上扩展了四个字段:

```python
task_id: UUID           # 本次运行的任务 id(队列的索引、停止标志的索引)
iteration_count: int    # 已迭代轮数,llm 节点每跑一次 +1
history: list[AnyMessage]      # 短期记忆(窗口内的历史对话)
long_term_memory: str          # 长期记忆(历史会话的摘要)
```

**`AGENT_SYSTEM_PROMPT_TEMPLATE`** —— 系统提示词模板,声明了 Agent 的五条行为规则(预设任务、工具调用、记忆利用、知识库检索、简洁性),用 `{preset_prompt}` 和 `{long_term_memory}` 两个占位符在运行时填充。

---

## 三、AgentQueueManager:事件总线 + 保险丝

`agents/agent_queue_manager.py`。一句话:**它是生产者和消费者之间那条"传送带"的管理者**,同时兼职超时检测、心跳保活、跨进程停止。

### 3.1 队列的存取:`queue()`(agent_queue_manager.py:148)

- 内部用 `_queues: dict[str, Queue]` 保存"task_id → 队列"的映射,**每个任务一条独立队列**;
- 第一次取某 task_id 的队列时,顺手往 Redis 写一个 `generate_task_belong:{task_id} = "account-{user_id}"`(1800s 过期)——记录"这个任务是谁发起的",供停止接口校验权限。

### 3.2 生产:`publish()`(agent_queue_manager.py:86)

- 把 `AgentThought` 放进队列;
- **终止型事件**(`STOP`/`ERROR`/`TIMEOUT`/`AGENT_END`)额外触发 `stop_listen()` —— 往队列再塞一个 `None` 作为"毒丸"(sentinel),消费者的循环看到 `None` 就 `break`。

### 3.3 消费:`listen()`(agent_queue_manager.py:40)

生成器,`while True` 循环 `get(timeout=1)`,拿到数据就 `yield`,拿到 `None` 就结束。`finally` 块里做了三件保命的事:

1. **心跳**:每累计 10 秒往队列发一个 `PING` 事件 —— 上层 SSE 连接靠它保活,防止前端/代理因长时间无数据而断开;
2. **超时**:总耗时超过 600 秒,发布 `TIMEOUT` 事件 → 间接触发毒丸 → 循环终止;
3. **停止检测**:每轮查一次 Redis 的 `generate_task_stopped:{task_id}`,存在则发布 `STOP` 事件终止。

> 注意 PING 事件被 yield 出去后,消费方(BaseAgent.invoke)会**跳过它不记录**;而在 SSE 层它就是一条纯粹的保活消息。

### 3.4 跨进程停止:`set_stop_flag()`(agent_queue_manager.py:117)⭐ 面试高频点

用户点"停止生成"按钮时,HTTP 请求到达的是**另一个进程**,它拿不到这个 Agent 实例和内存队列,怎么办?—— 用 Redis 做跨进程信箱:

```
停止接口进程                                Agent 运行进程
    │ set_stop_flag(task_id,...)                │
    │ 1. 查 belong 键:任务存在吗?              │
    │ 2. 校验归属:account-{user_id} 匹配吗?    │
    │ 3. setex(stopped 键, 600, 1)             │
    │                              listen 循环里 _is_stopped → True
    │                              → 发布 STOP → 毒丸 → 终止
```

三道防线的设计:任务不存在就不设标志(防误操作);归属不匹配就不设(防止 A 用户停掉 B 用户的任务);600s 过期(和 listen_timeout 一致,不留垃圾键)。

---

## 四、BaseAgent:线程 + 队列的骨架

`agents/base_agent.py`。`BaseAgent(Serializable, Runnable)` 继承 LangChain 的 `Runnable`,所以它可以无缝接入 LCEL 链。核心是两个私有属性:

```python
_agent: CompiledStateGraph        # LangGraph 编译后的图(子类构建)
_agent_queue_manager: AgentQueueManager
```

### 4.1 `stream()`:把"图的执行"搬到子线程(base_agent.py:105)

```python
thread = Thread(target=self._agent.invoke, args=(input,))
thread.start()
yield from self._agent_queue_manager.listen(input["task_id"])
```

为什么要子线程?因为 `stream()` 是一个**生成器**,消费节奏由上层控制(前端慢、网络慢都会拖慢它);而图的执行必须全速跑完。**子线程负责生产,主线程负责消费**,两边通过队列解耦,互不阻塞。

调用前还做了字段兜底:`task_id` 缺省生成 uuid、`history` 缺省空列表、`iteration_count` 缺省 0。

### 4.2 `invoke()`:流式的"聚合器"(base_agent.py:55)

一次性调用,内部就是消费 `self.stream()` 并把事件流折叠成 `AgentResult`:

- **`AGENT_MESSAGE` 事件按 id 叠加**:同一 `event_id` 的后续片段,`thought`/`answer` 累加到首个事件上(`model_copy(update=...)`),同时累进 `agent_result.answer` —— 这就是"同 id 增量事件"的合并逻辑;
- **其他事件直接按 id 覆盖**;
- `STOP`/`TIMEOUT`/`ERROR` 会改写 `agent_result.status` 和 `error`;
- 最后填 `message`(取最后一条 AGENT_MESSAGE 的消息快照)、`latency`(各步耗时求和)。

> 设计要点:**`stream()` 是唯一的事实来源,`invoke()` 只是流式的一种消费方式**。上层做 SSE 也好、一次性调用也好,走的都是同一条事件流,保证两种模式的输出完全一致。

---

## 五、FunctionCallAgent:LangGraph 状态图

`agents/function_call_agent.py`,继承 `BaseAgent`,实现 `_build_agent()`。

### 5.1 图结构

```
                    ┌─────────────────────────────────────────┐
 START ──► preset_operation ──(条件边)──► long_term_memory_recall ──► llm
                    │                                              ▲  │
                    │(触发审核,直接 END)                          │  │(有 tool_calls)
                    ▼                                              │  ▼
                   END                                           tools
```

- `preset_operation` →(条件边)→ `long_term_memory_recall_node`:最后一条消息若是 **AI 消息**,说明审核拦截后已经给出预设响应,直接 END;否则进入记忆召回;
- `long_term_memory_recall_node → llm`:固定边;
- `llm` →(条件边 `_tools_condition`)→ `tools` 或 `END`:最后一条 AI 消息里有 `tool_calls` 就去执行工具,否则正常结束;
- `tools → llm`:固定边,工具结果喂回 LLM,**这就是 ReAct 循环**。

### 5.2 四个节点逐个看

**`_preset_operation_node`(输入审核)**:如果开启了审核且 query 命中敏感词,直接发布 `AGENT_MESSAGE`(预设回复)+ `AGENT_END`,返回 `{"messages": [AIMessage(preset_response)]}` —— 返回 AI 消息正是给条件边的信号。没命中则返回空列表(不改变状态)。

**`_long_term_memory_recall_node`(拼 prompt)**:组装最终发给 LLM 的消息列表:
`SystemMessage(模板填充了 preset_prompt + long_term_memory)` + `history`(成对校验,奇数条直接报错) + 当前 `HumanMessage`。
细节:用 `RemoveMessage(id=human_message.id)` 先删掉原句、再 append 一条新的 `HumanMessage(human_message.content)` —— 因为删了原消息后 `messages[-1]` 的 id 已失效,必须重建才能追加成功。

**`_llm_node`(核心循环体)**,按顺序做了五件事:
1. **迭代次数熔断**:`iteration_count > max_iteration_count` 时,发布"超过迭代上限"的 `AGENT_MESSAGE` + `AGENT_END`,返回 AI 消息(条件边据此走 END)——防止模型陷入无限调工具的死循环;
2. **绑定工具**:检测 `llm.bind_tools` 存在且 `tools` 非空才绑定(`strict=False`);
3. **流式生成**:`llm.stream()` 逐 chunk 累加成 `gathered`(LangChain 的 AIMessageChunk 支持 `+=` 合并);
4. **判定生成类型**:首个 chunk 决定 `generation_type` —— 有 `tool_calls` 是 `"thought"`(推理),有 `content` 是 `"message"`(答案);
5. **按类型发布事件**:`message` 型每个 chunk 发布一条 `AGENT_MESSAGE`(同 id,增量);输出审核在这里逐 chunk 做敏感词替换(`re.sub` → `**`);`thought` 型发布一条 `AGENT_THOUGHT`(内容是 tool_calls 的 JSON)。

**`_tools_node`(执行工具)**:工具列表转字典 → 提取 `tool_calls` → 逐个 `tool.invoke(args)`,**单工具异常不中断,把错误信息字符串当工具结果**喂回 LLM(让模型自己决策下一步,而不是整个任务崩掉)→ 组装 `ToolMessage` → 按工具名区分发布 `AGENT_ACTION` 或 `DATASET_RETRIEVAL` 事件。

### 5.3 一轮完整对话的时序

```
用户提问 ─► stream() 起子线程跑图
  preset_operation(不命中)
  memory_recall(发布 LONG_TERM_MEMORY_RECALL)
  llm 第1轮 ─► 决定调工具 ─► 发布 AGENT_THOUGHT ─► tools
  tools ─► 执行 ─► 发布 AGENT_ACTION/DATASET_RETRIEVAL ─► 回到 llm
  llm 第2轮 ─► 直接生成答案 ─► 逐 chunk 发布 AGENT_MESSAGE ─► 发布 AGENT_END
listen() 消费所有事件 ─► SSE 推给前端 ─► 收到毒丸 None,生成器结束
```

---

## 六、值得记住的设计点(面试/复盘素材)

1. **生产者-消费者 + 毒丸终止**:子线程跑图、队列传事件、`None` 作终止哨兵 —— 用最朴素的 `queue.Queue` 解耦了 LangGraph 的同步执行和上层的流式消费。
2. **Redis 的三个角色**:任务归属登记(`belong` 键,谁发起的)、停止信箱(`stopped` 键,跨进程通信)、配合 600s 超时形成三道终止防线。
3. **事件 id 的两种语义**:`AGENT_MESSAGE` 同 id = 增量片段(靠叠加还原全文);其他事件同 id 不存在,`invoke` 里直接覆盖。理解了这一点,前端合并 SSE 分片和后端 `invoke` 聚合就是同一套逻辑。
4. **心跳 PING 与超时 TIMEOUT 都由消费方(listen)自己产生**——生产端卡死也能被兜住,因为超时判断在消费循环里,不依赖图正常退出。
5. **三处优雅降级**:工具执行失败 → 错误信息当工具结果喂回 LLM;迭代超限 → 熔断并友好提示;历史消息奇数条 → 发布错误事件并抛异常(这是唯一快速失败的点,因为格式错误属于上游数据 bug,重试无意义)。
6. **`stream()` 为纲,`invoke()` 为目**:两种调用模式共享同一条事件流,避免"流式/非流式两套逻辑"的经典维护坑(Dify 同款设计)。

### 可自测的问题

- 为什么 `publish` 终止事件后还要额外塞一个 `None`,而不是让消费者判断事件类型?(答:消费者的 `get` 是泛化的,不解析语义;且 PING/超时/停止都由 listen 自己判断,统一用哨兵最简单可靠)
- 如果去掉子线程直接在当前线程跑图,`stream()` 会出现什么问题?(答:图的 `invoke` 是阻塞的,会在所有事件产生完之后才返回,生成器失去流式意义)
- `set_stop_flag` 为什么要校验 `belong` 键里的归属?(答:防止越权——任何拿到 task_id 的用户都能停别人的任务)
