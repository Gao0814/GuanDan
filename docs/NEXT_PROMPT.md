# 下一步实施提示词

## Step L5-A3a：DeepSeek runtime 脱敏聚合可观测性

L5-A2b22 已完成，唯一判定：

```text
botzone_successful_smoke_tombstone_cleanup_verified
```

L5-A2b21 的唯一 finished tombstone 已严格验证并删除，state 文件数 `1 → 0`，目录保留且为空；原 v5 audit 不变。新 cleanup audit 为 405 bytes，SHA-256：

```text
10037c02ffeca2e4967aa3925e893d4386cd9df76cd213086c8ede2260079c13
```

L5-A2b21 已证明 `deepseek` 模式 connector 能完成 Botzone 人工无贡桌协议闭环，但 v5 audit 没有模型调用与 fallback 计数。本步骤只离线实现低基数、可守恒、不可反推牌局内容的 runtime 聚合可观测性；不得联网或恢复 live。

### 范围

优先新增：

- `integrations/botzone/agent_observability.py`
- `tests/test_botzone_agent_observability.py`

仅在确有需要时最小修改：

- `integrations/botzone/agent_runtime.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- 与上述契约直接相关的现有 Botzone 测试

禁止修改：

- `engine/`
- `agents/`
- Botzone cards/models/protocol/poll/session/transport 语义
- 上传 Bot ZIP、RAG 语料、配置文件与 `.env`
- `docs/`（实施结果由后续规划任务统一更新）

### 固定观测模型

新增 frozen/slots 的不可变快照与受控 recorder。内部可使用整数 Counter，但对外只返回排序稳定、不可变、JSON 友好的低基数计数；不得保留逐手事件。

每个真正进入 Agent 动作选择的 `play` 决策必须精确归入一个最终来源：

- `rule_primary`：显式 `--agent rule` 的规则 Agent 正常选择；
- `local_shortcut`：DeepSeekAIAgent 的 only-pass、一次出完或 opening formula 本地快捷路径，未调用模型；
- `model`：模型返回严格合法 action ID，并成为最终动作；
- `deepseek_rule_fallback`：模型 timeout、异常或无效 suggestion 后，由 DeepSeekAIAgent 内部 RuleBased fallback 形成最终动作；
- `adapter_rule_fallback`：主 Agent 抛异常、返回非严格整数或 outside-legal ID，由 Botzone adapter 外层 RuleBased fallback 形成最终动作。

每次实际调用 `_StrictDeepSeekClient.suggest_action_id()` 必须精确归入一个模型结果：

- `success`：严格非 bool 整数，且存在于当前 `legal_actions`；
- `timeout`：捕获 `TimeoutError`；
- `exception`：其他 delegate 异常；
- `invalid_suggestion`：正常返回但对象、action ID 类型、合法集合或结构无效。

所有模型自由文本继续丢弃。不得把异常消息、异常类名、HTTP 状态、延迟、URL、prompt、response、reasoning、action ID、玩家、match 或牌局内容写入 recorder/snapshot/audit。

### 守恒与行为边界

- `agent_decision_count == sum(decision_source_counts)`。
- `model_attempt_count == sum(model_outcome_counts)`。
- DeepSeek 正常组合下，`model_attempt_count == model + deepseek_rule_fallback`；`local_shortcut` 与 `adapter_rule_fallback` 不增加模型调用。
- `rule_fallback_count == deepseek_rule_fallback + adapter_rule_fallback`。
- deal、pending resend、Header 重发、ack、finished、transport timeout/failure 均不增加 Agent 或模型计数。
- 同一已持久化 request 不得因重启、重发或重复 poll 重复计数。
- 多 match/player 只汇总整数，不保留 identity；finished 清理 Agent cache 不清空本次 runner 的累计聚合。
- recorder 或快照异常不得改变合法动作、fallback、pending/effect、ack 或 connector 停止语义；无法形成一致快照时 audit 必须 fail-closed，不得输出部分模型指标。
- 计数必须拒绝 bool、负数、未知类别、重复类别和不可变性破坏。

### Runner 与 audit

`RunnerSummary` 以安全默认值新增：

- `agent_mode`
- `agent_decision_count`
- `decision_source_counts`
- `model_attempt_count`
- `model_outcome_counts`
- `rule_fallback_count`

audit 从 v5 加法升级为 v6：保留所有 v5 字段、名称与语义，仅增加上述固定聚合字段。映射统一序列化为按类别名排序的 `[name, count]` 数组；零计数不得伪造事件。`write_audit()` 必须在写盘前复核类型、allowlist 与全部守恒。

默认 rule 模式必须可审计且零模型计数；deepseek preflight 仍不产生 Agent/model 事件。现有 CLI 参数、退出码、stdout、transport 与 state 行为保持不变。

### 必须新增的离线测试

1. recorder/snapshot frozen、slots、不可变、稳定 JSON、严格整数和 allowlist。
2. rule primary、三个本地快捷路径、合法模型选择、timeout、其他异常、None/bool/string/float/负数/越界 ID 的精确分类。
3. DeepSeek 内部 fallback 与 adapter 外层 fallback 分离；每个决策和每次模型调用只计一次。
4. fallback 自身异常/非法 ID、provenance 缺失和 handler failure 不伪造成功动作来源。
5. deal、pending resend、transport failure、重启、ack、finished 不重复增加计数。
6. 多 match/player 聚合守恒，finished cache cleanup 后 runner 累计不丢失。
7. v6 audit 精确字段快照、v5 字段逐项不变、稳定排序、malformed summary fail-closed。
8. audit 与所有 repr/异常路径不含 URL、key、Header、match、玩家、牌、history、prompt、response、reasoning、action ID 或异常正文。
9. fake client/transport 下验证实际 DNS/socket/HTTP/Botzone/DeepSeek 请求数为 0。
10. 现有 rule/deepseek response、provenance、session、connector、runner 与 preflight 回归保持不变。

最低验证：

```text
python -m unittest tests.test_botzone_agent_observability tests.test_botzone_deepseek_agent_runtime tests.test_botzone_runner tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部离线门槛通过时唯一判定：

```text
botzone_deepseek_runtime_observability_verified
```

完成后建立只含本步骤允许文件的独立 Git 检查点。不得运行 preflight、connector、runmatch 或任何真实网络请求，不得读取真实配置或 `.env`，也不得请求 live 授权。

该判定只证明聚合观测契约与既有动作路径兼容，不证明 DeepSeek 可达、实际调用成功、动作质量或胜率。后续 L5-A3b 必须先做零网络 preflight 与固定 live 审计门槛设计，再单独请求授权。
