# 下一步实施提示词

## Step L3-A1：Botzone 无贡 RuleBasedAI 离线 play adapter

请在 GuanDan 项目中完成 Step L3-A1。本步实现无贡 `deal + play` 的离线规则投影、RuleBasedAI 选择和 Botzone `[action, claim]` 回写，并通过现有 `MockConnector` 做端到端关键回合测试。不得实现真实 HTTP transport、CLI/module runner，不得联网或读取任何敏感配置。

### 前置与检查点

当前唯一判定：

```text
botzone_phase3_official_request_contract_verified
```

已验证定向 39 项、全量 485 项、`git diff --check` 和边界扫描。L2-A1a 已提交为：

```text
9752f500498717b050440d24586e47ea287eeb07
```

开始本步前，必须先复核并创建一个只包含当前 L2-A1b 七个修改文件的独立检查点，不得把 docs 或 L3 文件混入：

- `integrations/botzone/models.py`
- `integrations/botzone/protocol.py`
- `integrations/botzone/session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_profile.py`
- `tests/test_botzone_protocol.py`
- `tests/test_botzone_session.py`

### 建议新增文件

- `integrations/botzone/profile.py`
- `integrations/botzone/play_adapter.py`
- `tests/test_botzone_play_adapter.py`
- `tests/test_botzone_action_provenance.py`
- `tests/test_botzone_rule_agent_e2e.py`
- 必要时 `tests/test_botzone_rule_compatibility.py`

不得修改 `engine/`、`agents/`、现有 CLI、RAG、evaluation、DeepSeek 或现有 connector/session 契约。除非定向反例证明 L2-A1b 存在明确 bug，否则不要修改已封板的协议模块。

### 架构边界

1. 不创建伪造的四家隐藏手牌，也不调用随机 `GuanDanGame.reset()`。
2. adapter 只从 `HandlerContext` 的公开字段构造单回合规则投影：
   - 本家当前实体手牌；
   - 本地座位与当前级牌；
   - `TableView` 给出的 free/follow 和公开桌面领牌；
   - 累计公开 history、`done` 与 `pass_on`。
3. 规则投影只需一个本家 `PlayerState`；调用 `BaseRuleEngine.generate_legal_actions()` 生成合法动作。不得调用 engine 私有状态或私有 helper。
4. Agent 只收到 token 化的公开 observation 和 canonical `legal_actions`，只返回当前列表中的原始 `action_id`。
5. Botzone 实体 ID、match key、request digest、session 对象、`ActionClaim` 和 response bytes 不得进入 Agent 输入。
6. adapter 在 Agent 返回后，用当前决策内的不可变 `action_id → engine action → Botzone response` 映射回查；不得让 Agent 直接生成牌数组。
7. 默认且唯一基础 Agent 为 `RuleBasedAIAgent`。可注入测试 double，但本步不得导入或配置 DeepSeek。

### 卡牌与座位映射

- Botzone 花色 `h/d/s/c` 精确映射为 engine `H/D/S/C`；`SJ/BJ` 保持无花色。
- Botzone 玩家 `0..3` 映射为 engine `1..4`，队伍关系保持 `0/2 ↔ 1/3`。
- engine `Card` 不保存双副本身份；每个 canonical action 必须从当前 `own_hand` 按牌面 multiset 绑定实体 ID。
- 同牌面双副本使用稳定、确定性的实体 ID 选择，例如升序 ID；不得依赖 set/dict 非稳定顺序。
- action 的实体 ID 必须唯一且为当前手牌子集；pass 固定为空 action。
- 输入 hand、history、映射表和 Agent payload 不得被修改。

### 规则投影与桌面动作

- 使用 `resolve_table_view()` 判断 free/follow；不得自行采用另一套轮次算法。
- follow 时把 `TableView.table_leader.response.action` 转为 carrier，把 claim 转为 declared cards，并用公开 `detect_pattern()` 验证牌型。
- 无法识别的 Botzone 牌型、未知 claim、领牌者/当前玩家矛盾或 engine 不支持的桌面动作必须整体 fail-closed；不得把它降级为 free lead。
- `GameState` 投影不得包含猜测的对手手牌；`TableConstraint.pending_player_ids` 只填规则生成确实需要的公开值，不伪造隐藏状态。
- legal actions 的排序与 `public_action_id()` 分配必须稳定，并在可构造同状态 fixture 上与 `GuanDanGame.legal_actions()` 逐字段等价。

### 公开 observation

生成与当前 Agent 契约兼容的结构：

- `my_info`：engine 玩家 ID、队伍、级牌、token 手牌、精确手牌数和剩余单张数；
- `current_round`：公开累计 step、可验证 round、当前玩家、桌面 action 和 free/follow constraint；
- `other_players`：只用 27 张初始容量减公开 carrier 出牌数，并结合 `done` 生成 hand count/finished/finish rank；
- `history.actions`：只由累计公开事件转换，保留 carrier/declared 区别；
- `history.finish_order`：只来自 `done`；
- `legal_actions`：与单独传给 Agent 的列表内容一致。

