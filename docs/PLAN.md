# GuanDan 优化计划

当前进度与风险见 `docs/PROJECT_STATUS.md`。下一步实施任务见 `docs/NEXT_PROMPT.md`。

## 1. 当前结论

截至 2026-08-03，项目已经完成：

- 单局掼蛋规则引擎和 4 AI 对局闭环；
- `observe()` / `legal_actions()` / `step(action_id)` 公开契约；
- DeepSeek 接入、失败降级和本地必出 / 仅 pass 快捷路径；
- 手牌评分、动作剪枝、基础记牌；
- 本地公式化开局；
- 带元数据的规则库、经验库和场景化 RAG。
- Step J-A 精确公开牌池和逐玩家公开事实层。
- Step J-B1 未见牌归属域和公开容量约束。
- Step J-B2 受控残局精确可行分配枚举。
- Step J-C1 离线牌面信念真值评测。
- Step J-C2a 公开行为事件提取。
- Step J-C2b1 最小软评分和 rank 候选排序。
- Step J-C2b2 并列安全 Top-K 与零软分单样本消融。
- Step J-C3a 固定种子残局采集与微聚合基准运行器。
- Step J-C3b RuleBasedAI 独立种子正式基准，判定为保留进入策略分布验证。
- Step J-C3c1 evaluation-only 战略性 pass 策略分布基准载体。
- Step J-C3c2 独立种子策略分布验收，判定拒绝无条件 pass 信号。
- Step J-C3d1 撤销无条件 pass 扣分并恢复 hard-only neutral ranking。
- Step J-C3d2 独立 corpus neutral baseline 封板。
- Step J-D1a 完整分配的精确物理权重与 token 边际整数计数。
- Step J-D1b 完整分配的逐玩家 rank 持有/副本精确整数边际。
- Step J-D1c1 evaluation-only 单样本精确 Brier、copy 误差与十档充分统计量。
- Step J-D1c2a 多样本精确微聚合、ECE/MCE 与规范化 diagnostics。
- Step J-D1c2b critical 固定 seed collector 与开发容量验证。
- Step J-D1c2c 默认 RuleBasedAI 独立语料正式校准。
- Step J-D1c3a forced/25/50/100 strategic-pass corpus 载体与开发容量验证。

当前优化目标从“能运行”转为“阶段判断一致、推断可审计、策略质量可测”。`record.txt` 联网单局只读复盘新增了三个直接样本：开局公式拆对出高单、同队互相消耗炸弹、危险对手剩两张时未阻断。单局不构成收益证明，但可以作为确定性回归 fixture。

## 2. 总体目标

AI 决策分为四层：

1. 公开局面：只读取 `observe()` 和原始 `legal_actions()`。
2. 局面分析：统一阶段、手牌评分、未见牌池和逐玩家信念状态。
3. 策略路由：选择开局跑牌、中局控场、协助队友、阻断对手或残局收束。
4. 动作选择：本地确定性策略优先，其余场景由 RAG + DeepSeek 在合法动作中选择。

规则引擎始终是合法性和状态推进的唯一真值。

## 3. 阶段定义

阶段不能再由各模块分别判断，统一由一个阶段分类器输出：

- `opening`：历史动作不超过 8，自己至少 18 张，三个未完赛玩家均至少 16 张。
- `midgame`：不满足开局或残局条件的常规阶段。
- `endgame`：自己少于 10 张、任一未完赛玩家少于 6 张，或已有玩家完赛。
- `near_open_endgame`：外部玩家合计剩余不超过 20 张。
- `critical_endgame`：外部玩家合计剩余不超过 12 张。

优先级从高到低为：

`critical_endgame > near_open_endgame > endgame > opening > midgame`

## 4. 已完成阶段

### Step A-F：规则、接口、DeepSeek 和回归闭环

状态：完成。

### Step G：手牌评分、理牌与基础记牌

状态：完成基础版本。

已实现：

- `agents/hand_evaluator.py`
- `agents/card_tracker.py`
- 阶段感知动作摘要和剪枝

限制：

- `CardTracker` 仍是全局点数统计旧链路；
- Step J-A 已提供独立公开事实层，但尚未形成逐玩家候选牌、置信度和可行分配。

### Step H：公式化开局与场景化 RAG

状态：完成 MVP。

已实现：

- `agents/opening_strategy.py` 本地开局决策；
- 仅 pass、一次出完和公式化开局跳过 API；
- RAG front matter 元数据；
- 按 `scene / phase / hand_strength / action_context` 检索；
- 规则证据和经验依据分层进入提示词。

待量化：

- 开局高价值牌浪费率；
- 开局两轮后的平均散牌数；
- RAG 场景覆盖率和命中质量；
- 新旧策略 A/B 对局结果。

联网单局发现的待修复项：

- 现有公式把拆对的单 K 排在天然单 9 和天然长套之前，因为只对当前动作打分，不评估残余点数结构；
- CLI 只把 `last_decision_source == "local"` 标为本地，没有标记 `local_opening_formula`；
- H2-A1/A1a 与 K-A1 至 K-A3d2 已封板；K-A3c2 原正式结论保持无效，下一步为 K-A3d3a 真实模型质量试验前置审计与授权请求。

## 5. 当前实施阶段

### Step I：统一阶段模型

状态：完成。定向 71 项、全量 126 项测试通过。

目标：

- 新增唯一的阶段分类模块；
- 开局策略、动作剪枝、RAG 和提示词共用同一阶段结果；
- 删除或停止使用重复的阶段判断。

验收：

- 边界值测试完整；
- 同一 observation 在所有模块中阶段一致；
- 不改变合法动作集合。

### Step J：逐玩家牌面信念状态

状态：J-A 至 J-D1c3c2c3c2b 已完成，confidence 默认关闭。H2-A1/A1a 与 K-A1 至 K-A3d2 已完成；K-A3c2 原正式运行无效，下一步为 K-A3d3a。

目标：

- 精确维护两副牌级别的未见牌池，保留点数和花色；
- 按玩家记录已出牌、pass 次数和剩余牌数；
- 输出逐玩家 `possible / likely / confirmed` 信息；
- 所有推断带来源和置信度；
- 只有逻辑唯一时才能标记 `confirmed`。

当前阶段已包含确定性公开事实、硬约束、完整残局枚举、token/rank 级精确物理权重和经策略多样性校准的组合边际契约；排序保持 hard-only neutral。runtime confidence 虽可默认关闭地生成和序列化，但动作质量评测未观察到净增益，因此不进入默认策略消费；仍不做 MCTS 或蒙特卡洛搜索。

验收：

- 未见牌池与真实公开历史 100% 一致；
- 逢人配按 `carrier_cards` 计入真实已出牌；
- 每位玩家剩余容量与 `other_players.hand_count` 一致；
- pass 只作为软证据，不产生错误的硬排除；
- 推断结果可序列化、可测试、可审计。

详细设计见 `docs/BELIEF_STATE.md`。

实施拆分：

