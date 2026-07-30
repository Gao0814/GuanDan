# 下一步实施提示词

## 使用说明

本提示词交给负责源码和测试实现的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

实现 Step J-A：精确公开牌池与逐玩家公开事实层。

不要实现概率猜牌、软信号、策略路由、残局求解或 RAG 扩展。

## 提示词

```text
请在 GuanDan 项目中实现 Step J-A“精确公开牌池与逐玩家公开事实层”。

开始前必须阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/INVARIANTS.md
- docs/TESTS.md

当前基线：

- Step I 已完成；
- 定向阶段测试 71 项通过；
- 全量 python -m unittest discover -q 为 126 项通过；
- 统一阶段上下文位于 agents/game_phase.py。

本任务目标：

把当前全局点数型 CardTracker 的下一层基础能力独立实现为可审计的公开牌面状态：

1. 精确描述两副牌的 108 张基础牌池；
2. 从牌池扣除自己的公开手牌；
3. 从牌池扣除历史动作的真实 carrier_cards；
4. 按 player_id 记录每位玩家已经打出的真实牌；
5. 记录每位其他玩家的公开剩余手牌数量和 pass 次数；
6. 输出 token 级、点数级未见牌和诊断信息；
7. 不推测任何隐藏牌归属。

范围要求：

1. 新增独立模块 agents/card_belief.py。
2. 保留现有 agents/card_tracker.py 行为和接口，不在本任务中重写它。
3. 不修改 engine/。
4. 不修改 docs/；完成后只向项目规划代理报告结果。
5. 不新增第三方依赖。
6. 不接入 DeepSeek 提示词，不修改 RAG。
7. 不实现 Step J-B/J-C 或 Step K。

数据来源只能是公开内容：

- observation.my_info.hand_cards
- observation.other_players
- observation.history.actions
- observation.history.finish_order
- 可选的 GamePhaseContext

牌池规格：

- 普通点数：3、4、5、6、7、8、9、10、J、Q、K、A、2；
- 花色：S、H、C、D；
- 每个普通 token 在两副牌中有 2 张；
- SJ 2 张；
- BJ 2 张；
- 总数必须为 108。

建议数据结构：

- frozen/slots dataclass PlayerPublicBelief
- frozen/slots dataclass CardBeliefState
- CardBeliefState.to_dict() 返回 JSON 友好结构
- 一个只消费 observation 的构建函数或 builder

CardBeliefState 至少包含：

- phase
- external_unknown_count
- unseen_cards_by_token
- unseen_cards_by_rank
- players
- diagnostics
- token_pool_exact

PlayerPublicBelief 至少包含：

- player_id
- team/relation
- remaining_count
- finished
- finish_rank
- played_cards
- pass_count
- confirmed_cards（J-A 固定为空）
- likely_ranks（J-A 固定为空）
- confidence（J-A 固定为 0）

扣牌要求：

1. 历史动作优先使用 carrier_cards。
2. 只有缺少 carrier_cards 时才能回退到 declared_cards。
3. 逢人配必须扣除真实 carrier card，不能扣除 declared_as。
4. 普通牌 token 和王都要保留副本计数。
5. 重复扣除超过牌池数量时不能出现负数，必须加入 diagnostics。
6. 无法识别的 token 必须加入 diagnostics。
7. 回退历史只有点数、没有花色时：
   - 可以更新点数级计数；
   - 不能伪造具体花色；
   - token_pool_exact 必须为 false；
   - diagnostics 必须说明原因。
8. 未见牌总数与公开其他玩家剩余数量不一致时，记录 diagnostics，不得静默修正或读取隐藏手牌。

禁止行为：

- 不根据 pass 断言玩家没有可压制牌；
- 不输出隐藏牌概率；
- 不把任何未知牌标为 confirmed；
- 不枚举玩家牌面分配；
- 不使用 engine 内部 GameState、PlayerState 或真实对手手牌；
- 不改变 legal_actions 或动作合法性。

测试要求：

新增 tests/test_card_belief.py，至少覆盖：

1. 完整基础牌池为 108 张；
2. 普通 token 各 2 张，SJ/BJ 各 2 张；
3. 自己手牌正确扣除；
4. 历史 carrier_cards 正确扣除；
5. 逢人配历史扣真实 carrier，不扣 declared_as；
6. 按 player_id 记录 played_cards；
7. pass 只增加 pass_count；
8. other_players.hand_count 正确进入 remaining_count；
9. legacy declared_cards 回退；
10. 只有点数无花色时 token_pool_exact=false；
11. 重复扣牌产生 overdraw 诊断且计数不为负；
12. 未知 token 产生诊断；
13. 外部容量与未见牌不一致产生诊断；
14. to_dict() 可被 json.dumps 序列化；
15. 所有 players 的 confirmed_cards 和 likely_ranks 为空，confidence 为 0。

兼容要求：

- 当前 tests/test_card_tracker.py 必须保持通过；
- Step I 的统一阶段测试必须保持通过；
- 不修改现有 CardTracker 的 CLI 文本契约。

完成后运行：

python -m unittest tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q

最终报告必须包含：

- 修改文件；
- 牌池和扣牌规则；
- diagnostics 类型；
- 定向和全量测试数量；
- 未解决风险；
- 明确说明本任务只完成公开事实层，没有实现猜牌准确率或策略提升。
```

## 完成判定

只有同时满足以下条件，Step J-A 才能标记完成：

- 108 张牌池守恒；
- 真实 `carrier_cards` 扣牌正确；
- 逐玩家公开历史和容量可审计；
- 异常输入有诊断且不产生负计数；
- 未输出隐藏牌概率或错误确认；
- 现有 126 项测试无回归；
- 未修改 `engine/`、现有 CardTracker 契约或 docs；
- 实施代理向项目规划代理报告实际测试结果。
