# 牌面信念状态设计

## 1. 目的

牌面信念状态用于把公开历史转换为可审计的未见牌池和逐玩家弱推断，为中局策略和残局决策提供结构化输入。

它不是规则真值，也不能访问其他玩家真实手牌。

当前状态：Step J-A 至 J-D1c3c2b2 已完成；默认关闭的 DeepSeek prompt 接线已通过 345 项全量测试。下一步为 J-D1c3c2c1 配对 prompt 覆盖与成本基准；默认策略消费继续暂停。

## 2. 数据来源

只允许读取：

- `observation.my_info.hand_cards`
- `observation.other_players`
- `observation.history.actions`
- `observation.history.finish_order`
- 可选的公开 `GamePhaseContext`

测试和离线评测可以使用预设真实手牌计算准确率，但真实手牌不得传入运行时推断器。

J-B 只消费 J-A 生成的 `CardBeliefState`，不得重新读取引擎内部状态。

## 3. 基础牌池

两副牌共 108 张：

- 普通点数 `3` 到 `2`，每个花色 2 张；
- `SJ` 2 张；
- `BJ` 2 张。

历史动作优先按 `carrier_cards` 扣除真实牌；只有旧历史缺少该字段时，才回退到 `declared_cards`。

## 4. 输出结构

建议输出：

```text
phase
external_unknown_count
unseen_cards_by_token
unseen_cards_by_rank
players:
  player_id
  relation
  remaining_count
  played_cards
  pass_count
  confirmed_cards
  possible_ranks
  likely_ranks
  confidence
diagnostics
```

## 5. 证据等级

- `public_fact`：自己手牌、真实已出牌、公开剩余张数。
- `hard_constraint`：牌池守恒、玩家容量、唯一可行分配。
- `soft_signal`：pass、首出牌型、拆牌、保炸倾向等行为。

只有 `public_fact` 和逻辑唯一的 `hard_constraint` 可以产生 `confirmed_cards`。

`soft_signal` 只能影响排序和置信度。

## 6. pass 处理

pass 不能推出“该玩家没有能压的牌”，因为玩家可以策略性 pass。

允许记录：

- pass 的桌面牌型；
- 当时剩余牌数；
- 当时是否接近残局；
- 对相关点数或牌型的低权重负向信号。

禁止把 pass 直接转换成硬排除。

## 7. 阶段目标

### 开局

- 精确记录已出牌；
- 只突出王、级牌、A 和潜在炸弹点数；
- 不做高置信度逐玩家猜牌。

### 中局

- 引入逐玩家已出牌结构；
- 区分队友与对手；
- 维护可能控制牌和可能炸弹的弱信号。

### 近似明牌残局

- 展示全部未见牌；
- 使用玩家剩余容量约束；
- 枚举或传播可行分配；
- 输出候选数量、边际概率和置信度；
- 候选不唯一时明确保留不确定性。

## 8. 验收原则

- 牌池守恒优先于猜牌覆盖率；
- 错误的确定结论比没有结论更严重；
- 置信度必须能通过离线 ground truth 校准；
- 推断错误不能影响合法性判断；
- 推断器异常时，AI 必须仍能基于 observation 和合法动作继续运行。

## 9. 实施拆分

### Step J-A：公开事实层

状态：已完成。

已实现：

- 108 张基础牌池；
- 自己手牌扣除；
- 历史真实 `carrier_cards` 扣除；
- 按玩家记录已出牌和 pass 次数；
- 记录其他玩家公开剩余容量；
- 输出点数级和 token 级未见牌；
- 对旧格式、重复扣牌和数量不一致输出诊断。

本阶段不输出隐藏牌概率，不把任何未知牌标为 `confirmed`。

验证：

- 定向测试 31 项通过；
- 全量测试 141 项通过；
- 异常输入只产生诊断，不尝试补全隐藏牌。

### Step J-B1：所有权域与容量约束

状态：已完成。

- 玩家容量约束；
- token/点数级可能归属集合；
- 完赛玩家、零容量玩家和自己从外部归属域排除；
- 容量总和、空归属域和不精确输入诊断；
- 只有输入精确、容量一致且逻辑唯一时才能产生隐藏 `confirmed_cards`。

本阶段不使用 pass 排除归属，不输出概率，不枚举完整残局分配，不接入策略主链。

### Step J-B2：有限残局分配

状态：已完成。