1. J-A：牌池守恒、真实已出牌、逐玩家公开状态和诊断，已完成；
2. J-B1：未见牌可能归属域、玩家容量约束和一致性诊断，已完成；
3. J-B2：关键残局的有限可行分配与唯一性证明，已完成；
4. J-C1：使用离线真实手牌建立覆盖率、错误确认和边界违例基线，已完成；
5. J-C2a：从公开历史提取 pass 响应、首出/跟牌和公开牌型事件，已完成；
6. J-C2b1：仅用敌方单张后 pass 建立有上限的 rank 软评分，已完成；
7. J-C2b2：扩展离线评测为并列分数友好的 Top-K 指标，做零软分/实际软分消融，已完成；
8. J-C3a：固定种子离线残局样本采集、总体和分阶段聚合，已完成；
9. J-C3b：用独立固定种子和预注册门槛运行 RuleBasedAI 正式基准，已完成；
10. J-C3c1：实现 evaluation-only 战略性 pass 策略和策略分层报告，已完成；
11. J-C3c2：用独立固定种子运行策略分布稳健性验收，已完成，判定拒绝；
12. J-C3d1：移除无条件 pass 负分并恢复零软分 hard-only ranking，已完成；
13. J-C3d2：验证 neutral ranking 在 forced/战略 pass 轨迹下均不损失召回，已完成；
14. J-D1a：聚合完整分配的精确物理权重和 token 边际整数计数，已完成；
15. J-D1b：在完整 matrix 上聚合 rank 持有与副本数的精确整数边际，已完成；
16. J-D1c1：建立单样本、evaluation-only 的概率评分与校准充分统计量，已完成；
17. J-D1c2a：从单样本原始充分统计量精确微聚合 Brier、copy MSE、ECE/MCE，已完成；
18. J-D1c2b：实现固定 seed 残局采集器并运行开发容量试验，已完成；
19. J-D1c2c：使用预注册独立语料运行正式校准，已完成；
20. J-D1c3a：建立 forced/25/50/100 strategic-pass marginal corpus 载体并运行开发试验，已完成；
21. J-D1c3b：使用独立 seed 运行多策略正式校准，已完成但支持度不足，判定 `benchmark_invalid`；
22. J-D1c3b2：不改模型、分桶或阈值，使用全新 seed 扩大独立样本并重新正式验收，已完成并通过；
23. J-D1c3c1：建立 critical-endgame-only 的 runtime confidence 数据契约，已完成；
24. J-D1c3c1a：严格布尔标志、玩家集合和非法分子守恒路径，已完成；
25. J-D1c3c2a：建立默认关闭的 pipeline 和 DeepSeek shadow 审计，证明动作与 prompt 等价，已完成；
26. J-D1c3c2b1：建立有界、确定、精确分数的 prompt payload，不接入模型，已完成；
27. J-D1c3c2b2：增加默认关闭的 prompt 消费开关并保持关闭态完全兼容，已完成；
28. J-D1c3c2c1：建立四策略配对 prompt 覆盖、预算与精确插入基准并运行开发试验，已完成；
29. J-D1c3c2c2：使用独立 seed 正式验收 prompt readiness 与成本，双运行完成但完整审计证据未留存，判定 `benchmark_invalid`；
30. J-D1c3c2c2a：使用仓库外 canonical JSON 审计文件和全新 seed 恢复正式验收，已完成并通过；
31. J-D1c3c2c3a：建立 evaluation-only、provider 可注入的固定配对动作消融载体，已完成并通过；
32. J-D1c3c2c3b：经用户授权后预注册并运行小规模真实 DeepSeek 响应安全与动作变化验收，已完成并保留；
33. J-D1c3c2c3c1：建立同状态动作分支和确定性 RuleBased 续局质量代理，已完成并通过；
34. J-D1c3c2c3c2：用独立语料运行真实模型动作质量验收，已执行但未完成，判定 invalid；
35. J-D1c3c2c3c2a：用全新 seed 和耐久后台进程恢复同一正式验收，运行完整但正式键序审计失败，判定 invalid；
36. J-D1c3c2c3c2b：只读复核 c3c2a 不可变证据并显式映射策略，已完成，判定无观察到的质量增益；
37. confidence 策略接入：停止推进，保持默认关闭；
38. H2-A1：建立开局动作残余结构代价、避免无收益拆组，并修复公式来源日志，已完成；
39. H2-A1a：精确公开 fixture、真实评分和未知 token fail-closed，已完成并核验；
40. K-A1：建立只读公开信息的策略意图上下文与确定性路由契约，已完成；
41. K-A1a：严格 phase context 数值类型并聚合多项 diagnostics，已完成并核验；
42. K-A2a：在 DeepSeek 主链做默认关闭的策略意图 shadow 装配，已完成并验证；
43. K-A2b1：建立 evaluation-only 离线路由分布载体并运行开发容量试验，已完成，初次严格复核未通过；
44. K-A2b1a：严格复核 router source、phase、available reason-intent 和 unavailable 中性契约，已完成并封板；
45. K-A2b2：根据开发分布运行独立 seed 正式覆盖验收，已完成，判定 `strategy_router_coverage_insufficient`；
46. K-A2b2a：不改实现和门槛，使用全新 seed 将语料扩大到每策略 200 局，已完成并通过；
47. K-A3a：建立有界、默认不消费的 intent prompt payload 初版，已实现但严格复核未通过；
48. K-A3a1：补齐路由优先级与跨字段一致性，已完成并封板；
49. K-A3b：增加默认关闭的 intent prompt 消费接线，已完成并封板；
50. K-A3c1：建立 evaluation-only prompt 覆盖、成本与配对摘要载体，已完成并通过；
51. K-A3c2：使用独立 seed 正式验证 prompt coverage 与字符成本，已完成；结构和覆盖通过，但预注册字符包络失败，判定无效；
52. K-A3c2a：穷举并锁定 phase×reason 的精确字符包络测试契约，已完成并封板；
53. K-A3c2b：以全新 seed `19000..19199` 和预先锁定的正确包络恢复正式验收，已完成并通过；
54. K-A3d1：建立 evaluation-only、provider 可注入、四阶段分桶的策略意图动作消融载体，已完成并通过；
55. K-A3d2：建立同状态 off/on 动作的 RuleBased 分支续局质量代理载体，已完成并通过；
56. K-A3d3a：完成真实模型质量试验的检查点、预算、安全门槛和明确授权前置，下一步。

J-A 验证结果：

- `python -m unittest tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：31 项通过；
- `python -m unittest discover -q`：141 项通过；
- 未修改 `engine/`、现有 `CardTracker`、RAG 或 DeepSeek 提示词。

J-B1 验证结果：

- `python -m unittest tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：43 项通过；
- `python -m unittest discover -q`：153 项通过；
- 只建立公开硬约束，不枚举完整分配，不输出概率或软推断。

J-B2 验证结果：

- `python -m unittest tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：61 项通过；
- `python -m unittest discover -q`：171 项通过；
- 只做受控确定性分配枚举；截断结果不确认、不缩小硬归属域。

J-C1 验证结果：

- `python -m unittest tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：78 项通过；
- `python -m unittest discover -q`：188 项通过；
- ground truth 仅进入离线评测，运行时模块没有 `evaluation` 依赖。

J-C2a 验证结果：

- `python -m unittest tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：92 项通过；
- `python -m unittest discover -q`：202 项通过；
- 只提取公开行为事件，没有软评分、概率、置信度或策略集成。

J-C2b1 验证结果：

- `python -m unittest tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：107 项通过；
- `python -m unittest discover -q`：217 项通过；
- 只有一个未校准 pass 启发式，尚无多种子 Top-K 改进证据。

J-C2b2 验证结果：

- `python -m unittest tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：120 项通过；
- `python -m unittest discover -q`：230 项通过；
- 只建立单样本、并列安全的零软分消融指标；尚无多种子改进证据。

J-C3a 验证结果：

- `python -m unittest tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：130 项通过；
- `python -m unittest discover -q`：240 项通过；
- 固定种子运行、阶段采集、原始计数微聚合和真值隔离已经建立；
- seed `0..19` 的开发试跑只用于测量容量：866 个 eligible、480 个 evaluated、386 个因每局 24 上限跳过，不能作为正式启发式结论。

J-C3b 正式结果：

- HEAD：`39bd0247b9459999cdeb489703ff288eed7df791`；
- seed `1000..1199`，两次 200 局运行报告和 canonical JSON SHA-256 完全一致；
- 8719 个目标阶段样本全部有效，无截断、无诊断；
- candidate recall 和 Top-1/Top-3 recall 无回退；
- overall Top-1 precision `+0.007357`、Top-3 precision `+0.006385`、MRR `+0.003233`；
- 唯一判定：`retain_for_policy_diverse_validation`；
- 该结论只覆盖 RuleBasedAI 的被迫 pass 轨迹，不授权置信度校准或策略接入。

J-C3c1 验证结果：

- `python -m unittest tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_ranker tests.test_card_signals tests.test_belief_metrics tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q`：140 项通过；
- `python -m unittest discover -q`：250 项通过；
- rate 0/25/50/100 的公开、确定性战略 pass 轨迹和隔离报告已经建立；
- seed `20..29` 开发试跑中，25% 战略 pass 的 overall Top-3 recall delta 约为 `-0.126899`，显示当前无条件 pass 负向信号存在明显策略分布风险；
- 该试跑不用于正式判定，J-C3c2 必须使用独立 seed 和预注册召回护栏。

J-C3c2 正式结果：

