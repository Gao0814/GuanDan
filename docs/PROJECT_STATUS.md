# 项目状态看板

更新时间：2026-08-01

## 1. 当前基线

- 当前实现检查点：`bc689a37f462672033d754cce7060897d70c7612 J-D1c3c2c1 confidence prompt coverage benchmark`
- 验收运行 HEAD：`6b62156a98cfb97dd11e30df5f95a62dba99accd`
- 当前工作状态：Step J-D1c3c2c3a 已完成但两个 harness/test 文件尚未提交；唯一开发判定 `confidence_action_ablation_harness_verified`
- 测试基线：`python -m unittest discover -q`
- 实际验证结果：351 项测试全部通过
- 当前规则范围：单局掼蛋核心规则
- 当前 AI 边界：只读取公开 observation 和合法动作，只返回合法 `action_id`

## 2. 总体进度

### 可运行主链

完成度：100%

已完成：

- 单局规则引擎；
- 合法动作显式展开；
- 4 AI 自动对局；
- 中文调试回放；
- DeepSeek 接入和失败降级；
- 仅 pass、一次出完等本地快捷路径。

### 当前优化愿景

完成度：约 98%

目标愿景包括：

1. 前期公式化开局；
2. 中期动态策略；
3. 逐玩家记牌和猜牌；
4. RAG 根据实时局面检索规则和经验；
5. 残局达到可量化的近似明牌。

当前已完成统一阶段、公开牌面事实、硬归属域、受控残局分配、四策略正式校准、fail-closed confidence、默认关闭的 prompt 接线、正式 prompt coverage，以及无网络成对动作消融载体。J-D1c3c2c3a 已证明固定采样、off/on 唯一差异、AB/BA 顺序、provider fail-closed 分类和聚合守恒可用。下一步在明确网络与最多 48 次请求授权后，运行小规模真实 DeepSeek 响应安全试验；默认策略继续关闭。

## 3. 分模块状态

| 模块 | 状态 | 当前能力 | 主要缺口 |
|---|---|---|---|
| 规则引擎 | 已完成 | 规则、动作、状态、终局稳定 | 暂无本轮优化需求 |
| 公式化开局 | MVP 完成 | 满足条件时本地选择并跳过 API，使用统一阶段 | 缺少 A/B 数据 |
| 统一阶段 | 已完成 | 开局、剪枝、RAG、提示词共用公开阶段上下文 | 尚未接入 Step J 信念状态或 Step K 策略路由 |
| 手牌评分 | 基础完成 | 输出结构、控制力和潜力分 | 权重未校准 |
| 动作剪枝 | 基础完成 | 区分首出和跟牌，保留关键动作，使用统一阶段 | 缺少策略收益评测 |
| 基础记牌 | 基础完成 | `CardTracker` 按点数统计已出和外部剩余 | 仍是旧链路，不提供逐玩家候选 |
| 公开牌面事实 | Step J-A 完成 | 精确 108 张牌池、token/点数扣牌、逐玩家公开历史与诊断 | 尚未接入决策主链 |
| 硬归属约束 | Step J-B1 完成 | token/点数可能归属域、容量校验、唯一候选确认 | 多玩家实时域通常仍较宽 |
| 残局精确分配 | Step J-D1c3c2c3a 开发通过 | 正式 prompt coverage 和无网络成对动作载体已验证 | 尚无真实模型响应安全、动作质量或胜率结论 |
| 信念离线评测 | Step J-C1 完成 | 域召回、确认精度/覆盖、边界违例、域缩减指标 | 尚无正式独立种子结论与策略分布验证 |
| 公开行为事件 | Step J-C2a 完成 | lead/follow/pass 响应链、声明/carrier 差异、逐玩家事实画像 | 目前只有敌方 single pass 进入软评分 |
| rank 排序 | Step J-C3d1/J-C3d2 完成 | hard-only neutral；四策略 12 桶 baseline/soft 完全相同 | 暂无经过验收的新软证据 |
| rank 排序评测 | Step J-C2b2 完成 | 真值隔离、并列安全 Top-K、零软分基线和单样本 delta | 尚未支持策略分布分层结论 |
| rank 离线基准 | Step J-C3a/J-C3b 完成 | 固定种子采集、微聚合、阶段桶、可重复正式验收 | RuleBasedAI 不覆盖有牌可压时的战略性 pass |
| pass 策略分布基准 | Step J-C3c1/J-C3c2 完成 | 0/25/50/100% 确定性主动 pass、独立 seed 双运行验收 | 已拒绝无条件 pass 信号；不代表其他软信号无效 |
| RAG | Step H 完成 | 标签化规则库/经验库，场景检索 | 标签维度粗，未接策略意图 |
| 中期策略 | 未完成 | 主要依赖模型和经验提示 | 没有结构化策略路由 |
| 残局推断 | 未完成 | 外部剩余少时显示完整点数 | 尚未接近逐玩家明牌 |
| 策略评测 | 部分完成 | 已有信念校准、策略分布和 prompt coverage 正式指标 | 没有真实模型动作质量与胜率指标 |

## 4. 已确认问题

### 已解决：阶段判断不统一（Step I）

已完成：

- `agents/game_phase.py` 仅从公开 observation 输出不可变阶段上下文；
- 公式化开局、DeepSeek 剪枝、RAG 和 DeepSeek 提示词使用同一阶段结果；
- `near_open_endgame` 与 `critical_endgame` 在剪枝和 RAG 中继承 `endgame` 行为；
- history 与 `step_no` 不一致时按较晚进度判定，避免误回退到 opening。

验证：新增阶段边界与消费者一致性测试；全量 `unittest` 126 项通过。

### 已解决：公开牌面事实不可审计（Step J-A）

已完成：

