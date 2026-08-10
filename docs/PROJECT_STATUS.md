# 项目状态看板

更新时间：2026-08-10

## 1. 当前基线

- prompt coverage 实现检查点：`bc689a37f462672033d754cce7060897d70c7612`
- prompt coverage 恢复验收 HEAD：`6b62156a98cfb97dd11e30df5f95a62dba99accd`
- K-A3d1 检查点：`b75dace33d399704e45909ce31c339a7a7e14226`；K-A3d2 检查点：`415c86dc5034ca85862f52e94d1406aa58042b98`
- 当前工作状态：L4-A3c1 已封存为 `1924db4a...9a9388f`；后续唯一 live 因零请求却接受历史 finished 而 invalid。下一步 L4-A3d1 离线加固 finished 同局来源，不直接 live
- 测试基线：`python -m unittest discover -q`
- 实际验证结果：最新 live 为 exit 0/`finished_target`，但 request/response/header 均为 0，仅观察到 1 条 finished；未形成 deal/play 闭环
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

K-A3c2 已使用 seed `18000..18199` 完成四策略各 200 局的正式双运行。两份 canonical JSON 完全一致，SHA-256 为 `35587b8d532dc9ba3fc8d82d6f6a690692362a31a908c066b2ad4783bfd1d148`；全部样本 ready 且精确插入，零 omitted/invalid/mismatch/diagnostics，覆盖门槛全部通过。正式判定仍为 `strategy_intent_prompt_coverage_benchmark_invalid`：四个 near-open 桶均观测到合法的 `91/100` payload/delta 最大值，超过预注册的 `89/98`。静态穷举表明这是字符包络门槛计算错误，不是 formatter 或配对实现错误；不得事后追认本次运行通过。

K-A3c2a 已通过 40 个真实 formatter 调用锁定逐 phase×reason 精确字符数。四阶段 payload/delta 包络为 midgame `74..81 / 83..90`、endgame `74..81 / 83..90`、near-open `84..91 / 93..100`、critical `83..90 / 92..99`；唯一判定 `strategy_intent_prompt_envelope_contract_verified`。原 K-A3c2 结论不变，下一步只能使用全新 seed 做 K-A3c2b。

K-A3c2b 已使用 seed `19000..19199` 完成四策略各 200 局的独立正式双运行。两份 canonical JSON 逐字节相同，SHA-256 为 `a3f6b35f791435af22ccf3e877e5b5d571028d9dc05d36ce506e10c2a31ad66b`；16 个桶全部 ready、精确插入、达到样本门槛且字符范围位于已封板包络内，零异常与 diagnostics。唯一判定 `strategy_intent_prompt_coverage_recovery_verified`。

K-A3d1 已建立独立、provider 可注入的四阶段成对动作消融载体。seed `400..409` 双运行 canonical SHA-256 均为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；四策略每阶段 4 对，64 对全部 both-valid 且 changed，AB/BA 平衡，零异常与 diagnostics。唯一判定 `strategy_intent_action_ablation_harness_verified`。

K-A3d2 已建立同状态 RuleBased 分支续局质量代理。seed `500..509` 双运行 canonical SHA-256 均为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；32 pair 全部 quality-evaluable，64 branches 全部完成。假 provider 的代理统计为 on/off/tie=`5/11/16`，只验证载体，不是策略意图收益结论。唯一判定 `strategy_intent_action_quality_harness_verified`。

## 3. 分模块状态

| 模块 | 状态 | 当前能力 | 主要缺口 |
|---|---|---|---|
| 规则引擎 | 已完成 | 规则、动作、状态、终局稳定 | 暂无本轮优化需求 |
| 公式化开局 | H2-A1/A1a 完成 | 残余结构代价、严格 token、天然单 9 fixture、CLI 本地公式标记 | 尚未做固定种子胜率评测 |
| 统一阶段 | 已完成 | 开局、剪枝、RAG、提示词共用公开阶段上下文 | 尚未接入 Step J 信念状态或 Step K 策略路由 |
| 手牌评分 | 基础完成 | 输出结构、控制力和潜力分 | 不是胜率；动作结构可重叠，权重未校准 |
| 动作剪枝 | 基础完成 | 区分首出和跟牌，保留关键动作，使用统一阶段 | 缺少策略收益评测 |
| 基础记牌 | 基础完成 | `CardTracker` 按点数统计已出和外部剩余 | 仍是旧链路，不提供逐玩家候选 |
| 公开牌面事实 | Step J-A 完成 | 精确 108 张牌池、token/点数扣牌、逐玩家公开历史与诊断 | 尚未接入决策主链 |
| 硬归属约束 | Step J-B1 完成 | token/点数可能归属域、容量校验、唯一候选确认 | 多玩家实时域通常仍较宽 |
| 残局精确分配 | Step J-D1c3c2c3c2b 完成 | 只读恢复审计有效，24 对质量代理全部 tie | 未观察到 confidence 动作质量增益，默认关闭 |
| 信念离线评测 | Step J-C1 完成 | 域召回、确认精度/覆盖、边界违例、域缩减指标 | 尚无正式独立种子结论与策略分布验证 |
| 公开行为事件 | Step J-C2a 完成 | lead/follow/pass 响应链、声明/carrier 差异、逐玩家事实画像 | 目前只有敌方 single pass 进入软评分 |
| rank 排序 | Step J-C3d1/J-C3d2 完成 | hard-only neutral；四策略 12 桶 baseline/soft 完全相同 | 暂无经过验收的新软证据 |
| rank 排序评测 | Step J-C2b2 完成 | 真值隔离、并列安全 Top-K、零软分基线和单样本 delta | 尚未支持策略分布分层结论 |
| rank 离线基准 | Step J-C3a/J-C3b 完成 | 固定种子采集、微聚合、阶段桶、可重复正式验收 | RuleBasedAI 不覆盖有牌可压时的战略性 pass |
| pass 策略分布基准 | Step J-C3c1/J-C3c2 完成 | 0/25/50/100% 确定性主动 pass、独立 seed 双运行验收 | 已拒绝无条件 pass 信号；不代表其他软信号无效 |
| RAG | Step H 完成 | 标签化规则库/经验库，场景检索 | 标签维度粗，未接策略意图 |
| 中期策略 | K-A3d2 完成 | 默认关闭接线、正式覆盖、动作配对和 RuleBased 质量代理载体已封板 | 尚未运行真实模型质量试验，不代表策略收益 |
| Botzone 接入 | L4-A3c 已授权待执行 | stdout 单行契约、零 transport 与 state 清理已独立验证 | 尚未启动真实 smoke，未证明一局完成 |
| 残局推断 | 未完成 | 外部剩余少时显示完整点数 | 尚未接近逐玩家明牌 |
| 策略评测 | 部分完成 | 已有信念校准、策略分布、prompt coverage 和真实响应质量代理 | confidence 未观察到净增益；尚无中局路由与完整对局指标 |

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

### 已解决：真实 DeepSeek 响应安全 live pilot（Step J-D1c3c2c3b）

J-D1c3c2c3b 在用户授权后使用 `https://api.deepseek.com`、`deepseek-v4-pro`、timeout 60 秒、零重试完成：

- seed `13000..13009`，四策略每桶 2 个样本，共 24 pair / 48 次请求；
- logical/physical requests 为 48/48，总耗时 1411.005 秒；
- ledger 连续 1..48，off/on 各 24；off 延迟 588053ms，范围 7543..54488ms；on 延迟 807020ms，范围 11651..76913ms；
- 四策略均 10/10/0 games、零 diagnostics，每策略 6 pair，每桶 selected=2、off-first/on-first 各 1；
- 48 个响应全部 valid，24 pair 全部 both-valid；异常、malformed、no-action、非法类型、outside legal/prompt 均为 0；
- forced/25/50/100 的 same/changed 为 2/4、3/3、4/2、4/2，总计 13 same / 11 changed；
- off/on pass 分别为 6/6，pressure 均为 0；
- 未输出或持久化 key、prompt、action ID、reasoning、响应正文、样本身份、手牌或 ground truth；
- 未运行完整 DeepSeek 对局。

仓库外证据目录：`C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-live-c3b-e0065c6a3da7`。

- runner SHA-256：`be12c6fc3e265704dab0f2be7b556aeff947f3a7bccae209540b428ce3716167`；
- ledger SHA-256：`a45517e6948bf421a8af28f6f4e4a3c8bc0cddf7a925c359df9bab38c3c32753`；
- report SHA-256：`02e3fe45a983e89d2982a4acba12fc437f70ee30914957096b9385caf09c756c`；
- audit summary SHA-256：`f338f5cefdfec254482a5a4af803d507d31670f9a3f3bfbb64dd9095ffb55963`。

唯一判定：`retain_for_action_quality_evaluation`。11 个 changed 仍可能包含服务非确定性，不证明 confidence 导致变化。

### 已解决：确定性分支续局质量载体（Step J-D1c3c2c3c1）

J-D1c3c2c3c1 只新增 `evaluation/confidence_action_quality.py` 和对应测试，保持 c3a 公开 API、默认值和开发 canonical hash 不变：