- HEAD：`f1bfabd7ba136553c12ed61824b79f8e4b9ef446`；
- seed `2000..2099`，四种策略各 100 局，两次报告和 SHA-256 完全一致；
- 所有数据完整性、策略行为、硬候选安全和 forced-only 复验通过；
- 25% 战略 pass 下 overall Top-1/Top-3 recall delta 分别为 `-0.170742` / `-0.092955`；
- near-open/critical Top-3 recall delta 分别为 `-0.088401` / `-0.099062`；
- 唯一判定：`reject_unconditioned_pass_signal`；
- MRR 正增量不能覆盖 Top-K 真实 rank 召回失败；
- 当前 pass 负分必须撤销，不能进入置信度校准或 runtime。

J-C3d1 验证结果：

- `agents/card_ranker.py` 已删除 pass penalty 参数、评分路径和 evidence；
- hard candidates、confirmed、J-B2 收窄和通用 metrics 保持稳定；
- 所有 possible candidate 恢复零软分、空 evidence；
- 定向 140 项、全量 250 项测试通过；
- seed `30..34` 开发试跑中，四种 pass 策略的全部 overall delta 严格为 0；
- 下一步只做独立 seed neutral 封板，不恢复被拒绝信号。

J-C3d2 正式结果：

- HEAD：`3ee050e1ff80615038348b11e7ba185ded463ca2`；
- seed `3000..3049`，四策略各 50 局，两次报告与 SHA-256 一致；
- 所有对局和样本有效，无截断或 diagnostics；
- 12 个 bucket 的 baseline/soft snapshot 完全相等；
- 所有 delta 精确为 0；
- 判定：`neutral_baseline_verified`；
- J-C 分支封板，后续不恢复无条件 pass 负分。

J-D1a 验证结果：

- `CardAllocationResult.physical_assignment_count` 聚合所有完整 count matrix 的物理权重；
- `PlayerAllocationBounds` 聚合逐 token 持有分子与副本数加权分子；
- 权重使用 `math.factorial` 和 Python 整数，未引入第三方依赖或浮点数；
- 不完整、无效、跳过和无解结果不输出部分权重或边际；
- token 副本数分子满足全局守恒；
- 定向 132 项、全量 256 项测试通过；
- 该步骤没有输出 rank 边际、概率、置信度或策略收益。

J-D1b 验证结果：

- 新增逐玩家 `holding_assignment_count_by_rank` 与 `copy_assignment_count_by_rank`；
- rank 持有分子按同一 matrix 中同 rank token 的并集计一次；
- rank 副本数分子等于对应 token 副本数分子之和，并满足跨玩家守恒；
- `10S`、`SJ`、`BJ` 等 token 使用严格公开映射；
- 非法 token 或 token/rank 牌池不一致会在搜索前 fail closed；
- 非完整结果不泄露部分 rank 边际；
- 定向 139 项、全量 263 项测试通过；
- 该步骤尚未输出概率、置信度、校准结论或策略收益。

J-D1c1 验证结果：

- 新增冻结的 `MarginalCalibrationBin` 与 `MarginalEvaluationReport`；
- presence Brier、rank copy 平方误差和桶内预测和全部用 `Fraction` 累计；
- 每个活跃外部玩家 × 每个正数公开 rank 都评分，包含负例；
- fail-closed 覆盖 allocation、rank 边际、守恒和显式真值；
- invalid 报告计数归零、误差为 `0/1`，并固定输出 10 个空桶；
- runtime 目录没有新 evaluation 依赖，报告不保留真实手牌或逐 pair 明细；
- 定向 152 项、全量 276 项测试通过；
- 尚未运行多种子校准，也未生成 runtime 置信度。

J-D1c2a 验证结果：

- 新增 `MarginalCalibrationAggregate` 与 `MarginalBenchmarkBucket`；
- 从 valid 报告原始误差和与 pair count 做精确微聚合；
- 输出 Brier mean、copy MSE、正例率、确定性错误率、ECE 和 MCE 的最简分数；
- 十档预测和跨样本精确通分，空桶稳定为 `0/1`；
- invalid 报告仅进入无效计数和同报告去重后的诊断类别；
- malformed 报告显式失败，输出顺序无关且不保留样本内容；
- 定向 166 项、全量 290 项测试通过；
- 尚未实现 seed 采集器或运行校准语料。

J-D1c2b 验证结果：

- 新增 critical-only collector 与共享 evaluation truth helper；
- overall 和外部牌数三个互斥桶均由原始报告精确聚合；
- 开发 seed `40..59` 两次完整报告和 SHA-256 一致；
- 20/20 局完成，522 个样本全部有效，无跳过和 diagnostics；
- 三个桶分别有 171、177、174 个样本；
- overall Brier mean `335904977521 / 1779098428800`；
- overall copy MSE `135996253741 / 667161910800`；
- overall ECE `459367 / 21393680`，MCE `10435 / 157608`；
- certainty error rate 为 `0/1`；
- 定向 179 项、全量 303 项测试通过；
- 判定 `development_capacity_verified`，尚不是正式校准。

J-D1c2c 预注册参数：

- seed `5000..5099`，100 局，完整运行两次；
- 级牌 `2`，`max_steps=5000`，每局最多 128 样本；
- 外部牌上限 12、节点上限 1,000,000、解上限 100,000；
- 默认 `RuleBasedAIAgent`；
- 正式运行期间不改实现、分桶、参数、阈值或样本筛选。

J-D1c2c 正式结果：

- 两次 100 局报告完全相同，SHA-256 为 `c4a91d81bed216e919189fe4fdddf76c76ee8e35eb28f5fcae21ebc9e401e190`；
- 100/100 局完成，2727 个样本全部有效，无 skip 或 diagnostics；
- 三个外部牌数桶有效样本均超过 900；
- overall 与三个桶的 certainty error 均为 0；
- overall/三桶的 ECE、Brier skill、支持度 MCE 全部通过预注册门槛；
- 判定 `retain_for_policy_diverse_calibration`；
- 该结论只覆盖默认 RuleBasedAI，不授权 runtime confidence。

J-D1c3a 验证结果：

- 多策略 wrapper 只复用 evaluation-only agent 与现有 marginal collector；
- 四个 rate 的 agent、对局、计数器和 corpus 完全隔离；
- 开发 seed `60..69` 双运行 SHA-256 均为 `dc5bfa083d686e57cb711e9892738713904da96178988931deda7318427a58a3`；
- 四策略各 10/10 局完成，invalid/skip/diagnostics 全为 0；
- 主动 pass 比例呈 0、约 0.397、约 0.496、1.0 的行为梯度；
- 三个 external bucket 在每个策略中均有样本；
- 定向 187 项、全量 311 项测试通过；
- 判定 `policy_diversity_capacity_verified`，尚未形成正式多策略校准结论。

J-D1c3b 预注册参数：

- seed `7000..7049`，四策略各 50 局，完整运行两次；
- 级牌 `2`，每局最多 128 样本，其他搜索上限保持不变；
- 正式运行期间不改实现、策略、gate、seed、分桶或校准门槛；
- 任一策略或任一外部牌数桶失败都不能被跨策略平均掩盖。

J-D1c3b 正式结果：

- seed `7000..7049` 四策略各 50 局，双运行报告完全相等；
- SHA-256 为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 四策略全部完成，无 invalid、skip 或 diagnostics，行为梯度与样本守恒通过；
- 15/16 个策略/范围通过全部护栏；
- `strategic_pass_100 / external_0_4` 只有一个 count>=100 的支持 bin，未达到至少两个支持 bin 的前提；
- 唯一判定 `benchmark_invalid`，不授权 runtime confidence，也不构成模型拒绝结论。

J-D1c3b2 预注册方向：

- seed `7000..7049` 只用于样本量规划，永久排除出后续验收；
- 使用全新 seed `8000..8119`，四策略各 120 局，完整运行两次；
- 保持实现、策略 gate、十档分桶、支持阈值和全部数值护栏不变；
- 扩容目的仅是让偏斜的 `strategic_pass_100 / external_0_4` 获得足够支持，不能做事后调参；
- 只有完整性、支持度和全部数值护栏同时通过，才能进入 J-D1c3c。

J-D1c3b2 正式结果：

