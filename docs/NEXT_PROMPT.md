# 下一步实施提示词

## Step L4-A1：Botzone 本地 AI HTTP connector 与前台 runner 离线验收

请在 GuanDan 项目中完成 Step L4-A1。本步实现可启动的 Botzone 本地 AI connector 代码，但所有验收必须使用注入式 fake HTTP opener/transport，禁止连接 Botzone、禁止读取真实 URL/密钥、禁止创建或加入真实对局。

### 前置与检查点

历史判定保持：

```text
botzone_adapter_observation_hardening_verified
```

L3-A1 主链检查点为：

```text
39bd881f7155a35a49f989910be7dcd8bd23e02a
```

当前 L3-A1a 仅包含以下四个预期改动，已验证定向 45 项、全量 500 项和 `git diff --check`：

- `integrations/botzone/play_adapter.py`
- `tests/test_botzone_play_adapter.py`
- `tests/test_botzone_action_provenance.py`
- `tests/test_botzone_adapter_observation.py`

开始本步前，必须先复核并把这四个文件创建为独立检查点。不得把 docs 或 L4-A1 文件混入该检查点。

### 目标

在不改变 L1/L2/L3 契约的前提下，补齐：

1. 标准库实现的真实 HTTP GET transport；
2. 只从显式环境变量或启动参数读取的 runtime 配置；
3. 组合 `SessionStore`、现有 connector、`NoTributeRuleBasedHandler` 的前台运行器；
4. 超时、断线、退避、停止与敏感信息脱敏；
5. 完全离线的 fake opener/mock gateway 端到端测试。

本步不运行真实 connector，不发送网络请求，不自动建桌，不使用 `runmatch`，不接入 DeepSeek。

### 推荐模块

- `integrations/botzone/http_transport.py`：HTTP GET、Header 编码、响应大小上限和错误归一化；
- `integrations/botzone/runtime_config.py`：显式参数/环境变量解析，不导入项目根 `config.py`，不加载 `.env`；
- `integrations/botzone/runner.py`：依赖装配、前台循环、退避与退出状态；
- `integrations/botzone/__main__.py`：仅提供 `python -m integrations.botzone` 启动入口；
- `tests/test_botzone_http_transport.py`；
- `tests/test_botzone_runtime_config.py`；
- `tests/test_botzone_runner.py`。

若现有结构需要不同文件名，可以最小调整，但不得修改 `engine/`、`agents/`、现有 `cli/`、RAG、evaluation 或 DeepSeek。不要为了命名把现有 `MockConnector` 做无关重构。

### 配置与敏感信息

- 连接 URL 只允许通过显式启动参数或进程环境变量 `BOTZONE_LOCAL_AI_URL` 传入；
- state dir 只允许通过显式启动参数或 `BOTZONE_STATE_DIR` 传入；
- 不读取 `.env`，不导入会隐式加载 `.env` 的根 `config.py`；
- URL 视为整体敏感信息，因为路径中包含连接密钥；不得输出、记录、持久化、散列或放入异常文本；
- 不得记录 match ID、`X-Match-*` Header、请求/响应正文、手牌、Cookie 或账号信息；
- `repr()`、配置错误、transport 错误、runner 摘要、stdout/stderr 均不得泄露 URL；
- 截图中曾暴露的旧连接 URL/密钥必须在 Phase 4 前轮换，本步不得检查其值。

### HTTP transport 契约

- 只允许 HTTPS URL；拒绝 userinfo、fragment 和非 HTTPS scheme；
- 每次 poll 必须是 GET 且无 body；
- 只转发 connector 已生成并校验的 `X-Match-<match_id>` pending response Header；
- Header 名和值必须拒绝 CR/LF、控制字符和无法安全编码的值；
- 使用有限 timeout 和有限响应体大小；超时、DNS/TLS、HTTP 状态、重定向和过大响应统一转成不含敏感信息的稳定错误；
- 默认拒绝重定向，避免把敏感 URL 或 Header 转发到其他地址；
- transport 单次调用不内置重试，pending response 的保留/ack 仍由现有 connector/session 事务负责；
- HTTP 客户端/opener 必须可注入，测试不得打开 socket。

### runner 契约

- 默认 Agent 为 `RuleBasedAIAgent`；
- 组合现有 `SessionStore`、connector 和 `NoTributeRuleBasedHandler`，不得让 Agent 看到 Botzone ID、URL、Header 或 match ID；
- 以前台进程运行，不自建后台服务、不打开 GUI、不自动创建对局；
- 支持注入 clock/sleep/transport，并提供测试用有限 cycle 上限；
- transport 失败采用有上限的确定性退避，成功后重置；不得 busy-loop；
- `KeyboardInterrupt` 正常停止，启动配置错误使用稳定非零退出码；
- `tribute/return/unknown` 继续 fail-closed，不生成 pass 或替代动作；
- 启动摘要和结束摘要只保留非敏感聚合计数，不显示 URL、Header、请求正文或 match ID。

### 必测场景

- GET method、空 body、timeout 与批量 pending Header 的精确传递；
- Header 注入、非法编码、HTTP 错误、DNS/TLS/timeout、重定向和超大 body 安全失败；
- URL 不出现在异常、`repr()`、stdout/stderr、session snapshot 或诊断中；
- 参数与环境变量优先级、缺失/空/非法配置、严格整数/布尔边界；
- 证明 runtime 配置模块不导入 dotenv 或根 `config.py`，不读取 `.env`；
- runner 的失败退避、成功重置、最大连续失败、有限 cycle 和 Ctrl+C；
- fake gateway 下 `deal → play → transport failure → restart → resend → ack`，实体牌 effect 只提交一次；
- 多 match Header 与 session 隔离、finished 清理；
- unsupported stage 不调用 Agent、不产生可执行 response；
- 所有既有 L1/L2/L3 测试和全量回归保持通过；
- 测试通过 monkeypatch/fake opener 证明没有真实 socket 或网络访问。

### 建议验证命令

```text
python -m unittest tests.test_botzone_http_transport tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_connector tests.test_botzone_session tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_adapter_observation -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部离线 transport、配置、runner、安全边界与回归通过时，唯一判定：

```text
botzone_local_connector_offline_verified
```

该判定只证明 connector 在 fake gateway 下可启动、可恢复、可安全处理协议；不代表真实 Botzone 已连接，不授权联网，不证明能完成真实对局或具备对抗能力。

### 最终报告

报告 L3-A1a 检查点、新增模块、配置来源、GET/Header/重定向策略、退避与退出行为、fake gateway E2E、定向/全量测试和边界扫描。明确说明未读取真实 URL/密钥、未读取 `.env`、未联网、未创建对局、未修改 engine/agents、未接入 DeepSeek。