- 仅为 SHA-256 固定优先级最终入选的 critical 样本保留内存 `deepcopy(game)`；
- clone 前后只通过 `observe()` 和 `legal_actions()` 验证公开等价，不读取或写入 `game._state`；
- off/on both-valid 后在独立 clone 执行动作，再由独立 `RuleBasedAIAgent` 仅使用公开接口推进到终局；
- same action 只 rollout 一次并复用，changed action 运行两个独立分支；
- 终局只使用 `step()` 结果和公开 `history.finish_order`，三人顺序补入唯一末游；
- 质量字典序固定为观察者团队 win/draw/loss 分数，其次为团队两人完赛位置和，其余为 tie；
- 新模块 5 项、相关 81 项、全量 362 项测试通过，`git diff --check` 和禁止边界扫描通过；
- c3a seed `120..129` 兼容哈希仍为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`。

开发双运行使用 seed `140..149`、四策略、每桶 2 个样本、`max_rollout_steps=5000`：

- 两次耗时 27.158s / 27.252s，report、`to_dict()` 和 canonical JSON 完全相等；
- canonical SHA-256 为 `3a989255412180b293afcd9f99a8a32d6d399c891d829bd16d37e94b5f64eaa6`；
- 24 pair 全部 both-valid、quality-evaluable，48 个 changed-action 分支全部完成，零 diagnostics；
- forced/25/50/100 的 on-better/off-better/tie 分别为 1/1/4、1/0/5、0/0/6、1/0/5；
- 总计 on-better/off-better/tie = 3/1/20，但假 provider 的动作差异是刻意构造，只验证载体。

唯一开发判定：`confidence_action_quality_harness_verified`。

### 已确认：首次真实动作质量运行无完整报告（Step J-D1c3c2c3c2）

J-D1c3c2c3c2 在检查点 `ad85662a47f126991e8ebe0360dc0c6c4a2f1be6` 上使用 seed `15000..15009`、`deepseek-v4-pro`、60 秒 timeout、零重试和 48 请求上限执行：

- 外层执行器在 30 分钟时限中断；发现子进程仍运行后立即终止，没有恢复、补采或重跑；
- ledger 只有连续 45 条记录，off/on 为 23/22，均为 returned 且严格整数；
- 未达到 48 请求、24 pair 和完整 report 门槛；没有生成 `report.json`；
- 不报告 same/changed、rollout、质量比较或胜负代理结果；
- 本地 5 / 81 / 362 项测试与 `git diff --check` 通过，运行前后工作区干净；
- 未输出密钥、prompt、action ID、reasoning 或响应正文，未修改 runtime。

仓库外失败证据目录：`C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-quality-c3c2-ad85662a47f1-0f1b1b08851742fea86a9965e8617154`。

- runner：12718 bytes，SHA-256 `ffcc5448ea7ff5b960c58869db0c1e6d34f8eac621de425a11f56332ac4bb7a6`；
- ledger：9576 bytes，SHA-256 `908fbd2e05f2c1d85e3092c4f72054ccdd810ff2c669324c15d0cf516a9d08ab`；
- failure audit summary：1190 bytes，SHA-256 `4475786a589534b77ef8421f8f614753d1be7f9665e175312bae6396464af250`。

唯一判定：`quality_benchmark_invalid`。旧 seed 与 45 条部分记录永久只作为失败审计，不能补全或进入后续质量统计。

### 已确认：耐久运行完成但正式键序审计假阴性（Step J-D1c3c2c3c2a）

J-D1c3c2c3c2a 使用 seed `16000..16009` 和持久后台进程完成：

- run ID `6999cb8cde244f0c96a95601c504062f`，PID 8728 正常退出，耗时 1890.133 秒；
- 48 条 ledger 连续，off/on=24/24，全部 returned 且为严格整数；
- off/on 延迟和为 590242 / 1247160 ms；
- 四策略均 10/10/0 games，主动 pass 为 0、40/102、59/98、111/111，比例严格递增；
- 每策略每桶 selected=2、overall=6，provider 全部 valid，24 pair 全部 both-valid；
- 所有 rollout 分支完成，diagnostics 为空；
- 正式 `audit_summary.json` 错误依赖 canonical JSON 的键迭代顺序，令 `integrity_pass=false`；
- 原 summary/completion 未重写，未重跑，也未使用 report 形成质量结论；
- 只读 addendum 记录键序假阴性，但不覆盖正式 completion。

审计目录：`C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-quality-c3c2a-ad85662a47f1-699cabeb8ea448878a510de9c2fec30f`。

- runner：9708 bytes / `c020860c67c2663c9ed87adda974774697c396d186b82c4f7547bbccebc33a5c`；
- process state：508 bytes / `4a4ff3d487f3257fbc7d0a82392c04d3c9f5df9cabb667fa534a2be5359c2adc`；
- heartbeat：219 bytes / `33bba4c0a966dd88e0e9c1293dc783be346cba0c65e5744acb8de28269d3d6e3`；
- ledger：10263 bytes / `c60f5d35d9ee907efd926c7e3f03ba5fdb918c463892da3f1abab6a6c2ee49df`；
- report：15623 bytes / `57df2cd1826f3e5226ab66cf2a7590f7158ec88c4843e0f7839672b3f3bb090f`；
- audit summary：21345 bytes / `9d9522155bea9d3c0dc24d40c33d6b0f3872d4e5ed75c8788a8d154cc0f1a2ab`；
- completion：916 bytes / `cfed3329699e822a84313c0e92b0c3a1dbec2dd08956f3ae0e126d9fea0b25c6`；
- 显式映射 addendum：`52bab7e2de283b48d76839be4926fd75597d66046078512d8c04c94c9c5d3229`。

唯一判定：`quality_recovery_invalid`。完整数据存在不等于正式审计通过。

### 已解决：不可变证据只读恢复审计（Step J-D1c3c2c3c2b）

c3c2b 未联网、未调用模型、未修改或重跑 c3c2a 源证据：

- 原 summary 唯一 false path 为 `integrity_pass`；唯一原子原因是 `tuple(policies) == NAMES` 把 canonical `sort_keys=True` 后的键序误当业务顺序；
- 恢复验证改用固定策略名 lookup 与内部 rate 核对，源文件前后 hashes 不变；
- forced/25/50/100 主动 pass 为 0/87、40/102、59/98、111/111，比例严格递增；
- ledger 连续 1..48，off/on=24/24，全部 returned 且为严格整数；
- 四策略均 10/10/0，每策略每桶 selected=2，所有 provider、pair、branch、diagnostics 和 bucket-to-overall 守恒通过；
- 双验证输出逐字节相等，未发现敏感内容。

质量结果：

| 策略 | same / changed | on / off / tie | off W/D/L | on W/D/L | placement off/on | steps off/on |
|---|---:|---:|---:|---:|---:|---:|
| forced-only | 4 / 2 | 0 / 0 / 6 | 2/1/3 | 2/1/3 | 32/32 | 101/101 |
| pass-25 | 5 / 1 | 0 / 0 / 6 | 2/1/3 | 2/1/3 | 30/30 | 99/99 |
| pass-50 | 4 / 2 | 0 / 0 / 6 | 4/2/0 | 4/2/0 | 23/23 | 85/83 |
| pass-100 | 2 / 4 | 0 / 0 / 6 | 2/1/3 | 2/1/3 | 32/32 | 96/101 |

overall 为 24 pair、same/changed=15/9、33 个 rollout branch 全部完成；on/off better=0/0、tie=24，on/off team win 均为 10。按预注册顺序，唯一恢复审计判定：`no_observed_action_quality_gain`。

恢复目录：`C:\Users\86166\AppData\Local\Temp\guandan-confidence-action-quality-c3c2b-readonly-6999cb8c-6630f371c650462c949a210cd063c320`。

- verifier：13213 bytes / `27a82023…f774799c`；
- run1/run2：各 19096 bytes，逐字节相同 / `f619c3e1…c9d83f02`；
- manifest：1062 bytes / `7d777803…6d92ad98`。

原 c3c2a 的 `quality_recovery_invalid` 保持不变。恢复结论不证明 confidence 因果效果或胜率提升。

### 已封板：confidence prompt 未观察到动作质量净增益

`no_observed_action_quality_gain` 不授权完整 DeepSeek 对局评估，也不授权默认开启 confidence。现有 shadow/prompt 代码保留为默认关闭的研究能力，不继续增加 API 消融、提示词内容或策略消费。后续若有新的独立证据或机制，必须作为新研究分支重新预注册。

### 新确认：联网单局暴露开局、协作和残局规划缺口

`record.txt` 的终局为 `[4, 1, 3, 2]`，按当前规则是平局，不是玩家 1/3 队落败。开局评分 97/71/90/81 只表示单手启发式结构，不是胜率，也不能按队伍相加。

已确认：

- 第 1 轮单 K 可由默认开局公式确定复现；公式不评估残余结构，把拆对 K 排在天然单 9 和天然 10-J 钢板之前；
- CLI 没有把 `local_opening_formula` 显示为本地来源；
- 第 2 轮玩家 1/3 连续用 4 炸、5 炸互压，暴露桌面队友关系没有进入确定性策略；
- 第 16 轮玩家 4 出 8 后只剩 2 张，玩家 3 有 9/J 可压却 pass，直接放出对手头游；
- 第 20 轮 J 确为公开牌池中的最高剩余单牌，但玩家 1 只剩一张，先出 6 有直接放跑风险；问题应定义为 `6,7,J,J` 的多手序列规划，而不是机械改成先出低牌。

详细复盘见 `docs/LIVE_GAME_REVIEW.md`。单局不授权胜率声明或直接调整评分权重。

### 已解决：H2-A1/A1a 开局残余结构与严格封板

已核对实现：

- 完整消耗点数代价 0，拆对子 24，部分拆三张 32，部分拆四张及以上 48；
- malformed carrier 预期代价 80；
- 同一候选集合中 K/Q/J/10/9 修复后为 65/65/56/55/86，单 9 胜出；
- CLI 正确区分 `（本地）`、`（本地公式）` 和模型/其他来源；
- 定向 26 项、相关 73 项、全量 370 项均通过。

H2-A1 初次复核发现三项缺口：

1. `test_record_public_fixture...` 把 `hand_eval={"total_score": 97}` 直接写入，断言只验证该常量，没有调用 `evaluate_hand()`；
2. fixture 的花色/重复 token 与 `record.txt` 不完全相同，`remaining_single_card_count` 写为 1，而真实公开点数单张数为 3；
3. 公开手牌和 carrier 同时包含未知 token `ZZ` 时，`_residual_structure_cost()` 实测返回 0，不符合“未知 token 保守代价 80”的预注册要求。

H2-A1a 已完成修复：

- 精确写入四位玩家的初始 token multiset，通过 `reset()/observe()/legal_actions()` 获取公开 fixture；
- 真实 `evaluate_hand()` 得到 97/40/27/30、`极强`，公开散牌数为 3；
- K/Q/J/10/9/天然钢板分数为 65/65/56/55/86/72，最终选择 `9C`；
- 非字符串、未知、裸点数、错误花色、空串和带空格 token 在 hand/carrier 任一路径均返回 80；
- 单文件 21 项、相关 74 项、全量 371 项通过，`git diff --check` 通过。

唯一判定：`opening_residual_structure_hardening_verified`。该判定封板 Step H，只授权 K-A1，不形成动作质量或胜率结论。

### P1：尚无中局策略收益结论

K-A1 至 K-A3c1 已封板。K-A3c2 正式双运行的结构、覆盖、插入和可重复性均通过，但预注册 near-open 最大字符数低估 2 个字符，因此唯一判定为 `strategy_intent_prompt_coverage_benchmark_invalid`。下一步 K-A3c2a 只用穷举测试锁定 formatter 的精确字符包络；不改文案、runtime 或 benchmark，也不比较动作。

### K-A1/A1a 复核：严格契约已封板

已核对：

- `StrategyIntentContext` 为 frozen/slots、JSON 友好、unavailable 不保留部分结论；
- 当前 round 最后一个非 pass 动作与 table action 严格核对；
- 路由优先级和三个联网单局公开 fixture 符合预注册结果；
- 深层校验 `GamePhaseContext` 的 phase、五个计数字段、`other_hand_counts` 容器与元素类型；
- `bool` 不能冒充整数，非法 phase context 整体 unavailable；
- 可安全判断的独立错误按 `_DIAGNOSTIC_ORDER` 去重聚合，上游容器不可读时不派生级联诊断；
- 三组合法 fixture 的完整 `to_dict()` 快照与路由优先级保持不变；
- 定向 18 项、相关 86 项、全量 389 项通过。

初次复核发现的反例：

1. 公开手数为 1 时传入 `GamePhaseContext.my_hand_count=True`，router 返回 `available / run_out`，违反“不接受 bool 冒充 int”；
2. 同一 observation 同时存在非法 team 和非法 hand_count 时，只返回 `invalid_team`，没有按固定顺序聚合两个 diagnostics。

两项均已由 K-A1a 修复并有回归锁定。唯一判定：`strategy_router_hardening_verified`。该判定只授权 K-A2a shadow 装配，不代表策略收益或胜率提升。

### K-A2a 复核：shadow 装配已验证

已核对：

- 新增 `strategy_router_shadow_enabled=False` 严格布尔开关与非展示 `last_strategy_intent`；
- 每次决策重置审计字段，only-pass、一次出完与开局公式命中均跳过 router；
- 普通模型链只传入同一 phase、原始 legal actions 并复用已有手牌评估；
- available/unavailable 只写审计字段，router 或 shadow-only 评分异常均 fail-closed；
- off/on 的 client kwargs、结构化 prompt、action、fallback 和 `last_decision_source` 一致；
- 禁止消费扫描无匹配，未调用网络或读取隐藏状态；
- 定向 25 项、相关 100 项、全量 396 项通过。

唯一判定：`strategy_router_shadow_verified`。该判定只授权 K-A2b1 离线路由分布载体，不授权策略消费。

### K-A2b1 历史复核：开发分布有效，载体严格契约未封板

已核对：

- 只新增 evaluation 载体与对应测试，runtime 无反向导入；
- 每个 rate 使用独立 game、agent、sample set 和聚合器；
- only-pass、一次出完、opening 按固定顺序跳过；
- sample、availability、intent/reason/relation、observed/eligible 与 phase-to-overall 守恒已实现；
- seed `200..209` 双运行 canonical SHA-256 均为 `32e42e0e7dc56377811fc52aa5d387d0b0f16e45102a3f88bea1a8e86d755ccb`；
- 四策略均 10/10/0，unavailable、invalid、duplicate、sample-limit 和 diagnostics 均为 0；
- 主动 pass 为 `0/122`、`49/136`、`76/143`、`142/142`，比例严格递增；
- 单模块 8 项、相关 58 项、全量 404 项通过，边界扫描与 `git diff --check` 通过。

严格反例：

1. available context 的 `phase` 从 `midgame` 改为 `endgame`，`_available_context_is_well_formed()` 仍返回 `True`；
2. `source` 改为未知值，仍返回 `True`；
3. reason 改为未知值，或 control 搭配 `weak_hand`，仍返回 `True`；
4. unavailable 结果也未严格复核 source、phase、非空 diagnostics 和“不保留部分结论”契约。

这些缺口不改变本次真实 router 的开发分布计数，但会使未来回归被错误计入正式 phase/intent/reason 分布。因此唯一项目管理判定为 `strategy_router_distribution_harness_invalid`。K-A2b1a 只修复输出 fail-closed 复核，并要求合法语料的报告与上述 SHA-256 逐字节不变。

### K-A2b1a 复核：输出 fail-closed 已封板

已验证：

- context 必须为精确 `StrategyIntentContext`，source 固定且 phase 与当前 bucket 一致；
- reason/urgent IDs/diagnostics 严格为 tuple，三个布尔语义字段严格为 bool；
- available 只接受锁定 reason-intent 映射，并校验出完、relation、leader ID、free lead 和 hand strength；
- unavailable 必须清空所有玩家、领牌、评分和意图字段，且有非空规范 diagnostics tuple；
- malformed context 只记一次 `invalid_router_result`，不泄露伪 intent/reason/relation/diagnostics；
- wrong source/phase/status、非 tuple、bool 冒充、未知/错配 reason、relation/leader 矛盾与 unavailable 部分泄露均已有回归；
- 单模块 11 项、相关 61 项、全量 407 项通过；
- 独立双运行耗时 2.603s / 4.903s，report、`to_dict()` 与 canonical JSON 完全相等；
- 开发 SHA-256、四策略完整性、pass 计数与所有分布字段保持不变。

唯一判定：`strategy_router_distribution_hardening_verified`。该判定只授权 K-A2b2 独立 seed 正式覆盖验收，不授权策略消费。

### K-A2b2 正式结果：结构完整，endgame 容量不足

已验证：

- HEAD 与 K-A2b1a 检查点均为 `7f014db0c871a6ff851ab331e4ef4f19c357a909`，运行前后工作区干净；
- seed `16000..16099`、四策略各 100 局完整运行两次，耗时 28.364s / 36.501s；
- 两份 report、`to_dict()` 与 canonical JSON 逐字节相等，SHA-256 为 `e77e5632b4b71f4a12fc1b213be78b413c70486f60e06e3f5cd35c941aa2d40d`；
- 四策略均 100/100/0，unavailable、invalid、duplicate、sample-limit 与 diagnostics 全为 0；
- 全部计数守恒、pass 比例梯度、overall intent、分阶段 intent、relation 和全部 reason 覆盖通过；
- 273 项审计中 270 项通过，唯一失败为 `forced_only`、`strategic_pass_25`、`strategic_pass_50` 的 endgame available 最低门槛；
- endgame available 分别为 583、660、663、777，只有 100% pass 策略达到 700；
- 单模块 11 项、相关 61 项、全量 407 项再次通过。

唯一判定：`strategy_router_coverage_insufficient`。失败属于预注册绝对样本容量，不是路由契约、载体完整性或分支覆盖错误。K-A2b2a 使用全新 seed 将每策略扩大到 200 局，保持实现、分桶、采样和全部门槛不变。

### K-A2b2a 正式结果：独立覆盖已封板

已验证：

- HEAD 为 `7b9aaae53faf7c5135cd147333d6195a10b90f87`，K-A2b1a 检查点为 `7f014db0c871a6ff851ab331e4ef4f19c357a909`；
- 永久排除 seed `16000..16099`，本次仅使用全新 seed `17000..17199`；
- 四策略各 200 局完整运行两次，耗时 57.145s / 55.747s；
- 两份 report、`to_dict()` 与 canonical JSON 逐字节相同，SHA-256 为 `ee321d18a50f923e92bbcc7e99c7e90a0ee87ac8b57b35b95e091f988c670c0e`；
- runner 落盘报告后只做仓库外 audit-only manifest 修复，未重跑 benchmark，原始两份报告未修改；
- 四策略均 200/200/0，unavailable、invalid、duplicate、sample-limit 和 diagnostics 全为 0；
- pass 比例严格递增，全部计数守恒通过；
- 结构完整性 97/97、原覆盖门槛 176/176、总计 273/273 通过；
- 单模块 11 项、相关 61 项、全量 407 项再次通过，边界扫描无禁止引用。

唯一判定：`strategy_router_coverage_verified`。该结论只授权 K-A3a 建立 intent prompt payload 契约；不授权直接修改 DeepSeek client、RAG、剪枝、fallback 或动作选择。

### K-A3a 复核：局部校验通过，完整语义契约未封板

已确认：

- 只新增 formatter 与对应测试，现有 runtime 消费路径无反向引用；
- payload frozen/slots、JSON 友好，ready 文本固定四行；
- 十种 reason 到四种 intent 的中文映射、800 字符预算和 omitted 清空契约已实现；
- 单模块 7 项、相关 43 项、全量 414 项通过，`git diff --check` 与边界扫描通过。

但以下非法 context 实测仍返回 ready：

1. `stable_control` 同时存在紧急对手；
2. `weak_hand` 同时存在紧急队友；
3. `opponent_urgent` 同时满足“队友比对手更紧急”；
4. `urgent_opponent_ids` 非空但 `minimum_opponent_hand_count=None`；
5. 紧急对手控桌，但 minimum count 为 5 且 urgent IDs 为空；
6. `weak_hand` 搭配非弱总分、`stable_control` 搭配弱总分，或 control score 大于 total score；
7. `teammate_more_urgent` 同时由队友控桌，绕过更高优先级 `teammate_controls_table`。

这些反例说明 formatter 不能只逐 reason 检查局部条件，必须根据完整公开字段按 K-A1 原优先级推导唯一 expected reason。唯一判定：`strategy_intent_prompt_contract_invalid`。K-A3a1 只修复该契约，不修改文本快照或任何消费路径。

### K-A3a1 复核：跨字段语义已封板

已验证：

- total/control 分数范围、`control <= total` 与 39/40 weak 分界已锁定；
- minimum opponent count 与 urgent IDs 的 None/1/2/3 关系、队友 0/1/2/3 紧急度和 leader urgency 已锁定；
- formatter 在基础字段有效后按 K-A1 原优先级推导唯一 expected reason；
- reason/intent 不是唯一 expected 值时整体 omitted；
- 九类预注册伪造 context 全部 omitted，分别使用 `invalid_context_fields` 或 `invalid_intent_reason`；
- 十种合法 reason、四种 intent、三个公开 snapshot、固定四行文本和预算边界保持不变；
- 单模块 11 项、相关 47 项、全量 418 项通过，`git diff --check` 与边界扫描通过；
- 现有 runtime 消费路径仍未引用 formatter。

唯一判定：`strategy_intent_prompt_contract_hardening_verified`。该判定只授权 K-A3b 默认关闭的 prompt 消费接线，不授权 RAG 路由、动作质量实验或默认启用。

### K-A3b 复核：默认关闭接线已封板

已验证：

- 新增严格 bool、默认关闭的 `strategy_intent_prompt_enabled`，且 prompt 必须依赖 router shadow；
- 每次决策重置 intent/payload 审计字段，三个 local shortcut 均跳过 router 和 formatter；
- shadow-only 不加载 formatter，prompt 模式最多调用 router/formatter 各一次；
- ready payload 才新增 `strategy_intent_prompt` keyword，omitted 和异常不传该键；
- client 独立复核精确类型、metadata、phase、intent、reason 文案、四行文本和 800 字符上限；
- 合法章节位于可选 confidence 之后、场景标签之前，均只出现一次；
- off、shadow-only、omitted、router/formatter 异常的 kwargs、prompt、动作、fallback 与 decision source 保持兼容；
- 定向 56 项、相关 88 项、全量 424 项通过，`git diff --check` 与边界扫描通过；
- config、CLI、engine、RAG、evaluation 无消费或反向引用。

唯一判定：`strategy_intent_prompt_wiring_verified`。该判定只授权 K-A3c1 evaluation-only prompt 覆盖载体，不授权真实 API、动作质量实验、RAG 路由或默认启用。

### K-A3c1 复核：离线 prompt 覆盖载体已验证

已验证：

- 只新增 evaluation collector 与对应测试，runtime 无反向导入；
- 四种 strategic-pass 策略使用独立 game、agent、seen set、聚合器和 pair hasher；
- only-pass、一次出完、opening、duplicate 和 per-phase limit 顺序固定；
- off/on 共用 observation、phase、hand evaluation 和 pruned actions，intent 不影响推进动作；
- ready 只接受在场景标签前精确插入，delta 严格为 payload char+9；
- omitted 要求 off/on 逐字节相等，报告只保留聚合计数和 digest；
- seed `300..309` 双运行耗时约 3.3s，canonical SHA-256 均为 `032ff0964a0fe4c377c612f27263e553abfe22ad759d14b5714ebf788d280a20`；
- 四策略均 10/10/0，样本/ready 为 350/350、377/377、391/391、469/469；
- 16 个策略×阶段桶均有 ready，所有 omitted、invalid、duplicate、limit、mismatch 和 diagnostics 为 0；
- payload 范围 74..90 字符，prompt delta 范围 83..99 字符；
- 定向 6 项、相关 52 项、全量 430 项通过，边界扫描和 `git diff --check` 通过。

唯一判定：`strategy_intent_prompt_coverage_capacity_verified`。该判定只授权 K-A3c2 独立 seed 正式覆盖验收，不授权动作消融、真实 API、RAG 路由或默认启用。

### K-A3c2 复核：正式覆盖运行因预注册字符包络错误而无效

已确认：

- HEAD / K-A3c1 检查点为 `1fca3270843d51c2b565b37e7823b57ed9b950b5`，运行前后工作区干净；
- seed `18000..18199`、四策略各 200 局，正式 benchmark 恰好运行两次；
- 两份报告和 canonical JSON 完全一致，SHA-256 均为 `35587b8d532dc9ba3fc8d82d6f6a690692362a31a908c066b2ad4783bfd1d148`；
- 四策略均完整完成，主动 pass 比例严格递增；16 个策略×阶段桶均达到 ready 样本门槛；
- unavailable、router/payload invalid、omitted、duplicate、sample-limit、pair mismatch 与 diagnostics 均为 0；
- 每个样本均精确插入，prompt delta 严格等于 payload 字符数加 9；
- 四个 near-open 桶的 payload/delta 范围均为 `84..91 / 93..100`，超过预注册的 `84..89 / 93..98`；
- 静态穷举固定四行 formatter 的全部 phase×reason 组合得到真实理论包络：midgame `74..81 / 83..90`、endgame `74..81 / 83..90`、near-open `84..91 / 93..100`、critical `83..90 / 92..99`；
- 最大值对应合法 reason `urgency_tie_block_opponent`，文案为“双方同样紧迫，优先阻断对手”；没有发现 runtime、formatter、插入或采样缺陷。

唯一判定：`strategy_intent_prompt_coverage_benchmark_invalid`。该正式运行不能因事后发现门槛算错而追认通过；当时要求先完成 K-A3c2a，再以全新、未使用 seed 另行预注册 K-A3c2b 恢复验收。

### K-A3c2a 复核：字符包络契约已封板

已确认：

- 仅修改 `tests/test_strategy_intent_prompt.py`，未修改 formatter、runtime、evaluation benchmark 或 docs；
- 穷举四阶段×十种合法 reason，共 40 个真实 formatter 调用；
- 全部 payload 为 ready、diagnostics 为空，且 `char_count == len(text)`；
- 40 个逐组合长度全部匹配预注册表，每阶段最大值均来自 `urgency_tie_block_opponent`；
- payload/delta 包络精确为 midgame `74..81 / 83..90`、endgame `74..81 / 83..90`、near-open `84..91 / 93..100`、critical `83..90 / 92..99`；
- 定向 12 项、相关 60 项、全量 431 项通过，`git diff --check` 和禁止边界扫描通过。

唯一判定：`strategy_intent_prompt_envelope_contract_verified`。该结论不追认 K-A3c2 通过，只授权在 K-A3c2a 形成检查点且工作区干净后，使用 seed `19000..19199` 执行 K-A3c2b。

### K-A3c2b 复核：独立 prompt 覆盖恢复验收通过

已确认：

- HEAD / K-A3c2a 检查点为 `a8cf1291de2fde62c6c7ed7ecfeaa878671f5490`，运行前后工作区干净且本步未修改仓库；
- 锁定 seed `19000..19199`、rates `(0,25,50,100)`、级牌 2、`max_steps=5000`、每局每阶段上限 128；
- 正式 benchmark 恰好运行两次，耗时 62.944s / 63.941s；
- 两份 canonical JSON 逐字节相同，SHA-256 均为 `a3f6b35f791435af22ccf3e877e5b5d571028d9dc05d36ce506e10c2a31ad66b`；
- 四策略均 200/200/0，主动 pass 比例按精确交叉乘法严格递增；
- 16 个 phase bucket 全部满足 sample=router available=payload ready=exact insertion，并达到预注册最低样本；
- payload/delta 字符范围全部位于 K-A3c2a 包络内，sum/min/max 均满足固定 9 字符插入关系；
- duplicate、sample-limit、router unavailable/invalid、payload omitted/invalid、pair mismatch 与 diagnostics 全为 0；
- 定向 12 项、相关 60 项、全量 431 项通过，边界扫描与 `git diff --check` 通过；
- 仓库外 manifest 实际 SHA-256 为 `a913dab602153cbef2216dea5d7977a53827342f46acc70df246274bbf24eae9`。

唯一判定：`strategy_intent_prompt_coverage_recovery_verified`。K-A3c2 原正式 invalid 结论保持不变；该恢复结论只授权规划 K-A3d1 evaluation-only 动作消融载体。

### K-A3d1 复核：策略意图动作消融载体已验证

已确认：

- 仅新增 `evaluation/strategy_intent_action_ablation.py` 和 `tests/test_strategy_intent_action_ablation.py`；原有四个 docs 改动未触碰；
- 严格校验 seed、rate、正偶数 samples-per-phase、级牌和上限；
- 每策略独立 game、StrategicPassAIAgent、seen set、候选池、阶段聚合器与 pair hash；
- 每个 policy×phase 按固定 SHA-256 优先级选样，off/on kwargs 唯一差异为 ready `strategy_intent_prompt`；
- 每阶段 AB/BA 平衡，一侧异常不阻止另一侧，七类 provider 结果严格分类且无 fallback；
- 报告 frozen/slots、mapping 不可变、JSON 安全，不保留样本、prompt、action ID、手牌或 reasoning；
- seed `400..409` 双运行耗时 3.222s / 3.236s，报告完全相同，SHA-256 均为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；
- 四策略均 10/10/0，每策略 selected=16、both-valid=16、same=0、changed=16；每轮 provider 128 次，off/on 各 64；
- 所有异常、malformed、no-action、非法类型、越过 legal/prompt、单侧 valid 和 diagnostics 均为 0；
- 定向 8 项、相关 74 项、全量 439 项通过，边界扫描与 `git diff --check` 通过。

唯一判定：`strategy_intent_action_ablation_harness_verified`。该结果只证明动作响应配对载体可用，不形成动作质量、因果效果或胜率结论；下一步先建立本地 RuleBased 分支续局质量代理，不直接申请真实 API。

### K-A3d2 复核：策略意图动作质量代理载体已验证

已确认：

- K-A3d1 独立检查点为 `b75dace33d399704e45909ce31c339a7a7e14226`，K-A3d2 独立检查点为 `415c86dc5034ca85862f52e94d1406aa58042b98`，各自只含对应两个 harness 文件；
- 本步只新增 `evaluation/strategy_intent_action_quality.py` 与 `tests/test_strategy_intent_action_quality.py`，既有 docs 未混入；
- 采样、优先级、AB/BA、provider 分类与 prompt pair digest 和 K-A3d1 对齐；
- game clone 只在候选进入 top-N 时创建，并通过公开 `observe()/legal_actions()` 验证等价；未读取 `_state`；
- same action 复用一次 rollout，changed action 使用两个独立 clone；后续只由独立 RuleBasedAI 通过公开 API 推进；
- 终局只使用公开 winner/finish order，比较顺序为队伍结果、队伍名次和、tie；步数不打破平局；
- seed `500..509` 双运行耗时 4.411s / 4.419s，报告完全相同，SHA-256 均为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；
- 四策略均 10/10/0；32 pair 全部 changed、quality-evaluable，64 branches 全部完成且 diagnostics 为空；
- 假 provider 的 on/off/tie=`5/11/16`，该数值不用于判断 strategy intent prompt；
- K-A3d1 兼容复验及原 hash 通过；定向 7 项、相关 80 项、全量 446 项通过。

唯一判定：`strategy_intent_action_quality_harness_verified`。该结果只证明本地质量代理载体可用；下一步必须先完成真实模型实验前置审计并取得明确联网授权。

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

### P1：没有完整策略收益基准

407 项测试和确定性分支代理证明当前实现满足已有功能契约且可比较局部反事实结果，但不能证明：

- 公式开局提高胜率；
- RAG 改善动作质量；
- 记牌提高残局判断；
- 提示词变长带来实际收益。

## 5. 当前里程碑

### Step H：公式化开局与场景化 RAG

状态：H2-A1/A1a 完成并严格核验，唯一判定 `opening_residual_structure_hardening_verified`。

### Step I：统一阶段分类

状态：完成并已核验。

完成内容：公开阶段分类、消费者接入、残局阶段继承和回归测试。未扩展到 Step J 信念状态或 Step K 策略路由。

验证结果：

- 定向测试：71 项通过；
- 全量测试：126 项通过；
- 未修改 `engine/`。

### Step J：逐玩家牌面信念

状态：J-A 至 J-D1c3c2c3c2b 已完成；恢复审计判定 `no_observed_action_quality_gain`，confidence prompt 路径封板并保持默认关闭。

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
- Step J-D1c3c2c3b：在用户授权最多 48 次无重试请求后运行小规模真实 DeepSeek 动作响应验收，已完成，判定 `retain_for_action_quality_evaluation`；
- Step J-D1c3c2c3c1：建立同状态 off/on 动作的确定性 RuleBased 分支续局质量载体，已完成，判定 `confidence_action_quality_harness_verified`；
- Step J-D1c3c2c3c2：使用 seed `15000..15009` 运行真实模型动作质量验收，45/48 请求后中断，已完成失败审计，判定 `quality_benchmark_invalid`；
- Step J-D1c3c2c3c2a：使用全新 seed 和耐久后台完成 48/48 请求，但正式 summary 因 JSON 键序假阴性失败，已完成，判定 `quality_recovery_invalid`；
- Step J-D1c3c2c3c2b：不联网、不改原证据，以显式策略映射运行独立只读恢复审计，已完成，判定 `no_observed_action_quality_gain`；
- confidence 策略接入：封板，不进入完整对局评估，默认继续关闭；

设计见 `docs/BELIEF_STATE.md`。

### Step K：中局策略路由与残局决策

状态：K-A3d2 已完成，唯一判定 `strategy_intent_action_quality_harness_verified`；K-A3d3a 最终判定 `strategy_intent_live_quality_preflight_ready`；K-A3d3b 在零请求、无启动状态证据时退出，唯一判定 `strategy_intent_live_quality_benchmark_invalid`。K-A3c2 原结论仍为 `strategy_intent_prompt_coverage_benchmark_invalid`。

依赖：

- Step I 阶段分类稳定；
- Step J 能提供结构化信念状态。

K-A3d2 已形成独立检查点且开发双运行通过。K-A3d3a 首次执行时，HEAD 为 `a450fd2367b53ba455e904e1361422f9f965eb58`，工作区干净；7 / 80 / 446 项回归、`git diff --check`、K-A3d1/K-A3d2 固定 hash 和兼容性复核全部通过。阻塞仅为调用进程未显式提供 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 和 `DEEPSEEK_API_KEY`。本次没有读取 `.env`、创建 runner、联网、调用模型或发送 probe。

第二次重试仍缺少同样三项变量，已按快速门槛停止，没有重复运行回归。当时同时观察到未提交的 `.env.example` 改动；该文件未被读取或修改。项目所有者随后已处理工作区并从带有三项变量的新进程启动任务，当前工作区干净。

新进程随后通过不输出值的 presence 检查确认三项变量均存在，工作区干净。项目所有者明确选择 `https://api.deepseek.com` / `deepseek-v4-flash`，理由是当前实验预算下的性价比取舍；这不是通用价格或质量结论。K-A3d3b 已锁定不得混用或回退到历史 `deepseek-v4-pro`，但本次在任何请求前即失败，因此没有 flash 模型结果可解释。

