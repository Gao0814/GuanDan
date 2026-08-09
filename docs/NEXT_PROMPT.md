# 下一步实施提示词

## Step L4-A3a：Bot JSON 交互信封、历史重放与响应包装契约

请在 GuanDan 项目中执行 Step L4-A3a。本轮只做离线协议修复和测试，不联网、不启动真实 connector、不创建 Botzone 对局，也不请求 live 授权。

### 已确认事实

- 手工无贡测试桌已显示本地 AI 为“已连接”，证明本机 GET 长轮询、URL 和 Botzone 网关链路可达。
- 进入对局后 connector 在第一个请求以 `malformed_request`、exit code 5 退出；`requests_seen=1`，但尚未调用 Agent，也没有生成 response Header。
- Botzone 实际下发的是标准 Bot JSON 交互信封：顶层包含 `requests` 与 `responses`；GuanDan 的 `deal`、`play` 对象位于 `requests` 数组内。
- 当前 `poll.py` 把整个顶层 JSON 直接交给 `parse_stage_request()`，而该函数要求顶层存在 `stage`，这是本次失败的直接协议原因。
- 不能只取 `requests[-1]`：首条 `deal` 保存本家座位和 27 张实体牌，后续 `play` 需要重放此前 `requests/responses` 才能在冷启动或重连时恢复当前手牌。
- 已观察的无贡 `play.global` 除既有字段外还包含空的 `tribute_cards` 与 `return_cards`。
- Bot 标准输出必须包装为 `{"response": ...}`；当前 handler 只生成内部 `[]` 或 `[action, claim]`。
- 用户提供的真实请求含完整手牌，只可用于确认结构，不得复制到源码、测试、fixture、文档、日志或提交。
- L4-A2c5b2 及此前 invalid/inconclusive 结论永久保留。L4-A2c5b2a 文件系统矩阵暂缓，不再是当前关键路径。

### 官方依据

实现前重新阅读并引用当前官方页面：

- Bot JSON 交互协议：<https://wiki.botzone.org.cn/index.php?title=Bot%2Fzh-cn>
- GuanDan 内层请求/响应协议：<https://wiki.botzone.org.cn/index.php?title=GuanDan>

必须区分：Bot 网关的外层交互信封与 GuanDan 裁判的内层 stage 请求。不得根据旧测试或截图推测字段。

### A. 前置检查

1. 工作区必须干净，记录 HEAD；如不干净则 `precondition_failed`，不得清理用户改动。
2. 阅读 `AGENTS.md`、`docs/BOTZONE_INTEGRATION_PLAN.md`、`docs/CODING_BOUNDARY.md`、`docs/INVARIANTS.md`，以及 `integrations/botzone/` 下的 `poll.py`、`protocol.py`、`models.py`、`session.py`、`connector.py`、`play_adapter.py` 和相关测试。
3. 确认本轮不读取 `.env`、`BOTZONE_LOCAL_AI_URL`、Cookie、账号信息或真实 Header 值。
4. 不使用用户提供的真实 27 张牌；测试必须使用人工合成、无敏感信息的牌 ID。

### B. 外层 Bot JSON 模型

建议新增 `integrations/botzone/bot_io.py`，也可按现有命名风格选择等价模块。模型应使用 `frozen=True, slots=True`，并满足：

- 顶层必需字段为 `requests`、`responses`。
- 官方字段 `data`、`globaldata`、`time_limit`、`memory_limit` 作为可选字段；实际请求未携带这些字段时仍合法。
- 拒绝未知顶层字段、错误容器类型、空 `requests`、bool 冒充整数和不可 JSON 化值。
- 严格要求 `len(requests) == len(responses) + 1`。
- 每个 `requests[i]` 必须经现有 GuanDan stage parser 解析，不重复实现牌 ID、history 或 claim 规则。
- `tribute`、`return` 和未知 stage 继续结构化 fail-closed，不生成可执行 response。

### C. 历史重放

从完整信封重建本家当前上下文：

1. 第一条请求必须是合法无贡 `deal`，提供稳定的 `your_id`、level 和 27 张实体手牌。
2. `responses[i]` 必须与 `requests[i]` 对应：
   - `deal` 的历史 response 精确为 `[]`；
   - `play` 的历史 response 精确为合法 `[action, claim]`；
   - action 实体 ID 从当时本家手牌中精确扣除一次；pass 不扣牌；
   - claim 继续使用现有自然牌/配子多重集规则校验。
