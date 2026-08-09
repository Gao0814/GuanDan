# 下一步实施提示词

## Step L4-A3b：信封修复检查点与真实 smoke 零网络准入

请在 GuanDan 项目中执行 Step L4-A3b。本轮只封存 L4-A3a、复核回归并执行一次零网络 preflight；不得启动 connector、发送 GET、创建或加入 Botzone 对局。只有得到 `preflight_ready` 后，才能在最终报告中向用户请求新的 live 授权。

### 已封板事实

- L4-A3a 唯一判定：`botzone_bot_json_envelope_contract_verified`。
- 外层 Bot JSON 使用累计 `requests/responses`；GuanDan `deal/play` 是其中的内层请求。
- 第一条无贡 deal 与既往 play response 可冷启动重放本家实体手牌。
- 无贡 `play.global` 要求 `tribute_cards`、`return_cards` 都是空 mapping。
- Header 前的输出已 canonical 包装为 `{"response": ...}`。
- 定向相关测试 47 项、全量 532 项和 `git diff --check` 已由实现任务报告通过。
- 实现任务未联网、未读取 `.env` 或真实连接值。
- 旧 `malformed_request` smoke、L4-A2b 以及全部既有 invalid/inconclusive 结论永久保留，不能被本步追认。
- 旧测试桌、旧授权与旧 state/audit 不得复用。

### A. 工作区与差异门槛

开始时允许工作区不干净，但差异必须严格限制在以下 L4-A3a 与规划文件：

```text
integrations/botzone/bot_io.py
integrations/botzone/connector.py
integrations/botzone/poll.py
integrations/botzone/protocol.py
integrations/botzone/session.py
tests/test_botzone_bot_io.py
tests/test_botzone_connector.py
tests/test_botzone_live_preflight.py
tests/test_botzone_poll.py
tests/test_botzone_profile.py
tests/test_botzone_protocol.py
tests/test_botzone_rule_agent_e2e.py
tests/test_botzone_runner.py
tests/test_botzone_session.py
docs/BOTZONE_INTEGRATION_PLAN.md
docs/NEXT_PROMPT.md
docs/PLAN.md
docs/PROJECT_STATUS.md
docs/TESTS.md
```

要求：

1. 记录执行前 HEAD 和 `git status --short`。
2. 不还原、清理或覆盖任何差异。
3. 如存在 allowlist 外的修改，立即返回 `precondition_failed`，不得提交或执行 preflight。
4. 只读确认新增实现没有修改 `engine/`、`agents/`、CLI、RAG、evaluation、配置或 `.env`。
5. 不读取或输出真实 URL、密钥、Cookie、Header、match ID、手牌或历史请求正文。

### B. L4-A3a 回归复核

重新运行 L4-A3a 的 Botzone 定向集合，至少覆盖 bot_io、poll、connector、session、protocol、profile、runner、live preflight 与 RuleBased E2E；随后运行：

```text
python -m unittest discover -q
git diff --check
```

复核以下契约：

- `len(requests) == len(responses) + 1`；
- deal/pass/自然牌/配子 response wrapper；
- 冷启动历史重放与实体牌守恒；
- pending resend、ack 后 effect 提交与多 match 隔离；
- `tribute/return` 和非空贡还 mapping fail-closed；
- fixture 不包含真实 live 数据或敏感配置。

任一回归或边界失败即 `botzone_envelope_live_smoke_preflight_invalid`，不得提交、不得继续 preflight。

### C. 独立检查点

回归通过后：

1. 只暂存上述 allowlist 文件。
2. 提交消息使用 `Add Botzone JSON envelope replay`。
3. 记录完整 commit hash 和精确提交文件列表。
4. 提交后工作区必须干净；否则停止，不执行 preflight。

该提交只表示离线协议检查点，不表示 live 可用。

### D. 零网络真实环境 preflight

检查点干净后执行：

1. 只确认 `BOTZONE_LOCAL_AI_URL` 在当前进程为 present，不输出值、host、path、长度或 hash；不读取 `.env`。
2. 在 `%LOCALAPPDATA%` 下创建本任务独占、全新、空的 state 目录；不得使用仓库目录、旧 `BOTZONE_STATE_DIR`、旧 smoke 目录或旧测试桌状态。
3. 使用当前环境 URL 和显式新 state 目录，前台执行现有 `python -m integrations.botzone --preflight-only` 恰好一次。
4. 硬上限 30 秒，不重试；只接受 exit code 0 和固定输出 `preflight_ready`。
5. preflight 前后 state 目录必须为空；结束后只删除本任务创建且仍为空的目录。
6. 确认 preflight 未构造 transport/opener，request/GET/network/connector count 均为 0。
7. 不运行 `live_preflight` 诊断矩阵，不恢复 L4-A2c5b2a，不修改永久环境变量。

若配置缺失、目录不可用、超时、输出错误、目录残留或网络计数非零，唯一判定：

```text
botzone_envelope_live_smoke_preflight_invalid
```

全部通过后的唯一判定：

```text
botzone_envelope_live_smoke_preflight_ready
```

### E. 锁定后续 live 预算

preflight ready 后只锁定、不得执行下一步 L4-A3c：

- Agent：默认 `RuleBasedAI`；
- 对局：用户新建一张测试桌，明确选择“需要进贡=否”；
- 连接方式：用户可见的前台 connector，不使用隐藏 launcher；
- state/audit：`%LOCALAPPDATA%` 下全新目录和文件；
- timeout：120 秒；
- `max_cycles=100`；
- `max_wall_seconds=900`；
- `stop_after_finished=1`；
- 最多 100 次 GET；
- 不重试第二个 live 进程；
- 不使用 runmatch，不接 DeepSeek，不复用旧桌、旧 state、旧 audit 或旧授权。

只有 preflight ready 时，最终报告末尾才能原样请求：

```text
已完成 L4-A3b 零网络前置审计。拟使用当前已配置的 BOTZONE_LOCAL_AI_URL，启动一次前台 RuleBasedAI 无贡 smoke：全新测试桌、全新 LocalAppData state/audit，最多 100 次 GET，timeout 120 秒，最长 900 秒，完成 1 局即停，不重试。是否明确授权执行本次 L4-A3c 真实 Botzone 请求？
```

用户未明确授权前不得联网。

### 最终报告

报告必须包含：

- 执行前后 HEAD、提交 hash、精确提交文件；
- 定向与全量测试结果、`git diff --check`；
- 环境变量仅 present/missing；
- preflight exit、固定输出、耗时、state 前后 empty；
- request/GET/network/connector count；
- 唯一判定；
- ready 时的固定 live 授权问题，或 invalid 时的单一阻塞原因。