K-A3d3a 随后完成全部前置：HEAD `f0a087a4146b0950764b8b08bf03ff6c15723d98`，工作区干净，7 / 80 / 446 项回归通过，两个固定 hash 与兼容性复核通过，唯一判定 `strategy_intent_live_quality_preflight_ready`。

唯一 K-A3d3b 后台进程 PID `33612` 异常退出。仓库外目录只保留 SHA-256 为 `a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd` 的 runner；没有 process state、heartbeat、ledger、report 或 completion，ledger/request count 为 0。未启动第二进程、重跑或补采，工作区保持干净。唯一判定 `strategy_intent_live_quality_benchmark_invalid`，没有动作、rollout 或质量结果可解释。

只读行号审计显示原 runner 的项目 imports 位于顶层，`main()` 在第 168 行，audit directory 参数读取/校验在 169..171，首次 state 写入在 181，而异常保护从 190 才开始。没有 stderr、exit code 或 traceback，当前只能锁定 `startup_failure_before_state_write`，不能确认是 import、参数、目录还是首次写入。下一步 K-A3d3c1 必须离线建立父级 spawn 前状态与子级 import 前状态；不得联网或沿用旧授权。

K-A3d3c1 首次尝试只读复核 runner 仍为 14,724 bytes，SHA-256 不变，PID `33612` 已退出；随后因 `docs/NEXT_PROMPT.md`、`docs/PLAN.md`、`docs/PROJECT_STATUS.md`、`docs/TESTS.md` 未提交而判定 `strategy_intent_live_startup_hardening_invalid`。该次没有创建 recovery candidate、第二个 live 进程、runner 状态或网络请求，也未读取 `.env`。该判定只表示工作区前置失败，不增加新的 runner 根因证据。

