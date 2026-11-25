# 辅助Agent会话散落 Bug：detached 实例 setattr 静默失败（第二次现身）

> 日期：2026-11-02
> 涉及：`internal/model/account.py` / `internal/service/assistant_agent_service.py` / `pkg/paginator/paginator.py`
> 关联案例：workflow `is_debug_passed` 更新静默失败（同一个病，第二次遇到）

## 一、现象

1. `GET /assistant-agent/messages` 返回空列表，但明明和辅助 Agent 聊过多次；
2. 数据库 `account.assistant_agent_conversation_id` 永远指向**最新**会话；
3. 每次 chat 都新建一个 conversation，每个会话里**恰好只有 1 条消息**，历史散落在 9 个会话里。

## 二、排查过程（方法论比结论值钱）

### 1. 先别猜，直接查库取证

```sql
-- 每个会话的消息数
SELECT c.id, c.created_at, count(m.id)
FROM conversation c LEFT JOIN message m ON m.conversation_id = c.id
WHERE c.created_by='<账号id>' AND c.invoke_from='assistant_agent'
GROUP BY c.id, c.created_at ORDER BY c.created_at DESC;
```

结果：9 个会话各 1 条消息 → 说明**复用分支从来没走到**，每次 chat 都走了新建分支。

### 2. 决定性证据：用"下一次请求的行为"反推"上一次写入是否成功"

- 09:17 chat 存了消息（会话 44486822），此时字段若成功写入 = 44486822；
- 09:21 的 GET 请求如果读到 44486822，就该复用它并返回那条消息；
- 实际 GET 新建了空会话 ab382e58、返回空列表；
- **反推：09:17 chat 对 account 字段的赋值根本没写进数据库。**

### 3. 同一个 commit 里"一半持久化一半丢失"= detached 实例

属性代码里 conversation 和 account 字段赋值在**同一个 `auto_commit()`** 里：

```python
if not self.assistant_agent_conversation_id or not conversation:
    with db.auto_commit():
        conversation = Conversation(...)          # ✅ 成功入库（能查到）
        db.session.add(conversation)
        db.session.flush()
        self.assistant_agent_conversation_id = conversation.id   # ❌ 丢失
```

同一个 commit 只可能有一种解释：**account 实例不在 session 里（detached）**，`setattr` 改的是一个"孤儿对象"，commit 时什么也没发生，且**不报任何错**。

为什么 account 会 detached？chat 是流式接口，`chat()` 是生成器函数——生成器体（包括访问 `account.assistant_agent_conversation` 属性）在**流式响应阶段**才执行，此时请求阶段的 SQLAlchemy session 已经结束，`current_user` 指向的 ORM 实例已脱管。而 GET 接口在 handler 里同步执行、对象仍挂载，所以赋值能成功（ab382e58 的绑定就是 GET 写进去的）。

## 三、修复：显式 UPDATE 语句（绕过 identity map）

```python
from sqlalchemy import update  # 文件顶部补导入

if not self.assistant_agent_conversation_id or not conversation:
    with db.auto_commit():
        conversation = Conversation(
            app_id=assistant_agent_id,
            name="New Conversation",
            invoke_from=InvokeFrom.ASSISTANT_AGENT,
            created_by=self.id,
        )
        db.session.add(conversation)
        db.session.flush()

        # 用显式UPDATE语句写库，绕过identity map，detached实例也不受影响
        db.session.execute(
            update(Account)
            .where(Account.id == self.id)
            .values(assistant_agent_conversation_id=conversation.id)
        )
        # 同步内存值，保证本次请求后续代码能读到
        self.assistant_agent_conversation_id = conversation.id
    return conversation
```

要点：Core 层的 `update()` 语句**不经过 ORM identity map**，发出即执行，与对象挂载状态无关——这是处理"流式/异步阶段写库"的通用答案。

## 四、通用规律（两次案例的合并结论）

| 症状 | 诊断 |
|---|---|
| ORM setattr + commit 后数据库没变，且无任何报错 | 八成是 detached 实例：setattr 落在 session 外 |
| 生成器/流式接口里改 ORM 对象不生效 | 请求阶段 session 已结束，对象脱管 |
| 同一 commit 里 A 表写入成功、B 对象字段丢失 | B 对象 detached，A 是独立语句所以没事 |
| 怀疑 detached | 用"下一次请求读到的值"反推"上一次写没写进去" |

**预防口诀：流式/异步上下文里写库，一律用显式 `update()/insert()` 语句，不用 ORM 实例 setattr。**

## 五、同日顺手修掉的另一个 bug

`pkg/paginator/paginator.py`：`PaginatorReq` 的 `current_page`/`page_size` 字段没设 `default`，前端不传参时 WTForms 给 `None`，覆盖 dataclass 默认值后 `math.ceil(total / None)` 报 TypeError。两处修法任选：

- 表单字段加 `default=1` / `default=20`（入口兜底）；
- `Paginator.__init__` 里 `req.current_page.data or 1`（使用处兜底，防御性更强）。

注意：手写了 `__init__` 的 dataclass，字段默认值是死代码——`@dataclass` 不会生成 `__init__`，默认值只在自动生成的构造函数里生效。

## 六、面试话术

> "我在流式 Agent 接口里遇到过一个隐蔽 bug：ORM 字段赋值 + commit 后数据库没变化。排查发现生成器体在响应流阶段才执行，此时 SQLAlchemy 请求级 session 已结束，实例已 detached，setattr 静默失败。修复方案是改用 Core 层显式 UPDATE 语句绕过 identity map。这个坑我在 workflow 模块和 Agent 会话管理上踩过两次，之后团队的规范是：流式/异步上下文里一律用显式 SQL 语句写库。"

一个 bug 踩两次 + 提炼成团队规范 = 面试里最有说服力的故事结构。
