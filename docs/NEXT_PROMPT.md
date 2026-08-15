# 下一步实施提示词

## Step L5-A3b：v6 可观测性 live 准入与门槛预注册

L5-A3a 已完成并封存：

```text
botzone_deepseek_runtime_observability_verified
```

实现检查点：

```text
0c51c5ff85f4edbe980dc1b5e63397da6f5747cc
```

v6 audit 已在 integration 层加入不可变、低基数、可守恒的 Agent/模型聚合，并保持 v5 字段语义不变。本步骤只做代码检查点复核、回归、真实进程环境的零网络 preflight，以及下一次人工网页桌 live 的固定门槛和授权问题；不得启动 connector、创建对局或联网。

### 固定前置

1. HEAD 必须包含 `0c51c5ff85f4edbe980dc1b5e63397da6f5747cc`，并复核该提交范围与报告一致；工作区必须干净。
2. state 目录必须存在且为空；L5-A2b21 v5 audit 与 L5-A2b22 cleanup audit 的 bytes/SHA-256 必须保持不变。
3. 不得存在 `integrations.botzone` connector 残留进程。旧桌关闭情况不阻塞零网络 preflight，只在后续请求 live 授权前由项目所有者确认。
4. 只以脱敏元数据核对 Botzone URL 与 DeepSeek key 为 `present`，endpoint/model/timeout/retries 精确为已锁定的 `https://api.deepseek.com`、`deepseek-v4-flash`、60、0；不得输出值或读取 `.env` 内容。
5. 使用项目 `.venv`，在受监督子进程中设置 `PYTHON_DOTENV_DISABLED=1`；不得修改持久配置。

任一前置失败只报告固定 `precondition_failed`，不得创建 state/audit、启动 preflight 或请求 live 授权。

### 回归与零网络 preflight

先运行：

```text
python -m unittest tests.test_botzone_agent_observability tests.test_botzone_deepseek_agent_runtime tests.test_botzone_runner tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

随后使用已存在、为空、仓库外的 state 目录，恰好运行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only
```

可通过参数或当前进程环境传入 state 目录，但不得回显路径。硬上限 30 秒，不重试。成功必须同时满足：

- exit code 0；
- stdout 规范化后只有 `preflight_ready`；
- stderr 为空；
- state 前后为空；
- 无残留进程；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent decision 与 `suggest_action_id()` 均为 0。

失败时唯一判定为对应 `precondition_failed` 或：

```text
botzone_deepseek_observability_live_preflight_invalid
```

不得重跑、联网或请求授权。

### 下一次 live 的预注册审计门槛

preflight 通过后，只准备授权问题，不执行 live。下一次必须继续使用人工网页无贡桌，永久禁止 runmatch；使用一个 connector、一个新桌、全新且不存在的 v6 audit 文件，state 启动前为空。

v6 协议完整性门槛：

- connector `exit=0` 且 `stop_reason=finished_target`；
- request、response、Header 均非零；
- qualified finished 精确为 1，finished 分类守恒；
- transport failure=0，协议 diagnostics/detail/profile 为空；
- state 最终只允许一份最小 finished tombstone；
- `agent_mode=deepseek`，audit 写入本身证明 `observability_valid=true` 的内部门槛已通过。

v6 Agent/模型守恒门槛：

- `agent_decision_count == sum(decision_source_counts)` 且大于 0；
- `model_attempt_count == sum(model_outcome_counts)`；
- `model_attempt_count == model + deepseek_rule_fallback`；
- `rule_fallback_count == deepseek_rule_fallback + adapter_rule_fallback`；
- 所有类别均属于 L5-A3a 固定 allowlist，计数为严格非 bool 非负整数，数组 canonical 且无重复；
- `agent_decision_count <= responses_prepared`，不得推导或持久化逐手数据。

描述性判定顺序：

1. 任一协议、守恒、敏感边界或完整性门槛失败：

```text
botzone_deepseek_observed_live_smoke_invalid
```

2. 协议闭环通过，但 `model_outcome_counts.success == 0` 或 `decision_source_counts.model == 0`：

```text
botzone_deepseek_live_no_model_success_observed
```

3. 协议闭环通过，且至少一次模型 `success` 最终形成 `model` 来源合法动作：

```text
botzone_deepseek_observed_live_smoke_verified
```

第三项只证明本次小样本中观察到至少一次合法模型动作，不证明动作优于 RuleBased、因果收益或胜率提升。

### preflight 通过后的用户确认与授权问题

先要求项目所有者确认：

```text
所有历史 Botzone 本地 AI 测试桌均已结束或关闭：是
本次只创建一个新的 GuanDan 测试桌：是
我会等待实施任务回复 connector_running_create_one_table_when_page_connected，并在页面显示“已连接”后创建“需要进贡=否、用本地 AI 替代我”的唯一新桌：是
进入对局后我会回复“人工新桌已创建并进入对局”：是
页面未连接、建桌失败或出现贡还时，我不会创建第二桌：是
```

只有全部确认为“是”，才提出以下完整授权，仍不得代替用户回答：

```text
我明确授权执行 L5-A3c：不调用 runmatch；使用当前 BOTZONE_LOCAL_AI_URL 启动唯一一个 deepseek 模式 connector，向 local-AI endpoint 最多发送 100 次 GET，单次 Botzone GET timeout 为 120 秒；允许将本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段发送到 https://api.deepseek.com 的 deepseek-v4-flash。DeepSeek timeout 为 60 秒、retries 为 0；最长运行 3600 秒，qualified finished=1 即停。实施任务发出 connector_running_create_one_table_when_page_connected 后，我只创建一个人工无贡桌并在进入后确认。若出现 tribute/return、非零 tribute、协议错误或固定失败门槛，立即停止且不重试。v6 audit 只保存固定聚合计数，不保存 URL、密钥、Header、match、玩家、牌、history、prompt、response、reasoning、action ID 或异常正文。
```

preflight 与全部准入准备通过时，本步骤唯一判定：

```text
botzone_deepseek_observability_live_preflight_ready
```

本步骤不得创建新 Git 提交或修改仓库文件；只输出脱敏门槛结果和授权问题。用户授权必须在后续 L5-A3c 实施任务的当前上下文中明确给出，历史授权不可复用。