形成 docs 检查点后，K-A3d3c1 在 HEAD `cf9d29cb31fcff2e9b3401b6d68a2db5fe1a37fd` 完成。新 candidate 位于仓库外；`bootstrap_runner.py` 为 5,502 bytes / `776f4504...b01e445`，`launch_bootstrap.py` 为 7,269 bytes / `6a186d7c...e5ca84a`，最终离线审计为 1,281 bytes / `aabebaeb...59af6e`。两次正常 self-check 结构 hash 均为 `ede8bfc3...41e80ec`；四类失败场景均产生预期父/子状态证据。request/network/client/suggest count 全为 0，唯一判定 `strategy_intent_live_startup_hardening_verified`。

K-A3d3c2 随后完成独立恢复前置并取得新授权，锁定 seed `700..709`、`deepseek-v4-flash`、策略 0/50/100、24 pair/48 请求、60 秒、零重试和 65 分钟；未复用 `600..609` 或旧授权，live runner 继承父 spawn 前与子 import 前状态链。

K-A3d3c2 前置通过并取得一次性新授权后，唯一 live run 完成 48/48 请求，off/on 各 24，全部 returned、零重试和零请求失败。父状态链完整，子状态经过 completed 后转为 failed，child exit code=1；report 和 audit summary 已落盘，但 manifest/completion 缺失。源码第 244–245 行错误地从 `audit/` 查找实际位于 candidate root 的 `live_quality_runner.py`，导致 manifest metadata 读取失败。按完整性优先规则，唯一判定 `strategy_intent_live_quality_recovery_invalid`；已生成 report 不进入质量或胜率解释，授权已用尽且未重跑。

