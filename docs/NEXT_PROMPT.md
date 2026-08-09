# 下一步实施提示词

## Step L2-A1：Botzone mock connector 与会话持久化

请在 GuanDan 项目中完成 Step L2-A1。本步实现可注入 transport 的 connector 状态机、local-AI poll 文本模型、按 match 隔离的持久化 session 和纯 mock 测试。不得实现真实 HTTP transport，不得读取或使用本地 AI URL/密钥、`.env`、Cookie、账号或真实 Header 值，不得联网，不得创建/加入对局，不得调用 Agent、DeepSeek、engine 或现有 CLI。

### 前置与检查点

L1-A1 唯一判定：

```text
botzone_no_tribute_protocol_verified
```

已验证定向 14 项、全量 460 项、`git diff --check` 与边界扫描。当前 L1-A1 文件若仍为未跟踪状态，开始 L2-A1 前必须先复核上述测试，并创建一个只包含以下文件的独立检查点；不得把 docs 或 L2 文件混入：

- `integrations/__init__.py`
- `integrations/botzone/__init__.py`
- `integrations/botzone/cards.py`
- `integrations/botzone/models.py`
- `integrations/botzone/protocol.py`
- `tests/test_botzone_cards.py`
- `tests/test_botzone_protocol.py`
- `tests/test_botzone_profile.py`

### 建议新增文件

- `integrations/botzone/poll.py`
- `integrations/botzone/session.py`
- `integrations/botzone/connector.py`
- `tests/test_botzone_poll.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_connector.py`

不得修改 L1-A1 的协议契约，除非定向反例证明其存在明确 bug；任何修复必须单独说明并保持 L1 测试通过。

### Poll 契约

1. 严格解析首行 `m n`，随后 `2*m` 行按 match ID/request JSON 成对出现，再解析 `n` 条 finished row。
2. 同一次 poll 支持多个 match；报告顺序保持输入顺序，不依赖 mapping 或 canonical JSON 键序。
3. request JSON 交给现有 `parse_stage_request()`；malformed request 只阻断对应 match，不污染其他 match。
4. finished row 模型保留 match ID、本地座位、玩家数和整数分数；玩家数 0 明确表示异常结束。
5. 严格处理 LF/CRLF、空尾行、计数不符、额外行、非法 UTF-8/JSON、重复 match ID、Header 注入字符和超长输入。
6. match ID 只作为不透明会话键；不得解释其格式，不得出现在异常正文或普通日志。

### Session 契约

1. 每个 match 独立保存 schema version、request digest、已解析 stage、必要公开状态、pending response、pending/inflight 状态和最后完成状态。
2. 初始 deal 的本家实体手牌可以存入用户显式指定的 state directory，用于重启恢复；不得写入日志、测试快照或最终报告。
3. 使用标准库和原子替换写入；损坏、版本不兼容、缺文件或中途 play 无状态时 fail-closed，不创建猜测状态。
4. 重复 request digest 必须幂等：如果已有同 digest 的 response，复用完全相同的 pending response，不再次调用 handler。
5. pending response 只有在一次 transport 调用成功返回后才能转为 acknowledged/清除；异常、超时或 transport 失败必须保留原始字节内容。
6. finished row 结束对应 session，但不得影响其他 match；异常结束也必须清除可执行 pending 状态。

### Connector 契约

1. 通过调用方注入的 `Transport` 和 `RequestHandler` 工作；本步只使用 fake/mock，不创建 `urllib`、`requests`、socket 或真实 URL transport。
2. 每轮先从 session store 加载 pending response，构造抽象的 `X-Match-<match_id>` header mapping，再调用 fake transport。
3. Header 名和值拒绝 CR/LF；日志和异常只允许规范化类别与计数，不含 URL、match ID、request JSON、response JSON、牌或 Header。
4. 一侧 match malformed/handler 异常不能破坏其他 match；没有 handler response 时不得伪造 pass、空数组或任意动作。
5. `tribute`、`return`、未知 stage 和 L1 `UnsupportedStage` 不调用 handler、不产生 pending response，并记录规范化 unsupported 诊断。
6. 不提供可连接真实 Botzone 的默认 transport、CLI 或 module runner；Phase 2 通过仍不能启动 live connector。

### 测试要求

- 单/多 match poll、多个 finished、aborted、LF/CRLF 和输入顺序；
- 计数、行数、JSON、重复 match、超长/注入和 malformed 隔离；
- pending prepare→transport failure→重启恢复→成功 acknowledge 的完整事务；
- 重复 request 幂等、handler 每 digest 最多调用一次；
- 两个以上 session 的手牌、history、pending 和 finished 完全隔离；
- state schema/version、损坏文件、原子写失败和无状态中途 play fail-closed；
- unsupported stage 不调用 handler、不生成 response；
- fake transport 验证待回传 header mapping，但测试不得包含真实 URL、真实 match ID 或密钥；
- 扫描确认无网络库、`.env`、环境变量、API key、真实 URL、engine/agents/CLI 导入和私有状态读取。

验证命令：

```text
python -m unittest tests.test_botzone_poll tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_cards tests.test_botzone_protocol tests.test_botzone_profile -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部事务、隔离、重启和回归通过时，唯一判定：

```text
botzone_mock_connector_verified
```

该判定只允许进入 Phase 3 RuleBasedAI adapter。它不代表存在 live 启动命令，不授权联网，不证明真实 Botzone 可用，也不支持贡还或升级规则。

### 最终报告

报告 L1 检查点、修改文件、poll/session/connector 契约、mock 调用和事务计数、定向/全量测试、边界扫描及剩余风险。明确说明没有真实 transport、没有 URL/密钥读取、没有联网、没有 Agent、没有可启动的 live connector。