- `agents/card_belief.py` 从两副牌 108 张精确牌池开始计算；
- 只消费公开 observation 与可选 `GamePhaseContext`；
- 扣除自己手牌和历史真实 `carrier_cards`，旧历史才回退 `declared_cards`；
- 同时维护 token 级、点数级未见牌以及 `token_pool_exact`；
- 记录逐玩家关系、公开剩余牌数、完赛状态、真实已出牌和 pass 次数；
- 异常历史、未知 token、重复扣牌和外部容量不一致均输出诊断；
- J-A 不推断隐藏牌，`confirmed_cards`、`likely_ranks` 为空，`confidence=0`。

验证：定向 31 项、全量 141 项测试通过；未修改 `engine/`、`CardTracker`、RAG 或 DeepSeek 提示词。

### 已解决：基础硬归属域缺失（Step J-B1）

已完成：

- `agents/card_constraints.py` 只消费 J-A 的 `CardBeliefState`；
- 自己、已完赛玩家、零容量和异常容量玩家不进入外部候选域；
- 精确牌池建立 token/点数两层归属域，不精确牌池只保留点数域；
- 容量不一致、无候选、空归属域和 token/点数总量冲突均有诊断；
- 多候选状态不确认；只有精确、一致且唯一候选承载全部未见牌时才确认；
- pass 不改变硬归属域。

验证：定向 43 项、全量 153 项测试通过；未修改 `engine/`、J-A、`CardTracker`、RAG、DeepSeek 或 CLI。

### 已解决：有限残局完整分配缺失（Step J-B2）

已完成：

- `agents/card_allocations.py` 只消费 J-A/J-B1 的不可变输出；
- 默认仅枚举不超过 12 张的精确、一致输入；
- 相同 token 副本按整数份额分配，不重复计算副本排列；
- 完整搜索聚合解数量和逐玩家 token 最小/最大持有数；
- `confirmed_cards` 只来自所有完整解共同保证的最小副本数；
- 节点或解数量截断时保留 J-B1 原始域并禁止确认；
- 无解、不精确、容量冲突和域异常均有明确状态与诊断。

验证：定向 61 项、全量 171 项测试通过；未修改 `engine/`、J-A/J-B1 契约、RAG、DeepSeek、CLI 或主决策链。

### 已解决：猜牌质量无离线基线（Step J-C1）

已完成：

- `evaluation/belief_metrics.py` 仅接受离线调用方显式传入的真实手牌；
- 严格校验真实玩家集合、公开容量和未见 token multiset；
- 评估 token 域召回、确认精确率/覆盖率、J-B2 边界违例和 owner edge 缩减；
- 不完整 J-B2 回退 J-B1，不使用部分搜索上下界；
- 基础输入无效时返回零化报告，不做部分评分；
- 报告只含聚合指标，不包含真实手牌或 token 明细；
- `agents/`、CLI 和 RAG 不导入 `evaluation`。

验证：定向 78 项、全量 188 项测试通过。

### 已解决：软信号缺少可审计事件层（Step J-C2a）

已完成：

- `agents/card_signals.py` 只消费公开 history 和 J-A 事实；
- 按原始 action index 重建 lead、follow、pass 及响应目标；
- pass 不替换桌面动作，follow 会替换；
- 新 round、回退 round 和无效 round 不复用错误上下文；
- 声明牌、真实 carrier 和二者点数差异分别保留；
- 高价值牌释放只按真实 carrier 统计；
- 逐玩家聚合 lead/follow/pass、牌型和高价值牌释放；
- 与 J-A pass/played_cards 不一致时只诊断，不修改事实；
- 不输出所有权、分数、概率、置信度或隐藏牌结论。

验证：定向 92 项、全量 202 项测试通过。

### 已解决：软信号没有候选排序载体（Step J-C2b1）

已完成：

- `agents/card_ranker.py` 从 J-B1 或完整 J-B2 投影逐玩家 rank 候选；
- 同 rank 多 token 自动合并；
- confirmed rank 只来自硬来源，固定优先且不受软负分；
- 唯一软信号是对敌方有效 single 选择 pass；
- 只对严格更高的 possible rank 扣分；
- 每项扣分带公开事件索引、响应索引、领先 rank 和实际 delta；
- 负分有累计下限，到下限后不生成零 delta 证据；
- tier 只由 hard status 和 soft score 决定，同分不因稳定排序拆开；
- 不修改 owner 域或 confirmed，不输出概率和置信度。

验证：定向 107 项、全量 217 项测试通过。

### 已解决：软排序缺少并列安全的单样本消融（Step J-C2b2）

已完成：

- `evaluation/ranking_metrics.py` 只接受离线调用方显式传入的真实外部手牌；
- 从同一 soft ranking 派生候选和硬状态完全一致的零软分 baseline；
- score tier 跨越 K 边界时整体纳入 Top-1/Top-3；
- 统计召回、精确率、实际选择规模及最坏位置 MRR；
- 所有 delta 按 `soft - baseline` 计算；
- 输入无效时 fail closed，报告不包含真实 token、rank 或手牌明细。

验证：定向 120 项、全量 230 项测试通过；`git diff --check` 通过。

### 已解决：缺少可重复的多种子聚合器（Step J-C3a）

已完成：

- `evaluation/rank_benchmark.py` 使用固定 seed 和现有规则 AI 推进合法动作；
- 只采集 `near_open_endgame` 与 `critical_endgame`；
- 按 J-A 至 J-C2b2 顺序运行公开推断和离线真值评测；
- 真实手牌只在 `evaluation/` 中提取和短暂传递；
- baseline/soft 按原始计数微聚合，MRR 按真实 rank 数加权；
- overall 由两个互斥阶段桶原始报告合并；
- 无效、样本上限、步数上限和重复样本均有计数和规范化诊断；
- 报告不可变、可 JSON 序列化且不保留 seed 或真值明细。

验证：定向 130 项、全量 240 项测试通过；`git diff --check` 通过。

开发试跑：seed `0..19` 仅用于容量评估，不进入正式结论。20 局全部完成，共 866 个目标阶段 observation；默认每局 24 样本只评估 480 个，跳过 386 个且每局均触发上限。因此正式基准必须提高样本上限并要求零跳过。