- 只消费 J-A 的精确 token 计数和 J-B1 的硬归属域；
- 仅在外部未知牌不超过 12 张且输入一致时枚举；
- 把相同 token 的副本作为计数分配，避免重复计算副本排列；
- 严格满足每位玩家公开剩余容量和每个 token 的归属域；
- 输出完整可行分配数量、每位玩家每种 token 的最小/最大持有数；
- 只有完整搜索的所有可行解都保证持有时才能确认对应副本；
- 设置搜索节点和解数量上限，并输出截断诊断；
- 搜索被截断、输入不精确或不一致时不得输出新确认。

### Step J-C1：离线真值评测

状态：已完成。

- ground truth 只进入离线评测函数，不进入运行时推断器；
- 校验真实外部手牌 multiset 与 J-A 未见牌池完全一致；
- 评估真实持牌玩家是否在 token 可能归属域中；
- 评估 `confirmed_cards` 的正确副本数、错误确认数、精确率和覆盖率；
- 完整 J-B2 结果评估真实 token 数是否落在最小/最大持有数内；
- 输出结构化、可序列化的评测报告，不回传真实手牌。

### Step J-C2a：公开行为事件

状态：已完成。

- 从公开 history 重建 pass 所响应的最近有效非 pass 动作；
- 区分每轮首出与跟牌；
- 保留声明牌、真实 carrier、逢人配声明差异和公开牌型；
- 按玩家聚合 pass、首出、跟牌、牌型和高价值牌释放计数；
- 异常历史只产生诊断，不伪造事件上下文；
- 本阶段只输出事实事件，不产生分数、候选排序或隐藏牌结论。

### Step J-C2b1：最小软评分与候选排序

状态：已完成。

- 候选集合从 J-B1 或完整 J-B2 硬域生成；
- confirmed rank 保持硬约束最高优先级；
- 仅将“对敌方单张选择 pass”转换为小幅、有上限的负分；
- 队友单张、非 single、孤立 pass 和坏响应链不产生该负分；
- 每个分数变化带 action index、响应 action index 和领先点数；
- `likely_ranks`；
- 同分只表示同一 score tier，序列化顺序不代表额外置信。

### Step J-C2b2：Top-K 评测与权重消融

状态：已完成。

- 从 soft ranking 自动派生候选集合相同的零软分基线；
- 扩展离线评测以支持 score tier 并列；
- score tier 跨越 K 时整组纳入，稳定 rank 顺序不决定命中；
- 对比零软分基线与实际软排序；
- 记录 Top-1/Top-3 召回、实际选择规模、精确率和最坏位置 MRR；
- 输出指标 delta，但不根据单个手工样本声明启发式有效；
- 没有多样本改善证据时不增加更多行为启发式。

### Step J-C3a：多种子离线残局基准

状态：已完成。

- 用固定种子和现有确定性规则 AI 推进完整对局；
- 只在 `near_open_endgame` 与 `critical_endgame` 采集公开 observation；
- 对每个样本运行 J-A、J-B1、J-B2、J-C2a、J-C2b1、J-C2b2；
- 真实手牌只由离线评测器从引擎状态提取，不进入 `agents/`；
- 报告按阶段和总体聚合，不包含逐样本真值或可逆明细；
- 聚合原始计数并重算比例，MRR 按真实 rank 数加权；
- 记录游戏数、候选样本数、有效/无效/跳过数和诊断频次。

开发试跑 seed `0..19` 只用于确定正式运行容量。默认每局 24 样本产生明显截断，因此正式基准使用更高上限并要求 `sample_limit_skipped_count=0`。

### Step J-C3b：预注册正式基准与启发式验收

状态：已完成。

- 固定独立 seed `1000..1199` 和全部运行参数；
- 在运行前定义主指标、护栏和保留门槛；
- 同一输入运行两次并校验报告和 canonical JSON hash 一致；
- 根据结果决定保留、调整或撤销 `opponent_single_pass`；
- 不用同一批样本反复调参并宣称泛化提升。

正式结果：

- 200 局全部完成，8719 个样本全部有效；
- near-open 3260 样本，critical 5459 样本；
- candidate recall 与 Top-1/Top-3 recall 无回退；
- overall Top-1/Top-3 precision 分别增加 `0.007357` / `0.006385`；
- overall worst-case MRR 增加 `0.003233`；
- 判定为保留进入策略分布验证，不代表 runtime 可用。

### Step J-C3c1：策略分布基准载体

状态：已完成。