下一步 K-A3d3c3a 只允许在新目录运行双份独立只读 verifier，复核原文件 hash、48 条 ledger、report 守恒、状态链和已确认路径缺陷。不得修改原证据或补写 completion/manifest，不得联网。只有恢复完整性全部通过后，才能按原预注册门槛形成新的只读恢复描述性结论；K-A3d3c2 原 invalid 永久保留。

K-A3d3c3a 随后完成：原 9 个文件集合与完整 SHA-256 前后不变，独立 verifier 双运行逐字节一致，48 个请求、24 pair、三策略四阶段及 provider/branch/W-D-L/quality 守恒全部通过，第 244–245 行路径错误得到确认。重新计算 changed=`7`、on/off better=`2/1`、team wins=`8/6`；按预注册顺序首先触发 changed<8，因此唯一新判定 `no_observed_strategy_intent_action_quality_gain`。这不追认 K-A3d3c2，不构成因果或胜率结论，也不授权默认启用。strategy-intent prompt 保持默认关闭，K-A3d3 分支封板。

### Step L：Botzone 本地 AI 接入

状态：Phase 0 至 L4-A3b1 已完成。L4-A3b1 用 direct main 与两次 binary PIPE module capture 独立验证 `preflight_ready` 输出契约，唯一判定 `botzone_live_smoke_recovery_authorization_ready`。下一步 L4-A3c 只能在用户明确授权后启动一次前台 RuleBasedAI 无贡 smoke。详细计划见 `docs/BOTZONE_INTEGRATION_PLAN.md`。

