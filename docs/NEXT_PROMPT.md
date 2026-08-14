# 下一步实施提示词

## Step L5-A2b7a：恢复同任务输入后执行唯一一次 runmatch DeepSeek live smoke

当前状态为 `precondition_failed: runmatch_participants_missing`。上一次实施任务看不到规划任务中的敏感 Bot ID 和授权原文，因此在任何配置读取、state/audit 创建或网络操作前停止；授权未消耗。

### 必须先在本实施任务中收齐

实施任务必须要求项目所有者在同一任务的下一条消息中粘贴以下完整内容。不得从 docs、其他任务摘要或历史报告推断 Bot ID/授权：

```text
Bot ID 1：<可参与 GuanDan 的现有 Bot ID>
Bot ID 2：<可参与 GuanDan 的现有 Bot ID>
Bot ID 3：<可参与 GuanDan 的现有 Bot ID>
me 座位：0
旧本地 AI 测试桌已全部关闭：是
接受省略 X-Initdata，并在非零 tribute 或 tribute/return 阶段立即停止且不重试：是

我明确授权执行 L5-A2b7a：向由当前 BOTZONE_LOCAL_AI_URL 在内存中派生的 runmatch endpoint 发送一次 GET，并向当前 local-AI endpoint 最多发送 100 次 GET；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；只启动一个 connector，只创建一个 runmatch 对局，最长 3600 秒，完成一局即停。若首个请求显示非零 tribute，或出现 tribute/return，立即停止且不重试。
```

收到后先严格核对三项 ID 非空、`me=0`、两项确认均为“是”、授权中的 endpoint/model/预算与本文件完全一致。核对通过后在同一任务中直接继续固定执行顺序，不再要求把敏感输入写入 docs，也不另开执行任务。

三个非本家座位复用同一个现有 Bot ID。公开 runmatch 说明只要求 `X-Player-*` 中有且只有一个 `me`，没有声明其他 Bot ID 必须互不相同；但“与建桌相同的限制”仍可能由平台拒绝该组合。若 runmatch 拒绝，记录固定创建失败并停止，不更换 Bot、不重试。

### 敏感输入边界

- Bot ID 只从当前实施任务内紧邻的项目所有者消息读取并在内存中使用。
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
X-Player-1: <本实施任务中收到的 Bot ID 1>
X-Player-2: <本实施任务中收到的 Bot ID 2>
X-Player-3: <本实施任务中收到的 Bot ID 3>
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