### 已解决：RuleBasedAI 轨迹上缺少正式多样本结论（Step J-C3b）

正式参数：

- HEAD `39bd0247b9459999cdeb489703ff288eed7df791`；
- seed `1000..1199`，200 局，级牌 `2`；
- `max_steps=5000`、`max_samples_per_game=512`；
- 外部牌上限 12、节点上限 1,000,000、解上限 100,000。

结果：

- 两次运行报告完全相同，SHA-256 均为 `97c8057e62ec12d0951c362e5db42a02699e9ab9897db6205a4ba71b01b25855`；
- 200/200 局完成，8719/8719 样本有效，无 invalid、skip 或 diagnostics；
- near-open 3260 样本，critical 5459 样本；
- 三个桶 candidate recall 均保持 1.0，Top-1/Top-3 recall delta 均为 0；
- overall Top-1 precision `+0.007357`，Top-3 precision `+0.006385`；
- overall Top-1 平均规模 `-0.118396`，Top-3 平均规模 `-0.102980`；
- overall worst-case MRR `+0.003233`；
- near-open 与 critical 的 precision、MRR 均为正增量。

唯一判定：`retain_for_policy_diverse_validation`。

### P1：战略性 pass 分布尚未验证

RuleBasedAI 只在不存在非 pass 合法动作时 pass，因此 J-C3b 测到的主要是被迫 pass。下一步必须构造公开信息驱动、确定性的战略性 pass 轨迹，并验证：

- 有合法压制动作但主动 pass 时，当前负向 rank 信号是否仍保持召回护栏；
- 不同战略性 pass 比例下 precision、选择规模和 MRR 的变化；
- forced-only 与策略 pass 轨迹是否使用独立、可重复的同 seed 对照；
- evaluation-only 策略不得访问隐藏牌或进入 runtime 主链。

### 已解决：缺少战略性 pass 策略分布载体（Step J-C3c1）

已完成：

- `run_rank_benchmark()` 增加向后兼容的可选 `agent_factory(seed, player_id)`；
- `evaluation/pass_policy_benchmark.py` 只从公开 observation 和 legal actions 判断机会；
- 机会严格要求敌方 single 且 pass/非 pass 同时合法；
- rate 0 完全回退规则 AI，rate 100 在所有合格机会主动 pass；
- rate 25/50 使用 `(37 * step_no + 17 * player_id + 11) % 100` 稳定门控；
- gate 不读取 seed、隐藏牌、随机数、时间或 Python hash；
- 机会、主动 pass 和各策略 rank 报告独立聚合；
- 多策略使用全新 game、agent 和计数器；
- 报告不包含 seed、轨迹、observation 或真值明细。

验证：定向 140 项、全量 250 项测试通过；`git diff --check` 通过。

开发试跑 seed `20..29` 只用于锁定 J-C3c2 容量和门槛，不作为正式结论：

- 4 个策略均完成 10 局，无 invalid、skip 或 diagnostics；
- forced-only Top-3 recall delta 为 0；
- strategic-pass 25/50/100 的 overall Top-3 recall delta 分别约为 `-0.126899`、`-0.146730`、`-0.179860`；
- 三者 MRR 虽为正增量，但残局真实 rank 召回明显下降，不能用 MRR 抵消；
- 正式 J-C3c2 必须将 Top-K recall 设为首要护栏。

### 已解决：无条件 pass 信号是否可泛化（Step J-C3c2）

正式参数：

- HEAD `f1bfabd7ba136553c12ed61824b79f8e4b9ef446`；
- seed `2000..2099`，0/25/50/100% 四个策略各 100 局；
- 两次完整报告相同，SHA-256 均为 `83d3e96dbbb2e8765e5e906b24f6953c093d131af575e9c54b99aaa9198317ce`；
- 四个策略全部完成，无 invalid、skip、diagnostics 或硬候选覆盖变化。

关键结果：

- forced-only 再次通过：Top-1/Top-3 recall 无回退，overall precision 与 MRR 为正增量；
- 25% 战略 pass 的 overall Top-1 recall delta 为 `-0.170742`；
- 25% 战略 pass 的 overall Top-3 recall delta 为 `-0.092955`；
- near-open Top-3 recall delta 为 `-0.088401`；
- critical Top-3 recall delta 为 `-0.099062`；
- 50%/100% 战略 pass 的召回退化进一步扩大；
- MRR 上升来自排序更集中，不能抵消真实 rank 被错误降级。

唯一判定：`reject_unconditioned_pass_signal`。

含义：

- 当前 `opponent_single_pass` 不得进入置信度校准或 runtime；
- 不能仅凭公开 pass 判断对方缺少更高 rank；
- RuleBasedAI 轨迹上的小幅收益是策略分布偏差，不构成泛化证据；
- 硬候选、公开事件层、离线评测和策略压力测试仍然有效。

### 实施要求：撤销已拒绝的默认软扣分（J-C3d1）

J-C3d1 按以下要求恢复安全基线：

- `build_card_rankings()` 只投影 J-B1/J-B2 的 hard candidates；
- 所有 possible candidate 默认 `soft_score=0`、`evidence=()`；
- confirmed/possible tier 和稳定 rank 顺序保留；
- 不再解析 pass 事件生成 `opponent_single_pass` 负分；
- 保留通用 evidence/metric 数据结构，供未来经过验收的新信号使用；
- 不以 feature flag 或隐藏参数保留被拒绝逻辑。

### 已解决：撤销已拒绝的默认软扣分（Step J-C3d1）

已完成：

- 从 `build_card_rankings()` 签名删除两个 pass penalty 参数；
- 删除 pass event、single response、队伍和 rank strength 评分路径；
- 删除 `opponent_single_pass` evidence 及专用 diagnostics；
- hard candidates、J-B2 收窄、confirmed count 和 hard source 保持不变；
- 所有 possible candidate 固定 `soft_score=0`、`evidence=()`；
- 有 confirmed 时 confirmed/possible 分为 tier 1/2，无 confirmed 时 possible 全部 tier 1；
- 通用 `RankScoreEvidence` 和 ranking metrics 继续支持人工 soft ranking；
- 旧 penalty keyword 由 Python 签名显式抛出 `TypeError`。

