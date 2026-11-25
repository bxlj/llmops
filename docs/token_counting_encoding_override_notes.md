# 第三方供应商 Token 统计报错：tiktoken 编码器兜底与模型定价 metadata 接入

> 日期：2026-11-15
> 涉及：`internal/core/language_model/providers/{moonshot,zhipu,tongyi}/chat.py` / `internal/core/language_model/entities/model_entity.py` / `internal/core/agent/agents/{react_agent,function_call_agent}.py` / `internal/service/language_model_service.py`
> 关联：模型 yaml 新增 `metadata.pricing`（11 个模型文件）

## 一、现象

应用调试（`POST /apps/<app_id>/conversations`，走 ReACT Agent）流式过程中，后端线程抛出异常：

```text
Exception in thread Thread-48 (invoke):
  File "D:\llmops\internal\core\agent\agents\react_agent.py", line 183, in _llm_node
    input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
  File "...\langchain_openai\chat_models\base.py", line 2335, in get_num_tokens_from_messages
    raise NotImplementedError(msg)
NotImplementedError: get_num_tokens_from_messages() is not presently implemented for model glm-5.3.
```

特点：

1. 只在**非 OpenAI 系**模型上出现（glm-5.3、kimi-k2.6、qwen3.8 均会复现），gpt-4o-mini 正常；
2. 异常发生在子线程里，HTTP 接口仍返回 200，前端表现为流式输出中断/无响应，不看后端日志很难定位；
3. 触发点是课程新增的 **token 统计 + 成本计算**代码，此前项目里没有任何地方调用 `get_num_tokens_from_messages`，所以问题一直潜伏。

## 二、调用链与根因

### 1. 业务侧：Agent 节点的成本计算

`react_agent.py` / `function_call_agent.py` 的 `_llm_node` 在 LLM 流式输出结束后新增：

```python
# react_agent.py:183-191
input_token_count = self.llm.get_num_tokens_from_messages(state["messages"])
output_token_count = self.llm.get_num_tokens_from_messages([gathered])

# 获取输入/输出价格和单位
input_price, output_price, unit = self.llm.get_pricing()

# 计算总token+总成本
total_token_count = input_token_count + output_token_count
total_price = (input_token_count * input_price + output_token_count * output_price) * unit
```

成本功能有两个前提：**能数出 token（本次报错点）** 和 **能拿到单价（pricing metadata，见第四节）**。

### 2. 库侧：langchain_openai 1.6.0 的两道关卡

`ChatOpenAI.get_num_tokens_from_messages` 内部先调 `_get_encoding_model()` 拿 `(模型名, 编码器)`，然后有两道判断：

```python
# site-packages/langchain_openai/chat_models/base.py
def _get_encoding_model(self):
    model = self.model_name  # 例如 "glm-5.3"
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        # 关卡①已内置兜底：查不到模型名就退回通用编码器，不会抛 KeyError
        encoding = tiktoken.get_encoding("cl100k_base")
    return model, encoding   # 注意：返回的模型名仍然是 "glm-5.3"

def get_num_tokens_from_messages(self, messages, ...):
    model, encoding = self._get_encoding_model()
    if model.startswith("gpt-3.5-turbo-0301"):
        ...
    elif model.startswith(("gpt-3.5-turbo", "gpt-4", "gpt-5", "o1", "o3", "o4")):
        tokens_per_message = 3   # 关卡②：只认 OpenAI 自家模型名前缀
    else:
        raise NotImplementedError(...)  # glm-5.3 在这里中弹
```

**关键认知：关卡①的 KeyError 兜底只换了编码器，没换模型名。** 第三方模型名能拿到编码器，却过不了关卡②的前缀白名单。所以仅靠库的默认兜底不够，必须把模型名也一起替换掉。

### 3. tiktoken 是什么、为什么不认第三方模型名

tiktoken 是 OpenAI 的分词器库，`encoding_for_model(模型名)` 本质是"拿模型名查内置字典"，字典里只收录 OpenAI 自家模型。本项目里已有同一个思路的另一种写法——`token_buffer_memory.py:80` 的记忆裁剪直接绕过"按名查字典"，硬取通用编码器：