- 增加存在合法压制动作但选择战略性 pass 的公开轨迹；
- 区分规则 AI 的被迫 pass 与其他策略的主动 pass；
- 输出每种策略的机会数、主动 pass 数和安全聚合 rank 指标；
- 保持 J-C3a 默认 RuleBasedAI 行为与报告不变。

### Step J-C3c2：策略分布稳健性验收

状态：已完成，判定拒绝无条件 pass 信号。

- 固定独立 seed、四种 pass rate 和运行参数；
- Top-1/Top-3 recall 是首要护栏，MRR 改善不能抵消真实 rank 召回损失；
- 使用独立于 J-C3b 的样本验证方向和召回护栏；
- 未通过时不得用 RuleBasedAI 结果校准 runtime 置信度。

正式结果显示 25% 战略 pass 已使 overall Top-3 recall 降低约 9.30 个百分点，near-open/critical 均明显失败。MRR 上升不改变拒绝结论。

### Step J-C3d1：恢复零软分安全基线

状态：已完成。

- 移除 `opponent_single_pass` 默认负分；
- hard candidates、confirmed 和 score tier 契约保持稳定；
- possible candidates 的 soft score 归零且 evidence 为空；
- pass 事件继续保留在公开事实层，但不直接转成持牌结论；
- 通用软证据数据结构保留给未来经过独立验收的新信号。

### Step J-C3d2：neutral ranking 回归

状态：已完成，判定 `neutral_baseline_verified`。

- 使用独立 seed `3000..3049` 和四种 pass 策略；
- 同一参数完整运行两次并校验 canonical JSON hash；
- forced-only 与战略 pass 轨迹的 soft/baseline 指标应完全一致；
- candidate 和 Top-K recall delta 均为 0；
- 确认撤销后不再存在策略分布导致的错误降级。

### Step J-D1a：物理分配权重

- 状态：已完成；
- 只在完整 J-B2 搜索中统计；
- 每个 token 的相同牌面副本视为物理可区分副本；
- count matrix 的权重使用精确多项式系数；
- 聚合总物理分配权重、逐玩家 token 持有权重和副本数加权和；
- 使用 Python 整数，不输出浮点概率；
- 截断、跳过、无解和无效结果不暴露部分边际。
- 新增 `physical_assignment_count`、`holding_assignment_count_by_token` 和 `copy_assignment_count_by_token`；
- 定向 132 项、全量 256 项测试通过。

### Step J-D1b：rank 精确整数边际

- 状态：已完成；
- 在每个完整 count matrix 上先按玩家汇总同 rank 的 token 副本数；
- rank 副本数分子可以汇总 token 副本分子，但 rank 持有分子必须按事件并集计数；
- 对同一玩家、同一 rank、同一 matrix 最多增加一次持有权重；
- 继续只输出 Python 整数，不计算 float、概率或置信度；
- 不完整结果的 rank 边际必须为空；
- 不再把 pass 本身解释为确定或默认的无牌证据。
- 新增 `holding_assignment_count_by_rank` 与 `copy_assignment_count_by_rank`；
- 定向 139 项、全量 263 项测试通过。

### Step J-D1c1：单样本概率评分

- 状态：已完成；
- 仅在 `evaluation/` 消费完整 J-D1b 与显式 ground truth；
- 使用 `physical_assignment_count` 作为共同分母；
- 对逐玩家/逐 rank 持有事件计算精确 Brier 和校准分桶充分统计量；
- 对 rank 副本期望计算精确平方误差充分统计量；
- 使用整数和 `fractions.Fraction` 聚合，报告 JSON 中只保留整数分子/分母；
- 报告不得包含玩家-rank 真值明细、真实 token 或真实手牌；
- 不完整或不一致的 allocation 必须 fail closed。
- 新增 presence Brier、copy 平方误差和十档预测和的精确分数；
- 定向 152 项、全量 276 项测试通过。

### Step J-D1c2a：多样本精确聚合

- 状态：已完成；
- 对 valid 单样本报告做原始充分统计量微聚合；
- 使用 `Fraction` 跨不同物理分母求和，不平均单样本比例；
- 输出精确 Brier mean、copy MSE、ECE、MCE 与确定性错误率；
- 聚合十档 prediction count、prediction sum 与 truth positive count；
- invalid 样本只进入无效计数和规范化 diagnostics。
- 输出精确 Brier mean、copy MSE、正例率、确定性错误率、ECE 与 MCE；
- 定向 166 项、全量 290 项测试通过。

### Step J-D1c2b：固定种子采集器