已确认：

- 本地 AI 是本机主动 GET 的长轮询接口，response 通过 `X-Match-<match_id>` Header 在后续 GET 中回传；一次 poll 可承载多个对局；
- Botzone 网关下发的是标准 Bot JSON 交互信封，顶层 `requests/responses` 保存完整交互历史；GuanDan 的 `deal/play` 是 `requests` 中的内层对象；
- 官方 `runmatch` 使用游戏名、位置 Bot ID 和唯一 `me` 创建对局；本地位置不要求上传本机源码；
- Botzone GuanDan 使用 `0..107` 实体牌 ID，协议定义 `deal / tribute / return / play` 四阶段；
- 用户提供的建桌 UI 确认“需要进贡”可选“否”；项目支持范围现锁定为无贡 profile，只运行 `deal + play`；
- play response 是 `[action, claim]`，对应当前 `carrier_cards / declared_cards` 边界；
- 当前 engine 没有贡还/抗贡，且 `Card` 不保存两副同牌的实体 ID；adapter 仍需处理实体 ID，并对贡还 stage 显式 fail-closed；
- play 阶段可以由 integration 构造只含本家手牌、级牌和桌面动作的规则投影，再把 canonical actions 交给 Agent；
- 第一阶段默认 RuleBasedAI，DeepSeek 不进入基础验收。

已解除的 Phase 0 阻塞：

- claim 按牌面多重集匹配，副本等价、顺序无关；integration 将使用更严格的 `0..107` canonical 输出；
- Botzone 最多两张红桃级牌配子，当前 engine 的一张上限记录为合法子集差异；
- 无贡时四次 deal 后直接由 Botzone 玩家 0 首个 play，严格跳过 tribute/return；
- runmatch `X-Initdata` 中“需要进贡=否”的精确表示；该项只阻塞自动建桌，不阻塞已明确选择“否”的手动建桌路径；
- 目标账号可见本地 AI 配置入口；真实 smoke 前必须轮换截图中已暴露的密钥/URL。

推荐实施顺序：L1-A1 codec/protocol → Phase 2 mock connector/session → L2-A1a Phase 3 准入加固 → Phase 3 RuleBasedAI 的 deal + play → Phase 4 用户授权且手动设为无贡的真实 smoke → 可选 runmatch 自动化 → Phase 5 可选 DeepSeek。贡还不在当前范围；收到相关 stage 必须失败，不得绕过。

L1-A1 实现结果：

- 108 实体 ID 全量 round-trip，保留两副副本身份；
- frozen/slots 的 deal、play、history、action/claim 与 unsupported 模型；
- 严格拒绝 bool、非法 ID、重复实体 action、错误长度、未知手牌和 malformed history；
- `tribute/return/unknown` 返回不可执行 `unsupported_stage`；
- 无贡 fixture 锁定四家完整 deal 后由 Botzone 玩家 0 首个 play；
- L2-A1 已提供 poll parser、session store、pending response 基础事务和注入式 fake transport connector；仍没有真实 HTTP transport、runner 或可启动的 live connector。

L2-A1a 已解决：

- claim 含配子时允许虚拟 ID 重复，9/10 张炸弹通过；
- handler 收到按 match 隔离的不可变 context 和当前实体手牌；
- pending play effect 只在 transport 成功后原子扣牌一次；
- latest window 已可验证地合并为累计公开 history。

L2-A1b 已解决随后发现的官方请求差异：

- deal/play 分别使用严格 global 字段集合，无贡 play 接受且只接受 `resist=false`；
- 固定四槽 history 仅接受前缀 `[]`，规范化后只保留真实事件；
- session schema v3 持久化 `local_player_id`，重启、多 match、冲突 deal 和旧 schema 均 fail-closed；
- 纯函数完成 `0..3 → 1..4`，`TableView` 可验证地推导 free lead、桌面领牌和 `pass_on`。

L3-A1 已完成单本家规则投影、RuleBasedAI action-id 选择、实体 ID/claim 回写与 mock connector failure/restart/ack E2E。它保持 engine/agents 不变，只覆盖单配子合法子集。

L3-A1a 已完成：同一轮 single 3→single 4 的 current/history round 均为 1，桌面 action 使用 `action_id=None`；history 固定六字段，手牌稳定排序，外部一/双配子 table action 可重建 canonical declared cards 与 wildcard info；跨历史重复实体、本家已出牌仍在手中、27 张容量与 done 边界均 fail-closed；矛盾 HandlerContext 不创建或调用 Agent。

L4-A1 已完成标准库 HTTPS GET transport、显式 runtime 配置、前台 runner 和 `python -m integrations.botzone` 入口。URL 仅来自显式参数/环境变量且在 repr/错误中脱敏；fake gateway 已验证 pending failure/restart/resend/ack、退避、failure limit、有限 cycle 与 Ctrl+C。未读取 `.env`、未联网。

