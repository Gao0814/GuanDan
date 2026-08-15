# 下一步实施提示词

## Step L5-A2b20：失败人工桌残留 session 放弃与清理

L5-A2b19 永久判定：

```text
botzone_manual_no_tribute_deepseek_mode_smoke_invalid
```

唯一 connector 在项目所有者的“已连接，且人工新桌已创建并进入对局”消息到达前，因 state 从 0 变为 1 而按旧握手门槛被终止。随后才收到项目所有者确认，因此该桌不能追认。本次没有完成 v5 audit，runmatch=0，state 保留一个未读取、未清理文件，无残留 connector。

该失败暴露的是人工协调门槛过严：网页建桌会立即产生 request/state，而聊天确认必然可能稍后到达。后续握手不得再要求“确认消息到达前 state 始终为空”；应改为启动前 state=0、旧桌全关、只创建一个新桌，并允许 connector 启动后项目所有者在页面显示已连接时直接建桌，随后补充确认。

本步只处理 L5-A2b19 的残留 session，不修改代码、不运行测试/preflight、不启动 connector、不调用 Botzone/DeepSeek、不读取 `.env` 或连接配置。

### 项目所有者必须先完成并确认

```text
当前网页测试桌已结束或关闭：是
所有其他 Botzone 本地 AI 测试桌也已结束或关闭：是
我确认 L5-A2b19 永久无效，不再恢复或发送该旧 session 的任何 pending response：是
我明确授权执行 L5-A2b20：只读解析固定 state 目录中的唯一 session，生成不含敏感内容的聚合清理审计；在确认没有残留 connector、session 严格符合当前 schema、文件名与内部 key 一致且 resolved path 位于固定 state 根后，精确删除该单一旧 session 文件。即使 delivery_state 为 pending/inflight，也因网页桌已关闭且我明确放弃恢复而允许删除；禁止递归删除、通配符、删除 state 目录或修改既有 audit。任何 schema/key/path/文件数门槛不满足立即停止。
```

### 固定执行

1. 确认 HEAD 包含 `5bb44fd4052e181d08455594ab0879c0ee305dfb` 和当前文档检查点，工作区干净，无命令行匹配 `integrations.botzone` 的残留进程。
2. 只检查固定 state/audit 目录；state 必须精确含一个普通文件，不扫描其他用户目录。
3. 使用当前 `session.py` schema 在内存中严格解析，验证文件名与内部 match key 的 SHA-256 命名一致。不得输出 match、牌、history、response、digest、文件名、路径或异常正文。
4. 只聚合并写入一个全新 cleanup audit：schema/version valid、stage、delivery state、handler/cached/pending/effect/finished 布尔值、own-hand/history 数量范围、删除前后文件数、state_empty、zero-network。audit 不得包含原始值或可关联标识。
5. cleanup audit 必须先完成 schema/value allowlist 和敏感形态扫描；若不通过，不得删除。
6. 确认目标 resolved path 的父目录精确为固定 state 根；仅调用一次非递归单文件删除。禁止 glob、目录删除、重命名、覆盖或修改既有 audit。
7. 删除后确认 state 目录存在且为空，新 cleanup audit 可解析且既有 audit 全部不变，无残留 connector。
8. 报告只含固定聚合、新 audit bytes/SHA-256、既有 audit unchanged 和网络/connector/test 计数为 0。

### 判定

- 唯一 session 严格合法、脱敏审计通过并精确删除：`botzone_failed_manual_session_cleanup_verified`。
- schema/key/path/审计失败或删除后 state 非空：`botzone_failed_manual_session_cleanup_invalid`。
- 缺少桌面关闭/放弃授权或工作区/进程/目录前置不满足：对应 `precondition_failed`。

成功后才能进入 L5-A2b21 的简化人工网页桌 live 授权。本步不得顺带启动 live，也不形成协议闭环、DeepSeek 调用、动作质量或胜率结论。
