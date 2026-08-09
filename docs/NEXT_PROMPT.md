# 下一步实施提示词

## Step L4-A1a：Botzone live smoke 准入加固与离线前置审计

请在 GuanDan 项目中完成 Step L4-A1a。本步只加固真实 Botzone smoke 前的启动、停止、状态清理和审计边界；全部验证使用 fake opener/fake gateway，不得连接 Botzone、不得读取真实 URL/密钥、不得创建或加入真实对局。

### 前置与检查点

历史判定保持：

```text
botzone_local_connector_offline_verified
```

L3-A1a 已封存为：

```text
253159f7cf00e9995cc986bac816bf67a8596a4e
```

当前 L4-A1 只有以下七个未跟踪文件，已复核定向 42 项、全量 511 项和 `git diff --check`：

- `integrations/botzone/http_transport.py`
- `integrations/botzone/runtime_config.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `tests/test_botzone_http_transport.py`
- `tests/test_botzone_runtime_config.py`
- `tests/test_botzone_runner.py`

开始本步前必须先把这七个文件独立封存，不得混入 docs 或 L4-A1a 修改。

### 当前必须关闭的 live 缺口

1. runner 只能按 cycle 数或 Ctrl+C 停止，不能按完成对局数停止，也没有 wall-clock 硬上限；
2. `unsupported_stage`、malformed poll、session/handler 错误只进入 diagnostics，runner 仍可能继续 poll；
3. `RunnerSummary` 未聚合 request/response/header/finished 数，无法形成最小 smoke 守恒审计；
4. finished session 当前仍持久化 match ID、本家实体手牌、完整累计 history、缓存 response 和 request digest；
5. HTTP response 未明确保证关闭；Header 名仍需锁定为严格 ASCII HTTP token；
6. module 入口对 failure limit、协议失败和未完成的 cycle/wall limit 没有区分退出码；
7. 缺少不联网的 `preflight-only`，无法在 live 授权前验证配置、state dir 和启动输出脱敏。

### 允许修改

- `integrations/botzone/http_transport.py`
- `integrations/botzone/runtime_config.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- 必要时最小修改 `integrations/botzone/connector.py` 与 `integrations/botzone/session.py`
- 对应 Botzone 测试；可新增 `tests/test_botzone_live_preflight.py`

不得修改 `engine/`、`agents/`、现有 `cli/`、RAG、evaluation、DeepSeek 或协议/adapter 的动作语义。不得新增第三方依赖。

### bounded smoke runner

- `RunnerSummary` 至少聚合 cycles、successful cycles、transport failures、headers sent、requests seen、responses prepared、finished seen、diagnostics 和 stop reason；
- 支持严格正整数 `max_cycles`、`max_wall_seconds`、`stop_after_finished`；bool 不得冒充整数；
- wall-clock 在每次 poll 前后检查；单次阻塞仍受 transport timeout 限制，并明确总时间最多超出一个 timeout；
- 达到 `stop_after_finished=1` 后不得再发下一次 poll；
- transport failure 可按现有有界退避重试，成功后清零连续失败；
- 除 `transport_failure` 外，任何非零 connector diagnostic 均按 live fail-closed 停止，不得继续轮询或伪造响应；
- `unsupported_stage` 必须产生独立 stop reason 和非零退出码；
- `KeyboardInterrupt` 正常、安全停止，但不得把它算作完成 smoke；
- 同时满足多个停止条件时使用固定优先级并测试。

### 退出码与前台输出

锁定稳定分类，具体数字可按现有风格选择，但必须测试并写入模块帮助：

- 配置/preflight 失败；
- transport 连续失败上限；
- 协议、session、handler 或 unsupported-stage 失败；
- cycle/wall 上限到达但没有 finished；
- 完成指定 finished 数；
- 用户中断。

stdout/stderr 只允许固定状态与聚合整数。不得输出 URL、state dir、match ID、Header 名/值、请求/响应、手牌、history、action、异常原文或账号信息。

### finished session 最小化

