# 下一步实施提示词

## Step L3-A1a：Botzone adapter 公开 observation 与实体牌守恒加固

请在 GuanDan 项目中完成 Step L3-A1a。本步保留 L3-A1 的规则投影、合法动作、实体绑定和 response 编码，只修复公开 observation 的轮次/字段语义与实体牌守恒。不得实现真实 HTTP transport、CLI/module runner，不得联网或读取敏感配置。

### 前置与检查点

L3-A1 历史判定保持：

```text
botzone_no_tribute_adapter_verified
```

已验证定向 39 项、全量 494 项、`git diff --check` 和 adapter 边界扫描。L2-A1b 已提交为：

```text
1766c91895874b963ca7f78ea2a39810183028d6
```

开始本步前，必须先复核并创建一个只包含当前 L3-A1 六个改动文件的独立检查点，不得把 docs 或本步修复混入：

- `integrations/botzone/profile.py`
- `integrations/botzone/play_adapter.py`
- `tests/test_botzone_action_provenance.py`
- `tests/test_botzone_play_adapter.py`
- `tests/test_botzone_rule_agent_e2e.py`
- `tests/test_botzone_connector.py` 的 adapter 边界扫描更新

### 已复现的问题

同一轮中玩家 0 首出单 3、玩家 1 跟单 4、轮到玩家 2 时，真实 round 应仍为 1。当前实现输出：

```text
current_round.round_no = 3
history.round_no = [1, 1]
table_action.action_id = 0
```

原因：`_verified_round_no()` 直接使用“非 pass 动作数 + 1”，把每次跟牌也当成新 round；历史 round 又固定为 1。`GuanDanGame.observe()` 的桌面 action 则应使用 `action_id=None`。RuleBasedAI 暂不读取这些字段，所以现有测试仍通过，但阶段分类、策略路由和 DeepSeek 会读取，不能进入 live 链路。

### 轮次重放契约

只用累计公开 history 重放，不读取 engine 私有状态：

1. 按事件顺序处理，每个事件前只查看此前最多四个真实公开事件。
2. 对事件玩家采用与 `resolve_table_view()` 相同的反向扫描：先遇到该玩家上一手则 free；先遇到其他玩家非 pass 则 follow；没有非 pass 也为 free。
3. free 的非 pass 动作开启新 round；follow、pass 都属于当前 round。
4. 首个事件必须是 free 的非 pass；非法首 pass、free pass 或无法唯一重放时 fail-closed。
5. 当前请求若 `TableView.free_lead=False`，`current_round.round_no` 等于最后事件 round；若为 free，则为下一 round；空 history 的首个 play 为 round 1。
6. `history.actions[*].round_no` 与当前 round 必须来自同一次不可变重放结果，不能分别计算。

覆盖首轮、连续跟牌、跟牌后 pass、三家 pass 回到领牌者、完成玩家跳过、接风和多轮累计。

### 精确公开字段

与 `GuanDanGame.observe()` 锁定同名字段的 key set 和语义：

- `current_round.table_action.action_id` 必须为 `None`，不得使用伪 ID `0`；
- history action 只含 `step_no/round_no/player_id/declared_pattern/declared_cards/carrier_cards`，不得夹带 legal-action 专用字段；
- table action 保留完整 `wildcard_count/wildcard_info/display_text`；
- 普通 single/pair/triple/bomb/straight 等 declared cards 使用 engine canonical rank token；只有 straight flush 保留花色；
- table `constraint` 和 `display_text` 必须使用稳定 canonical 表示；
- 本家 hand token 顺序使用公开 `sort_cards()`，不依赖 Botzone deal 原始顺序；
- observation 内的 `legal_actions` 与单独传给 Agent 的 canonical 列表逐字段相同，但 Agent 对副本的修改不影响 provenance。

在可由 `GuanDanGame` 公开 API 构造的 free/follow/multi-step fixture 上，逐字段比较 observation 的公共结构；对手隐藏手牌不同导致的公开计数差异必须在 fixture 中显式对齐，不得忽略。

### 外部 action 的 wildcard 重建

`_history_entry_to_action()` 必须从公开 `[action,claim]` 重建：

- carrier cards；
- canonical declared cards；
- declared pattern；
- `wildcard_count`；
- 每张红桃级牌 carrier 对应的 `WildcardInfo.declared_as`；
- stable display text。