L4-A1a 已关闭 live 准入缺口：runner 聚合 cycle/request/response/header/finished/diagnostics，并按 interrupt、protocol、finished、failure、wall/cycle 固定优先级停止；finished 原子替换为不含 match/手牌/history/response/digest 的最小 tombstone；response 全路径关闭，Header 为严格 ASCII token；退出码、最小 audit 和零网络 `--preflight-only` 已锁定。

L4-A2a 已完成：工作区干净，两个 Botzone 环境变量 present，state dir 与用户确认路径一致且为空；唯一 preflight-only 返回 `preflight_ready`，之后目录仍为空、网络请求为 0。用户随后明确授权 L4-A2b：RuleBasedAI、手动无贡一局、最多 100 次 GET、最长 600 秒、timeout 30 秒、连续失败 5、finished 1 局即停。下一任务按 `docs/NEXT_PROMPT.md` 启动唯一进程，失败不得重跑。

L4-A2b 首次调用返回 `precondition_failed: checkpoint_head_mismatch`。只读复核确认 `029b8d...` 仍是当前 HEAD 的祖先，之后仅有 `docs/BOTZONE_INTEGRATION_PLAN.md`、`docs/NEXT_PROMPT.md`、`docs/PLAN.md`、`docs/PROJECT_STATUS.md`、`docs/TESTS.md` 五份规划文档变化。该失败发生在进程启动前，没有 GET、audit、state 或网络活动，因此不计为 live run，既有一次性授权保持有效。后续门槛改为“实现检查点为祖先且差异严格限于上述 docs allowlist”；发现任何代码、测试、配置或其他路径变化时仍须 `precondition_failed`。

修正门槛后的 L4-A2b 启动前检查全部通过，但唯一 `Start-Process` 启动尝试因 `launcher_environment_error` 失败。没有 connector PID、GET、live audit 或 state 证据，未重试或启动第二进程。按预注册完整性边界，唯一判定 `botzone_no_tribute_local_ai_smoke_invalid`，该结论不得追认为通过。现有授权未产生实际联网请求，但不得直接用于重试；下一步 L4-A2c1 只使用合成变量和无网络子进程定位 launcher 根因，后续 live 必须重新申请授权。

L4-A2c1 随后完成，唯一判定 `botzone_launcher_environment_diagnosis_verified`。证据目录为仓库外 `guandan-botzone-launch-diagnosis-b7e96cb1b1ec4fbe8ec6ff497735382f`；三份证据分别为 700 / `56f885eb...a3f0d2b`、348 / `76da7669...8ae4faa`、1,358 / `274f0153...a2489e` bytes/hash。PowerShell Desktop 5.1 可用隐藏窗口、工作目录、PassThru 和 Wait，但使用 `RedirectStandardOutput`/`RedirectStandardError` 时可稳定在创建进程前触发 `ArgumentException`；加 `UseNewEnvironment` 仍失败，排除仅环境继承根因。去除 PowerShell 内建重定向、保留合成 sentinel 和其余启动形状后连续两次成功，固定退出码均为 17。根因类别锁定为 `stream_redirection`，全程 request/GET/network/connector count=0。下一步 L4-A2c2 只新增 Python 进程内分流 launcher 与离线平台测试，不修改规则、协议或 Agent；通过后仍须先完成零网络 L4-A2c3a，再申请新的 live 授权。

L4-A2c2 已完成，唯一判定 `botzone_windows_live_launcher_hardening_verified`。新增 `integrations/botzone/live_launcher.py` 与 `tests/test_botzone_live_launcher.py`；PowerShell 只负责无 Redirect 参数的隐藏进程创建，Python 在同一进程内拒绝覆盖地创建独立 stdout/stderr 并调用既有入口。路径、参数、异常、文件关闭与敏感边界均 fail-closed；定向 5、相关 17、全量 520 项通过。两次 Windows 合成平台 probe 均退出 17，sentinel、工作目录、参数和流分离正确，network/GET/connector count=0。当前两个文件仍未跟踪，下一步 L4-A2c3a 必须先独立提交它们并恢复干净工作区，再执行一次新的零网络 preflight；不得直接 live。

L4-A2c3a 已先将 L4-A2c2 独立封存为 `30d9b5897d97939f64dab32b97772118c72ef3d1`，提交范围精确且 5 / 17 / 520 项回归通过。恢复准入 metadata、空 state dir、无残留进程和工作区均通过，但第一项 `python -m integrations.botzone --preflight-only` 在 30 秒离线上限内没有返回 `preflight_ready`；因此第二项 launcher probe 未执行，未重试。脱敏 summary 为 522 bytes / `9c4ed801...bc00b2`。唯一判定 `botzone_live_launcher_recovery_preflight_invalid`；state 与工作区事后仍为空/干净，request/GET/network/connector count=0。本结果不能通过增加 timeout 或重跑来覆盖；下一步 L4-A2c4a 只用合成 URL、临时 state 和独立阶段 heartbeat 区分 import/config/file-op/process-exit 阻塞，不请求 live 授权。

L4-A2c4a 随后判定 `botzone_preflight_timeout_diagnosis_inconclusive`。`python_startup` 在 1 秒内成功；第二阶段 `runtime_config_import` 在 1 秒内以 `ModuleNotFoundError` 退出，因为仓库外临时脚本被直接执行时仓库根不在子进程 import path。该结果不是项目 import 超时的有效复现，根因保持 `unknown`；阶段 3–8 未执行。新证据为 `phase_probe.py` 5,122 / `d794c5a2...b58c4f`、`driver.py` 2,757 / `0eedb86a...41cfb9`、`diagnosis.json` 575 / `d479ea2f...47b718` bytes/hash。旧证据未改，所有网络/connector 计数为 0。下一步 L4-A2c4b 必须在正式阶段前用 `cwd=repo root`、`python -c + runpy` 连续两次验证 cwd/sys.path/spec/origin；资格失败不得再次消耗正式矩阵。

L4-A2c4b 已完成，判定 `botzone_preflight_timeout_diagnosis_recovery_inconclusive`。两次 qualification 的 cwd/path/spec/origin 全部为 true；八阶段和阶段 8 的全新目录复验全部在 1 秒内退出 0，最后 heartbeat 均为 `completed / exit`。有效合成环境未复现 30 秒超时，根因规范化为 `not_reproduced`。新证据为 `runpy_probe.py` 5,797 / `87a385bf...dcdb7b`、`driver.py` 3,941 / `51e5fb96...e20012`、`summary.json` 2,432 / `38d7bda0...fbd3e`、`manifest.json` 1,425 / `30f01deb...08376` bytes/hash；旧证据不变，所有网络/connector 计数为 0。下一步不再重复黑盒 preflight；L4-A2c5a 新增轻量专用入口，在导入 runtime 前先写 audit，并通过 state file-op callback 持续原子记录阶段。通过后才允许单独运行一次真实环境零网络 preflight。

L4-A2c5a 已完成，判定 `botzone_instrumented_live_preflight_contract_verified`。新增 `live_preflight.py` 与专属测试，并为 `preflight_state_directory()` 增加默认关闭的 keyword-only stage callback。专用入口在延迟 runtime import 前原子写 bootstrapping，累计记录配置和 `resolve` 至 `cleaned` 的 state 阶段；退出码 2/3/4/5/70/130 与固定成功输出已锁定。定向 10、相关 23、全量 526 项通过；合成子进程 10 秒内退出 0，state 为空、audit 完整，边界扫描无 transport/runner/connector/session/adapter 导入，全部网络计数为 0。三个文件随后已独立封存为 `8ceb038d3dc6d6a4cfae3525b2bc92b2cc6da78c`；该契约通过不代表真实环境 preflight 或 live 已通过。

L4-A2c5b 已完成，唯一判定 `botzone_instrumented_live_preflight_invalid`。L4-A2c5a 已独立封存为 `8ceb038d3dc6d6a4cfae3525b2bc92b2cc6da78c`，范围精确且 10/23/526 回归与 `git diff --check` 通过。唯一真实环境 preflight 在 30 秒上限内未返回，终止后 audit 最后为 `running / directory_ready`，未到 `temporary_opened`，stdout/stderr 为空；state 仍为空且全部网络计数为 0。证据为 preflight 262 bytes / `770f567b...36a4365b2`，两个空流文件均为 `e3b0c442...b855`。这只能把阻塞区间限定在 `NamedTemporaryFile(...)` 返回前，不能推断权限、杀毒软件、磁盘或 Python 根因。随后执行的 L4-A2c5b1 只使用仓库外标准库载体逐项诊断候选名生成、独占创建、写入、同步、替换和清理，未重跑 preflight 或进入 live。

