# 下一步实施提示词

## 使用说明

本提示词交给负责源码和测试实现的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

实现 Step J-B1：基于 J-A 公开事实层建立未见牌可能归属域与玩家容量约束。

本轮不做残局完整分配枚举、概率猜牌、pass 软推断、策略路由、DeepSeek 提示词或 RAG 扩展。

## 提示词

```text
请在 GuanDan 项目中实现 Step J-B1“未见牌可能归属域与玩家容量约束”。

开始前必须阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/INVARIANTS.md
- docs/TESTS.md
- agents/card_belief.py
- tests/test_card_belief.py

当前基线：

- Step I 已完成并提交为 d08b3bf stepI；
- Step J-A 已完成但当前尚未提交；
- J-A 定向测试 31 项通过；
- 全量 python -m unittest discover -q 为 141 项通过；
- J-A 公开事实模型位于 agents/card_belief.py。

本任务目标：

在不重新解析 observation、不访问隐藏手牌的前提下，只消费 J-A 的 CardBeliefState，建立确定性的逐玩家归属约束：

1. 找出仍可持有外部未知牌的玩家；
2. 为每个未见 token 和点数建立可能归属玩家集合；
3. 用公开 remaining_count 检查总容量与未见牌数量是否一致；
4. 排除自己、已完赛玩家和剩余容量为 0 的玩家；
5. 仅在输入精确、容量一致且归属逻辑唯一时输出 confirmed；
6. 对无法证明、输入不精确或容量冲突的情况保留不确定性并输出诊断。

范围要求：

1. 新增独立模块 agents/card_constraints.py。
2. 新增 tests/test_card_constraints.py。
3. 只消费 CardBeliefState，不重新读取 observation。
4. 保持 agents/card_belief.py 的 J-A 数据契约稳定；除非测试证明存在阻塞性缺陷，否则不要修改它。
5. 不修改 engine/、agents/card_tracker.py 或现有合法动作接口。
6. 不修改 docs/；完成后只向项目规划代理报告。
7. 不新增第三方依赖。
8. 不接入 deepseek_ai.py、deepseek_client.py、RAG 或 CLI。
9. 不实现 J-B2、J-C 或 Step K。

建议数据结构：

- frozen/slots dataclass PlayerCardConstraints
- frozen/slots dataclass CardConstraintState
- build_card_constraints(card_belief: CardBeliefState) -> CardConstraintState
- CardConstraintState.to_dict() 返回 JSON 友好结构

CardConstraintState 至少包含：

- phase
- possible_owners_by_token
- possible_owners_by_rank
- players
- diagnostics
- is_consistent
- token_constraints_exact

PlayerCardConstraints 至少包含：

- player_id
- relation
- remaining_capacity
- possible_tokens
- possible_ranks
- confirmed_cards

确定性规则：

1. 外部候选玩家只包括 relation != "self"、finished=false 且 remaining_count > 0 的玩家。
2. 自己、已完赛玩家和零容量玩家不得出现在任何外部未知牌归属域中。
3. 每个计数大于 0 的未见点数，其初始可能归属域是全部外部候选玩家。
4. token_pool_exact=true 时，每个计数大于 0 的未见 token 使用同样的初始归属域。
5. token_pool_exact=false 时，不得伪造 token 级精确归属；token_constraints_exact=false，并加入诊断。
6. 外部候选玩家 remaining_count 总和必须与 unseen_cards_by_rank 总数一致；不一致时 is_consistent=false。
7. 未见牌存在但没有候选玩家，或某张牌的归属域为空时，必须诊断为不一致。
8. 只有同时满足以下条件才允许产生 confirmed_cards：
   - token_pool_exact=true；
   - 容量总和一致；
   - 没有空归属域或其他一致性错误；
   - 该 token 的归属玩家在硬约束下唯一。
9. 当前 J-B1 没有行为型硬排除。因此通常多个活跃外部玩家会共享相同归属域，confirmed_cards 应保持为空。
10. 当且仅当只有一个合格外部玩家且其容量等于全部未见牌数量时，可将全部未见 token 按实际副本数确认给该玩家。
11. 重复 token 必须按 unseen_cards_by_token 的计数保留，不能只保留去重后的 token 名称。
12. 不得修改传入的 CardBeliefState 或其中的 mapping。

诊断至少区分：

- token_pool_inexact
- external_capacity_mismatch
- no_possible_owner
- empty_owner_domain
- invalid_remaining_capacity

诊断名称可以沿用项目现有字符串风格，但测试必须验证关键类别。

禁止行为：

- 不读取 observation、GameState、PlayerState 或真实对手手牌；
- 不根据 pass、出牌风格、队友关系或模型输出缩小硬归属域；
- 不输出概率、边际概率、likely_ranks 或人工置信度；
- 不进行完整可行分配枚举、回溯搜索、MCTS 或蒙特卡洛；
- 不把“可能持有”写成“确认持有”；
- 不改变 legal_actions、动作合法性或游戏状态；
- 不声称本任务提高猜牌准确率或策略胜率。

测试要求：

tests/test_card_constraints.py 至少覆盖：

1. 多个活跃外部玩家时，每个未见点数的归属域包含全部候选玩家；
2. token 精确时，每个未见 token 建立归属域；
3. 自己不进入归属域；
4. 已完赛玩家不进入归属域；
5. remaining_count=0 的玩家不进入归属域；
6. 多候选玩家时 confirmed_cards 为空；
7. 单一候选玩家且容量一致时，全部未见 token 被唯一确认；
8. 唯一确认保留重复 token 的副本数；
9. 外部容量不一致时 is_consistent=false 且不产生 confirmed；
10. token_pool_exact=false 时不产生 token 级精确确认；
11. 有未见牌但无候选玩家时产生诊断；
12. 负数或格式异常容量产生诊断且不参与候选域；
13. to_dict() 可被 json.dumps 序列化；
14. 输出 dataclass 不可变；
15. 构建过程不修改输入 CardBeliefState；
16. pass_count 的变化不会缩小硬归属域。

兼容要求：

- tests/test_card_belief.py 必须保持通过；
- tests/test_card_tracker.py 必须保持通过；
- tests/test_game_phase.py 必须保持通过；
- 全量 unittest 必须无回归。

完成后运行：

python -m unittest tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q

最终报告必须包含：

- 修改文件；
- 候选玩家和归属域规则；
- 一致性与 confirmed 判定条件；
- diagnostics 类型；
- 定向和全量测试数量；
- 未解决风险；
- 明确说明 J-B1 只建立硬约束基础，未实现 J-B2 分配枚举、J-C 概率猜牌或策略提升。
```

## 完成判定

只有同时满足以下条件，Step J-B1 才能标记完成：

- 只消费 J-A 的 `CardBeliefState`；
- 自己、完赛玩家和零容量玩家不会成为外部未知牌候选持有者；
- token/点数归属域与公开牌池一致；
- 容量冲突和不精确输入有明确诊断；
- 多解时不产生错误确认；
- 只有硬约束唯一时才产生 `confirmed_cards`；
- 现有 141 项测试无回归；
- 未修改 `engine/`、RAG、DeepSeek 提示词、CLI 或 docs；
- 实施代理向项目规划代理报告实际测试结果。
