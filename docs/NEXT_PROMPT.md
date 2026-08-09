# 下一步实施提示词

## Step L4-A3c：真实 Botzone 无贡前台 smoke

授权状态：用户已在 2026-08-09 针对下述固定范围明确回复“授权”。若执行发生在保留该对话上下文的同一任务中，此门槛已通过；若提示词被复制到无法核对该用户消息的新任务，必须重新取得同范围授权。无法核对授权时只报告 `authorization_required`，不得读取真实配置、创建运行目录、启动 connector 或发送 GET。

授权文本必须明确覆盖：使用当前已配置的 `BOTZONE_LOCAL_AI_URL`，RuleBasedAI，全新手动无贡测试桌，全新 LocalAppData state/audit，最多 100 次 GET，timeout 120 秒，最长 900 秒，完成 1 局即停，不重试。

### 已封板事实

- L4-A3a 检查点：`2ac51fb2c80a5a0ae4b7dabd4f2aa161e11f1498`。
- L4-A3b1 检查点：`28de0cb36f7356bc35ade874fa8f75fa63b1f331`。
- L4-A3b1 唯一判定：`botzone_live_smoke_recovery_authorization_ready`。
- direct main 与两次 binary PIPE module capture 已验证 `preflight_ready` 单行契约、空 stderr、空 state 和零 transport。
- L4-A3b 原 `botzone_envelope_live_smoke_preflight_invalid` 永久保留，只归类为监督/捕获假阴性，不追认原始 stdout bytes。
- L4-A3a 已修复旧 smoke 的外层 Bot JSON、历史重放、空贡还字段和 `{"response": ...}` 包装缺口。
- 旧测试桌、旧授权、旧 state/audit、旧 run ID 均不得复用。

### A. 启动前门槛

1. 能在当前对话中核对用户紧接固定预算问题后的明确“授权”；只有文档转述而没有用户消息时不算授权。
2. HEAD 必须包含 `28de0cb36f7356bc35ade874fa8f75fa63b1f331`，工作区必须干净。
3. 只确认 `BOTZONE_LOCAL_AI_URL` 在当前进程为 present；不输出、复制、散列或拆解值，不读取 `.env`。
4. 内部确认没有正在运行的 `integrations.botzone` connector；只报告 `running/not_running`，不输出进程命令行。
5. 用户确认 Botzone 页面没有仍在进行的旧本地 AI 测试桌，并会新建测试桌。
6. 不运行新的 preflight，不重复单元测试，不修改仓库文件。

任一门槛失败即 `precondition_failed`，不得发送 GET。

### B. 全新运行资源

授权和门槛通过后生成一个新 run ID，并在 `%LOCALAPPDATA%\GuanDan` 下准备：

- 全新、空、独占的 state 目录；
- 全新 audit JSON 路径；
- 路径不得位于仓库内，不得与任何历史目录/文件相同；
- audit 文件启动前必须不存在；
- 不创建 stdout/stderr 重定向文件，不使用 PowerShell `Start-Process`。

不得输出完整绝对路径，只可报告资源已创建以及最终 empty/tombstone 状态。

### C. 唯一前台 connector

从仓库根、当前 Python 环境启动恰好一个前台进程：

```text
python -m integrations.botzone \
  --state-dir <fresh-localappdata-state> \
  --timeout-seconds 120 \
  --max-cycles 100 \
  --max-wall-seconds 900 \
  --stop-after-finished 1 \
  --audit-file <fresh-localappdata-audit>
```

实际 Windows PowerShell 可使用等价参数形式，但必须保持一个前台进程：

- 不传 `--url`，仅由当前进程环境提供；
- 不使用 `Start-Process`、隐藏窗口、第二个 connector 或自动重试；
- 使用工具的持久前台会话等待该进程，不得因普通 10/30 秒工具 yield 将其终止；
- 运行期间定期检查同一会话，直到进程自行结束或超过预注册 wall/timeout 边界；
- 若任务环境无法维持单一前台会话，必须在首次 GET 前 fail-closed。

进程启动并进入长轮询后，立即向用户发送简短操作提示：

```text
connector 已启动。请刷新 Botzone，确认“连接状态”为已连接；然后新建一张测试桌，将“需要进贡”明确设为“否”，选择“用本地 AI 替代我”，并完成创建。请勿复用旧桌。
```

等待用户操作和进程结果，不自动调用 runmatch。

### D. 运行边界

- 默认 Agent 必须是 `RuleBasedAI`；不启用 DeepSeek、RAG 实验开关或模型 prompt。
- 只支持 `deal/play`；出现 `tribute/return` 必须按 `unsupported_stage` 失败，不能用 pass 绕过。
- 最多 100 cycles/GET、900 秒 wall、单次 GET timeout 120 秒、完成 1 局即停。
- 不因暂时没有桌而启动第二个进程。
- transport/protocol/limit/interrupt 任一退出都不重跑。
- 不读取或展示原始请求、response Header、match ID、手牌、history 或 session 内容。
- 用户要求停止时终止唯一进程并判定未完成，不得自动恢复。

### E. 结束审计

进程结束后只读取终端聚合行与 audit JSON；不得读取活动 session 正文。验证：

1. audit schema/version 合法，且不含 URL、Header、match ID、手牌或请求正文。
2. `exit_code=0`。
3. `stop_reason="finished_target"`。
4. `finished_seen=1`。
5. `requests_seen > 0`、`responses_prepared > 0`、`headers_sent > 0`。
6. `transport_failures=0`。
7. diagnostics 为空；没有 `malformed_request`、`unsupported_stage`、outside-legal 或 action/provenance 错误。
8. state 目录只允许为空或包含已验证的最小 finished tombstone；不得输出或复制 tombstone 外内容。
9. 工作区仍干净，仓库没有日志、audit、state 或配置变化。

### F. 判定

全部门槛通过：

```text
botzone_no_tribute_local_ai_smoke_verified
```

任一门槛失败、未完成、用户未建桌、超时、transport/protocol 诊断、贡还 stage、audit 缺失或状态残留：

```text
botzone_no_tribute_local_ai_smoke_invalid
```

invalid 时保留脱敏聚合证据，不修改代码、不重试、不补采；下一步根据唯一失败类别另行规划。

### G. 结论边界

smoke verified 只证明：

- 本地 AI 网关、Bot JSON envelope、adapter、RuleBasedAI、response Header 与 session ack 能完成一局无贡 Botzone 对局；
- 不证明胜率、策略提升、双配子完整覆盖、贡还、多局升级或 DeepSeek 可用；
- 后续实际对抗能力评测必须另行预注册对手、座位、局数与指标。

### 最终报告

报告必须包含：

- 执行 HEAD、检查点与工作区状态；
- 授权参数和 Agent/profile，不输出 URL；
- connector 是否单进程前台运行；
- cycles、GET 上限、wall、timeout、finished、request/response/header、transport 与 diagnostics 聚合；
- state/audit 安全检查；
- 唯一判定；
- 不重试和不形成胜率结论声明。