验证：定向 140 项、全量 250 项测试通过；`git diff --check` 通过。

开发试跑 seed `30..34` 只用于确认 J-C3d2 口径：四种 pass 策略均无 invalid/skip，overall 的 candidate、Top-1、Top-3、选择规模和 MRR delta 全部严格为 0。

### 实施要求：neutral baseline 正式封板（J-C3d2）

J-C3d2 使用独立 seed `3000..3049`，要求四种策略：

- 两次完整报告和 canonical JSON hash 一致；
- 每个策略 50 局全部完成，无 invalid、skip 或 diagnostics；
- overall、near-open、critical 的 baseline snapshot 与 neutral snapshot 完全相同；
- 所有 delta 严格为 0；
- 通过后将 J-C3 分支封板，转入 J-D1 残局分配概率设计。

### 已解决：neutral baseline 正式封板（Step J-C3d2）

正式参数与结果：

- HEAD `3ee050e1ff80615038348b11e7ba185ded463ca2`；
- seed `3000..3049`，四种 pass 策略各 50 局；
- 两次完整报告相同，SHA-256 均为 `83d947387910c266034473e6eba96223fa744d4bf7d815631166275f4b247034`；
- 每种策略 50/50 局完成，无 incomplete、invalid、skip 或 diagnostics；
- forced/25/50/100 共 8759 个有效样本；
- near-open/critical 每个策略均超过预注册的 500 样本门槛；
- 12 个 bucket 的 baseline 与 neutral snapshot 逐字段完全相等；
- candidate recall 均为 1.0；
- candidate、Top-1/Top-3、选择规模和 MRR delta 全部精确为 0.0。

唯一判定：`neutral_baseline_verified`。

J-C 结论：

- 被拒绝的 pass 信号已安全撤销；
- 公开 pass 事件仍可审计，但不产生持牌结论；
- hard candidates 与完整 J-B2 仍是当前唯一可信推断来源；
- 没有新猜牌能力、概率、置信度、策略集成或胜率提升。

### 已解决：可行分配矩阵获得精确物理权重（Step J-D1a）

J-B2 当前将相同 token 的副本按整数份额分配，每个 count matrix 计一个
`feasible_assignment_count`。实际双副本物理牌可区分，因此不同 count matrix
对应的物理分配数量可能不同。J-D1a 已完成精确整数权重统计：

- count matrix 权重为每种 token 的多项式系数乘积；
- 所有统计只来自完整搜索；
- 截断、跳过、无解或输入无效时不输出部分权重；
- 先输出整数分母、持有权重和副本数加权和，不输出浮点概率；
- 不使用 pass、队伍策略或 ground truth 调整权重。

实现结果：

- 每个完整 count matrix 的权重为 `product_t(c_t! / product_p(k_(p,t)!))`；
- `physical_assignment_count` 是所有完整 matrix 权重之和；
- 逐玩家记录每个 token 的持有分子和副本数加权分子；
- token 副本守恒满足所有玩家副本分子之和等于 `token_count * physical_assignment_count`；
- `truncated`、`invalid_input`、`skipped_too_many_cards` 和 `no_feasible_allocation` 不暴露部分权重；
- 旧的 matrix 计数、min/max、confirmed 和 possible-owner 语义保持不变。

验证：定向 132 项、全量 256 项测试通过；J-D1a 仍不输出概率、rank 边际、置信度或策略结论。

### 已解决：rank 持有边际不能由 token 持有分子直接相加（Step J-D1b）

同一 rank 可以包含多个花色 token，同一物理分配中一个玩家也可能同时持有这些 token。因此：

- rank 副本数加权分子可以由同 rank token 的副本数分子求和；
- rank“至少持有一张”的分子是事件并集，不能对 token 持有分子直接求和；
- J-D1b 已在每个完整 matrix 的记录点按玩家聚合 rank 副本数，并对 rank 持有事件只计一次；
- 普通 token 使用完整 rank 前缀，`10S` 正确映射为 `10`，joker 保持 `SJ` / `BJ`；
- token 与公开 rank 池不一致或 token 非法时，在搜索前返回 `invalid_input`；
- 完整且有解时输出 `holding_assignment_count_by_rank` 与 `copy_assignment_count_by_rank`；
- 截断、无解、跳过和无效输入不输出部分 rank 边际；
- 定向 139 项、全量 263 项测试通过。

### P1：组合边际不是已校准的经验置信度

J-D1b 的整数分子除以 `physical_assignment_count`，只表示“满足当前公开硬约束的物理分配等权”模型下的组合边际。当前还不能声称：

- 该模型已在真实或规则 AI 轨迹上校准；
- 0.8 的组合边际对应约 80% 的经验命中率；
- rank 边际可直接改变动作剪枝、提示词或策略选择；
- 边际之间相互独立，或可通过逐 rank 概率相乘得到整手牌概率。

J-D1c1 已在 `evaluation/` 建立单样本、有理数可审计的评分充分统计量：

- 所有活跃外部玩家 × 正数公开 rank pair 都进入评分；
- presence Brier、rank copy 平方误差和十档预测和使用 `Fraction` 精确累计；
- 确定性错误单独计数，不掩盖为无效输入；
- 非完整或不一致输入返回完全零化报告；
- ground truth 只由离线调用方显式传入，报告不保留真值明细；
- runtime 目录不导入 `evaluation/marginal_metrics.py`；
- 定向 152 项、全量 276 项测试通过。

J-D1c2a 已完成跨样本精确微聚合：

- 只消费内存中的 J-D1c1 报告，不读取游戏、真值或 seed；
- Brier、copy 误差与桶内预测和使用 `Fraction` 跨样本通分；
- Brier mean、copy MSE、正例率和确定性错误率按总 rank pair 数重算；
- ECE 使用 pair 加权绝对 gap，MCE 取非空桶最大 gap；
- invalid 样本只进入计数与规范化 diagnostics；
- malformed 手工报告显式抛出 `ValueError`；
- 输出不可变、顺序无关、JSON 友好且不保留样本明细；
- 定向 166 项、全量 290 项测试通过。