```python
# internal/core/memory/token_buffer_memory.py
encoding = tiktoken.get_encoding("cl100k_base")
```

两条路殊途同归：第三方模型统一借用 `cl100k_base`（gpt-3.5-turbo / gpt-4 使用的词表）做近似计数。

## 三、修复：重写 `_get_encoding_model`

在 moonshot、zhipu、tongyi 三个继承 `ChatOpenAI` 的供应商类中各加一份重写（以 zhipu 为例）：

```python
# internal/core/language_model/providers/zhipu/chat.py
import tiktoken
from typing import Optional, Tuple

class Chat(ChatOpenAI, BaseLanguageModel):
    openai_api_base: str = "https://open.bigmodel.cn/api/paas/v4"

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写词表模型获取逻辑，智谱模型名不在tiktoken字典中，
        固定使用gpt-3.5-turbo的分词器防止token统计报错"""
        model = "gpt-3.5-turbo"
        return model, tiktoken.encoding_for_model(model)
```

这样关卡②拿到的模型名是 `gpt-3.5-turbo`，白名单通过，编码器为 `cl100k_base`。

### 为什么只改这三家、另外两家不动

| 供应商 | 基类 | 处理方式 | 原因 |
|---|---|---|---|
| openai | `ChatOpenAI` | 不改 | gpt-4o-mini / gpt-4o 本就在白名单，gpt-4o 系还会自动用更准的 `o200k_base` 词表 |
| moonshot / zhipu / tongyi | `ChatOpenAI` | **重写** | 模型名不在白名单，必弹 NotImplementedError |
| wenxin | `QianfanChatEndpoint`（langchain_community） | 不改 | 未重写 `get_num_tokens_from_messages`，沿 langchain_core 基类的基础实现（逐消息 `get_buffer_string` + 分词器计数），不会报错 |

### 验证

用**运行环境的 venv**（注意不是 D:\llmops\.venv，见第六节）实例化四个供应商的 Chat，直接调用计数方法（token 计数不联网，构造时传一个假的 `openai_api_key` 即可绕过凭证校验）：

```python
from pydantic import SecretStr
from langchain_core.messages import HumanMessage
from internal.core.language_model.providers.zhipu.chat import Chat

llm = Chat(model="glm-5.3", openai_api_key=SecretStr("sk-dummy"))
enc_name, _ = llm._get_encoding_model()       # -> ("gpt-3.5-turbo", Encoding(...))
llm.get_num_tokens_from_messages([HumanMessage(content="你好")])  # 正常返回 int，不再抛错
```

实测结果：glm-5.3 / kimi-k2.6 / qwen3.8-max 均正常返回 token 数（编码器模型显示 gpt-3.5-turbo），gpt-4o-mini 保持原生行为不变。

> 注意：这是**近似计数**。cl100k_base 与各家真实分词器存在细微差异，用于记忆裁剪、上下文窗口保护、成本估算足够；不能作为精确账单依据。

## 四、配套：模型定价 metadata 接入

成本公式里的单价来自 `BaseLanguageModel.get_pricing()`：

```python
# internal/core/language_model/entities/model_entity.py:82
def get_pricing(self) -> tuple[float, float, float]:
    input_price = self.metadata.get("pricing").get("input", 0.0)
    output_price = self.metadata.get("pricing").get("output", 0.0)
    unit = self.metadata.get("pricing").get("unit", 0.0)
    return input_price, output_price, unit
```

数据链路：

```text
providers/<供应商>/<模型>.yaml  (metadata.pricing)
  → provider_entity.py 启动时读盘，构造 ModelEntity（metadata 为自由 dict，实体天然支持）
  → language_model_service.py:149 实例化 Chat 时 metadata=model_entity.metadata 传入
  → Agent 节点 self.llm.get_pricing() 取出
```

yaml 格式（`unit: 0.001` 表示按每 1K tokens 计价，input/output 为每 1K 的人民币单价）：

```yaml
metadata:
  pricing:
    input: 0.0120
    output: 0.0120
    unit: 0.001
    currency: RMB
```

已为 11 个模型补齐，定价口径：