- seed `8000..8119` 四策略各 120 局，双运行报告完全相等；
- SHA-256 为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 四策略全部完成，无 invalid、skip 或 diagnostics，主动 pass 比例严格递增；
- 每个策略的三个 external bucket 均超过 980 个有效样本；
- 16 个范围全部满足至少两个支持 bin、certainty=0、ECE、Brier skill 和 supported MCE 护栏；
- 判定 `policy_diverse_calibration_verified`；
- 只授权进入最小 runtime confidence 契约设计，不授权动作决策或胜率声明。

J-D1c3c1 设计边界：

- 新增独立 runtime 模块，消费 `CardBeliefState`、`CardConstraintState` 和完整 `CardAllocationResult`；
- 只覆盖 `critical_endgame` 且外部未知牌不超过 12 张的已验证范围；
- 公开整数分子/分母，不做浮点四舍五入、概率重映射或主观高/中/低分档；
- 任一前置条件或守恒校验失败时返回无玩家、零分母的 unavailable 状态；
- 不导入 `evaluation/`，不读取 observation、history 或 ground truth；
- 本步骤不修改 DeepSeek、RAG、剪枝、提示词或动作选择。

J-D1c3c1 实现结果：

- 新增 `agents/card_confidence.py` 与 `tests/test_card_confidence.py`；
- available 仅限已验证 critical 范围，输出精确 presence/copy 整数边际；
- 已覆盖阶段、精确性、搜索、外部数量、分母、玩家、容量、rank 和多数分子异常；
- 定向 76 项、全量 318 项测试通过；
- 新模块无 evaluation、ground truth、engine state、observation/history、DeepSeek 或 RAG 引用；
- 现有决策路径未导入新模块。

J-D1c3c1a 硬化范围：

- exact、consistent、search-complete 标志必须是实际 `True`，不能接受 `1` 或 truthy 字符串；
- constraints 与 allocation 不得包含公开 active external 集合之外的额外玩家；
- copy 守恒只能使用已验证整数，不得对 malformed 原始值直接求和；
- 字符串、`None`、float、`bool` 等非法 copy 分子必须稳定返回 unavailable，不能抛异常；
- 正常 available 输出和所有现有测试保持不变；
- 以上硬化已完成，允许进入 J-D1c3c2a shadow 装配。

J-D1c3c1a 实现结果：

- 四个布尔语义字段改为严格 `is True`；
- belief/constraints/allocation 的正容量外部候选玩家集合严格比较；
- copy 分子验证后进入规范化整数表，守恒求和不再触碰原始 malformed 值；
- 合法 available `to_dict()` snapshot 保持不变；
- 单文件 11 项、相关 80 项、全量 322 项测试通过；
- 新模块与现有 decision path 边界扫描通过。

J-D1c3c2a 设计边界：

- 新增独立 runtime pipeline，复用统一 phase，只在 critical 阶段执行精确枚举；
- `DeepSeekAIAgent` 新增显式 `card_confidence_shadow_enabled=False`，不接 AppConfig 或环境变量；
- 默认关闭时不导入、不调用 pipeline，现有 client 调用参数、prompt 和 action ID 完全不变；
- 开启时只更新只读审计字段 `last_card_confidence`，不得传给 prompt、RAG、剪枝或策略；
- 每次决策开始清空旧审计值，local shortcut 不计算 confidence；
- pipeline 失败返回 unavailable，不能阻断或改变 DeepSeek 降级路径；
- shadow off/on 动作等价已证明，下一步先封板 J-D1c3c2b1 序列化，再考虑 J-D1c3c2b2 消费。

J-D1c3c2a 实现结果：

- 新增 `agents/card_confidence_pipeline.py` 与对应测试；
- `DeepSeekAIAgent` 增加默认关闭的 shadow 开关和最后审计状态；
- 非 critical 不构建 belief 或 allocation，critical 公开链路各执行一次；
- pipeline 正常 unavailable 原样保留，异常规范为 `pipeline_error`；
- shadow 结果不传给 prompt、RAG、剪枝、client 或动作选择；
- off/on 的 client kwargs、动作、fallback 与 decision source 完全一致；
- 定向 40 项、相关 124 项、全量 331 项测试通过。

J-D1c3c2b1 设计边界：

- 新增独立 formatter 模块和单元测试，不修改 agent 或 DeepSeekClient；
- 只格式化已验证 available source/scope；
- 使用约分精确分数，不输出 float、百分比或 high/medium/low；
- 保留全部玩家和正数公开 rank，不基于概率删选；
- 输出必须在固定字符预算内；超预算整体 omitted，不能截断；
- 后续 J-D1c3c2b2 只能消费该封板 payload，不能直接序列化 runtime dataclass。

J-D1c3c2b1 实现结果：

- 新增 `agents/card_confidence_prompt.py` 与对应测试；
- payload frozen/slots，ready/omitted 字段稳定且 JSON 友好；
- formatter 严格复核 phase/source/scope、外部数、分母、玩家容量和 rank 布局；
- 分数使用 `gcd` 约分，固定边界说明，不输出 float 或主观标签；
- 2400 字符预算超限时整体 omitted，不截断；
- 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项测试通过。

J-D1c3c2b2 设计边界：

- agent 增加 `card_confidence_prompt_enabled=False`，并要求 prompt 开启时 shadow 必须开启；
- 仅从 `last_card_confidence` 构建封板 payload，不直接读取 observation 或中间边际；
- ready payload 作为类型化对象传给 DeepSeekClient；
- omitted/unavailable 时不增加 client keyword，不增加 prompt 章节；
- DeepSeekClient 只接受合法 ready payload，并在记牌信息之后插入固定 `【残局牌面信念】` 章节；
- 关闭态和 omitted 态 prompt/client kwargs 保持原样；
- 不修改 RAG、剪枝、legal actions、fallback 或默认配置。

J-D1c3c2b2 实现结果：

- agent 增加默认关闭的 prompt 开关和 payload 审计字段；
- 只允许 off、shadow-only、prompt 三种严格 bool 模式；
- ready payload 是 client kwargs 的唯一差异；
- omitted/unavailable 与 shadow-only kwargs、prompt、动作和 fallback 相同；
- client 对 malformed payload 整体忽略；
- 新章节只插入一次且不改变其他 prompt 段落；
- 定向 54 项、相关 48 项、全量 345 项测试通过。

J-D1c3c2c1 设计边界：

- evaluation-only collector，不发出 DeepSeek 网络请求；
- 复用 strategic-pass 0/25/50/100 四种独立轨迹；
- critical 样本构建同一份 off/on prompt，唯一差异应为封板 confidence 章节；
- 聚合 ready/omitted、诊断、payload 字符和 prompt 字符 delta；
- 报告不保留 seed、observation、prompt、手牌、玩家或逐样本内容；
- 开发 seed 只验证容量、确定性、覆盖和成本，不形成动作质量结论。

J-D1c3c2c1 实现与开发结果：

- 新增 `evaluation/confidence_prompt_benchmark.py` 与对应测试；
- 四策略独立采集 critical 样本并按三个 external bucket 聚合；
- off/on prompt 只在内存配对，报告不保留 prompt、observation 或玩家明细；
- seed `80..89` 双运行报告完全一致，SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；
- 四策略共 1084 个样本全部 ready，零 omitted、budget omitted、pair mismatch 和 diagnostics；
- 每个样本 delta 精确为 payload chars + 11；
- 定向 28 项、相关 77 项、全量 351 项测试通过；
- 判定 `confidence_prompt_coverage_capacity_verified`。

J-D1c3c2c2 正式方向：

- 已在检查点 `bc689a37f462672033d754cce7060897d70c7612` 使用 seed `10000..10049` 完成四策略各 50 局双运行；
- report、`to_dict()`、canonical JSON 和 SHA-256 两次相等，哈希为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- stdout 被工具层截断，未保留四策略全部分桶聚合，无法审计完整性、coverage 和字符成本门槛；
- 按预注册约束没有第三次运行、补采或调整参数；
- 唯一判定 `benchmark_invalid`，不得进入 J-D1c3c2c3。

J-D1c3c2c2a 恢复方向：

