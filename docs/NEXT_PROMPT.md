# 下一步实施提示词

## Step L5-A2b15：finished tombstone 精确清理与人工建桌准入

L5-A2b13 的 `botzone_deepseek_runmatch_no_tribute_smoke_invalid` 永久保留。L5-A2b14 已判定 `botzone_live_residual_state_audit_verified`：completion audit 缺失；固定 state 仅含一个严格有效的 finished tombstone，所有 active session、pending/inflight、handler、effect 和缓存 response 聚合均为 0；审计前后 state 摘要完全一致。

本步只清理这个已审计 tombstone，并准备后续网页人工建桌路线。不得修改代码，不得运行测试/preflight，不得启动 connector，不得发送 runmatch/local-AI/DeepSeek 请求，不得读取 `.env` 或连接配置值。

### 前置

1. 确认工作区干净，当前 HEAD 包含 L5-A2b14 文档检查点，且没有命令行匹配 `integrations.botzone` 的残留进程。
2. 只读复核 L5-A2b14 聚合 audit：文件必须为 996 bytes、SHA-256 为 `fca58e8210aa3dcd11941500bfd7954c2327a111d8b59cd786d85b5b60c5e03f`，schema/value allowlist 与敏感扫描均为通过。
3. 重新确认 state 仍精确包含一个可严格解析的 finished tombstone，且 active/pending/inflight/handler/effect/cache 聚合仍全部为 0；不得输出文件名、match ID 或原始 JSON。

### 精确清理

1. 解析并验证目标文件的 resolved path 位于固定 state 根目录内；禁止递归删除、通配符和跨目录操作。
2. 仅删除这一份已验证 finished tombstone；不得删除 state 目录、audit 文件或其他任何文件。
3. 删除后确认 state 目录存在且为空；audit 目录及 L5-A2b14 聚合 audit 保持不变。
4. 只报告删除前/后的文件数、`state_empty`、audit bytes/SHA-256 是否不变和残留 connector 布尔值；不回显任何受保护值或路径。

### 后续人工建桌路线

清理成功后只准备 L5-A2b16 的新授权，不在本步联网：

- 不再调用 `runmatch` endpoint。
- 后续只启动一个 DeepSeek connector；Botzone 显示“已连接”后，由项目所有者在网页手动创建一个 GuanDan 测试桌。
- 人工设置“需要进贡=否”，本家选择“用本地 AI 替代我”，其余位置选择测试 Bot。
- 项目所有者必须明确确认网页已显示新桌创建成功并进入对局；在此之前不得把任意 local-AI request 归入新桌验收。
- live 仍使用最多 100 次 local-AI GET、DeepSeek 60 秒/零重试、单 connector、最长 3600 秒、qualified finished=1 即停；具体授权在 L5-A2b16 重新取得。

### 判定

- 精确 tombstone 删除成功、state 为空、audit 不变、零网络：`botzone_finished_tombstone_cleanup_verified`。
- 目标不再是唯一合法 finished tombstone、audit 不匹配或删除后 state 非空：`botzone_finished_tombstone_cleanup_invalid`。
- 工作区、进程或目录边界不满足：对应 `precondition_failed`。

本步不形成 runmatch、local-AI、DeepSeek、动作质量或胜率结论。禁止在清理步骤中顺带启动人工建桌 live。