- 状态：已完成，判定 `development_capacity_verified`；
- 由于 J-D1b 默认精确上限为 12 张，首个采集器只把 `critical_endgame` 作为可评分目标；
- 使用开发固定 seed 采集完整分配样本，不把 near-open 的 13..20 张跳过结果混入校准；
- 按外部未知牌 `0..4`、`5..8`、`9..12` 分桶；
- 先建立 neutral 组合模型基线，不叠加 pass 或其他软信号；
- 开发试跑只测完成率、有效样本量、截断和运行成本，不形成正式校准结论。
- seed `40..59` 双运行 hash 一致，20/20 局和 522/522 样本完成；
- 无 invalid、skip、diagnostics 或 certainty error；
- 定向 179 项、全量 303 项测试通过。

### Step J-D1c2c：正式校准

- 状态：已完成，判定 `retain_for_policy_diverse_calibration`；
- 独立 seed 固定为 `5000..5099`，两次各 100 局；
- 对 overall、阶段桶和外部牌数桶运行双次可重复验收；
- 完整性、Brier skill、ECE、支持度 MCE 和 certainty error 使用预注册门槛；
- 正式语料不得用于调桶或修改模型。
- seed `5000..5099` 双运行 hash 一致，100/100 局和 2727/2727 样本完成；
- 数据完整性、certainty、ECE、Brier skill 和 supported MCE 门槛全部通过；
- 结论只覆盖默认 RuleBasedAI 轨迹。

### Step J-D1c3a：策略分布载体

- 状态：已完成，判定 `policy_diversity_capacity_verified`；
- 复用 evaluation-only `StrategicPassAIAgent` 的 0/25/50/100% 变体；
- 每个策略独立运行 marginal corpus，不共享 game、agent 或计数器；
- 同时报告战略 pass 机会数、主动 pass 数和完整 calibration bucket；
- 先用开发 seed 验证容量、行为梯度和双运行确定性；
- 不在该步骤设置 runtime confidence。
- seed `60..69` 双运行 hash 一致，四策略各 10/10 局完成；
- opportunity/pass 行为梯度正确，所有 corpus 无 invalid、skip 或 diagnostics；
- 定向 187 项、全量 311 项测试通过。

### Step J-D1c3b：多策略正式校准

- 状态：已完成，唯一判定 `benchmark_invalid`；
- 独立 seed `7000..7049`，四策略各 50 局并完整双运行；
- 双运行 SHA-256 均为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 数据完整性、策略行为和 15/16 个范围的护栏通过；
- `strategic_pass_100 / external_0_4` 只有一个 count>=100 的 calibration bin，支持度前提失败；
- 该结果不得解释为 runtime confidence 准入、模型拒绝或策略收益结论。

### Step J-D1c3b2：独立扩容复验

- 状态：已完成，判定 `policy_diverse_calibration_verified`；
- 冻结 J-D1c3b 的实现、策略、十档分桶、支持阈值和数值护栏；
- 排除所有历史开发与正式 seed，使用 `8000..8119`，四策略各 120 局并完整双运行；
- J-D1c3b 数据只用于样本量规划，不参与 J-D1c3b2 指标或判定；
- 双运行 SHA-256 均为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 四策略所有对局完成，invalid、skip、diagnostics 均为 0；
- 16 个范围全部通过支持度、certainty、ECE、Brier skill 和 supported MCE 护栏；
- 该结论只授权设计 runtime confidence 数据契约。

### Step J-D1c3c1：runtime confidence 数据契约

- 状态：已实现，待 J-D1c3c1a 边界封板；
- 新模块只消费 J-A/J-B1/J-D1b 不可变结果，不重新解析 observation 或 history；
- 只在 `critical_endgame`、精确一致牌池、完整搜索、正物理分母和外部未知牌不超过 12 张时 available；
- 对逐玩家逐 rank 输出 presence 与 expected-copy 的整数分子/分母；
- 不输出 float、百分比或未经验证的 high/medium/low 标签；
- 任一阶段、玩家、容量、rank、分子范围或跨玩家 copy 守恒异常时整体 unavailable，不保留部分结果；
- runtime 模块不得导入 `evaluation/`，ground truth 不得进入 API；
- 本步骤不接入策略、RAG、DeepSeek、提示词、剪枝或动作选择。

实现验证：

- 新增三层 frozen/slots runtime dataclass 和纯 builder；
- 正常 available 与已覆盖异常路径符合整数分数和整体 unavailable 契约；
- 定向 76 项、全量 318 项测试通过；
- runtime 与 evaluation/ground truth/engine state/decision path 边界扫描通过。

