# 下一步实施提示词

## Step L4-A2b：Botzone 无贡手动桌单局 live smoke

请在 GuanDan 项目中执行 Step L4-A2b。用户已明确授权使用当前进程中已配置、已轮换且保持脱敏的 Botzone 本地 AI URL，执行唯一一次真实联网 smoke。本任务不修改代码、不读取 `.env`、不输出任何 URL/密钥/Header/request/response/手牌/match ID，不使用 runmatch 或 DeepSeek。

### 已完成前置

- HEAD：`029b8d6034e55c70b83d2b1c8d4b052626895bd2`；
- L4-A1：`e4a4fba99211831c66062ac0f003094edc941c6a`；
- L4-A1a 判定：`botzone_live_smoke_preflight_ready`；
- L4-A2a 判定：`botzone_live_smoke_authorization_ready`；
- L4-A1a 定向 46 项、全量 515 项通过；
- 工作区干净；
- 用户已明确确认截图中暴露过的凭据已轮换；
- `BOTZONE_LOCAL_AI_URL` 与 `BOTZONE_STATE_DIR` 在当前进程中均 present；
- state dir 与用户确认路径一致、存在且为空；
- 唯一一次 `--preflight-only` 返回 `preflight_ready`，之后 state dir 仍为空、仓库仍干净、网络请求数为 0。

授权原文：

```text
明确授权执行本次 L4-A2b 真实 Botzone 无贡 smoke，提供prompt
```

该授权只覆盖本提示词锁定的唯一一次 live run，不覆盖 probe、第二进程、重跑、补采、runmatch、DeepSeek 或后续对抗评测。

### 固定 live 参数

- Agent：`RuleBasedAIAgent`；
- 用户手动创建一局 GuanDan 桌；
- “需要进贡”必须明确选择“否”；
- 本地 AI 只替代用户所在的一个座位；
- 正式 connector 进程恰好一个、启动恰好一次；
- `timeout_seconds=30`；
- `max_cycles=100`；
- `max_wall_seconds=600`；
- `stop_after_finished=1`；
- `max_consecutive_failures=5`；
- `backoff_seconds=1`；
- audit file 位于仓库外新建的本次专用临时目录；
- state dir 使用已通过 preflight 的仓库外空目录；
- 不使用 `--url` 命令行参数；URL 只由进程环境提供；
- 不自动创建桌、不调用 runmatch、不自动重启、不启动第二进程。

### 启动前快速门槛

只做以下快速检查，不重复运行完整回归或 preflight：

1. HEAD 仍为上述值，工作区干净；
2. 两项环境变量仍为 present，只输出 present/missing；
3. state dir 仍为空；
4. 没有已有 `python -m integrations.botzone` 进程；
5. 为本次运行创建仓库外新 audit 目录，初始为空。

任一失败：不启动 connector，判定 `precondition_failed`。不得修复配置、删除未知状态、复用旧 audit 或消耗授权。

### 唯一进程启动

使用当前进程环境直接启动：

```text
python -m integrations.botzone --timeout-seconds 30 --max-cycles 100 --max-wall-seconds 600 --stop-after-finished 1 --audit-file <仓库外本次专用 audit.json>
```

要求：

- 通过 PowerShell `Start-Process` 启动时必须 `-WindowStyle Hidden`，继承当前环境，工作目录为仓库根；
- stdout/stderr 重定向到同一仓库外专用 audit 目录中的固定文件；
- 记录唯一 PID 和启动状态，但不创建 runner 副本或脚本；
- 启动后确认进程存活，不读取或显示进程命令行；
- 一旦进程启动即视为授权已消耗；任何失败都不得启动第二进程。

启动成功后立即向用户发送中间更新，不要结束任务：

```text
唯一 Botzone connector 已启动。请现在在 Botzone 手动创建一局 GuanDan 测试桌，明确选择“需要进贡=否”，并选择“用本地 AI 替代我”。看到对局开始后回复“对局已开始”；不要创建第二局。
```

### 用户建桌后的跟踪

- 只跟踪已记录的唯一 PID；不得重启或另起进程；
- 最长等待 runner 自身的 600 秒 wall limit 加一个 30 秒 transport timeout 与少量退出余量；
- 用户回复“对局已开始”后继续等待同一进程；
- 若用户报告建桌配置错误、误选进贡、创建多局或要求停止，终止唯一进程并判定 invalid；
- 若进程超过上限仍存活，终止该进程一次并判定 invalid；
- 不读取 Botzone 页面 Cookie、账号存储或网络请求正文。

### 结束后只读审计

进程退出后只读取：exit code、固定 stdout/stderr、聚合 audit、state dir 文件数量与 tombstone JSON。不得输出文件名 hash、原始 session、请求、响应或 match ID。

成功门槛全部必须满足：

1. 唯一进程正常退出，未重启、未超时终止；
2. exit code=`0`；
3. stdout 仅为固定 `connector_finished` 聚合行，stderr 为空；
4. audit schema/version 合法；
5. `stop_reason="finished_target"`；
6. `finished_seen=1`；
7. `cycles` 在 `1..100`；
8. `transport_failures` 不超过有界恢复范围，且最终未触发 failure limit；
9. diagnostics 为空；
10. `0 <= headers_sent <= responses_prepared <= requests_seen`；
11. state dir 只剩一个最小 tombstone；内容精确为固定 schema/version/`finished=true`，不含 match ID、座位、手牌、history、response、digest、URL 或 Header；
12. audit/stdout/stderr 敏感关键词扫描无匹配；
13. 仓库工作区仍干净；
14. 用户确认该桌“需要进贡=否”且只创建一局；
15. 未使用 runmatch、DeepSeek、第二进程或补采。

若平台在正常 play 中合法产生 `headers_sent == responses_prepared`，可记录为补充观察，但不得把未预注册的精确相等作为事后新增门槛。

### 判定

任一启动、配置、进程、协议、诊断、完成、tombstone、审计或敏感扫描门槛失败，唯一判定：

```text
botzone_no_tribute_local_ai_smoke_invalid
```

不得重跑、补采、修改证据或把部分对局解释为通过。

全部门槛通过时，唯一判定：

```text
botzone_no_tribute_local_ai_smoke_verified
```

### 最终报告边界

报告检查点、固定预算、唯一进程、用户手动无贡建桌确认、聚合 audit、退出码、stop reason、cycle/request/response/header/finished 计数、diagnostics、tombstone 与敏感扫描。不得报告 URL、host/path、密钥、match ID、手牌、动作、请求/响应或对手身份。

该结果只证明 RuleBasedAI 在一局真实 Botzone 无贡手动桌中完成协议闭环。它不证明对抗能力、胜率、稳定性、平台长期兼容性、贡还支持或完整 Botzone GuanDan 支持；下一步若评估实力，必须另行设计座位平衡、固定对手和预注册局数，不复用本次授权。
