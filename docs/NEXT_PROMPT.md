# 下一步实施提示词

## Step L5-A1a：Botzone DeepSeek connector 启动与降级契约加固

本轮只修复 L5-A1 复核发现的两个离线契约缺口，不连接 Botzone，不调用真实 DeepSeek，不读取或输出真实 `.env`、API key、本地 AI URL、Header、Cookie、match ID、手牌、prompt 或模型响应正文。

### 已确认基线

- L5-A1 实现检查点：`71d9119`（`Add Botzone DeepSeek connector runtime`）。
- 已新增默认 `rule` / 显式 `deepseek` 组合根、match/player Agent 缓存、finished 清理和 DeepSeek 外层 RuleBased fallback。
- DeepSeek 只接收 adapter 生成的公开 observation 与 canonical legal actions；Botzone action/claim 仍由 provenance 编码。
- 模型异常、超时、`None`、bool、字符串、浮点数、越界或非法 action ID 已验证会回退规则动作。
- 定向 23 项、全量 565 项、`git diff --check` 已由实现任务和规划复核分别通过。
- 唯一功能判定保持：

```text
botzone_deepseek_connector_offline_wiring_verified
```

### 复核发现的剩余缺口

1. 默认非 fallback handler 原先将 Agent 异常分类为 `agent_failure`，将非整数或非法 action ID 分类为 `invalid_agent_action_id`。L5-A1 将选择和 ID 校验合并到同一个 `try`，使后两类也变成 `agent_failure`。正常动作不受影响，但默认 RuleBased adapter 的既有诊断契约发生了未锁定变化。
2. `__main__.py` 当前先构造 `LocalAIHttpTransport`，随后 `build_foreground_runner()` 才验证显式 deepseek 模式的 key/client/RAG 组合。构造 transport 不会发网，但缺失 DeepSeek 配置时应在 transport 构造前稳定失败，便于下一步零网络 preflight 审计。

### 目标

做最小加固并锁定精确行为：

- 默认 RuleBased handler 的正常 response 与历史错误分类恢复兼容；
- DeepSeek 主 Agent 失败才进入 RuleBased fallback；
- RuleBased fallback 自身异常、错误类型、非法 ID 与 provenance 缺失分别 fail-closed；
- 显式 deepseek 模式在 Botzone transport 构造前完成纯本地组合验证；
- `--preflight-only --agent deepseek` 可以验证 DeepSeek 配置与本地 RAG 组合，但不得构造 Botzone transport、调用 DeepSeek 或 poll Botzone。

### 修改前必须阅读

- `AGENTS.md`
- `docs/BOTZONE_INTEGRATION_PLAN.md`
- `integrations/botzone/agent_runtime.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `integrations/botzone/http_transport.py`
- `tests/test_botzone_action_provenance.py`
- `tests/test_botzone_deepseek_agent_runtime.py`
- `tests/test_botzone_runner.py`
- `tests/test_botzone_preflight_output.py`
- 与 DeepSeek config/fallback 相关的现有测试

### 实施要求

1. **恢复默认 handler 诊断兼容**
   - `agent.select_action()` 抛异常：`agent_failure`。
   - 返回值不是严格 `int`，包括 bool：`invalid_agent_action_id`。
   - action ID 不在原始 legal actions：`invalid_agent_action_id`。
   - provenance 缺失：`missing_provenance`。
   - 默认 RuleBased 正常 response 必须逐字段不变。

2. **锁定 DeepSeek fallback 分类**
   - 主 Agent 异常、错误类型或非法 ID：调用一次 RuleBased fallback。
   - fallback 正常：返回其合法 action，并沿用原 provenance 编码。
   - fallback `select_action()` 抛异常：`rule_fallback_failure`。
   - fallback 返回非严格整数或非法 ID：`invalid_rule_fallback_action_id`。
   - fallback 合法 ID 仍缺 provenance：`missing_provenance`，不得伪造动作。
   - 不允许 fallback 递归或第二次模型调用。

3. **组合顺序与 preflight**
   - 把 agent runtime 的纯本地构造/验证放在 Botzone `LocalAIHttpTransport` 构造之前。
   - 默认 rule 模式仍不加载 AppConfig、DeepSeekClient 或 RAG。
   - 显式 deepseek 缺 key、配置字段非法或 RAG 本地加载失败时，固定返回 `configuration_error` / exit 2；Botzone transport 构造次数为 0。
   - `--preflight-only --agent rule` 保持既有 `preflight_ready` 契约。
   - `--preflight-only --agent deepseek` 应完成纯本地 agent composition 验证后输出同一固定 `preflight_ready`；不得调用 `suggest_action_id()`、DNS、socket、HTTP、Botzone poll 或 DeepSeek。
   - 不得输出失败原因正文、配置值、路径、URL 或 key。

4. **范围控制**
   - 不修改 `engine/`、`agents/`、Botzone protocol/session/cards/bot envelope、上传 Bot 或 ZIP。
   - 不改变 match/player cache、pending/ack、finished cleanup 和 response provenance 的正常语义。
   - 不新增依赖，不联网，不启动真实 connector。

### 允许修改文件

- `integrations/botzone/agent_runtime.py`
- `integrations/botzone/play_adapter.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `tests/test_botzone_deepseek_agent_runtime.py`
- `tests/test_botzone_action_provenance.py`
- 必要的 runner/preflight CLI 测试

如确实需要修改其他文件，先停止并说明契约缺口，不要自行扩大范围。

### 最低测试

1. 参数化锁定默认 handler 的 `agent_failure`、`invalid_agent_action_id`、`missing_provenance`。
2. 参数化锁定 DeepSeek fallback 的成功、`rule_fallback_failure`、`invalid_rule_fallback_action_id`、`missing_provenance`。
3. 验证主 Agent 每次最多调用一次，fallback 每次最多调用一次。
4. rule 模式 config/client/RAG/transport 构造边界保持不变。
5. deepseek 缺 key时 `LocalAIHttpTransport` 构造为 0、runner 构造为 0、退出 2。
6. deepseek preflight 使用合成配置/fake factories，成功输出精确 `preflight_ready`，全部网络调用为 0。
7. preflight 配置失败时 stdout 只有固定 `configuration_error`，stderr 为空且不泄露异常正文。
8. 既有缓存隔离、finished 清理、pending 重发、response/provenance 与 RuleBased E2E 回归保持通过。

### 验证命令

```text
python -m unittest tests.test_botzone_deepseek_agent_runtime tests.test_botzone_action_provenance tests.test_botzone_runner tests.test_botzone_preflight_output -q
python -m unittest discover -q
git diff --check
```

另做静态边界扫描，确认无真实 URL/key、`.env` 内容、Header、Cookie、prompt/response 正文、新网络客户端或上传 ZIP 改动。

### 验收判定

全部通过后唯一判定：

```text
botzone_deepseek_connector_hardening_verified
```

该判定只允许规划 L5-A2 的真实环境零网络 preflight；不授权启动 connector，不代表 DeepSeek 可达、Botzone 对局闭环、动作质量或胜率提升。

完成后请报告：

1. 修改文件；
2. 精确诊断分类矩阵；
3. agent/config/transport 构造顺序；
4. preflight 的零网络证据；
5. 定向与全量测试结果；
6. 未解决风险。