非配子 action/claim 必须保持自然牌语义；一张或两张配子的外部桌面 action 都要能被准确表示。无法唯一匹配配子与 claim remainder、声明为王或 pattern 不受 engine 支持时 fail-closed，不得把它降级为普通自然动作或 free lead。

注意：这只允许读取 Botzone 对手已经公开打出的双配子动作作为桌面约束；本家合法动作生成仍保持当前 engine 的单配子子集，不得修改 engine。

### 实体牌守恒

只对真实 `action` ID 做守恒，不把虚拟 claim ID 当作实体牌：

- 累计公开 history 中同一实体 ID 最多出现一次；
- 已公开打出的实体 ID 不得仍存在于本家 `own_hand`；
- 本家当前手牌数 + 本家累计公开 action 数必须严格等于 27；
- 对手公开剩余数为 `27 - 累计 action 数`，范围必须为 `0..27`；
- `done` 玩家剩余数必须为 0，未 done 玩家不得为 0；
- 同一实体 ID 被不同玩家打出、重复打出、当前仍在本家手中或容量矛盾均整体 fail-closed；
- pass 和重复虚拟 claim ID 不改变实体牌计数。

不得为了通过守恒检查而猜测或补全隐藏手牌。

### HandlerContext 一致性

在 adapter 入口复核：

- `context.global_state == context.request.global_state`；
- play 时 `context.latest_window == context.request.history`；
- latest window 是累计 history 的精确 suffix；
- local player、done、finished 和当前手牌状态一致；
- deal 时 local player 与 `your_id` 一致。

任一矛盾返回稳定 `AdapterError` 类别，不调用 Agent、不生成 response 或 effect。

### 允许修改

- `integrations/botzone/play_adapter.py`
- 必要时 `integrations/botzone/profile.py`
- `tests/test_botzone_play_adapter.py`
- `tests/test_botzone_action_provenance.py`
- `tests/test_botzone_rule_agent_e2e.py`
- 必要时新增 `tests/test_botzone_adapter_observation.py`

不得修改 `engine/`、`agents/`、协议/session/connector 主契约、现有 CLI、RAG、evaluation 或 DeepSeek。若发现上游 L2 明确 bug，先报告并单独处理，不要混入本步。

### 必测场景

- 已复现的 single 3→single 4 同轮 fixture：current/history round 均为 1；
- 两轮以上 lead/follow/pass，history round 与 current round 全量快照；
- table action `action_id=None`、history 精确 key set 和 canonical display；
- 自然及一/双配子外部 table action 的 wildcard info 与 declared token；
- 手牌乱序输入得到稳定排序 observation 和不变 legal actions；
- 本家 27 张守恒、对手 0..27 容量、done 边界；
- 重复实体 ID、跨玩家重复、已出牌仍在 own hand、done 非零、未 done 零张全部拒绝；
- context global/window/history/local/finished 矛盾不调用 Agent；
- 与 `GuanDanGame.observe()/legal_actions()` 的 free、follow 和多步公开 fixture 对照；
- 保持自然/配子 response、provenance、failure/restart/ack E2E 和全部 L1/L2 回归通过；
- 边界扫描继续确认无网络、配置、`.env`、DeepSeek、CLI、私有 engine state 或隐藏手牌读取。

### 验证命令

```text
python -m unittest tests.test_botzone_play_adapter tests.test_botzone_action_provenance tests.test_botzone_rule_agent_e2e tests.test_botzone_adapter_observation tests.test_botzone_protocol tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_profile -q
python -m unittest discover -q
git diff --check
```

如果未新增 `tests/test_botzone_adapter_observation.py`，从定向命令中删除该模块，不要创建空测试文件。

### 验收判定

全部 observation、wildcard、守恒、provenance 和回归通过时，唯一判定：

```text
botzone_adapter_observation_hardening_verified
```

该判定才允许下一步设计真实 HTTP transport 与启动器的**离线 mock 验收**。它不代表可以联网、存在可用 live connector、Botzone 实盘已通过或已经证明对抗能力。

### 最终报告

报告 L3-A1 检查点、复现 fixture 修复前后值、轮次重放、精确 observation、wildcard 重建、实体守恒、context 一致性、定向/全量测试和边界扫描。明确说明未修改 engine/agents、未实现真实 transport/CLI、未读取敏感配置、未联网。
