# 下一步实施提示词

## 使用说明

本提示词交给负责源码和测试实现的代理。项目规划代理只维护 `docs/*.md`。

## 当前唯一任务

实现 Step J-C3d1：撤销已被正式策略分布验收拒绝的无条件 `opponent_single_pass` 负分，恢复 hard-only、零软分的安全 rank baseline。

本轮不是调参，也不是设计新启发式。不要用 feature flag、隐藏参数或更小权重保留被拒绝逻辑。

## 提示词

```text
请在 GuanDan 项目中实现 Step J-C3d1“撤销无条件 pass 软扣分”。

开始前必须阅读：

- AGENTS.md
- docs/PROJECT_STATUS.md
- docs/PLAN.md
- docs/BELIEF_STATE.md
- docs/TESTS.md
- agents/card_ranker.py
- agents/card_signals.py
- agents/card_constraints.py
- agents/card_allocations.py
- evaluation/ranking_metrics.py
- evaluation/rank_benchmark.py
- evaluation/pass_policy_benchmark.py
- tests/test_card_ranker.py
- tests/test_ranking_metrics.py
- tests/test_rank_benchmark.py
- tests/test_pass_policy_benchmark.py

已确认事实：

- HEAD `f1bfabd7ba136553c12ed61824b79f8e4b9ef446` 为 J-C3c1；
- J-C3c1 定向 140 项、全量 250 项测试通过；
- J-C3c2 使用 seed 2000..2099，四个 pass 策略各 100 局；
- 两次正式报告完全一致，SHA-256 为
  `83d3e96dbbb2e8765e5e906b24f6953c093d131af575e9c54b99aaa9198317ce`；
- forced-only 轨迹仍显示小幅正收益；
- 25% 战略 pass 下 overall Top-1 recall delta 为 -0.170742；
- 25% 战略 pass 下 overall Top-3 recall delta 为 -0.092955；
- near-open/critical Top-3 recall delta 分别为 -0.088401 / -0.099062；
- 唯一判定为 `reject_unconditioned_pass_signal`；
- MRR 上升不能抵消真实 rank 召回损失。

任务目标：

1. `build_card_rankings()` 继续从 J-B1 或完整 J-B2 生成 hard rank candidates；
2. confirmed rank、confirmed_count、hard_source 和 owner-domain 收窄保持不变；
3. 所有 possible candidate 固定 `soft_score=0`、`evidence=()`；
4. 不再根据 pass、single、玩家队伍或 rank strength 修改分数；
5. 保留通用 score/evidence 数据结构和离线 metric 校验能力；
6. 明确删除 pass penalty 调参入口，避免调用方误以为该信号仍有效。

范围：

1. 修改 `agents/card_ranker.py`。
2. 修改 `tests/test_card_ranker.py`。
3. 如兼容测试确有必要，可对直接依赖旧参数的测试做最小调整。
4. 不修改 `engine/`、`card_signals.py`、J-A/J-B 契约。
5. 不修改 `evaluation/ranking_metrics.py` 的通用 soft ranking 消融能力。
6. 不修改 `evaluation/rank_benchmark.py` 或
   `evaluation/pass_policy_benchmark.py`。
7. 不修改 DeepSeek、RAG、CLI、主决策链或 docs。
8. 不新增依赖，不实现新概率、新软信号、置信度或 Step K。
9. 不运行 J-C3d2 正式 neutral corpus。

必须删除的行为：

1. 删除 `build_card_rankings()` 的 keyword 参数：
   - `pass_single_penalty`
   - `max_pass_single_penalty`
2. 删除这两个参数的校验。
3. 删除遍历 pass event 并定位 response single 的评分路径。
4. 删除 `opponent_single_pass` evidence 的生成。
5. 删除只服务该评分路径且不再被使用的内部代码。
6. 删除或停止产生以下 pass-scoring 专用 diagnostics：
   - `missing_response_event`
   - `invalid_response_link`
   - `cross_round_response`
   - `invalid_leading_single`
   - `unknown_player_team`
7. 不得用默认 false 的开关、环境变量或私有参数保留旧评分。
8. 不得把 penalty 改成 0 后继续保留误导性的公开参数。

向后兼容边界：

1. 保留 `build_card_rankings(card_belief, constraints, allocation, signals)`
   四个核心参数。
2. 继续校验 belief/constraints/allocation/signals 的 phase 一致性。
3. signals 的公开事件仍可由 `card_signals.py` 生成和审计，但 ranker
   不再把 pass 转换成持牌结论。
4. `signal_diagnostics_present` 是否保留，应遵循当前 fail-closed 结构；
   但它不能改变 candidate 分数或 hard domain。
5. `RankScoreEvidence`、`PlayerRankCandidate.evidence`、
   `PlayerRankCandidate.soft_score` 和 `score_tier` 字段保留，
   供未来经过独立验收的新信号使用。
6. `evaluation/ranking_metrics.py` 仍应能评估测试中人工构造的非零
   soft ranking；不要把通用 evaluator 改成只接受零分。
7. 旧调用若继续传 `pass_single_penalty` 或
   `max_pass_single_penalty`，必须由 Python 签名显式抛出
   `TypeError`，不能静默忽略。

neutral ranking 规则：

1. confirmed candidate：
   - `hard_status="confirmed"`
   - `confirmed_count > 0`
   - `soft_score=0`
   - `evidence=()`
2. possible candidate：
   - `hard_status="possible"`
   - `confirmed_count=0`
   - `soft_score=0`
   - `evidence=()`
3. 若某玩家存在 confirmed：
   - 全部 confirmed 为 tier 1；
   - 全部 possible 为 tier 2。
4. 若不存在 confirmed：
   - 全部 possible 为 tier 1。
5. 同一 hard status 内按现有稳定 rank 顺序序列化。
6. 稳定顺序不表达概率、置信度或额外优先级。
7. pass 事件数量、领先 rank、敌我关系和 round 数不得改变
   candidates、soft score、evidence 或 tier。

测试要求：

更新 `tests/test_card_ranker.py`，至少覆盖：

1. J-B1 rank domain 聚合保持不变；
2. 完整 J-B2 收窄和 confirmed 保持不变；
3. 截断/无效 J-B2 回退行为保持不变；
4. self、完赛和零容量过滤保持不变；
5. enemy single 后一次 pass 不改变任何 possible score；
6. 多次、跨多个 round 的 enemy single pass 仍全部为零分；
7. teammate pass、非 single 和孤立 pass 同样不影响 ranking；
8. pass response 链变化不改变 candidate 玩家结果；
9. confirmed candidate 始终为零分、空 evidence、tier 1；
10. 有 confirmed 时 possible 全部为 tier 2；
11. 无 confirmed 时 possible 全部为 tier 1；
12. 所有 possible candidate `soft_score=0`、`evidence=()`；
13. 不生成 `opponent_single_pass` evidence；
14. candidate 集合、hard status 和 confirmed count 与撤销前 hard
    source 完全一致；
15. 调换同 tier rank 的稳定输入顺序不改变 tier；
16. 固定输入重复运行输出完全一致；
17. 输出不可变且 `to_dict()` 可 JSON 序列化；
18. `inspect.signature(build_card_rankings)` 不再包含两个 penalty 参数；
19. 显式传旧 penalty keyword 时抛出 `TypeError`；
20. ranker 源码不再包含字符串 `opponent_single_pass`；
21. ranker 源码不再包含 pass penalty 参数名；
22. signal diagnostics 不得修改 hard candidates 或产生分数；
23. `tests/test_ranking_metrics.py` 中人工构造的通用 soft ranking
    仍可评估；
24. J-C3a/J-C3c1 benchmark API 继续运行；
25. runtime 模块没有新增对 `evaluation` 的反向导入。

不要简单删除原测试后降低覆盖率。将原有 pass-penalty 测试改写为
“pass 对 neutral ranking 无影响”的回归测试。

兼容要求：

- `tests/test_card_ranker.py` 必须通过；
- `tests/test_pass_policy_benchmark.py` 必须通过；
- `tests/test_rank_benchmark.py` 必须通过；
- `tests/test_ranking_metrics.py` 必须通过；
- `tests/test_card_signals.py` 必须通过；
- `tests/test_belief_metrics.py` 必须通过；
- `tests/test_card_allocations.py` 必须通过；
- `tests/test_card_constraints.py` 必须通过；
- `tests/test_card_belief.py` 必须通过；
- `tests/test_card_tracker.py` 必须通过；
- `tests/test_game_phase.py` 必须通过；
- 全量 unittest 必须无回归。

完成后运行：

python -m unittest tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
git diff --check

最终报告必须包含：

- 修改文件；
- 被删除的参数、评分路径和 diagnostics；
- hard candidate/confirmed 契约如何保持；
- neutral tier 规则；
- 通用 evidence/metrics 为何保留；
- 旧 keyword 如何显式失败；
- 定向和全量测试数量；
- 未解决风险；
- 明确说明 J-C3d1 只撤销被拒绝信号并恢复安全基线，
  尚未完成 J-C3d2 正式 neutral 回归、新概率证据、置信度、
  策略接入或胜率提升。
```

## 完成判定

只有同时满足以下条件，Step J-C3d1 才能标记完成：

- `opponent_single_pass` 不再影响 rank；
- 所有 possible candidate 为零软分、空 evidence；
- hard candidates、confirmed 和 J-B2 收窄不变；
- penalty 参数已从签名删除且旧调用显式失败；
- 没有 feature flag 或隐藏路径保留旧逻辑；
- 通用 evidence 和 ranking metrics 能力仍保留；
- card signals 与策略压力基准继续可用；
- 未修改 engine、RAG、DeepSeek、CLI、docs 或主决策链；
- 现有 250 项测试无回归；
- 实施代理报告实际测试结果。
