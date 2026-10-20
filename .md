## 文档处理主流程：_completed(Document, list[LCDocument])

1. **遍历所有片段，初始化元数据**
    - 全局启用标识：`document_enabled = True`
    - 片段启用标识：`segment_enabled = True`

2. **初始化线程池**
    - 最大线程数：配置化参数 `max_workers`

3. **按 10 条一组切分数据块（chunks）**
    - 分组规则：`lc_segments[i:i+10]`
    - 每组提取对应 `node_id`

4. **提交任务至线程池并发执行**
    - 每个分组任务执行：`thread_func`

---

### 线程内执行逻辑（thread_func）

1. **进入 Flask 应用上下文**
2. **向量库入库（带 2 次重试机制）**
    - 执行：`vector_store.add_documents(...)`

#### ✅ 入库成功

- 更新 PostgreSQL 片段状态
    - `status = COMPLETED`
    - `enabled = True`
    - `completed_at = 当前时间`

#### ❌ 入库失败（捕获异常）

- 记录异常日志
- 更新 PostgreSQL 片段状态
    - `status = ERROR`
    - `stopped_at = 当前时间`
    - `enabled = False`

---

5. **主线程等待所有子任务完成（带超时控制）**
6. **更新主文档最终状态**
    - `status = COMPLETED`
    - `completed_at = 当前时间`
    - `enabled = True`

## 流程结束