J-D1c2b 已完成 fixed-seed collector 与开发容量验证：

- 共享 `extract_ground_truth_hands()` 是 evaluation 中唯一直接读取 `game._state` 的位置；
- collector 只采集 `critical_endgame`，按 `external_0_4`、`external_5_8`、`external_9_12` 分桶；
- seed `40..59` 双运行报告与 canonical JSON SHA-256 完全一致；
- SHA-256 为 `e99c03b9ab1b7fe568741073c94e1e05c3c53047e26e980038a7cf454d44741b`；
- 20/20 局完成，522/522 样本有效，无 invalid、skip 或 diagnostics；
- 三个桶分别为 171、177、174 个样本，均有覆盖；
- overall Brier mean 约 `0.188806`，Brier skill 相对经验正例率常数基线约 `0.239582`；
- overall ECE 约 `0.021472`，MCE 约 `0.066209`，确定性错误率为 0；
- 独立复核运行同样得到相同 hash 和计数；
- 定向 179 项、全量 303 项测试通过。

唯一开发判定：`development_capacity_verified`。该判定只允许预注册正式语料，不构成校准或 runtime 准入。

### 已解决：默认规则 AI 语料上的组合边际正式校准（Step J-D1c2c）

正式参数与结果：

- HEAD `241cbb95492d30d1cfbe5e8436791e42d12974bf`；
- seed `5000..5099`，默认 RuleBasedAI，100 局完整运行两次；
- 两次耗时约 180.9s / 179.7s，报告和 canonical JSON 完全相同；
- SHA-256 均为 `c4a91d81bed216e919189fe4fdddf76c76ee8e35eb28f5fcae21ebc9e401e190`；
- 100/100 局完成，2727/2727 样本有效，无 invalid、skip 或 diagnostics；
- 三个外部牌数桶分别有 902、901、924 个有效样本；
- overall/三桶 rank pair 共 36,804；
- overall Brier skill 约 `0.236809`、ECE 约 `0.021901`、supported MCE 约 `0.063909`；
- 三桶 Brier skill 均至少约 `0.221291`，ECE 均不超过约 `0.024514`；
- overall 与三个桶 certainty error 均为 0；
- 16 项数据完整性和所有预注册校准护栏全部通过。

唯一判定：`retain_for_policy_diverse_calibration`。

### P1：有效正式校准仍只覆盖单一策略轨迹分布

当前正式 corpus 来自默认 RuleBasedAI。虽然组合边际不使用 pass 软信号，但不同策略会改变到达 critical 局面的牌池、容量和历史分布。因此当前结论不能外推到：

- 主动战略 pass 轨迹；
- DeepSeek 或真实玩家策略；
- runtime confidence；
- 动作质量或胜率。

J-D1c3a 已建立隔离的多策略报告；J-D1c3b 也已执行，但因单一范围支持度不足而无效。因此可引用的正式校准结论仍只覆盖默认 RuleBasedAI，必须等待 J-D1c3b2 的全新独立语料。

### 已解决：策略分布多样性载体缺失（Step J-D1c3a）

实现与开发结果：

- 新增 `PolicyVariantMarginalReport` 与 `MarginalPolicyCorpusReport`；
- forced-only、25%、50%、100% 每个 rate 使用独立 agent、game、counter 和 corpus；
- forced-only corpus 与默认 marginal corpus 完全一致；
- seed `60..69` 四策略各 10 局，完整运行两次；
- 两次耗时约 62.6s / 62.3s，报告与 canonical JSON 完全相同；
- SHA-256 均为 `dc5bfa083d686e57cb711e9892738713904da96178988931deda7318427a58a3`；
- 四策略均 10/10 局完成，无 invalid、skip 或 diagnostics，三个外部牌数桶均非空；
- opportunity/active pass 分别为 `117/0`、`121/48`、`127/63`、`133/133`；
- 实际主动 pass 比例满足 forced < 25% < 50% < 100%；
- 所有策略和桶 certainty error 均为 0；
- 独立复核运行得到相同 hash、行为计数和样本计数；
- 定向 187 项、全量 311 项测试通过。

唯一开发判定：`policy_diversity_capacity_verified`。该判定只允许预注册正式多策略校准。

### 已解决：多策略正式校准支持度不足（Step J-D1c3b/J-D1c3b2）

正式结果：

- HEAD `2fc902dee07d59056a4c84770c5222f2947affe2`，运行前后工作区干净；
- seed `7000..7049`，四策略各 50 局，完整运行两次；
- 两次耗时约 322.8s / 321.9s，报告与 canonical JSON 完全相同；
- SHA-256 均为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 定向 187 项、全量 311 项测试通过；
- 四策略均 50/50 局完成，invalid、skip、diagnostics 全为 0；
- 每个策略的三个 external bucket 均至少 350 个有效样本；
- 策略行为边界和实际主动 pass 比例递增关系通过；
- 其余 15 个策略/范围的 certainty、ECE、Brier skill、supported MCE 和支持度要求通过；
- `strategic_pass_100 / external_0_4` 有 436 个有效样本、1201 个 rank pair，但十档 prediction count 为 `[0, 0, 60, 25, 0, 40, 26, 36, 2, 1012]`；
- 该范围只有 bin 9 达到 external bucket 的 count>=100 支持阈值，少于预注册的至少两个支持 bin。

J-D1c3b 唯一判定：`benchmark_invalid`。失败属于验收数据支持度不足，不可解释为模型数值失败，也不可被其余范围抵消。

J-D1c3b2 保持模型、十档分桶和全部护栏不变，使用全新 seed 完成扩容复验：