L4-A2c5b1 已完成，唯一判定 `botzone_state_tempfile_operation_boundary_verified`。临时目录资格验证低于 1 秒完成；真实 state 目录唯一诊断 exit code 5，最后阶段为 `exclusive_open_started`，没有 `exclusive_open_completed`，规范化诊断 `operation_error`。任务自有候选文件随后精确清理成功，真实目录前后均为空，全部网络计数为 0。证据为 `state_probe.py` 6,192 / `f86ea0c6...468c320`、`driver.py` 4,587 / `ba34fd1d...434488`、`summary.json` 3,127 / `0851b694...52bbc1` bytes/hash。该结果只定位到 `os.open(O_CREAT|O_EXCL|O_RDWR)`，未记录足以解释原因的脱敏 errno/winerror，也没有目录对照。随后执行的 L4-A2c5b2 保持零网络和仓库不变，尝试以当前目录、同卷全新目录、本地应用数据全新目录的固定矩阵确认错误分类和影响范围。

L4-A2c5b2 已完成，唯一判定 `botzone_exclusive_open_scope_diagnosis_invalid`。qualification 成功；configured state 与 same-volume fresh 均为 `PermissionError`、errno 13、winerror null，候选不存在且目录清空。但父载体把 local-appdata 的证据子目录与目标目录设为同名，第三项在探针启动前退出；summary/manifest 均未生成。旧结果不能形成目录范围，也不能归因。证据为 probe 5,908 / `469a2f9d...bf235b`、driver 5,341 / `56773435...b4be3`，三个 audit 分别 325 / `1f61f6d5...f3aba`、434 / `04f6d2e9...305de4`、435 / `985384cf...064ee` bytes/hash；已产生流均为空。当时规划的 L4-A2c5b2a 需要新 run ID、新脚本和路径拓扑验证，但现已暂缓；不得补齐或追认本次 invalid。

随后用户以仓库外本地应用数据目录手工启动前台 connector。Botzone 页面先显示已连接，证明 URL、GET 长轮询和网关链路可达；创建明确无贡的测试桌后，connector 在第一个对局请求退出，聚合 audit 为 `cycles=1`、`requests_seen=1`、`malformed_request=1`、`responses_prepared=0`、exit code 5。平台显示的“决策超时”是 connector 未返回合法响应的结果，不是 RuleBasedAI 或模型推理超时；本次 Agent 尚未被调用。

用户提供的真实消息结构与官方 Bot JSON 文档共同确认：顶层是 `requests/responses` 交互信封，首条内层 `deal` 提供本家座位和 27 张实体牌，最新内层请求为 `play`；不能只提取最后一项。当前 `poll.py` 直接把顶层对象传给只接受顶层 `stage` 的 `parse_stage_request()`，因此必然触发 `malformed_request`。真实 `play.global` 还包含空的 `tribute_cards/return_cards`，标准 Bot 输出需要 `{"response": ...}` 包装。真实牌 ID 和原始请求不得进入仓库。

L4-A2c5b2a 文件系统恢复矩阵暂缓，既有 invalid 结论不变。当前关键路径改为 L4-A3a：离线实现外层信封模型、完整历史重放、无贡 global 加固和 canonical response wrapper；通过后才允许规划全新的手工 smoke。

L4-A3a 已完成，唯一判定 `botzone_bot_json_envelope_contract_verified`。新增 `integrations/botzone/bot_io.py`，并更新 poll、connector、session 与 protocol：外层严格校验 `requests/responses` 基数，首条无贡 deal 与历史 play response 可冷启动恢复实体手牌，Header 前统一包装 `{"response": ...}`，空 `tribute_cards/return_cards` 纳入无贡契约；pending/ack/effect 与多 match 隔离边界保持不变。定向 47、全量 532 项和 `git diff --check` 通过，敏感与网络边界扫描通过。本步未联网、未修改 engine/agents/CLI/RAG/evaluation，也不追认旧 smoke。

L4-A3b 已完成 L4-A3a 检查点 `2ac51fb2c80a5a0ae4b7dabd4f2aa161e11f1498`，精确提交 19 个 allowlist 文件；提交后工作区干净，定向 50、全量 532 项与 `git diff --check` 通过。随后唯一零网络 preflight 使用全新 LocalAppData 目录，30 秒内 exit 0、stderr 空、目录前后为空并删除，request/GET/network/connector 均为 0；但监督结果 `stdout_is_preflight_ready=false`，且没有合格原始 stdout bytes，故唯一判定 `botzone_envelope_live_smoke_preflight_invalid`，不请求 live 授权。

入口代码显示 preflight 成功分支先打印 `preflight_ready` 再 return 0，但这不足以追认缺失的原始输出。当时规划的 L4-A3b1 纯测试契约要求：直接 main 捕获精确文本，并用两个合成 URL/临时目录的 module 子进程通过 binary PIPE 接受严格 UTF-8 的 LF 或 CRLF 单行；不得读取真实环境或重跑真实 preflight。该契约现已按下一段结果完成。

L4-A3b1 已完成，唯一判定 `botzone_live_smoke_recovery_authorization_ready`。新增 `tests/test_botzone_preflight_output.py`；direct main exit 0、输出精确 `preflight_ready\n`、state 空且 transport/opener 构造为 0，两次独立 module binary PIPE 均 exit 0、仅含合法 LF/CRLF 单行、normalized lines 一致、stderr 与 state 为空。定向 2、相关 18、全量 534 项与 `git diff --check` 通过，检查点为 `28de0cb36f7356bc35ade874fa8f75fa63b1f331`。该恢复结论不改写 L4-A3b invalid，也未读取真实配置或联网。

下一步 L4-A3c 已锁定为：当前环境 URL、前台单进程 RuleBasedAI、全新手动测试桌且“需要进贡=否”、全新 LocalAppData state/audit、timeout 120 秒、最多 100 GET、最长 900 秒、完成 1 局即停且不重试。用户已在紧接固定授权问题后明确回复“授权”；执行任务核对该消息后可进入启动前门槛。

## 6. 当前风险

1. 同时改阶段、猜牌、RAG 和策略会导致无法判断收益来源。
2. pass 是策略行为，不能作为“对方没有可压牌”的硬证据。
3. 无条件 pass 扣分已撤销；不得以 runtime confidence 名义重新引入该信号。
4. RAG 条目增加会扩大提示词，必须同步控制 token。
5. 当前没有 A/B 对局工具，策略增强暂时只能声明“已接入”，不能声明“已提升”。
6. 单局复盘容易把隐藏真值误当成玩家当时已知信息；每个建议必须区分公开可知、事后可知和需要 rollout 才能判断的内容。
7. Botzone 建桌若误设为需要进贡，会进入当前项目明确不支持的 stage；连接器必须验证无贡 profile，并拒绝 `tribute/return`。
8. Botzone 本地 AI URL/密钥位于连接 URL 中，任何日志、异常、fixture 或文档示例泄露都会构成安全问题。

## 7. 项目管理规则

- 每轮只推进一个可独立验收的里程碑；
- 先更新 docs，再写测试，再实现；
- 每轮结束必须更新本文件；
- 没有测试或数据时，不把推测写成完成；
- 引擎规则与 AI 策略保持分离；
- 新增依赖前必须说明理由；
- 不修改 `.env`、密钥或生产配置；
- 临时运行输出不得纳入源码提交。

## 8. Botzone L4-A3c 封板

- 唯一判定：`botzone_no_tribute_local_ai_smoke_invalid`。
- 唯一前台 connector 自行退出：`cycles=1`、`finished=0`、exit 5。
- 脱敏 audit：`requests_seen=1`、`responses_prepared=0`、`headers_sent=0`、`transport_failures=0`，诊断为 `malformed_request=1`。
- state 目录为空；未产生可发送 response，未完成任何一局。
- 请求在用户确认新建无贡测试桌前到达，不能证明来自新桌，也不能排除旧 match 重放。
- 现有 `malformed_request` 同时覆盖 JSON 与 envelope 多类错误，无法定位失败层级。
- 本次授权已消耗，不得重试或补采。下一步只做 L4-A3c1 离线分层脱敏诊断。

## 9. Botzone L4-A3c1 结果

- 唯一判定：`botzone_malformed_request_safe_diagnostics_verified`。
- 固定对外诊断：`request_json_invalid`、`envelope_shape_invalid`、`inner_request_invalid`、`historical_response_invalid`、`replay_history_invalid`；未知异常回退 `malformed_request`。
- 合法 envelope、replay、digest、response wrapper、pending/ack 与 Agent 边界保持不变。
- 非法输入不调用 Agent、不准备 response、不发送 Header，connector 仍以 `diagnostic_failure` 停止。
- 新诊断 4 项、相关 Botzone 22 项、全量 538 项、diff check 与边界扫描通过。
- 实现已独立提交为 `1924db4a398db2641c4ba8e9dcf8a71a79a9388f`。

## 10. Botzone finished 假完成封板

- 唯一判定：`botzone_no_tribute_local_ai_smoke_invalid`。
- 唯一 connector：exit 0、`finished_target`、cycles 1、finished 1，但 request/response/header 为 `0/0/0`。
- 无 transport failure、无 diagnostics、state 为空，说明退出路径本身安全，但没有任何协议交互。
- 根本契约缺口：runner 将全部 finished rows 直接视为完成目标，未验证它们是否属于本进程处理并回传 play response 的 match。
- 本次授权已消耗，不得重跑。下一步只做 L4-A3d1 离线 finished provenance 加固。
