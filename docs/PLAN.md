# GuanDan 优化计划

当前进度与风险见 `docs/PROJECT_STATUS.md`。下一步实施任务见 `docs/NEXT_PROMPT.md`。

## 1. 当前结论

截至 2026-07-31，项目已经完成：

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

当前优化目标从“能运行”转为“阶段判断一致、推断可审计、策略质量可测”。

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

状态：J-A 至 J-D1c3b2 已完成；多策略扩容正式校准判定 `policy_diverse_calibration_verified`。下一步实现 J-D1c3c1 runtime confidence 数据契约。

目标：

- 精确维护两副牌级别的未见牌池，保留点数和花色；
- 按玩家记录已出牌、pass 次数和剩余牌数；
- 输出逐玩家 `possible / likely / confirmed` 信息；
- 所有推断带来源和置信度；
- 只有逻辑唯一时才能标记 `confirmed`。

当前阶段已包含确定性公开事实、硬约束、完整残局枚举和 token/rank 级精确物理权重；排序已恢复 hard-only neutral baseline。仍不输出经过校准的概率或置信度，也不做 MCTS 或蒙特卡洛搜索。

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
23. J-D1c3c1：建立 critical-endgame-only、fail-closed 的 runtime confidence 数据契约，下一步；
24. J-D1c3c2：通过显式开关接入候选消费端并做等轨迹消融与策略收益验收；
25. 策略接入：仅在 J-D1c3c2 独立验收后开始。

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

### Step K：中局策略路由与残局决策

目标：

- 中局明确区分 `run_out`、`control`、`support_teammate`、`block_opponent`；
- 策略路由器先选择策略意图，RAG 再为意图检索经验；
- 近似明牌残局使用逐玩家信念状态；
- 危险对手、队友跑牌和牌权转移进入结构化决策。

验收：

- 路由结果对固定 observation 可复现；
- RAG 不单独决定动作；
- 模型只能从传入候选动作中选择；
- 固定种子和轮换座位 A/B 评测可重复。

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

当前仍不实现：

- 多局升级赛和贡还规则；
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
