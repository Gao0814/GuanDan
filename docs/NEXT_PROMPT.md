# 下一步实施提示词

## Step L5-A1：Botzone connector 的 DeepSeek 离线接线与规则降级

本轮只实现和验证离线接线，不连接 Botzone，不调用真实 DeepSeek，不读取或输出真实 `.env`、API key、本地 AI URL、Header、Cookie、match ID、手牌或请求正文。

### 背景与已确认决策

- 项目所有者已在 U0-A3 明确选择方案 **B：恢复 connector，通过本机调用 DeepSeek**。
- Botzone 上传 Bot 的规则基线继续保留；用户已人工完成两局，但上传评测环境访问 DeepSeek 的探测结果固定为 `probe_dns_or_connect_failed`。
- 唯一既有判定 `botzone_deepseek_egress_admission_blocked` 永久保留，不重试、不追认，也不再作为 connector 路线的前置。
- connector 已具备 Botzone GET/Header、Bot JSON envelope、session pending/ack、无贡协议、公开状态投影、合法 action provenance 与 RuleBasedAI 离线 E2E。
- 当前组合根 `build_foreground_runner()` 仍硬编码 `NoTributeRuleBasedHandler()`；CLI 没有 agent 模式选择。
- `NoTributeRuleBasedHandler` 已支持注入 agent factory，但当前每个 play 都重新创建 agent，不适合作为完整 DeepSeek 会话生命周期的最终形态。
- `DeepSeekAIAgent` 已实现公开 observation/legal actions 输入、合法 action ID 返回、局部快捷路径、RAG、记牌、策略意图以及内部 RuleBased fallback。

### 目标

为本机 Botzone connector 增加一个默认关闭、显式启用的 DeepSeek agent 模式，并用 fake client 完成离线端到端验证：

```text
Botzone envelope
  -> durable session / no-tribute adapter
  -> engine-compatible public observation + canonical legal_actions
  -> match-scoped DeepSeekAIAgent
  -> original legal action_id
  -> provenance lookup
  -> canonical Botzone {"response":[action,claim]}
```

任何模型异常、超时、错误对象、非整数或非法 action ID 都必须在 connector 内最终降级到同一公开局面的 `RuleBasedAIAgent` 合法动作，不得让一次模型失败变成 `agent_failure`、协议停止或 Botzone 决策超时。若经过严格合法 ID 校验后仍缺失 provenance，则属于 adapter 契约破坏，应继续 fail-closed，不能伪造 Botzone 动作。

### 修改前必须阅读

- `AGENTS.md`
- `docs/BOTZONE_INTEGRATION_PLAN.md`
- `docs/CODING_BOUNDARY.md`
- `docs/INVARIANTS.md`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `integrations/botzone/runtime_config.py`
- `integrations/botzone/connector.py`
- `integrations/botzone/session.py`
- `agents/base.py`
- `agents/rule_based_ai.py`
- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- `cli/run_4ai_debug.py`
- 与 Botzone adapter、runner、runtime config、RuleBased E2E、DeepSeek fallback 相关的测试

### 实施要求

1. **默认行为不变**
   - connector 默认仍使用 RuleBasedAI。
   - 只有显式 `--agent deepseek` 才构造 DeepSeek client/agent。
   - 不要以隐式环境开关改变默认模式；不要修改现有上传 ZIP。

2. **组合根集中**
   - 在 `integrations/botzone/` 内新增最小 agent composition/factory 模块，或对现有 runner 组合根做等价的小范围扩展。
   - 复用现有 `AppConfig`、`DeepSeekClient`、`DeepSeekAIAgent` 和 RAG 组装方式，不复制 DeepSeek HTTP 实现。
   - CLI 只负责解析严格的 `rule/deepseek` 模式并传给组合根；协议、session、transport 不感知模型细节。

3. **按 match 隔离生命周期**
   - DeepSeek agent 至少按 `HandlerContext.match_key + local_player_id` 隔离并复用，不能在每个 play 无条件重新创建。
   - 不同 match 不共享 CardTracker、last decision audit 或其他可变 agent 状态。
   - finished 后清理对应缓存；重复请求/pending 重发不得重复调用模型。
   - 若现有 handler/connector 缺少安全的 finished cleanup 通知，本步允许实现一个最小、显式的生命周期接口；不得把 match 状态放入全局变量。

4. **公开信息边界**
   - DeepSeek 只能接收 adapter 已生成的公开 observation 和 canonical legal actions。
   - 不得把 `match_key`、Botzone 实体牌 ID、session record、request digest、Header 或原始 envelope 传给 agent/client。
   - Agent 只能返回原始合法 `action_id`；Botzone `[action, claim]` 必须继续由 provenance 与 `encode_action_claim()` 生成。