- 已使用全新 seed `11000..11049` 完成四策略各 50 局双运行；
- 两份 9218-byte canonical JSON 逐字节一致，SHA-256 为 `679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- 四策略共 5733 个样本，16 个范围全部 available/ready/exact insertion，零 omitted/mismatch/diagnostics；
- payload 最大 683 字符，固定章节开销精确为每样本 11 字符；
- 判定 `confidence_prompt_coverage_verified`；原 seed `10000..10049` 结果仍为 `benchmark_invalid`；
- 原审计摘要错误依赖 JSON 键迭代顺序，恢复解析器按策略名/rate 只读复核；后续不得把 canonical 键顺序当业务顺序。

J-D1c3c2c3a 设计方向：

- 已只新增 evaluation 动作消融模块与对应测试，未修改 runtime、engine、client、RAG、CLI 或配置；
- critical 合格样本按固定 SHA-256 优先级选择，only-pass、一次出完和 unavailable/omitted/mismatch 不调用 provider；
- off/on kwargs 只差 confidence payload，每桶 AB/BA 平衡，一侧异常仍调用另一侧；
- provider 结果按异常、malformed、no-action、类型、legal/prompt 域严格分类，不使用 fallback；
- seed `120..129` 四策略每桶 4 个样本双运行，report 完全相等，SHA-256 为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 每轮 48 pair / 96 次假 provider 调用全部 valid，每桶 AB/BA 各 2；
- 判定 `confidence_action_ablation_harness_verified`，不宣称 confidence 改善动作。

J-D1c3c2c3b live pilot 方向：

- 已在 `e0065c6a3da70b3d4ded4b394817bfab3351c113` 上使用 `deepseek-v4-pro`、60 秒 timeout、零重试完成；
- seed `13000..13009` 四策略每桶 2 个样本，共 24 pair / 48 次真实请求；
- 48 个响应全部在 prompt candidates，24 pair 全部 both-valid，零异常和解析/合法性失败；
- same/changed 总计 13/11，off/on pass 均为 6，pressure 均为 0；
- 总耗时 1411.005 秒，审计文件均已仓库外持久化并哈希；
- 判定 `retain_for_action_quality_evaluation`；动作差异仅为描述性结果，不排除服务非确定性。

J-D1c3c2c3c1 实现与开发结果：

- 只新增 `evaluation/confidence_action_quality.py` 和对应测试，未修改 c3a、engine、runtime、DeepSeek client、RAG、CLI 或配置；
- c3a seed `120..129` canonical SHA-256 仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 仅为固定优先级入选样本保留内存 clone，公开等价校验、分支执行和 RuleBased 续局均不访问 `game._state`；
- same action 单分支复用，changed action 双分支独立运行；终局和质量字典序按预注册公开契约执行；
- seed `140..149` 双运行完全一致，canonical SHA-256 为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`；
- 24 pair 全部 both-valid、quality-evaluable，全部 rollout 完成，零 diagnostics；
- 四策略 on-better/off-better/tie 为 1/1/4、1/0/5、0/0/6、1/0/5；
- 新模块 5 项、相关 81 项、全量 362 项测试通过；
- 判定 `confidence_action_quality_harness_verified`，不形成真实模型动作质量或胜率结论。

J-D1c3c2c3c2 正式结果：

- c3c1 已提交为 `ad85662a47f126991e8ebe0360dc0c6c4a2f1be6`；
- seed `15000..15009`、四策略、每桶 2、最多 48 次零重试请求；
- 外层执行器在 30 分钟中断，子进程随后终止，未恢复或重跑；
- ledger 连续 45 条，off/on=23/22，全部 returned；
- 没有完整 `report.json`，不计算 same/changed、rollout 或质量结果；
- 失败证据已在仓库外持久化并哈希；
- 判定 `quality_benchmark_invalid`。

J-D1c3c2c3c2a 正式结果：

- seed `16000..16009`，48/48 请求、24 pair、全部 rollout 和零 diagnostics 均完成；
- 四策略均 10/10/0，主动 pass 比例严格递增；
- 持久后台进程正常退出，完整 ledger/report/summary/completion 均已落盘并哈希；
- 正式 summary 错误依赖 canonical JSON 键顺序，`integrity_pass=false`；
- 原证据未改写，未重跑，未形成质量结论；
- 判定 `quality_recovery_invalid`。

J-D1c3c2c3c2b 恢复方向：

- 不联网、不读 key、不发送请求，不修改任何原审计文件；
- 在新仓库外目录运行只读验证器，先复核全部源文件 hashes；
- 以显式 `forced_only=0`、`strategic_pass_25=25`、`strategic_pass_50=50`、`strategic_pass_100=100` 映射校验策略，不依赖 mapping 迭代顺序；
- 独立重算 ledger、策略、分桶、pair、rollout、diagnostics、JSON 和隐私守恒；
- 原 summary 除键序检查外若存在任何其他失败，恢复审计立即 invalid；
- 两次只读验证必须生成完全相等的 canonical recovered summary；
- 完整性恢复后才按 c3c2 原预注册 overall 门槛形成质量判定，原 c3c2a invalid 不被覆盖。

J-D1c3c2c3c2b 结果：

- 原 summary 只有由 canonical JSON 键序误用导致的派生 `integrity_pass=false`；
- 显式策略映射、全部源 hashes、48 请求、24 pair、33 branches 和所有守恒独立复核通过；
- 双验证输出逐字节一致；
- overall same/changed=15/9，on/off better=0/0，tie=24，双方 team win 均为 10；
- 唯一判定 `no_observed_action_quality_gain`；
- 不进入完整 DeepSeek 对局评估，confidence 默认保持关闭。

### Step K：中局策略路由与残局决策

状态：K-A1 至 K-A3d2 已封板。K-A3c2 原唯一判定保持 `strategy_intent_prompt_coverage_benchmark_invalid`；K-A3c2b 独立恢复判定为 `strategy_intent_prompt_coverage_recovery_verified`。下一步为 K-A3d3a。

目标：

- 中局明确区分 `run_out`、`control`、`support_teammate`、`block_opponent`；
- 策略路由器先选择策略意图，RAG 再为意图检索经验；
- 近似明牌残局使用逐玩家信念状态；
- 危险对手、队友跑牌和牌权转移进入结构化决策。
- 路由显式记录当前桌面动作来自队友还是对手，避免无收益压队友；
- 对手完成一次出牌后剩余不超过 2 张时进入阻断优先级。

验收：

- 路由结果对固定 observation 可复现；
- RAG 不单独决定动作；
- 模型只能从传入候选动作中选择；
- 固定种子和轮换座位 A/B 评测可重复。

K-A1 方向：

- 新增独立 `agents/strategy_router.py` 与对应测试；
- 只消费调用方传入的统一 phase、公开 observation、legal actions 和既有 hand evaluation；
- 输出 frozen/slots、JSON 友好的路由上下文，不修改候选动作；
- 先固定 `run_out`、`block_opponent`、`support_teammate`、`control` 四种意图及 fail-closed unavailable 状态；
- opening 不参与路由，继续由现有公式开局处理；
- 不接 DeepSeek、RAG、剪枝、confidence 或动作选择；
- 固定 fixture 验证优先级、团队关系、桌面领牌关系、紧急手数、弱/强牌和 malformed 输入；
- 纳入 `record.txt` 第 2、16、20 轮的最小公开 fixture，但不读取原始日志文件作为运行时依赖；
- 通过只授权 K-A2 shadow 集成，不代表策略质量提升。

K-A2a 方向：

- 在 `DeepSeekAIAgent` 增加严格布尔、默认关闭的 shadow 开关和非展示审计字段；
- 每次决策先重置审计字段，本地快捷路径和公式命中不运行 router；
- 其余路径复用已计算的唯一 phase 与手牌评估，只调用 router 一次；
- shadow 结果只写入审计字段，不进入 prompt、RAG、剪枝、client kwargs、fallback 或 action 选择；
- off/on 必须对模型调用、prompt、返回动作和 decision source 完全兼容；
- 通过只授权 K-A2b1 离线路由分布载体，不授权策略消费。

K-A2a 验证结果：

- 严格布尔开关默认关闭，每次决策重置非展示审计字段；
- 本地快捷路径跳过 router，普通链路复用同一 phase、原始 legal actions 和已有手牌评估；
- router 结果或异常都不改变 prompt、RAG、剪枝、fallback、action 和 decision source；
- 定向 25 项、相关 100 项、全量 396 项通过；
- 唯一判定 `strategy_router_shadow_verified`。