3. `your_id` 以首条 deal 为准；后续字段如再次出现必须一致。所有请求的 level 和 no-tribute profile 必须一致；矛盾时整体失败。
4. 最新未回答请求作为当前 stage；输出重建后的本家实体手牌、累计公开 history、latest window 和 current request。
5. 冷启动、进程重启和本地 session 缺失时，应能仅凭完整交互信封恢复公开状态与本家手牌。
6. durable session 仍负责 match 隔离、pending response、ack 和幂等；不得用信封重放绕过 transport 成功后才提交 effect 的事务边界。
7. full-envelope request digest 用于幂等；重复请求必须返回同一 canonical response。

### D. 无贡 global 契约

- `deal.global` 保持现有严格字段集合。
- `play.global` 接受官方实际结构中的 `tribute_cards` 与 `return_cards`。
- 当前 no-tribute profile 要求两者都是空 mapping；非空值必须 fail-closed，不能忽略、pass 或随意出牌。
- `tribute=0`、`resist=false`、`first/last` 及现有一致性校验保持不变。

### E. 响应包装

新增独立 canonical encoder：

- deal：`{"response":[]}`；
- play：`{"response":[[action ids],[claim ids]]}`；
- 使用紧凑、确定性的 UTF-8 JSON；
- 内部 handler 仍可返回现有游戏 response/effect，但写入 `X-Match-<match_id>` 前必须包装为 Bot JSON response；
- 不在本步引入 debug/data/globaldata 输出；
- wrapper 不得改变 action provenance：Agent 仍只返回原始 `legal_actions` 中的 `action_id`，adapter 才能编码实体 ID。

### F. 测试要求

至少新增或更新以下离线测试：

1. 合成 `deal + play` 信封，`responses=[[]]`，能够解析并重建 27 张本家手牌。
2. 官方可选顶层字段分别缺失、存在时的合法行为。
3. 空 requests、长度关系错误、未知字段、错误类型和 malformed inner request 整体拒绝。
4. `play.global` 的空 `tribute_cards/return_cards` 通过；非空或错误类型 fail-closed。
5. 冷启动重放：先前 pass、自然牌动作和单配子动作；实体手牌扣减与累计 history 守恒。
6. 历史 response 与当时 stage 不匹配、重复实体、未知实体、非法 claim、level/座位/profile 漂移均拒绝。
7. canonical Bot response wrapper 的 deal、pass、自然动作和配子动作快照。
8. mock connector 端到端验证 Header 中是包装后的 response，并保持 failure → restart → resend → ack 事务；失败前不得提前扣牌。
9. 多 match 信封与 session 隔离。
10. 既有直接 inner-stage parser 测试继续通过，避免破坏纯 GuanDan 协议层。

测试 fixture 只能保留合成结构，不得包含真实 URL、密钥、match ID、真实手牌或原始 live request。

### G. 修改边界

- 允许修改 `integrations/botzone/` 与对应 `tests/test_botzone_*.py`。
- 不修改 `engine/`、`agents/`、`cli/`、`rag/`、`evaluation/`、根配置或 `.env`。
- 不新增第三方依赖。
- 不启动真实 connector，不发送 GET，不调用 DeepSeek 或其他网络。
- 不顺带实现 tribute/return、多局升级、runmatch 或 DeepSeek Botzone 接入。

### H. 验证与判定

先运行新增定向测试，再运行：

```text
python -m unittest discover -q
git diff --check
```

同时扫描新增实现和 fixture，确认不含真实 URL、密钥、Cookie、Header 值、真实手牌或 `.env` 读取。

全部通过后的唯一判定：

```text
botzone_bot_json_envelope_contract_verified
```

该判定只证明离线外层信封、历史重放和响应包装契约正确，不证明 live connector 已可用。完成后更新实际文档状态；下一次真实 smoke 必须使用全新测试桌、预算和明确授权。

### 最终报告

报告应包含：

- 修改文件与职责；
- 外层 Bot JSON 与内层 GuanDan stage 的边界；
- 重放与 durable session 的职责划分；
- 新增测试及全量结果；
- 安全扫描结果；
- 唯一判定与未覆盖风险。