- 收到 finished row 后，必须删除活动 session 中的手牌、history、pending/cached response、request bytes/digest 和原始 match ID；
- 可直接原子删除活动文件，或写入仅含 schema/version、不可逆内部 key、finished 标志及必要聚合结果的 tombstone；
- tombstone 不得包含 match ID、座位明细、手牌、history、response、Header 或 URL；
- 重复 finished 必须幂等；finished 后不得再发送旧 pending response；
- crash/restart 前的活动 session 仍需保留恢复所需状态，因此只在已收到 finished 后清理；
- state dir 在 live 中必须使用仓库外绝对路径，不能位于项目目录、`logs/` 或 `archive_legacy/`。

### HTTP 与配置加固

- response 必须在成功、过大、状态错误和解析异常路径全部关闭；
- Header 名严格限制为 ASCII HTTP token，并继续只允许 `X-Match-<validated-id>`；值保持严格 ASCII、无控制字符；
- redirect、timeout、TLS、HTTP、DNS 和未知 opener 错误保持脱敏分类；异常链不得保留 URL；
- `preflight-only` 只做 URL 结构、数值边界和 state dir 可创建/原子写/清理检查，不构造真实请求、不调用 opener；
- state dir 检查不得删除已有 session；测试使用临时目录；
- runtime 仍只接受显式参数或 `BOTZONE_LOCAL_AI_URL` / `BOTZONE_STATE_DIR`，不加载 `.env` 或根 `config.py`；
- 实际 live 推荐只用环境变量，避免 URL 出现在命令历史和进程参数中。

### 最小审计报告

可增加显式 `--audit-file`，但必须：

- 由调用方指定仓库外路径并原子写入；
- 只含固定 schema/version、起止状态、上述聚合计数、stop reason、退出分类和规范化 diagnostics；
- 不含 URL、state dir、match ID、Header、请求/响应、手牌、history、action、平台原始 score 或时间戳型样本身份；
- 同一 fake corpus 结果确定性可序列化；malformed audit path fail-closed。

### 必测场景

- `stop_after_finished=1` 精确停止且不多发 poll；
- wall/cycle/failure/diagnostic/unsupported/interrupt 停止优先级和退出码；
- transport 失败后 pending response 保留，成功 ack 后 effect 只提交一次；
- finished 清除活动敏感状态，重复 finished 幂等，重启不恢复已结束手牌；
- malformed/tribute/return 不调用 Agent，并立即结束该 smoke；
- response 在成功和全部异常路径关闭；
- 非 ASCII Header、CR/LF、控制字符、重定向和未知 opener 异常安全失败且不泄露 URL；
- preflight-only 零 opener/零 socket/零 HTTP 调用，并验证仓库内、相对、不可写 state dir 拒绝；
- audit/stdout/stderr/source scan 不含敏感字段或真实配置值；
- fake gateway 完成一局的 deal/play/finished 聚合守恒；
- 所有 L1-L4 回归与全量测试保持通过。

### 建议验证命令

```text
python -m unittest tests.test_botzone_http_transport tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_connector tests.test_botzone_session tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_adapter_observation -q
python -m unittest discover -q
git diff --check
```

如未新增 `tests/test_botzone_live_preflight.py`，从定向命令删除该模块，不要创建空测试文件。

### 验收判定

全部离线启动、停止、清理、审计、安全边界和回归通过时，唯一判定：

```text
botzone_live_smoke_preflight_ready
```

该判定只允许下一步检查运行时三项前置：工作区干净、截图中暴露过的 Botzone URL/密钥已轮换、显式进程环境配置存在。之后仍必须向用户说明一局 smoke 的固定预算并取得新的明确联网授权；不得在本步启动 connector 或发送探测请求。

### 最终报告

报告 L4-A1 检查点、修改文件、停止优先级、退出码、finished 清理、response close、preflight-only、审计字段、定向/全量测试和边界扫描。明确说明未读取真实 URL/密钥、未读取 `.env`、未联网、未创建对局、未修改 engine/agents、未接入 DeepSeek。