K-A2b1 方向：

- 新建 evaluation-only 多策略路由分布载体，不修改 runtime；
- 复用 forced-only 与 25/50/100% strategic-pass 公开策略，每个 rate 使用独立对局；
- 按 midgame/endgame/near-open/critical 和四种 intent 聚合 available、unavailable、reason、桌面领牌关系与 diagnostics；
- 单独记录 opening、only-pass、一次出完和样本上限跳过，保持计数守恒；
- 报告不保留 seed、样本 ID、observation、action、玩家或手牌明细；
- 先运行小型双运行开发容量试验，用实际分布为 K-A2b2 锁定门槛；本步不判定策略质量。

K-A2b1 复核结果：

- seed `200..209` 双运行报告、`to_dict()` 和 canonical JSON 完全相等，SHA-256 为 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb`；
- 四策略均 10/10/0，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 四策略的四阶段均有 available 样本，主动 pass 比例严格递增；
- 单模块 8 项、相关 58 项、全量 404 项通过；
- 但 available 的 wrong source、wrong phase、unknown reason 和 reason-intent mismatch 均会被接受，unavailable 也缺少对 source/phase/非空 diagnostics/中性字段的复核；
- 唯一判定 `strategy_router_distribution_harness_invalid`。

K-A2b1a 方向：

- 只修改 `evaluation/strategy_router_benchmark.py` 和对应测试；
- 复核 context 类型、固定 source、与 bucket 一致的 phase、status 与 diagnostics；
- available 只接受已知 reason，且 reason 必须与 intent 映射一致；
- unavailable 必须有非空规范 diagnostics，且不保留任何玩家、领牌、手牌强度或意图结论；
- malformed context 统一记为 `invalid_router_result`，不泄露其中的伪 diagnostics；
- 合法语料报告字段与 canonical SHA-256 必须精确不变；
- 通过后才授权 K-A2b2，仍不授权策略消费。

K-A2b1a 验证结果：

- context 类型、固定 source、预期 phase、严格 bool/tuple、reason-intent 映射和 available 语义均已集中复核；
- unavailable 必须完全中性，malformed context 只计一次 `invalid_router_result`；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- seed `200..209` 双运行报告与开发 SHA-256 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb` 精确不变；
- 唯一判定 `strategy_router_distribution_hardening_verified`。

K-A2b2 方向：

- 不修改仓库文件，只用全新独立 seed 运行现有载体两次；
- 审计四策略的对局、采样、phase、intent、reason、relation 与全部守恒；
- 使用仓库外完整 JSON 与哈希证据，显式按策略名和 rate 复核，不依赖 JSON 键序；
- 只验证覆盖可重复且非退化，不比较动作质量，不授权策略消费。

K-A2b2 正式结果：

- seed `16000..16099`、四策略各 100 局，双运行 canonical SHA-256 均为 `e77e5632b4b71f4a12fc1b213be78b413c70486f60e06e3f5cd35c941aa2d40d`；
- 四策略全部完成，无 unavailable、invalid、skip、duplicate 或 diagnostics，全部守恒和 pass 梯度通过；
- overall/phase intent、relation 和 reason 覆盖全部通过；
- forced/25%/50% 的 endgame available 为 583/660/663，低于预注册 700；
- 273 项检查只有上述三项失败，唯一判定 `strategy_router_coverage_insufficient`。

K-A2b2a 方向：

- 不改实现、策略、phase、分桶、采样规则或覆盖门槛；
- 永久排除 seed `16000..16099`，使用全新 seed `17000..17199`；
- 每策略扩大到 200 局并完整双运行，继续使用仓库外 canonical JSON 审计；
- 只解决预注册绝对样本容量，不把扩容结果解释为动作质量。

K-A2b2a 正式结果：

- seed `17000..17199`、四策略各 200 局，双运行 canonical SHA-256 均为 `ee321d18a50f923e92bbcc7e99c7e90a0ee87ac8b57b35b95e091f988c670c0e`；
- 四策略全部完成，无 unavailable、invalid、duplicate、sample-limit 或 diagnostics；
- 结构完整性 97/97、覆盖 176/176、总计 273/273 通过；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- 唯一判定 `strategy_router_coverage_verified`。

K-A3a 方向：

- 新增独立 `agents/strategy_intent_prompt.py` 和对应单元测试；
- 只消费已经 available 的 `StrategyIntentContext`，严格复核 source、phase、intent、reason 与公开字段一致性；
- 输出 frozen/slots、JSON 友好、有固定字符预算的 ready/omitted payload；
- 使用固定文案映射，不透传任意字符串，不输出隐藏事实或把 intent 描述为规则命令；
- 本步不修改 DeepSeek client、agent、RAG、evaluation 或动作选择；
- 通过后只授权 K-A3b 默认关闭的 prompt 消费接线。

K-A3a 初次复核：

- fixed text、reason-intent 映射、预算、frozen/slots 与 omitted 清空均已实现；
- 单模块 7 项、相关 43 项、全量 414 项通过；
- 但局部 reason 校验没有重放 K-A1 路由优先级，多个跨字段矛盾 context 仍返回 ready；
- hand strength 与 total score、control score 与 total score、minimum count 与 urgent IDs 也未完整守恒；
- 唯一判定 `strategy_intent_prompt_contract_invalid`，不得进入 K-A3b。

K-A3a1 方向：

- 只修改 formatter 与对应测试，payload 字段和合法文本快照保持不变；
- 先验证 count/urgency/score 的内部守恒，再按 K-A1 固定优先级推导唯一 expected reason；
- context 的 reason 和 intent 必须与 expected reason 精确一致，否则整体 omitted；
- 覆盖被更高优先级条件遮蔽的 weak/control/urgency reason 反例；
- 通过后才授权 K-A3b 默认关闭的消费接线。

K-A3a1 验证结果：

- 九类预注册伪造 context 全部 omitted；
- score/strength、minimum/urgent IDs、teammate/leader urgency 守恒已锁定；
- 唯一 expected reason 按 K-A1 原优先级推导；
- 合法十 reason、三 snapshot 与固定文本保持不变；
- 单模块 11 项、相关 47 项、全量 418 项通过；
- 唯一判定 `strategy_intent_prompt_contract_hardening_verified`。

K-A3b 方向：

- 在 `DeepSeekAIAgent` 增加严格布尔、默认关闭且依赖 router shadow 的 prompt 开关；
- 只有 ready payload 才作为新增类型化 keyword 传给 client；
- client 独立复核 payload 并在固定位置精确插入一次；
- off、shadow-only、omitted 和异常路径的 kwargs、prompt、动作与 fallback 必须保持等价；
- 本步不让 intent 选择 RAG、改变剪枝或默认启用。

K-A3b 验证结果：

- off/shadow-only/prompt 三态与严格依赖已实现；
- ready 才增加类型化 keyword，client 对固定四行文本做独立复核；
- 插入顺序为 confidence、strategy intent、scene tags；
- omitted/异常路径保持原模型和 fallback 等价；
- 定向 56 项、相关 88 项、全量 424 项通过；
- 唯一判定 `strategy_intent_prompt_wiring_verified`。

K-A3c1 方向：

- 新增 evaluation-only 多策略×多阶段 prompt pair collector；
- 只使用公开 observation、legal actions、统一 phase、hand evaluation、router 与 formatter；
- 构建 off/on structured prompt，不调用模型或网络；
- 聚合 ready/omitted、精确插入、payload/prompt delta 字符成本、diagnostics 与 pair digest；
- 先运行小型双运行开发容量试验，为 K-A3c2 正式覆盖验收锁定门槛。

K-A3c1 验证结果：

- seed `300..309` 双运行 canonical SHA-256 均为 `032ff0964a0fe4c377c612f27263e553abfe22ad759d14b5714ebf788d280a20`；
- 四策略均 10/10/0，16 个 phase bucket 全部 ready；
- 零 unavailable、invalid、omitted、duplicate、limit、mismatch 与 diagnostics；
- payload 74..90 字符，delta 83..99 字符，逐样本精确相差 9；
- 定向 6 项、相关 52 项、全量 430 项通过；
- 唯一判定 `strategy_intent_prompt_coverage_capacity_verified`。

