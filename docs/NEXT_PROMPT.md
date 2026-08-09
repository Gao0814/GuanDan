# 下一步实施提示词

## Step L2-A1a：Botzone Phase 3 准入契约加固

请在 GuanDan 项目中完成 Step L2-A1a。本步不接 Agent、不实现 adapter、不实现真实 HTTP transport、不联网；只修复官方 claim 虚拟声明的 multiplicity，并补齐 mock connector 向后续 Phase 3 提供安全 session context 与实体手牌提交事务的契约。

### 前置与检查点

L2-A1 唯一判定保持：

```text
botzone_mock_connector_verified
```

已验证定向 28 项、全量 474 项、`git diff --check` 和边界扫描。开始本步前，必须把当前 L2-A1 的以下改动建立为独立检查点，不与本步修复混合：

- `integrations/botzone/poll.py`
- `integrations/botzone/session.py`
- `integrations/botzone/connector.py`
- `tests/test_botzone_poll.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_profile.py` 的 Phase 2 扫描范围修正

### 已证明的阻塞

#### 1. claim 虚拟 ID 重复

当前 `parse_action_claim()` 对 claim 使用实体 ID 唯一性校验。官方裁判 `isLegalClaim()` 只按牌面多重集验证 claim，不要求 claim 中的虚拟实体 ID 唯一。

两副牌同一点数最多只有 8 个不同实体 ID。合法的 9 张炸弹（8 张自然牌 + 1 配子）和 10 张炸弹（8 张自然牌 + 2 配子）必须在 claim 中重复一个或两个同点数虚拟 ID。当前实现会错误返回：

```text
ProtocolValidationError: claim contains duplicate physical IDs
```

必须保持 action 和 known hand 的实体 ID 唯一，但允许含配子的 claim 使用重复 `0..107` ID。自然牌仍严格要求 claim 与 action 为同一实体集合；pass 仍为 `[[], []]`。

#### 2. handler 缺少 session 上下文

当前 `RequestHandler` 只接收 `DealRequest | PlayRequest`。`PlayRequest` 不包含本家当前实体手牌，且多 match 时 handler 无法知道应读取哪个 session，因此不能安全进入 Phase 3。

新增冻结、slots 的 handler context/view，至少包含：

- opaque match key；
- request digest 与已解析 request；
- 本家当前实体手牌；
- 当前持久化公开 history/window；
- global state 与 finished 状态；
- 不可变、JSON 安全的必要字段。

match key 只供内部路由，不得出现在日志、异常、测试快照或最终报告。

#### 3. pending response 尚未携带手牌提交效果

当前 session 在平台确认 pending response 后只清除 bytes，不扣减本家已出的实体牌。新增类型化 pending effect/result：

- deal response 不改变手牌；
- play response 持久化精确 action 实体 ID；
- action ID 必须非 bool、唯一且为当前本家手牌子集；
- transport 失败、异常或重启时 response bytes 与 effect 一起保持 pending，本家手牌不提前变化；
- 只有 transport 成功 acknowledge 后才原子扣减一次；
- 重复 acknowledge、重复 request 或重启不得重复扣牌；
- finished/aborted 清除可执行 pending effect。

### 公开 history 累积

session 不能只覆盖保存最新四手。增加 latest window 与累计公开事件的确定性合并：

- 重复 window 不重复追加；
- 滑动 window 使用最长可验证 suffix/prefix 合并；
- 玩家、response 和顺序共同参与事件等价；
- finished 玩家跳过、pass 和相同牌面重复出现均有测试；
- 无法唯一对齐时 fail-closed，诊断 `history_alignment_failed`，不得猜测；
- 累计结果只来自 Botzone 公开 history 和本机已确认 response，不读取隐藏牌。

### 允许修改

- `integrations/botzone/protocol.py`
- `integrations/botzone/session.py`
- `integrations/botzone/connector.py`
- 必要时 `integrations/botzone/models.py`
- `tests/test_botzone_protocol.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_profile.py`

不得修改 `engine/`、`agents/`、`cli/`、RAG、evaluation 或 DeepSeek。

### 测试要求

- 9 张炸弹：8 个自然实体 ID + 1 配子，claim 含一个重复虚拟 ID，验证通过；
- 10 张炸弹：8 个自然实体 ID + 2 配子，claim 含两个重复虚拟 ID，验证通过；
- action/known hand 重复实体 ID仍失败；自然牌重复/换副本 claim 仍失败；claim 越界、王替代、牌面不守恒仍失败；
- 两个 match 的 handler context 能看到各自不同的 own hand，且不能交叉；
- pending play effect 在 transport failure、重启、成功 ack、重复 ack 全链路精确扣牌一次；
- malformed handler result、越权 action ID、Header 注入和 finished pending effect fail-closed；
- latest-window 重复、滑动、pass、finished skip、无法对齐与输入不变性；
- 保持 L1/L2 既有事务、幂等和隔离测试通过；
- 边界扫描继续禁止网络库、真实 URL、`.env`、环境变量、Agent/engine/CLI 导入和敏感值。

验证命令：

```text
python -m unittest tests.test_botzone_protocol tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_poll tests.test_botzone_cards tests.test_botzone_profile -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部修复与回归通过时，唯一判定：

```text
botzone_phase3_admission_contract_verified
```

该判定才允许下一步实现 Phase 3 RuleBasedAI adapter。它不表示 Agent 已接入、存在 live 启动命令、可以联网或支持贡还/升级。

### 最终报告

报告 L2 检查点、三个修复契约、9/10 张炸弹反例、handler context、pending effect 事务、history 合并测试、定向/全量回归和边界扫描。明确说明未调用 Agent、未修改 engine、无真实 transport、未读取 URL/密钥、未联网。