- HEAD `b2491a810f81eb6dc20f1732efd89b6705f56458`，运行前后工作区干净；
- seed `8000..8119`，四策略各 120 局并完整双运行；
- 两次耗时约 790.2s / 785.0s，报告、`to_dict()` 与 canonical JSON 完全相同；
- SHA-256 均为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 定向 187 项、全量 311 项测试通过；
- 四策略均 120/120 局完成，invalid、skip、diagnostics 全为 0；
- 有效样本分别为 3260、3399、3531、2997，三个 external bucket 均超过 980；
- 主动 pass 比例为 0、约 0.357、约 0.546、1.0，严格递增；
- 16 个策略/范围均至少有两个支持 bin，最少为 4 个；
- 16 个范围 certainty error 均为 0；
- overall ECE 最大约 0.020070，external ECE 最大约 0.023060；
- overall Brier skill 最小约 0.232614，external skill 最小约 0.214565；
- overall supported MCE 最大约 0.066710，external supported MCE 最大约 0.093299。

唯一判定：`policy_diverse_calibration_verified`。该结论只允许设计 runtime confidence 契约，不授权接入策略主链，也不证明动作质量或胜率提升。

### 已解决：runtime confidence 契约 fail-closed 硬化（Step J-D1c3c1/J-D1c3c1a）

J-D1c3c1 已新增 `agents/card_confidence.py` 与 `tests/test_card_confidence.py`：

- `RankMarginalConfidence`、`PlayerCardConfidence`、`CardConfidenceState` 均为 frozen/slots；
- builder 只消费 J-A/J-B1/J-D1b，不读取 observation、history、ground truth 或 engine state；
- available 限于 `critical_endgame`、1..12 张外部未知牌和完整精确 allocation；
- presence/copy 使用整数分子/分母；失败返回零分母、空玩家的 unavailable；
- 定向 76 项、全量 318 项和 `git diff --check` 通过；
- DeepSeek、RAG、CLI、engine 均未引用新模块。

封板前审阅发现：

- `bool(getattr(...))` 会让 `1`、非空字符串等 truthy 非布尔值通过 exact/consistent/search-complete 标志；
- constraint 玩家遍历会静默忽略不属于公开外部玩家集合的额外玩家；
- copy mapping 含字符串、`None` 等非法值时，后续直接 `sum()` 原始 mapping 可能抛出 `TypeError`，而不是返回 unavailable。

J-D1c3c1a 已完成：

- 四个 exact/consistent/search-complete 字段只接受实际 `True`；
- belief、constraints、allocation 正容量外部候选玩家集合严格一致；
- copy 分子完成类型与上界校验后写入 `validated_copies`，守恒不再读取 malformed 原始值；
- 新增 4 个布尔字段 × 2 类 truthy 值、额外/重复/未知/不可哈希玩家及 6 类 malformed copy 测试；
- 合法 available `to_dict()` snapshot 逐字段不变；
- 单文件 11 项、相关 80 项、全量 322 项测试通过；
- 边界扫描和 `git diff --check` 通过；现有决策路径仍未引用新模块。

### 已解决：runtime 受控装配与 shadow 审计（Step J-D1c3c2a）

J-D1c3c2a 已完成：

- 新增公开 pipeline，复用调用方统一阶段，critical 链路各调用一次；
- 非 critical 在 J-A 和 allocation 前立即 unavailable；
- 参数非法显式报错，内部异常规范为 `pipeline_error`；
- `DeepSeekAIAgent.card_confidence_shadow_enabled` 默认 False，仅启用时 lazy import；
- `last_card_confidence` 每步重置，三个 local shortcut 不计算；
- shadow off/on 的模型参数、动作、fallback 和 decision source 已验证一致；
- 定向 40 项、相关 124 项、全量 331 项测试通过；
- DeepSeekClient、RAG、CLI、engine 均未消费 confidence。

### 已解决：confidence 有界 prompt 表示（Step J-D1c3c2b1）

J-D1c3c2b1 已完成独立序列化契约：

- 新增 frozen/slots `CardConfidencePromptPayload` 与纯 formatter；
- available 的 phase/source/scope、玩家、容量、rank、分母和分子全部再次复核；
- presence/expected-copy 使用 `gcd` 约分，只输出整数或 `n/d`；
- 玩家与 rank 全量稳定输出，不做 Top-K 或主观等级；
- 固定 2400 字符预算，超限或 malformed 整体 omitted；
- formatter 不读取 observation、history、truth、engine、evaluation、DeepSeek 或 RAG；
- 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项测试通过；
- 现有 agent/client/RAG/CLI/engine 仍未引用 formatter。

### 已解决：默认关闭的 prompt 消费接入（Step J-D1c3c2b2）

J-D1c3c2b2 已完成：

- 新增严格 bool prompt 开关，非法类型和 prompt-only 组合显式报错；
- 每步重置 state/payload 审计，三个 local shortcut 跳过 pipeline 与 formatter；
- ready 是唯一新增 `card_confidence_prompt` keyword 的路径；
- client 再次复核 payload 类型、source/scope、文本和预算；
- omitted、pipeline/formatter 异常不改变模型调用或 fallback；
- 新章节仅位于记牌信息与场景标签之间，payload 原文只出现一次；
- config、CLI、engine、RAG、evaluation 未引用 prompt 开关或 formatter；
- 定向 54 项、相关 48 项、全量 345 项测试通过。

### 已解决：prompt 覆盖与成本开发基准（Step J-D1c3c2c1）

J-D1c3c2c1 已建立 evaluation-only collector 并完成开发双运行：

- seed `80..89`，四策略各 10 局，完整运行两次；
- 两次耗时约 60.44s / 60.30s；
- 报告与 canonical JSON 完全一致，SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；
- 四策略均 10/10 局完成，无 invalid、duplicate、sample-limit、mismatch 或 diagnostics；
- forced/25/50/100 样本分别为 264 / 279 / 295 / 246；
- 四策略三个 external bucket 均有 78 至 114 个样本；
- 1084 个样本全部 confidence available、payload ready，omitted 与 budget omitted 均为 0；
- ready exact insertion 等于 ready 总数，所有 delta 为正；
- 每样本 prompt delta 精确等于 payload char count + 11；
- 定向 28 项、相关 77 项、全量 351 项测试通过；
- 未调用 DeepSeek 请求、网络、真值或 `game._state`。