5. **双层 fail-closed 降级**
   - 保留 `DeepSeekAIAgent` 内部 fallback。
   - connector adapter 外层仍必须对异常、错误类型和非法 action ID 提供一次确定性的 RuleBased fallback。
   - fallback 也必须通过 `require_legal_action_id()` 与原 provenance 回查。
   - 只有公开状态投影、规则合法动作、provenance 或 response 编码本身不一致时才允许返回协议诊断；模型故障不得终止 connector。

6. **配置与敏感信息**
   - DeepSeek 配置继续使用现有 `AppConfig`/环境契约；不要新增明文凭据文件格式。
   - 缺失 API key 时，显式 deepseek 模式应在启动前返回稳定配置错误；rule 模式不得加载 DeepSeek 配置或 client。
   - 日志、repr、异常、audit 和测试不得包含 key、base URL、本地 AI URL、Header、prompt 或模型响应正文。

7. **首阶段功能范围**
   - 保持“需要进贡=否”；`tribute/return` 继续 fail-closed。
   - DeepSeek 模式默认使用现有主链开关值；不要在本步默认启用 confidence prompt 或 strategy-intent prompt。
   - 不修改 `engine/`、Botzone 卡牌协议、合法动作生成、session schema 或上传 Bot。
   - 不在本步进行真实网络、真实 Botzone smoke、动作质量或胜率实验。

### 建议文件范围

允许按最小实现选择：

- `integrations/botzone/agent_runtime.py`（建议新增）
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `integrations/botzone/runtime_config.py`（仅当严格 agent mode 配置确有必要）
- `tests/test_botzone_deepseek_agent_runtime.py`（建议新增）
- `tests/test_botzone_runner.py`
- `tests/test_botzone_rule_agent_e2e.py`
- 必要的 Botzone CLI/config 测试

禁止修改：

- `engine/`
- `agents/` 的策略与 DeepSeek 行为
- `integrations/botzone/protocol.py`、`cards.py`、`bot_io.py`、`http_transport.py`
- `botzone_upload_py36/`、`botzone_deepseek_probe_py36/`、`dist/`
- `.env`、真实配置、日志和仓库外审计证据

如实现证明必须超出允许范围，先停止并说明具体契约缺口，不要自行扩大任务。

### 最低测试矩阵

1. 默认 rule 模式不构造 AppConfig、DeepSeekClient、RAG 或 DeepSeekAIAgent，既有响应逐字段不变。
2. 显式 deepseek 模式使用 fake client 返回合法 action ID，最终 Botzone response 精确来自对应 provenance。
3. deal、pending response 重发、only-pass/本地快捷路径不会产生不必要的模型请求。
4. fake client 覆盖异常、超时、malformed suggestion、`None`、`bool`、字符串、负数、越界及不在 legal actions 的 ID；全部返回合法 RuleBased fallback。
5. 自然牌、pass、单配子 action/claim 的回写保持正确。
6. 相同 match/player 复用同一 agent；不同 match/player 严格隔离；finished 后清理。
7. transport failure → restart → pending resend → ack 期间不重复调用模型、不重复扣牌。
8. 缺失 key 的 deepseek 模式启动失败且零 transport；rule 模式在同环境正常构造。
9. Agent 观测中不存在 match key、Botzone 实体 ID、request digest、Header 或原始 envelope。
10. 所有测试使用 fake transport/fake client；真实 DNS、socket、HTTP、Botzone GET 和 DeepSeek 请求计数均为 0。

### 验证命令

先运行新增定向测试，再运行：

```text
python -m unittest tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_runner -q
python -m unittest discover -q
git diff --check
```

另做静态边界扫描，确认没有真实 URL/key、`.env` 内容、Header、Cookie、prompt/response 正文、上传 ZIP 改动或 runtime 对 evaluation 的反向导入。

### 验收判定

只有全部离线契约、回归、敏感边界和零网络门槛通过，才能判定：

```text
botzone_deepseek_connector_offline_wiring_verified
```

该判定只允许进入 L5-A2 的真实环境 preflight 与单局 smoke 规划；不代表 connector 已联网成功、DeepSeek 已实际响应、动作质量提升或胜率提升。

完成后请报告：

1. 修改文件与组合根设计；
2. agent 生命周期与清理边界；
3. DeepSeek 故障到 RuleBased fallback 的完整路径；
4. 定向与全量测试结果；
5. 零网络和敏感信息扫描结果；
6. 未解决风险。
