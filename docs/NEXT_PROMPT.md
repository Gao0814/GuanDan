# 下一步实施提示词

## Step L5-A2b7：执行唯一一次 runmatch DeepSeek live smoke

当前状态为 `botzone_deepseek_runmatch_live_authorized`。项目所有者已在紧邻本任务的消息中提供三个可参与 GuanDan 的 Bot ID、`me=0`、旧桌已关闭确认、无贡 fail-closed 接受和完整 live 授权。

三个非本家座位复用同一个现有 Bot ID。公开 runmatch 说明只要求 `X-Player-*` 中有且只有一个 `me`，没有声明其他 Bot ID 必须互不相同；但“与建桌相同的限制”仍可能由平台拒绝该组合。若 runmatch 拒绝，记录固定创建失败并停止，不更换 Bot、不重试。

### 敏感输入边界

- Bot ID 只从紧邻的项目所有者消息读取并在内存中使用。
- 不得把 Bot ID、local-AI URL、runmatch URL、API key、match ID、Header、手牌、prompt 或模型响应写入仓库、docs、普通日志或最终报告。
- 只报告固定状态、聚合计数和脱敏失败类别。
- 不读取仓库 `.env`；使用项目 `.venv\Scripts\python.exe`，并在子进程环境设置 `PYTHON_DOTENV_DISABLED=1`。

### 已锁定授权与预算

- runmatch endpoint：由当前 `BOTZONE_LOCAL_AI_URL` 仅在内存中派生；最多 1 次 GET。
- local-AI endpoint：最多 100 次 GET。
- DeepSeek：`https://api.deepseek.com` / `deepseek-v4-flash`。
- 允许发送：本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段。
- DeepSeek timeout 60 秒、retries 0。
- 仅 1 个 connector、1 个 runmatch 对局，最长 3600 秒，qualified finished=1 即停。
- 不发送 `X-Initdata`；首个请求非零 tribute，或出现 `tribute/return`，立即停止且不重试。

### 固定执行顺序

1. 快速复核 HEAD/工作区干净、四项配置元数据匹配、无残留 connector；不重复完整回归。
2. 创建全新仓库外 state/audit，确认初始为空。
3. 使用项目 `.venv` 与 dotenv 禁用开关启动唯一 DeepSeek connector。
4. 确认 local-AI poll 已连接后，仅发送一次 runmatch GET：

```text
X-Game: GuanDan
X-Player-0: me
X-Player-1: <当前用户消息中的 Bot ID 1>
X-Player-2: <当前用户消息中的 Bot ID 2>
X-Player-3: <当前用户消息中的 Bot ID 3>
```

5. 省略 `X-Initdata`。不持久化 runmatch 返回的 match ID。
6. 首个内层请求必须满足现有无贡 profile；否则 fail-closed。
7. DeepSeek 异常、超时、空值或非法 action ID 仅允许走现有 RuleBased fallback；最终 response 必须回查 engine 原始合法 action ID/provenance。
8. finished=1、达到任一预算或出现固定失败后终止；不创建第二局、不启动第二进程、不补采。
9. 清理 state 中已完成会话，确认无残留 connector；仅输出脱敏聚合审计。

### 验收结论

只有同时满足 runmatch 创建成功、非零 request/response/Header、qualified finished=1、transport failure=0、协议 diagnostics 为空、Botzone 无非法动作或决策超时、state 清理完成且无残留进程，才能判定：

```text
botzone_deepseek_runmatch_no_tribute_smoke_verified
```

runmatch 若拒绝重复 Bot、首个请求不是无贡、发生贡还、任何协议诊断、预算耗尽或闭环不完整，只能给出对应的 `invalid` / `precondition_failed`，并停止且不重试。

该步骤只验证一次 Botzone/DeepSeek/RuleBased fallback 闭环，不证明 DeepSeek 每手均被调用、动作质量或胜率提升。