唯一开发判定：`confidence_prompt_coverage_capacity_verified`。该结论只允许使用独立 seed 正式验收 prompt coverage，仍不允许动作收益或胜率结论。

### 已完成但无效：首次 prompt coverage 正式运行（Step J-D1c3c2c2）

J-D1c3c2c2 在检查点 `bc689a37f462672033d754cce7060897d70c7612` 上完成：

- seed `10000..10049`，四策略各 50 局，完整运行两次；
- 两次耗时 344.621s / 342.153s；
- report、`to_dict()` 和 canonical JSON 两次完全相等；
- SHA-256 两次均为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- 提交前后回归 28 / 77 / 351 项通过，`git diff --check` 通过；
- 运行前后工作区干净，边界扫描未发现网络、DeepSeek、ground truth 或 `game._state`；
- 已确认的 `strategic_pass_50` 片段为 50/50/0 局、1533 个有效 critical 样本、零 invalid/skip/diagnostics、主动 pass 313/577，overall 全部 ready 且无 mismatch；
- 工具层截断 stdout，未保留四策略 x overall/三桶的完整聚合与字符成本数据；按预注册约束未第三次运行、补采或改参数。

唯一判定：`benchmark_invalid`。失败原因是审计证据不完整，不是 coverage 数值门槛失败；任何局部片段均不得外推为正式通过。

### 已解决：可持久化 prompt coverage 恢复验收（Step J-D1c3c2c2a）

J-D1c3c2c2a 在不修改实现和门槛的前提下完成：

- 仓库外审计目录为 `C:\Users\86166\AppData\Local\Temp\guandan-confidence-prompt-jd1c3c2c2a-6b62156a98cf`；
- runner SHA-256 为 `61ac8e55fdc57e58ee09a6af80972f1dea67bcfddd413a0f02ecb29ce6b76202`；
- seed `11000..11049`，四策略各 50 局，完整运行两次；
- 两次耗时 321.921s / 321.047s；
- `run1.json` / `run2.json` 均为 9218 bytes，逐字节、JSON、canonical JSON 和策略 pair digest 完全一致；
- 两次 SHA-256 均为 `679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- recovered 审计摘要为 19833 bytes，SHA-256 为 `fc8e9f3d7aa016e4772350834039b4780eccf3d9330c5315eae77c9c8eac33d7`；
- 四策略均 50/50/0 局，eligible=evaluated=valid，invalid/skipped/diagnostics 均为 0；
- forced/25/50/100 分别采集 1380 / 1469 / 1510 / 1374 个样本；
- 各策略三个 external bucket 分别为 461/443/476、489/490/490、475/530/505、473/444/457，均不低于 350；
- 5733 个样本全部 available、ready、exact insertion，零 unavailable/omitted/budget omitted/pair mismatch；
- 16 个范围 payload 最大长度为 683，均不超过 2400；所有 delta sum/min/max 精确为 payload 对应值 + 每样本 11；
- 全程未调用 DeepSeek、网络、ground truth 或 `game._state`。

原始 `audit_summary.json` 将 canonical `sort_keys=True` 后的键顺序误当成策略调用顺序；只读恢复解析器按固定策略名和 rate 映射重新验证两份原始 JSON。原摘要保留，未修改 corpus 或重跑。后续审计器不得依赖 JSON mapping 的迭代顺序表达业务顺序。

唯一判定：`confidence_prompt_coverage_verified`。原 seed `10000..10049` 的 J-D1c3c2c2 仍保持 `benchmark_invalid`。

### 已解决：无网络成对动作消融载体（Step J-D1c3c2c3a）

J-D1c3c2c3a 只新增 `evaluation/confidence_action_ablation.py` 和对应测试：

- provider 必须显式注入，模块不创建 client、不读取配置或环境；
- 只采集 critical 的公开 observation/legal actions；
- 每策略和 external bucket 使用 SHA-256 固定优先级选择样本；
- only-pass、一次出完、confidence unavailable、payload omitted、prompt mismatch 均不会调用 provider；
- off/on kwargs 唯一差异为类型化 `card_confidence_prompt`；
- 每桶稳定交替 AB/BA，一侧异常不阻止另一侧；
- 异常、malformed、no-action、错误类型、outside legal/prompt 分层计数，不使用 fallback；
- 报告只保留聚合计数和 digest，不保留逐样本 observation、prompt、action ID 或 reasoning；
- 单文件 6 项、相关 76 项、全量 357 项通过，`git diff --check` 和禁止边界扫描通过。

开发双运行使用 seed `120..129`、四策略、每桶 4 个样本：

- 两次耗时 39.795s / 40.446s；
- report 与 `to_dict()` 完全相等，canonical SHA-256 为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 四策略均 10/10/0 局、零 diagnostics，每策略 12 pair、每桶 AB/BA 各 2；
- 每轮 off/on 各 48 次，96 次 provider 调用全部 valid；
- 假 provider 固定 off 选首候选、on 选末候选，因此每策略 12 个 changed 只证明接线，不代表真实模型效果。

唯一开发判定：`confidence_action_ablation_harness_verified`。

### P1：尚无真实 DeepSeek 响应安全结论

J-D1c3c2c3b 必须先提交 c3a 检查点，在用户明确授权当前 base URL/model 和最多 48 次无重试外部请求后，使用全新固定语料运行一次 24-pair live pilot。该步骤只验证响应可解析性、候选合法性和观察到的动作变化；单次 off/on 变化仍不能排除服务非确定性，也不能证明动作更优。

### P1：RAG 不能单独承担策略路由

RAG 当前能找到相关经验，但文本命中不等于稳定策略选择。

合理顺序应为：

```text
统一阶段
  -> 公开局面分析
  -> 本地策略路由
  -> RAG 检索对应策略证据
  -> 本地策略或 DeepSeek 选择合法动作