| 模型 | input（元/1K） | output（元/1K） | 依据 |
|---|---|---|---|
| gpt-4o-mini | 0.0011 | 0.0043 | OpenAI 官方 $0.15/$0.60 每百万 × 汇率 7.1 |
| gpt-4o | 0.0178 | 0.0710 | OpenAI 官方 $2.5/$10 每百万 × 汇率 7.1 |
| kimi-k2.6 | 0.0120 | 0.0120 | 12 元/百万档 |
| kimi-k3 | 0.0040 | 0.0160 | 无同名公开价，映射 Kimi K2 的 4/16 元每百万 |
| qwen3.8-flash | 0.0001 | 0.0003 | 阿里云百炼 qwen-flash 公开价 |
| qwen3.8-max | 0.0200 | 0.0600 | 阿里云百炼 qwen-max 公开价 |
| ernie-3.5-8k | 0.0008 | 0.0020 | 百度千帆 0.8/2 元每百万 |
| ernie-3.5-128k | 0.0080 | 0.0200 | 百度千帆 8/20 元每百万 |
| ernie-4.0-8k | 0.0300 | 0.0900 | 百度千帆 30/90 元每百万 |
| glm-5.3 | 0.0005 | 0.0015 | 映射 GLM-4.5 的 0.5/1.5 元每百万 |
| glm-5.3-flash | 0.0001 | 0.0002 | 映射 GLM-4.5-Flash 的 0.1/0.2 元每百万 |

带 ⚠️ 性质的映射价（kimi-k3、glm-5.3 系列）是课程型号无同名公开定价时按同厂同档真实型号填的，调价直接改对应 yaml 即可。改 yaml 和 chat.py 后都需**重启 flask**（`--no-debug` 无自动重载，yaml 在启动时由 `LanguageModelManager` 一次性读入缓存）。

## 五、遗留风险：兜底模型缺 metadata

`language_model_service.py` 的模型加载有静默回退：

```python
# 149-156：正常实例化失败时
except Exception as e:
    return self.load_default_language_model   # 注意无括号，返回的是方法对象本身

@classmethod
def load_default_language_model(cls):
    return Chat(model="kimi-k2.6", temperature=1)   # 没传 metadata！
```

而 `get_pricing()` 是 `self.metadata.get("pricing").get(...)` 链式调用、无空值保护。一旦走兜底分支，`metadata` 为空 dict，`.get("pricing")` 返回 `None`，下一行立刻 `AttributeError`。正常路径不受影响（11 个 yaml 均已带 pricing），但建议后续：

1. 兜底实例补 `metadata={"pricing": {...}}`；
2. `get_pricing()` 改成空值安全写法；
3. 顺手修掉 `return self.load_default_language_model` 缺括号的问题（当前返回的是方法对象而非模型实例）。

## 六、环境备忘：venv 与代码目录错位

本机有两个后端副本，运行中的进程是「Anaconda py310 的 python + CWD=D:\llmops 的代码 + D:\code\llmops-api\.venv 的 site-packages」的组合：

- 改代码：改 **D:\llmops**（真正加载的源码目录）；
- 查库行为/复现问题：用 **D:\code\llmops-api\.venv**（langchain_openai 1.6.0、langchain_community 0.4.2、tiktoken 0.14.0）；
- 判断谁在服务：`netstat -ano | grep :5000` 找 LISTENING 的 PID，再 `wmic process where ProcessId=<pid>` 看命令行，别只看进程列表。

## 七、经验小结

1. **"库已经兜底了"不等于"功能能用"**——tiktoken 的 KeyError 兜底只解决编码器，没解决上层的模型名白名单，排查要看完整调用链的每一道分支；
2. 第三方 OpenAI 兼容端点统一借 `cl100k_base` 计数是行业通用做法，代价是近似值，适用于截断/估算，不适用于计费；
3. 流式接口里的子线程异常不会反映在 HTTP 状态码上，SSE 中断先看后端日志的 `Exception in thread`；
4. 新增一个需要元数据（pricing）的功能时，同步检查所有构造路径——包括异常兜底分支，否则正常路径测试全绿、异常路径一触即溃。
