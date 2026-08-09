# 下一步实施提示词

## Step L4-A2a：Botzone 一局 live smoke 只读前置审计与授权请求

请在 GuanDan 项目中完成 Step L4-A2a。本步只做检查点、回归、运行时配置和零网络 preflight 审计，最后向用户请求一次明确的 Botzone 联网授权。不得启动 connector、不得发送探测请求、不得创建或加入对局、不得修改代码。

### 前置与检查点

历史判定保持：

```text
botzone_live_smoke_preflight_ready
```

L4-A1 检查点为：

```text
e4a4fba99211831c66062ac0f003094edc941c6a
```

当前 L4-A1a 实际修改范围为以下十个文件，已复核定向 46 项、全量 515 项和 `git diff --check`：

- `integrations/botzone/__main__.py`
- `integrations/botzone/http_transport.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/runtime_config.py`
- `integrations/botzone/session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_http_transport.py`
- `tests/test_botzone_runner.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_live_preflight.py`

开始本步前必须先把这十个文件独立封存。不得把 docs、运行时 state、audit 或其他文件混入检查点。提交后工作区必须干净。

### 只读审计顺序

1. 复核 L1 至 L4-A1a 所需检查点存在，L4-A1a 提交范围精确；
2. 运行 46 项定向测试、515 项全量基线和 `git diff --check`；
3. 确认工作区干净；若不干净，立即返回 `precondition_failed`，不检查环境、不运行 preflight；
4. 由用户明确确认截图中曾暴露的 Botzone 本地 AI 连接密钥/URL 已在 Botzone 设置页轮换；不得通过读取、比较、散列或输出 URL 自行推断；
5. 仅检查当前进程中 `BOTZONE_LOCAL_AI_URL` 与 `BOTZONE_STATE_DIR` 是否存在，不输出值、长度、hash、host、path 或任何片段；
6. state dir 必须是仓库外全新绝对目录，运行前不含 session/tombstone；audit file 也必须位于仓库外新目录；
7. 执行一次 `python -m integrations.botzone --preflight-only`；该调用只能输出固定 `preflight_ready`，必须为零 opener、零 socket、零 HTTP；
8. preflight 后确认 state dir 仍为空，仓库状态仍干净；
9. 只有全部通过后，输出 `botzone_live_smoke_authorization_ready` 并请求授权。

任何前置失败都不得尝试修复真实配置、读取 `.env`、回显 URL、启动 connector 或联网。只报告规范化缺失项。

### 凭据轮换要求

- 截图中出现过的旧密钥和旧 URL 视为已泄露，不能用于 smoke；
- 用户必须在 Botzone 本地 AI 设置页生成/提交新连接密钥，再把新 URL 注入启动 Codex 的进程环境；
- 不得把新 URL 粘贴到聊天、命令行参数、文档、测试、audit、日志或 Git；
- 本次 live 推荐只使用环境变量，不使用 `--url`，避免进入命令历史或进程参数；
- 审计只记录 `credential_rotation_confirmed=true` 与配置 `present`，不记录任何值。

如果用户尚未明确确认轮换，只返回：

```text
precondition_failed: botzone_credential_rotation_unconfirmed
```

不得替用户假设已经轮换。

### 锁定的一局 smoke 预算

授权请求必须精确说明后续 L4-A2b 将使用：

- Agent：`RuleBasedAIAgent`；
- 建桌：用户手动创建，仅一局；明确“需要进贡=否”；
- connector：前台单进程，正式 live run 恰好一次；
- `timeout_seconds=30`；
- `max_cycles=100`，即最多 100 次 GET poll；
- `max_wall_seconds=600`；
- `stop_after_finished=1`；
- `max_consecutive_failures=5`；
- `backoff_seconds=1`，按现有确定性指数退避；
- state/audit：仓库外全新目录；
- 不使用 runmatch，不自动建桌，不接入 DeepSeek，不做自动重启；
- transport failure 只按 runner 已封板的有界重试；协议、session、handler 或 unsupported stage 立即 fail-closed；
- 达到 finished、wall、cycle、failure、diagnostic 或用户中断任一边界后停止，不补采、不启动第二进程。

### live 后预注册判定

完整性优先，按以下顺序：

1. 进程恰好一次，参数与预算一致；
2. `finished_seen=1`、stop reason=`finished_target`、exit code=0；
3. requests/responses/headers/cycles 守恒，diagnostics 为空；
4. state dir 只剩最小 tombstone，扫描不含 match ID、手牌、history、response、digest、URL 或 Header；
5. audit schema 合法且只含聚合字段；
6. Botzone 桌面实际设置为“需要进贡=否”，请求只出现 deal/play；
7. 未出现非法响应、超时终止、跨局污染或 unsupported stage。

任一完整性门槛失败，唯一 live 判定为：

```text
botzone_no_tribute_local_ai_smoke_invalid
```

全部通过才可判定：

```text
botzone_no_tribute_local_ai_smoke_verified
```

该判定只证明一局真实平台接入闭环可用，不证明 AI 对抗能力、胜率、稳定性或完整 Botzone GuanDan 支持。

### 本步禁止事项

- 不读取 `.env`、真实 URL、密钥、Cookie、Header、账号或浏览器存储；
- 不联网、不调用 Botzone、不发送 GET probe；
- 不创建 runner 副本、后台进程、state 或 live audit；
- 不调用 DeepSeek 或其他外部服务；
- 不修改任何仓库文件；
- 不提交或保存 Botzone 页面截图中的敏感值。

### 建议验证命令

```text
python -m unittest tests.test_botzone_http_transport tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_connector tests.test_botzone_session tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_adapter_observation -q
python -m unittest discover -q
git diff --check
```

环境存在性和 `--preflight-only` 检查只能在上述仓库门槛通过、用户确认凭据轮换之后执行。

### 验收与授权请求

全部只读门槛通过时，唯一判定：

```text
botzone_live_smoke_authorization_ready
```

随后必须原样说明 endpoint 为“当前进程中已配置且已脱敏的 Botzone 本地 AI URL”，不得输出 host/path；列出上述固定预算，并询问：

```text
是否明确授权使用当前进程中已配置且已轮换的 Botzone 本地 AI URL，执行一次 L4-A2b 无贡手动桌 smoke：RuleBasedAI、最多 100 次 GET、最长 600 秒、30 秒单次 timeout、连续失败上限 5、完成 1 局即停止？
```

没有用户明确回答“授权”前，不得启动 connector。