K-A3c2 方向：

- 先提交 K-A3c1 检查点并要求工作区干净；
- 使用全新 seed、每策略 200 局完整运行两次；
- 保持实现、策略、phase、采样、字符预算和全部 pair 规则不变；
- 仓库外保存完整 canonical JSON、审计摘要和文件哈希；
- 通过只授权 K-A3d1 evaluation-only 动作消融载体。

K-A3c2 正式结果：

- seed `18000..18199`，四策略各 200 局，双运行 canonical SHA-256 均为 `35587b8d532dc9ba3fc8d82d6f6a690692362a31a908c066b2ad4783bfd1d148`；
- 16 个策略×阶段桶全部 ready、精确插入且达到样本门槛，所有 invalid/omitted/mismatch/diagnostics 为 0；
- 四个 near-open 桶均出现合法的 payload/delta 最大值 `91/100`，违反预注册上界 `89/98`；
- 唯一判定 `strategy_intent_prompt_coverage_benchmark_invalid`，不得事后修改门槛追认通过。

K-A3c2a 方向：

- 只修改 formatter 单元测试，不修改固定文本、runtime 或 benchmark；
- 穷举四阶段×十种 reason，锁定每个组合的精确字符数；
- 锁定理论包络：midgame `74..81 / 83..90`、endgame `74..81 / 83..90`、near-open `84..91 / 93..100`、critical `83..90 / 92..99`；
- 通过后才允许 K-A3c2b 使用未用过的新 seed 做正式恢复，不直接进入动作消融。

K-A3c2a 验证结果：

- 只修改 `tests/test_strategy_intent_prompt.py`，未修改 formatter、runtime、evaluation benchmark 或 docs；
- 40 个阶段×reason 组合全部通过真实 formatter，均为 ready、空 diagnostics，且 `char_count == len(text)`；
- payload 包络锁定为 midgame/endgame `74..81`、near-open `84..91`、critical `83..90`；
- 固定插入 delta 包络锁定为 `83..90`、`83..90`、`93..100`、`92..99`；
- 定向 12 项、相关 60 项、全量 431 项通过，唯一判定 `strategy_intent_prompt_envelope_contract_verified`。

K-A3c2b 方向：

- 先提交 K-A3c2a 检查点并确保工作区干净，不 stash、还原或混入现有 docs 改动；
- 使用未使用 seed `19000..19199`、四策略各 200 局，正式 benchmark 恰好运行两次；
- 使用 K-A3c2a 已封板包络，不修改 formatter、benchmark、采样或门槛；
- 报告先写入仓库外审计目录，再输出摘要，避免工具输出截断导致证据丢失；
- 通过只授权规划 K-A3d1 evaluation-only 动作消融，不默认启用 intent prompt。

K-A3c2b 验证结果：

- HEAD / K-A3c2a 检查点为 `a8cf1291de2fde62c6c7ed7ecfeaa878671f5490`，运行前后工作区干净；
- seed `19000..19199`、四策略各 200 局，正式 benchmark 恰好运行两次；
- 两份 canonical JSON 逐字节相同，SHA-256 均为 `a3f6b35f791435af22ccf3e877e5b5d571028d9dc05d36ce506e10c2a31ad66b`；
- 16 个 phase bucket 全部达到样本门槛，均为 sample=available=ready=exact insertion；
- 字符 min/max 全部落在 K-A3c2a 包络内，delta 的 sum/min/max 与 payload+9 精确一致；
- 零 duplicate、limit、unavailable、invalid、omitted、mismatch 和 diagnostics；
- 定向 12 项、相关 60 项、全量 431 项通过；
- 唯一判定 `strategy_intent_prompt_coverage_recovery_verified`，K-A3c2 原 invalid 不变。

K-A3d1 方向：

- 新增独立 `evaluation/strategy_intent_action_ablation.py` 与对应测试，不修改现有 confidence harness 或 runtime；
- 使用注入的 deterministic provider，off/on 共用同一公开局面和候选动作，on 仅增加类型化 strategy intent payload；
- 按四策略×四阶段以固定 SHA-256 优先级选样，平衡 AB/BA 调用顺序；
- 严格分类异常、malformed、no-action、非法类型、越过 legal/prompt 候选，并且不使用 fallback；
- 先以全本地 fake provider 双运行验证载体，不联网、不评价动作质量或胜率。

K-A3d1 验证结果：

- 仅新增 `evaluation/strategy_intent_action_ablation.py` 与对应测试，未修改 runtime 或既有 harness；
- 四策略×四阶段使用固定 SHA-256 优先级，每桶选择 4 对并平衡 AB/BA；
- off/on kwargs 唯一差异为 ready `strategy_intent_prompt`，七类 provider 结果 fail-closed 且无 fallback；
- seed `400..409` 双运行报告完全相同，canonical SHA-256 均为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；
- 每轮 128 次 provider 调用，64 对全部 both-valid 且 changed，所有异常分类和 diagnostics 为 0；
- 定向 8 项、相关 74 项、全量 439 项通过；
- 唯一判定 `strategy_intent_action_ablation_harness_verified`。

K-A3d2 方向：

- 先把 K-A3d1 的两个新增文件形成独立实现检查点，不混入既有 docs 改动；
- 新增独立 `evaluation/strategy_intent_action_quality.py` 与对应测试，不修改 K-A3d1 公共契约；
- 在固定优先级入选时只做内存 `deepcopy(game)`，clone 前后以 `observe()/legal_actions()` 验证公开等价，不读取 `_state`；
- off/on both-valid 后从独立 clone 执行动作，再由独立 RuleBasedAI 推进到终局；same action 只 rollout 一次并复用；
- 比较顺序固定为队伍 win/draw/loss 分数、队伍两人名次和，再 tie；不以步数、pass 或 pressure 打破平局；
- 先用 deterministic fake provider 双运行验证全部分支和守恒，不联网，不把代理结果称为真实模型质量或胜率。

K-A3d2 验证结果：

- K-A3d1 已独立提交为 `b75dace33d399704e45909ce31c339a7a7e14226`，本步只新增质量模块和测试；
- seed `500..509` 双运行报告完全相同，canonical SHA-256 均为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；
- 四策略×四阶段每桶 2 对，32 pair 全部 changed 且 quality-evaluable，64 branches 全部完成；
- 固定 RuleBased 续局代理为 on/off/tie=`5/11/16`，只描述假 provider 首/末候选差异，不代表 intent prompt 质量；
- K-A3d1 同参数采样与 digest 兼容，原开发 hash 保持不变；
- 定向 7 项、相关 80 项、全量 446 项通过；
- 唯一判定 `strategy_intent_action_quality_harness_verified`。

K-A3d3a 方向：

- K-A3d2 已独立提交为 `415c86dc5034ca85862f52e94d1406aa58042b98`；由项目所有者单独提交既有 docs，使真实运行前工作区干净；
- K-A3d3a 已连续两次因当前进程未显式提供 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DEEPSEEK_API_KEY` 而判定 `precondition_failed`；首次在干净 HEAD `a450fd2367b53ba455e904e1361422f9f965eb58` 完成全部离线前置，第二次按快速门槛停止且未重复回归；
- 当前新进程已确认三项变量 present 且工作区干净；项目所有者选择 `https://api.deepseek.com` / `deepseek-v4-flash` 作为本次 K-A3d3b 锁定配置；
- 重试时先检查三项显式进程环境元数据；仍缺失则立即停止，不重复运行 7 / 80 / 446 项回归；三项齐备后才继续完整前置审计并请求授权；
- 不得把 `.env.example` 当作配置注入方式；它的未提交改动必须由项目所有者在不暴露内容的前提下自行处理，真实密钥不得进入该文件；
- 不联网、不创建 runner、不发送 probe，只复核回归、harness hash、非敏感 endpoint/model 元数据与 key 是否存在；
- 预注册 seed `600..609`、策略 `(0,50,100)`、每 phase 2 对，共 24 pair、最多 48 次请求；
- timeout 60 秒、零重试、持久后台上限 65 分钟；真实请求必须另行取得用户对明确 endpoint/model 的授权；
- 48 次请求必须全部使用 `deepseek-v4-flash`，不得回退或混入历史 `deepseek-v4-pro`；结果只作 flash 内部 off/on 配对解释，不与旧 pro 结果合并；

