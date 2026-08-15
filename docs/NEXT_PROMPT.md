# 下一步实施提示词

## Step L5-A2b18：旧 active session 精确处置授权

L5-A2b17 已完成并封存：

```text
botzone_four_event_history_rotation_contract_verified
```

检查点 `5bb44fd4052e181d08455594ab0879c0ee305dfb` 精确包含 `bot_io.py`、`session.py` 及两份对应测试；定向 17 项、相关 65 项、全量 590 项和 `git diff --check` 通过。完整四事件零重叠窗口现可安全追加，短窗口零重叠继续 fail-closed，envelope replay 与 durable session 语义一致。

L5-A2b16 留下的一份 active session 仍保持未读、未改、未清理。它不是 finished tombstone，不能在没有项目所有者明确授权时删除。本步只允许在本机严格复核并精确删除这一份已废弃 session；不得修改代码、运行测试/preflight、启动 connector、调用 Botzone/DeepSeek、读取 `.env` 或连接配置。

### 项目所有者必须确认并授权

```text
所有历史 Botzone 本地 AI 测试桌均已结束或关闭：是
我确认 L5-A2b16 已永久无效，不再恢复该旧会话：是
我明确授权执行 L5-A2b18：只读解析固定 state 目录中的唯一 session；仅当它严格符合当前 session schema、文件路径与内部 match key 一致、delivery_state=idle、pending_response/pending_effect 均为空、finished 为空且没有残留 connector 时，精确删除这一份旧 session 文件。禁止递归删除、通配符、删除 state 目录或改动任何 audit；任何门槛不满足立即停止。
```

### 固定执行

1. 确认 HEAD 包含 `5bb44fd4052e181d08455594ab0879c0ee305dfb`，工作区干净，没有命令行匹配 `integrations.botzone` 的进程。
2. 只检查固定 state/audit 目录；不得扫描其他用户目录。
3. 复核 L5-A2b16 v5 audit 仍为 432 bytes、SHA-256 `924169f62cc033412735d88c0ee50f59cca4ec38f2ed67f94e2d7871380dcf8c`，schema v5 与敏感扫描通过；L5-A2b14 聚合 audit 仍为 996 bytes、原 SHA-256 不变。
4. state 必须精确含一个普通文件。使用当前 `session.py` 的严格 schema 解析，只在内存中验证：
   - 不是 tombstone；
   - stage 仅为 `deal` 或 `play`；
   - `delivery_state == "idle"`；
   - `pending_response is None`；
   - `pending_effect is None`；
   - `finished is None`；
   - 文件名与内部 match key 的 SHA-256 命名规则一致。
5. `handler_completed` 或 `cached_response` 只可作为布尔聚合报告；只要存在 pending/inflight/effect 就禁止删除。不得输出 match、牌、history、response、digest、文件名、路径或异常正文。
6. 解析目标 resolved path，确认其父目录精确为固定 state 根；仅调用一次非递归单文件删除。禁止 glob 删除、目录删除、重命名、覆盖或清理 audit。
7. 删除后确认 state 目录仍存在且为空；两份既有 audit 的 bytes/SHA-256 不变；无残留 connector。
8. 只报告固定聚合：删除前/后文件数、schema valid、stage 类别、delivery state、pending/effect/finished/cached/handler 布尔值、`state_empty`、audit unchanged、零网络计数。

### 判定

- 全部门槛满足且唯一旧 session 被精确删除：`botzone_abandoned_active_session_cleanup_verified`。
- session 合法但存在 pending/inflight/effect，或 schema/key/audit 不匹配：`botzone_abandoned_active_session_cleanup_invalid`，不得删除。
- 缺少授权、工作区/进程/目录前置不满足：对应 `precondition_failed`。

本步不形成协议闭环、DeepSeek 调用、动作质量或胜率结论。成功后才允许进入 L5-A2b19 的人工网页无贡桌新授权；不得在同一步启动 live。