```

### P1：没有策略质量基准

351 项测试证明当前实现满足已有功能契约，但不能证明：

- 公式开局提高胜率；
- RAG 改善动作质量；
- 记牌提高残局判断；
- 提示词变长带来实际收益。

## 5. 当前里程碑

### Step H：公式化开局与场景化 RAG

状态：MVP 完成，待量化。

### Step I：统一阶段分类

状态：完成并已核验。

完成内容：公开阶段分类、消费者接入、残局阶段继承和回归测试。未扩展到 Step J 信念状态或 Step K 策略路由。

验证结果：

- 定向测试：71 项通过；
- 全量测试：126 项通过；
- 未修改 `engine/`。

### Step J：逐玩家牌面信念

状态：J-A 至 J-D1c3c2c3a 已完成；无网络 harness 开发通过。下一步为 J-D1c3c2c3b 小规模真实 DeepSeek 响应安全试验。

拆分为：

- Step J-A：精确公开牌池与逐玩家公开事实，已完成；
- Step J-B1：可能归属域与玩家容量约束，已完成；
- Step J-B2：受控残局可行分配与唯一性证明，已完成；
- Step J-C1：离线真值评测基线，已完成；
- Step J-C2a：公开行为事件提取，已完成；
- Step J-C2b1：最小软评分与 rank 候选排序，已完成；
- Step J-C2b2：并列分数友好的 Top-K 评测和零软分消融，已完成；
- Step J-C3a：固定种子离线样本采集与阶段聚合，已完成；
- Step J-C3b：预注册并运行 RuleBasedAI 独立种子正式基准，已完成；
- Step J-C3c1：实现 evaluation-only 战略性 pass 策略与多策略基准载体，已完成；
- Step J-C3c2：使用独立种子运行策略分布稳健性验收，已完成，判定拒绝；
- Step J-C3d1：撤销无条件 pass 软扣分，恢复零软分安全基线，已完成；
- Step J-C3d2：固定种子验证 neutral ranking 在所有 pass 策略下无召回差异，已完成；
- Step J-D1a：在完整 J-B2 搜索中聚合物理分配整数权重和 token 边际计数，已完成；
- Step J-D1b：在完整 matrix 记录点聚合精确 rank 持有/副本整数边际，已完成；
- Step J-D1c1：建立 evaluation-only 单样本概率评分与精确分桶充分统计量，已完成；
- Step J-D1c2a：精确微聚合多样本 Brier、copy MSE、ECE/MCE 与十档统计，已完成；
- Step J-D1c2b：实现固定 seed 采集器并运行开发容量试验，已完成，判定 `development_capacity_verified`；
- Step J-D1c2c：预注册并运行独立语料正式校准，已完成，判定 `retain_for_policy_diverse_calibration`；
- Step J-D1c3a：建立 forced/战略 pass 多策略 marginal corpus 载体并运行开发容量试验，已完成，判定 `policy_diversity_capacity_verified`；
- Step J-D1c3b：预注册并运行独立多策略正式校准，已完成，判定 `benchmark_invalid`；
- Step J-D1c3b2：保持模型、分桶和阈值不变，使用全新 seed 扩大样本后重新正式验收，已完成，判定 `policy_diverse_calibration_verified`；
- Step J-D1c3c1：新增最小 runtime confidence 数据契约和单元测试，已完成；
- Step J-D1c3c1a：严格校验布尔标志、完整玩家集合并消除 malformed copy 求和异常，已完成；
- Step J-D1c3c2a：新增默认关闭的 runtime pipeline 与 DeepSeek shadow 审计，不改变 prompt 或动作，已完成；
- Step J-D1c3c2b1：建立独立、有界、确定、精确分数的 prompt 序列化契约，已完成；
- Step J-D1c3c2b2：增加默认关闭的 DeepSeek prompt 消费开关并验证兼容性，已完成；
- Step J-D1c3c2c1：建立四策略配对 prompt 覆盖、预算和精确插入基准并运行开发语料，已完成，判定 `confidence_prompt_coverage_capacity_verified`；
- Step J-D1c3c2c2：使用 seed `10000..10049` 完成正式双运行，但完整门槛输出未留存，已完成，判定 `benchmark_invalid`；
- Step J-D1c3c2c2a：使用仓库外审计文件和全新 seed `11000..11049` 恢复正式验收，已完成，判定 `confidence_prompt_coverage_verified`；
- Step J-D1c3c2c3a：建立无网络、provider 可注入、顺序平衡的成对动作消融载体，已完成，判定 `confidence_action_ablation_harness_verified`；
- Step J-D1c3c2c3b：在用户授权最多 48 次无重试请求后运行小规模真实 DeepSeek 动作响应验收，下一步；
- Step J-D1c3c2c3c：动作响应安全后再评估对局质量与胜率，尚未开始；
- 策略接入：继续暂停，直到动作响应与对局质量验收均通过。

设计见 `docs/BELIEF_STATE.md`。

### Step K：中局策略路由与残局决策

状态：尚未开始。

依赖：

- Step I 阶段分类稳定；
- Step J 能提供结构化信念状态。

## 6. 当前风险

1. 同时改阶段、猜牌、RAG 和策略会导致无法判断收益来源。
2. pass 是策略行为，不能作为“对方没有可压牌”的硬证据。
3. 无条件 pass 扣分已撤销；不得以 runtime confidence 名义重新引入该信号。
4. RAG 条目增加会扩大提示词，必须同步控制 token。
5. 当前没有 A/B 对局工具，策略增强暂时只能声明“已接入”，不能声明“已提升”。

## 7. 项目管理规则

- 每轮只推进一个可独立验收的里程碑；
- 先更新 docs，再写测试，再实现；
- 每轮结束必须更新本文件；
- 没有测试或数据时，不把推测写成完成；
- 引擎规则与 AI 策略保持分离；
- 新增依赖前必须说明理由；
- 不修改 `.env`、密钥或生产配置；
- 临时运行输出不得纳入源码提交。