K-A3d3b 结果：

- 前置已通过并取得一次性授权，但唯一后台进程 PID `33612` 在任何 state/heartbeat/ledger 落盘前异常退出；
- 失败目录只保留 runner，SHA-256 为 `a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd`；
- ledger 为 0，没有模型响应、pair、rollout 或质量结果可解释；
- 未重跑、未补采、未启动第二进程，唯一判定 `strategy_intent_live_quality_benchmark_invalid`；
- 下一步 K-A3d3c1 只做仓库外离线启动审计与 bootstrap 加固，不联网；原 seed `600..609` 永久停用。

K-A3d3c1 方向：

- 首次尝试只读复核原 runner 后，因四份规划文档未提交而停止并判定 `strategy_intent_live_startup_hardening_invalid`；未创建 candidate、第二进程或网络请求；
- 先由项目所有者提交四份 docs，恢复干净工作区，再重试同一 K-A3d3c1；
- 将父启动状态提前到 spawn 前，将子状态提前到项目 import 前；
- 延迟 project imports，并让参数、目录、首次写入和 import 全部进入最外层保护；
- 通过 `--offline-self-check` 验证正常/失败状态链，request count 必须为 0；
- 不能从缺失证据猜测唯一根因，只能锁定 `startup_failure_before_state_write`；
- 通过后才允许以全新 seed `700..709` 规划 K-A3d3c2，并重新请求用户授权。

K-A3d3c1 验证结果：

- 原失败 runner bytes/hash 与 PID 退出状态保持不变，只能确认 `startup_failure_before_state_write`；
- 新父启动器与子 runner 位于仓库外，SHA-256 分别为 `6a186d7c...e5ca84a`、`776f4504...b01e445`；
- 正常 self-check 两次结构 hash 均为 `ede8bfc3...41e80ec`；
- 缺失参数、无效目录、import 失败和原子写入失败均有预期 exit/status 证据；
- request/network/client/suggest count 均为 0；
- 唯一判定 `strategy_intent_live_startup_hardening_verified`。

K-A3d3c2 方向：

- 先只读复核 K-A3d3c1 证据、环境元数据和新预算，停下请求新的明确授权；
- 使用全新 seed `700..709`，旧 `600..609` 与 K-A3d3b 授权永久停用；
- 授权后恰好运行一次，策略 `(0,50,100)`、每 phase 2 对、24 pair/48 请求；
- endpoint/model 继续锁定 `https://api.deepseek.com` / `deepseek-v4-flash`，60 秒、零重试、65 分钟；
- live runner 必须继承父 spawn 前与子 import 前状态链；任何完整性失败只产生 recovery invalid。

K-A3d3c2 结果：

- 唯一授权 live run 完成 48/48 请求，off/on 各 24，全部 returned、零重试、零请求失败；
- report 与 audit summary 已写入，但 manifest/completion 缺失，子进程 exit code=1；
- 根因已定位到 runner 第 244–245 行错误地从 audit 目录读取实际位于 candidate root 的 runner metadata；
- 父状态完整，子状态为 bootstrapping→imports_ready→startup_ready→running→completed→failed；
- 按预注册完整性优先规则，唯一判定 `strategy_intent_live_quality_recovery_invalid`，不得解释已生成 report；
- 未重跑、补采或启动第二进程，旧授权已用尽。

K-A3d3c3a 方向：

- 不再次联网，独立只读验证原 report、48 条 ledger、状态链和源码路径缺陷；
- 在全新恢复目录运行两次自包含 verifier，不信任原 summary verdict，不补写原 manifest/completion；
- 完整性失败只产生 readonly recovery invalid；完整性通过后才按原 changed/on-off/team-win 顺序给出描述性判定；
- 无论恢复结果如何，K-A3d3c2 原 invalid 永久保留。

K-A3d3c3a 结果：

- 独立 verifier 双运行逐字节一致，完整重算 48 个请求、24 pair、三策略四阶段和全部 branch/W-D-L/quality 守恒；
- 源证据前后文件集合和 SHA-256 不变，第 244–245 行 manifest 路径缺陷得到确认；
- changed pair=`7`，在预注册第一道 `changed>=8` 门槛失败；后续 on/off better=`2/1`、team wins=`8/6` 不得越级解释；
- 新只读恢复判定 `no_observed_strategy_intent_action_quality_gain`；K-A3d3c2 原 invalid 不变；
- strategy-intent prompt 继续默认关闭，本分支封板，不进入扩大质量评估。
- 完整性通过后才解释 RuleBased 续局代理；小样本只决定是否保留到扩大验收，不构成因果或胜率结论。

### Step L：Botzone 本地 AI 接入

状态：Phase 0 基础官方调研已完成，唯一判定为 `botzone_manual_no_tribute_phase0_blocked`。三份固定版 Wiki 已封板，但 claim 实体 ID 约束、多配子裁判规则、无贡手动桌请求序列/先手和目标账号权限仍缺官方证据。下一步 Step L0-A2 只接受并审计用户辅助取得的官方裁判源码、官方 fixture 与脱敏账号可用性证据；不得进入 L1-A1。详细设计见 `docs/BOTZONE_INTEGRATION_PLAN.md`。

目标：

- 由本机连接器通过 Botzone 官方本地 AI 长轮询接口参加 GuanDan 测试对局；
- adapter 负责平台协议、牌 ID、阶段和 action/claim 转换；
- RuleBasedAI 仍只读取转换后的 observation/legal actions 并返回合法 `action_id`；
- 用真实平台 smoke 和后续座位平衡小批量对局观察本地 AI 的实际对抗能力。

阶段：

1. Phase 0：当前 blocked；通过 L0-A2 补齐手动建桌无贡协议、裁判语义、账号权限和差异清单；runmatch initdata 可作为后续自动化未知项；
2. Phase 1：纯数据模型、108 牌 ID codec 和阶段协议单测；
3. Phase 2：可注入 transport 的 connector、session persistence 与 mock Botzone；
4. Phase 3：无贡 `deal + play` adapter 接入 RuleBasedAI；`tribute/return` 只识别并 fail-closed；
5. Phase 4：经用户明确授权、手动设置“需要进贡=否”的小规模真实 Botzone smoke；
6. Phase 5：可选 DeepSeek，默认关闭且不属于基础验收。

关键门槛：本项目不实现贡还，只支持建桌时明确选择“需要进贡=否”的对局。真实 smoke 前仍须封板配子 claim 编码和 play 规则差异；若收到 `tribute/return`，必须以 unsupported stage 安全失败，不能以空响应、pass 或随意牌绕过。`runmatch` 要等官方无贡 `X-Initdata` 表示确认后再启用。

## 6. 质量指标

### 正确性

- 非法动作率为 0；
- 主回归和全部 `unittest` 通过；
- 公开牌统计无负数、无重复扣减；
- 标为 `confirmed` 的推断精确率必须为 100%。

### 推断质量

- 外部剩余不超过 20 张时，真实点数进入对应玩家 Top-3 候选的比例作为主指标；
- 外部剩余不超过 12 张时，记录逐玩家点数准确率；
- 同时记录覆盖率、置信度和错误确认数；
- 不用单次对局主观判断代替数据。

### 策略质量

- 固定种子、双方策略交换座位；
- 记录胜 / 负 / 平、平均完赛名次、关键牌消耗；
- 公式开局、RAG、信念状态分别做消融对照；
- DeepSeek 评测记录调用次数、失败率和平均上下文长度。

## 7. 非目标

当前主引擎仍不实现：

- 多局升级赛与 Botzone 贡还模式；integration 仅实现无贡 profile，未经新任务确认不得把贡还写入主引擎；
- 强化学习、自博弈训练；
- MCTS 和蒙特卡洛搜索；
- 把隐藏牌推断写入规则引擎；
- 把 RAG 或模型输出当成规则真值。

## 8. 实施顺序

每一步遵循：

1. 更新规格和验收口径；
2. 添加失败测试；
3. 做最小实现；
4. 运行相关测试和全部回归；
5. 记录指标，不以提示词变长作为能力提升依据。