所有派生计数必须守恒。历史不足、负容量、done 玩家仍有剩余牌、round 无法唯一重建或字段矛盾时 fail-closed，不填默认值或猜测值。

### action_id 与 provenance

- 为 `BaseRuleEngine.generate_legal_actions()` 的稳定序列使用 `public_action_id(index)` 分配 ID。
- 序列化字段保持现有公开契约：`action_id`、`declared_pattern`、`declared_cards`、`carrier_cards`、`wildcard_count`、`wildcard_info`、`display_text`。
- Agent 返回值必须先满足 `type(action_id) is int`；`bool`、字符串、float 等不得由 `int()` 宽松接受。
- 再调用 `require_legal_action_id()`，最后从当前不可变 provenance mapping 回查。
- 过期 ID、其他会话 ID、篡改 legal actions、mapping 缺失或 Agent 异常均不得产生 response，也不得 fallback 为 pass。

### Botzone response 编码

- deal response 为 UTF-8 canonical JSON bytes：`[]`，且无 `PlayEffect`。
- play response 为无换行的 canonical JSON bytes：`[action,claim]`。
- pass 精确为 `[[],[]]`，对应 `PlayEffect(action=())`。
- 自然牌必须 `claim=action`，保留同一实体 ID 集合。
- 含配子时，action 使用真实 carrier ID；claim 保留所有非配子实体牌面，并为每张配子选择确定性的 `0..107` 虚拟声明 ID。
- 配子声明必须使 claim 经公开牌型检测后与 engine `declared_pattern` 一致。特别覆盖：
  - single/pair/triple/bomb；
  - triple-with-pair；
  - straight 不得因统一选同花而意外编码成 straight flush；
  - pair-straight、steel-plate；
  - straight-flush 必须保留目标花色。
- 编码完成后必须用 `parse_action_claim(..., known_hand_ids=own_hand)` 自校验。
- `HandlerResult.effect.action` 必须与 response 的 action 精确相同，交由现有 ack 事务提交。
- 当前 engine 每手最多使用一张配子；不得为追求 Botzone 双配子能力修改 engine 或手工扩展动作。

### Handler 与 profile

- 提供可直接注入现有 `MockConnector` 的 callable handler。
- deal/play 只接受严格无贡 profile；`resist=false`、`tribute=0`、`first/last=null` 继续由协议层约束。
- `tribute/return/unknown` 不调用 Agent、不产生 response；保持 connector 的 `unsupported_stage` 路径。
- handler/adapter 异常只产生规范化错误类别；异常、测试快照和最终报告不得包含 match key、手牌、response bytes 或实体 ID 明细。

### 必测场景

- 108 ID 到 engine Card 的全映射、花色大小写、王和双副本稳定绑定；
- 四个座位和两组队伍映射；
- free lead、普通 follow、只能 pass、全 pass 后重新领牌、done/pass_on 接风；
- 自然 single/pair/straight/bomb 与配子各主要牌型的 action/claim；
- 同牌面双副本选择稳定，ack 前后 effect 精确；
- Agent spy 确认输入不含 Botzone ID、match key、digest 或 session 类型；
- `True`、字符串、float、越界、过期、跨会话 action ID 和异常 Agent 全部 fail-closed；
- projection legal actions 与可构造 `GuanDanGame` fixture 逐字段相同；
- deal→首个 play→follow/pass→下一 request 的 `MockConnector + SessionStore + RuleBasedAIAgent` 离线链路；
- 重复 request 不重复调用 Agent，transport failure/restart 后复用完全相同 response，ack 后精确扣牌一次；
- unsupported stage 不调用 Agent；多 match 的手牌、Agent player ID、provenance 和 pending effect 不交叉；
- 官方裁判差异 fixture 至少覆盖普通比较、炸弹层级、配子 straight 与 straight-flush 边界；发现不兼容时 fail-closed 并列入剩余能力缺口。

### 验证命令

```text
python -m unittest tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_protocol tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_profile -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部 adapter、provenance、mock E2E 和回归通过时，唯一判定：

```text
botzone_no_tribute_adapter_verified
```

该判定只证明无贡合法子集的离线 RuleBasedAI adapter 可用。它不代表存在真实 HTTP transport、可启动 connector、Botzone 实盘可用、支持贡还/升级或已经证明对抗能力。

### 最终报告

报告 L2-A1b 检查点、修改文件、规则投影、observation/legal-action 等价、实体 ID/claim 编码、provenance、mock E2E、定向/全量测试和边界扫描。明确说明未修改 engine/agents、未实现真实 transport/CLI、未读取敏感配置、未联网，且当前只覆盖 engine 已支持的单配子合法子集。