### Step J-D1c3c1a：fail-closed 边界硬化

- 状态：已完成；
- 所有布尔语义字段只接受实际 `True`，拒绝 truthy 非布尔值；
- constraints/allocation 玩家集合必须与公开 active external 玩家集合严格一致；
- 所有 copy 分子完成类型和范围校验后才能参与守恒求和；
- malformed copy 值不得触发 `TypeError` 或泄露部分边际；
- 不改变合法输入输出、公开字段或校准范围；
- 不接入任何决策消费者。

验证结果：

- 四个布尔语义字段严格拒绝 truthy 非布尔值；
- 三层外部候选玩家集合严格一致；
- malformed copy 分子不会进入守恒求和或触发异常；
- 合法 available snapshot 不变；
- 单文件 11 项、相关 80 项、全量 322 项测试通过。

### Step J-D1c3c2a：默认关闭的 shadow 装配

- 状态：已完成；
- 独立 pipeline 复用统一阶段并串联 J-A/J-B1/J-D1b/confidence；
- 非 critical 或任一异常返回 unavailable，不启动不必要枚举；
- agent 显式开关默认关闭，不由环境变量隐式开启；
- 开启时仅保存最后一次 confidence 审计状态；
- confidence 不进入 prompt、RAG、剪枝、策略或 action 选择；
- shadow off/on 必须在固定 observation 和固定 client 返回下选择相同 action ID。

验证结果：

- 非 critical 不启动公开推断或枚举，critical 各层调用一次；
- agent 默认关闭，结果只写 `last_card_confidence`；
- off/on client kwargs、action、fallback 和 decision source 一致；
- 定向 40 项、相关 124 项、全量 331 项测试通过。

### Step J-D1c3c2b1：有界 prompt 序列化

- 状态：已完成；
- 独立 formatter 只消费 `CardConfidenceState`，不读取 observation 或引擎；
- 只接受 available 和固定 source/scope；
- presence/expected copies 使用约分精确分数；
- 全量保留 canonical 玩家/rank 顺序，不做 Top-K 或主观等级；
- 固定字符预算，超限整体 omitted；
- 本步骤不修改 DeepSeek prompt 或任何动作路径。

验证结果：

- ready/omitted payload frozen、JSON 友好且稳定；
- 固定文本使用约分整数分数，无 float、百分比或主观等级；
- 2400 字符预算超限时整体 omitted；
- 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项测试通过。

### Step J-D1c3c2b2：默认关闭的 prompt 消费

- 状态：已完成；
- 新 prompt 开关默认 False，且依赖 shadow 开关；
- 只有 ready payload 进入 DeepSeekClient；
- omitted/unavailable 与纯 shadow prompt 完全相同；
- 固定章节位于记牌信息之后，不改变候选动作、RAG 或输出格式；
- 本步骤只验证接线和兼容性，不形成动作质量结论。

验证结果：

- off、shadow-only、prompt 三态和非法组合已覆盖；
- ready 只新增一个类型化 client keyword 和固定章节；
- omitted/unavailable 与 shadow-only 等价；
- 定向 54 项、相关 48 项、全量 345 项测试通过。

### Step J-D1c3c2c1：配对 prompt 覆盖与成本基准

- 状态：下一步；
- evaluation-only，不调用 DeepSeek API；
- 四策略 critical 样本分别构建 off/on prompt；
- 统计 confidence available、payload ready/omitted 和规范诊断；
- 统计 payload 字符数和 on-off prompt 字符增量；
- ready 样本必须证明 on prompt 等于 off prompt 的一次固定章节插入；
- 报告只含聚合统计和哈希，不含 prompt 或 observation。

### Step J-D1c3：runtime 准入判定

- 在正式运行前预注册校准与安全门槛；
- J-D1c3b2 已授权设计 runtime 置信度输出契约；
- 只有 J-D1c3c2c1 开发覆盖、J-D1c3c2c2 正式覆盖和 J-D1c3c2c3 动作消融依次通过，才允许默认策略读取；
- ground truth 只存在于 `evaluation/`，不得进入 runtime 推断。

### 暂停：置信度校准

- 用离线样本校准置信度区间；
- 做无软信号、分信号和组合信号消融；
- 只有指标达到预设门槛后才允许进入策略主链。

J-C 不得反向污染 J-A 的公开事实或 J-B 的硬约束，ground truth 永远不得进入 runtime observation。
