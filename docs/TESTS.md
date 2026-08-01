# GuanDan 测试与验收

## 1. 测试入口

全部测试：

```bash
python -m unittest discover -q
```

核心规则回归：

```bash
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q
```

AI 优化相关测试：

```bash
python -m unittest tests.test_hand_evaluator tests.test_card_tracker tests.test_action_pruning tests.test_opening_strategy tests.test_rag_step_h tests.test_deepseek_prompt_step_h tests.test_deepseek_step_e -q
```

## 2. 必须长期通过的测试

### 规则和接口

- 牌型识别、逢人配、王类白名单和顺子边界；
- 合法动作生成、同型和跨型压制；
- `reset()`、`observe()`、`legal_actions()`、`step(action_id)`；
- 接风、三游终局、末游、胜负和平局；
- AI 返回值始终来自当前合法动作集合。

### 本地快捷路径

- 仅有 `pass` 时不调用评分、记牌、RAG 或 DeepSeek；
- 存在一次出完动作时直接本地选择；
- 公式化开局命中时跳过 RAG 和 DeepSeek；
- 本地策略返回的 ID 必须来自原始 `legal_actions`。

### 动作剪枝

- 剪枝结果是原始合法动作的子集；
- 不合并 `carrier_cards`、逢人配声明或动作 ID 不同的动作；
- 跟牌保留 `pass`、压制动作、逢人配动作和一次出完动作；
- 提示词展示上限不能移除关键动作；
- 最终合法性校验仍针对原始合法动作集合。

### RAG

- 规则库和经验库 front matter 可解析；
- `scene / phase / hand_strength / action_context` 标签完整；
- 规则证据和经验依据分层；
- 冲突或越界条目不能进入 accepted evidence；
- 无匹配或检索异常不能破坏本地决策；
- RAG 不生成或执行动作。

## 3. Step I：阶段分类测试

新增阶段分类器后必须覆盖：

- 历史 0 和 8 个动作仍属于 `opening`；
- 历史 9 个动作进入 `midgame`；
- 自己 9 张进入 `endgame`；
- 任一其他玩家 5 张进入 `endgame`；
- 已有完赛玩家进入 `endgame`；
- 外部合计 20 张进入 `near_open_endgame`；
- 外部合计 12 张进入 `critical_endgame`；
- 临界值优先级正确；
- 开局、RAG、剪枝使用同一个阶段结果。

## 4. Step J：牌面信念测试

### J-A：公开事实层

状态：已完成。`tests/test_card_belief.py` 与兼容测试共 31 项通过，全量 141 项通过。

- 初始完整牌池为 108 张；
- 自己手牌和历史 `carrier_cards` 从未见牌池正确扣除；
- 同一点数同一花色的两副牌副本计数正确；
- 王各 2 张，普通牌每个花色各 2 张；
- 逢人配声明使用真实 `carrier_cards`，不能把声明牌当作真实已出牌；
- 旧历史缺少 `carrier_cards` 时才回退到 `declared_cards`；
- 不合法或重复历史产生诊断信息，而不是静默得到负计数。

### J-B1：所有权域与容量约束

状态：已完成。J-B1 与兼容测试共 43 项通过，全量 153 项通过。

- 只消费 J-A 的 `CardBeliefState`；
- 自己、已完赛和零容量玩家不进入外部未知牌归属域；
- token/点数归属域覆盖全部仍可持牌的外部玩家；
- 玩家公开剩余容量总和与未见牌总数一致；
- 输入不精确、容量冲突或空归属域产生诊断；
- 多个候选玩家存在时不产生 `confirmed_cards`；
- 只有硬约束唯一且输入一致时才允许确认；
- pass 次数不能缩小硬归属域。

### J-B2：有限残局分配

状态：已完成。J-B2 与兼容测试共 61 项通过，全量 171 项通过。

- 只在外部未知牌不超过 12 张、token 精确且约束一致时枚举；
- 相同 token 副本按计数分配，不重复计算副本排列；
- 每个完整解满足 token 总数、玩家容量和 J-B1 所有权域；
- 输出完整可行分配数量及逐玩家 token 数量上下界；
- 无可行解时输出诊断且不确认；
- 搜索节点或解数量达到上限时标记截断；
- 截断搜索不得输出唯一性结论；
- `confirmed` 只能来自所有完整可行解一致保证的副本。

### J-C：软推断与校准

#### J-C1：离线真值评测

状态：已完成。J-C1 与兼容测试共 78 项通过，全量 188 项通过。

- ground truth 与 J-A 未见 token multiset 不一致时拒绝评分；
- 真实持牌玩家进入 token 归属域时计为覆盖；
- 重复 token 按副本数统计确认正确数和错误数；
- 完整 J-B2 的真实持牌数必须落在对应 min/max 内；
- 截断、跳过或无解结果不得按完整上下界评分；
- 零分母指标有确定值，不产生异常或 NaN；
- 评测结果不包含或序列化真实手牌。

#### J-C2a：公开行为事件

状态：已完成。J-C2a 与兼容测试共 92 项通过，全量 202 项通过。

- 同一轮 pass 链接到此前最近一次非 pass 动作；
- 跟牌更新后，后续 pass 链接到新的桌面动作；
- 新 round 的首个非 pass 标为首出；
- 不存在前置非 pass 的孤立 pass 只产生诊断；
- 声明牌与真实 `carrier_cards` 分别保留；
- 每位玩家的 pass、首出、跟牌和牌型计数正确；
- 格式错误历史不导致异常或伪造证据；
- 输出不含可能归属、概率、置信度或确认牌。

#### J-C2b1：最小软评分与候选排序

状态：已完成。J-C2b1 与兼容测试共 107 项通过，全量 217 项通过。

- 候选 rank 只来自硬归属域；
- 完整 J-B2 可收窄候选，不完整结果回退 J-B1；
- confirmed rank 不受软负分影响；
- 对敌方 single 的有效 pass 只降低可压过该 single 的候选 rank；
- 队友 single、非 single、孤立 pass 和无效响应链接不计分；
- 重复弱信号累计但受明确下限保护；
- 每项负分都有公开事件证据；
- 同分候选属于同一 score tier；
- 评分不修改 possible owners 或 confirmed。

#### J-C2b2：Top-K 与零软分消融

状态：已完成。J-C2b2 与兼容测试共 120 项通过，全量 230 项通过。

- baseline 与 soft 使用完全相同的玩家、rank 候选和硬状态；
- baseline 将 possible 软分归零并清除 evidence；
- score tier 跨越 K 时整体进入 Top-K 选择集；
- 同分稳定顺序变化不改变评测结果；
- 统计 Top-1/Top-3 召回、精确率和实际选择规模；
- 缺失真实 rank 计为未命中，不泄露真值明细；
- 最坏位置 MRR 使用真实 rank 所在 tier 的末尾位置；
- 报告 baseline、soft 和 delta，零分母稳定无 NaN。

#### J-C3a：多种子离线残局基准

状态：已完成。J-C3a 与兼容测试共 130 项通过，全量 240 项通过。

- 固定种子和相同参数重复运行得到完全一致的聚合报告；
- 规则 AI 推进时每个动作 ID 都来自当前公开合法动作；
- 只采集 `near_open_endgame` 和 `critical_endgame`，并按统一阶段分别聚合；
- 每个 `(seed, step_no, observer_player_id)` 最多采集一次；
- 真实手牌只在 `evaluation/` 内从离线引擎状态提取；
- J-A 至 J-C2b2 使用公开 observation 构造，不能读取隐藏牌；
- 总体和分阶段指标由原始计数汇总后重算，不能直接平均样本比率；
- 最坏位置 MRR 按 `truth_rank_count` 加权；
- 报告记录游戏数、候选样本数、有效/无效/跳过数和诊断频次；
- 报告及 `to_dict()` 不包含 seed 对应手牌、逐样本 token/rank、玩家真值或其他可逆真值明细；
- 非法参数、步数上限和异常样本有确定状态，不产生 NaN；
- 不修改现有启发式，不输出置信度，不接入 RAG、DeepSeek 或策略主链。

#### J-C3b：预注册正式基准

状态：已完成。200 局双运行结果和 SHA-256 一致，8719 个样本全部有效，唯一判定为 `retain_for_policy_diverse_validation`。

- J-C3a 必须先形成可追溯 Git 提交；
- 固定 seed `1000..1199`，不得替换、筛选或删除不利种子；
- 固定 `current_level_rank="2"`、`max_steps=5000`、`max_samples_per_game=512`；
- 两次完整运行的报告和 canonical JSON SHA-256 必须一致；
- 200 局全部完成，无 invalid、sample limit skip、step limit 或其他诊断；
- 两个阶段必须各有至少 1000 个有效样本；
- candidate recall 保持 1.0，candidate recall delta 保持 0；
- Top-1/Top-3 recall 不低于 baseline；
- overall Top-1/Top-3 precision delta 至少为 0.002；
- overall worst-case MRR delta 至少为 0.001；
- 两个阶段的 precision 和 MRR delta 均大于 0；
- 结果只代表 RuleBasedAI 轨迹，不外推到战略性 pass、DeepSeek 或胜率。

#### J-C3c1：战略性 pass 策略基准载体

状态：已完成。J-C3c1 与兼容测试共 140 项通过，全量 250 项通过。

- evaluation-only 策略只读取公开 observation 和合法动作；
- 只有当前敌方 single、pass 合法且至少存在一个非 pass 合法动作时，才计为战略性 pass 机会；
- 队友领出、非 single、孤立桌面、仅 pass 或无 pass 均不计机会；
- 0% 策略与现有 RuleBasedAI 的动作轨迹和 rank 报告完全一致；
- 25%、50%、100% 策略使用稳定整数门控，固定 seed 可重复；
- 100% 策略在每个合格机会选择合法 pass；
- 未命中门控时完全回退现有 RuleBasedAI，不复制其动作排序；
- 每种策略使用独立新对局和新 agent，不共享状态；
- 报告包含策略名、机会数、主动 pass 数和聚合 rank 报告；
- 报告不包含 seed、逐样本动作、真实牌、token 或 rank 明细；
- 默认 J-C3a API 与 J-C3c1 前的 240 项基线保持兼容。

#### J-C3c2：策略分布正式验收

状态：已完成。四策略各 100 局双运行结果一致，唯一判定为 `reject_unconditioned_pass_signal`。

- J-C3c1 必须先形成可追溯提交，工作区保持干净；
- 正式 seed 与 J-C3b、J-C3c1 开发试跑完全独立；
- 四个策略使用相同 seed 和参数，并各自运行全新对局；
- 两次完整运行报告与 canonical JSON SHA-256 一致；
- 每个策略无 incomplete、invalid、sample skip 或 diagnostics；
- forced-only 必须再次满足 J-C3b 的召回和正向排序门槛；
- 所有策略 candidate recall 保持 1.0；
- 25% 战略 pass 的 Top-3 recall 回退超过 0.02 时，当前无条件 pass 信号不得进入置信度校准；
- 25% 战略 pass 通过但 50/100% 未通过时，只能进入策略条件化重设计；
- MRR 改善不能抵消 Top-K recall 护栏失败；
- 不在正式 seed 上调参或重新筛选样本。

#### J-C3d1：撤销无条件 pass 软扣分

状态：已完成。J-C3d1 与兼容测试共 140 项通过，全量 250 项通过。

- enemy single pass 不再改变任何 possible candidate 的 soft score；
- 单次、重复、不同 round 的 pass 均不生成 `opponent_single_pass` evidence；
- confirmed candidate、hard owner domain 和 J-B2 收窄结果保持不变；
- 所有 possible candidate `soft_score=0`、`evidence=()`；
- 无 confirmed 时所有 possible rank 属于同一 tier；
- 有 confirmed 时 confirmed/possible 仍分成两个 tier；
- 稳定 rank 顺序只用于序列化，不表达额外置信；
- 删除 pass penalty 参数，旧调用必须显式失败，不能静默忽略；
- `card_signals.py` 的公开 pass 事件继续保留；
- `ranking_metrics.py` 的通用 soft ranking 校验和合成消融能力继续保留；
- J-C3a/J-C3c1 基准运行器保持可用；
- 全量测试无回归。

#### J-C3d2：neutral corpus 封板

状态：已完成。四策略各 50 局双运行结果一致，12 个 bucket 全部相等，判定为 `neutral_baseline_verified`。

- J-C3d1 必须先形成可追溯提交，工作区干净；
- 固定独立 seed `3000..3049`，四种策略各 50 局；
- 两次完整报告和 canonical JSON SHA-256 一致；
- 每个策略无 incomplete、invalid、skip 或 diagnostics；
- 每个策略 near-open/critical 均至少 500 个有效样本；
- 策略机会数与主动 pass 数满足既有 rate 约束；
- 每个策略、每个阶段的 baseline 与 neutral snapshot 完全相等；
- 所有 candidate/Top-K/选择规模/MRR delta 严格为 0；
- neutral ranker 在 forced/战略 pass 策略下 soft 与 baseline 完全一致；
- 通过后判定 `neutral_baseline_verified`，否则 `benchmark_invalid`；
- 不在正式 seed 上修改实现、参数或筛选样本。

#### J-D1a：物理分配权重

状态：已完成。J-D1a 与兼容测试共 132 项通过，全量 256 项通过。

- 完整 search 的每个 count matrix 计算精确整数权重；
- token count 为 `c`、各玩家份额为 `k_i` 时，token 权重为
  `c! / product(k_i!)`；
- 一个矩阵总权重为所有 token 权重的乘积；
- 相同 token 两副本的 1/1 split 权重为 2，2/0 split 权重为 1；
- 全部 token count 为 1 时，总权重等于 feasible matrix count；
- 聚合全局物理分配权重；
- 聚合逐玩家逐 token 的持有权重和副本数加权和；
- 唯一分配、重复 token、非对称容量和受限 domain 均有精确测试；
- 所有 numerators 不超过全局分母对应的合法上界；
- complete 结果可序列化、不可变且固定输入可重复；
- truncated/skipped/invalid/no-feasible 结果的权重统计全部为空或 0；
- partial traversal 不得泄露边际信息；
- 现有 feasible count、min/max、confirmed 和 possible owners 不变；
- 不输出 float、概率、置信度或 ground truth。

#### J-D1b：rank 精确整数边际

状态：已完成。J-D1b 与兼容测试共 139 项通过，全量 263 项通过。

- token 必须映射到合法 rank，joker 保持 `SJ` / `BJ`；
- token 聚合得到的逐 rank 总数必须与 `unseen_cards_by_rank` 一致；
- 每个完整 matrix 内，逐玩家同 rank 副本数先求和；
- rank 副本数分子等于同 rank token 副本数分子之和；
- rank 持有分子按“至少持有一张”事件计一次，不能直接求和 token 持有分子；
- 覆盖一个玩家同时持有同 rank 多花色的重叠事件测试；
- 单 token rank 的 rank 持有/副本分子与 token 级结果一致；
- 所有玩家 rank 副本数分子之和等于 `rank_count * physical_assignment_count`；
- rank 持有分子位于 `[0, physical_assignment_count]`；
- complete 输出不可变、可 JSON 序列化且固定输入可重复；
- truncated/skipped/invalid/no-feasible 的 rank mapping 全部为空；
- 不改变 J-B2/J-D1a 的搜索、截断、硬域、确认或 token 边际语义；
- 不输出 float、概率、置信度，不使用 pass、策略或 ground truth。

#### J-D1c1：单样本概率评分

状态：已完成。J-D1c1 与兼容测试共 152 项通过，全量 276 项通过。

- 只接受完整、有解、物理分母为正且 phase 一致的 J-D1b；
- 严格校验 allocation 玩家、容量、rank key、整数边际和跨玩家副本守恒；
- ground truth 只允许在 `evaluation/` 显式传入，并与公开 token multiset 完全一致；
- 每个活跃外部玩家 × 每个正数未见 rank 构成一个持有事件；
- Brier 平方误差使用精确有理数累计；
- rank 副本期望的平方误差使用精确有理数累计；
- 固定 10 个概率桶，使用整数算术确定桶边界；
- 每个桶只保留样本数、预测概率和的分子/分母、真实正例数；
- 报告不包含玩家-rank 真值明细、真实 token、真实 rank 列表或手牌；
- invalid/truncated/skipped/no-feasible 结果返回零化无效报告；
- 报告不可变、JSON 友好、无 NaN/Infinity，固定输入可重复；
- pass 只作为公开行为事实，不作为默认持牌负证据。

#### J-D1c2a：多样本精确聚合

状态：已完成。J-D1c2a 与兼容测试共 166 项通过，全量 290 项通过。

- valid 样本按 rank pair 数做微聚合，不平均单样本分数；
- 不同分母的 Brier 和 copy 误差使用 `Fraction` 精确相加；
- Brier mean 与 copy MSE 从总误差和除以总 pair 数重算；
- ECE 使用 `sum(abs(prediction_sum - truth_positive)) / total_pair_count`；
- MCE 使用非空桶平均预测与真实率的最大绝对差；
- 确定性错误率和真实正例率输出精确分数；
- 十档桶跨样本精确聚合，空桶保持 `0/1`；
- invalid 样本不进入指标，只进入 invalid count 与规范化 diagnostics；
- 同一无效样本内重复诊断类别只计一次；
- 聚合结果不保留单样本报告、seed、玩家、rank、token 或手牌；
- 冻结、不可变、JSON 友好且固定输入顺序无关；
- malformed 手工报告必须显式拒绝，不能静默产生指标。

#### J-D1c2b：固定种子采集与开发容量

- 状态：已完成。定向 179 项、全量 303 项通过；开发判定 `development_capacity_verified`；
- 默认只采集 `critical_endgame`，因为精确分配默认上限为 12 张；
- 按 overall 和外部未知牌 `0..4`、`5..8`、`9..12` 聚合；
- 固定 seed、级牌、步数、样本上限和搜索上限；
- 同一参数双运行报告和 canonical JSON hash 一致；
- 每个游戏/玩家只构造一次 agent，所有动作经过合法 action ID 校验；
- 真值只在公开推断完成后由既有 evaluation-only helper 提取；
- 报告不保留 seed、逐样本报告、observation、玩家或真值明细；
- 重复样本、步数上限和样本上限有规范化 diagnostics；
- overall 必须由原始单样本报告合并，不平均分桶指标；
- 外部牌数桶互斥且完整覆盖所有 evaluated 样本；
- 开发 seed 只用于容量和运行成本，不据此宣称校准通过；
- 正式参数与门槛留给 J-D1c2c 预注册；
- 由原始充分统计量重算 Brier 与可靠性，不平均单样本比例；
- 不在正式 seed 上调桶、调参或筛选样本。

#### J-D1c2c：独立语料正式校准

状态：已完成。16 项完整性与全部校准护栏通过，判定 `retain_for_policy_diverse_calibration`。

- HEAD 必须包含 J-D1c2b，运行前后工作区均干净；
- seed `5000..5099`，默认规则 AI，完整运行两次；
- 两份报告、`to_dict()` 和 canonical JSON SHA-256 完全相同；
- 100/100 局完成，无 incomplete、invalid、skip 或 diagnostics；
- eligible、evaluated、valid 三者相等；
- 三个外部牌数桶各至少 700 个 valid 样本；
- overall 与每个桶 certainty error count 均为 0；
- overall ECE 不超过 `0.03`，每个桶 ECE 不超过 `0.05`；
- overall Brier skill 相对经验正例率常数基线至少 `0.15`；
- 每个外部牌数桶 Brier skill 至少 `0.10`；
- overall 中 prediction count 至少 200 的桶，其最大 absolute gap 不超过 `0.10`；
- 每个外部牌数桶中 prediction count 至少 100 的桶，其最大 absolute gap 不超过 `0.15`；
- overall 和每个外部牌数桶至少有两个达到对应支持度的校准桶；
- 原始 MCE 与 copy MSE 只报告，不单独作为拒绝门槛；
- 正式运行中不改实现、seed、上限、分桶、支持度或阈值。

正式结果：

- 双运行 SHA-256：`c4a91d81bed216e919189fe4fdddf76c76ee8e35eb28f5fcae21ebc9e401e190`；
- 100/100 局，2727 个样本全部有效；
- 三桶样本 902 / 901 / 924；
- overall Brier skill 约 0.236809、ECE 约 0.021901、supported MCE 约 0.063909；
- overall 与三桶 certainty error 均为 0。

#### J-D1c3a：策略分布 marginal corpus

状态：已完成。定向 187 项、全量 311 项通过；开发判定 `policy_diversity_capacity_verified`。

- 固定策略顺序为 forced-only、strategic-pass 25/50/100；
- 每个策略创建独立游戏、agent 和报告；
- rate 0 corpus 与默认 marginal corpus 完全一致；
- opportunity/pass 满足 `0 <= pass <= opportunity`；
- rate 0 主动 pass 为 0，rate 100 主动 pass 等于机会数；
- 每个策略报告完整对局、样本、外部牌数桶和校准指标；
- 同参数双运行报告和 hash 一致；
- 报告不包含 seed、逐样本、observation 或 truth；
- 开发试跑只验证容量与行为分布，不形成正式校准或 runtime 结论。

开发结果：

- 双运行 SHA-256：`dc5bfa083d686e57cb711e9892738713904da96178988931deda7318427a58a3`；
- 四策略各 10/10 局完成，无 invalid、skip 或 diagnostics；
- opportunity/pass 为 117/0、121/48、127/63、133/133；
- 四策略均覆盖三个 external bucket。

#### J-D1c3b：多策略正式校准

状态：已完成，唯一判定 `benchmark_invalid`。运行中未修改代码、测试、docs、策略、参数、分桶或阈值。

- HEAD 必须包含 J-D1c3a，运行前后工作区干净；
- seed `7000..7049`，四策略各 50 局，完整运行两次；
- 两份顶层报告和 canonical JSON SHA-256 完全一致；
- 每个策略 50/50 局完成，无 invalid、skip 或 diagnostics；
- 每个策略的三个 external bucket 各至少 350 个 valid 样本；
- forced 主动 pass 为 0，100% 主动 pass 等于机会数；
- 25/50% 均有主动 pass，实际比例满足 `rate25 < rate50 < rate100`；
- 每个策略的 overall 与三桶 certainty error 均为 0；
- 每个策略 overall ECE ≤ 0.03，每个 external bucket ECE ≤ 0.05；
- 每个策略 overall Brier skill ≥ 0.15，每个 external bucket skill ≥ 0.10；
- overall 中 count≥200 的支持桶 MCE ≤0.10；external 桶中 count≥100 的支持桶 MCE ≤0.15；
- 每个策略、每个聚合范围至少两个 calibration bin 达到对应支持度；
- 不计算跨策略平均指标，不用其他策略通过抵消单策略失败。

正式结果：

- 双运行耗时约 322.8s / 321.9s，报告完全相等；
- SHA-256 均为 `67ed39e3b39b22dd7f2b660c70dc66eb5f6add3c11c0e3dc8315a1a8ca6a7eee`；
- 定向 187 项、全量 311 项测试通过；
- 四策略各 50/50 局完成，无 invalid、skip 或 diagnostics；
- 每个策略的三个 external bucket 均至少 350 个有效样本；
- 行为边界、行为比例梯度、样本守恒和双运行确定性全部通过；
- `strategic_pass_100 / external_0_4` 有 436 个有效样本和 1201 个 rank pair；
- 该范围 prediction count 为 `[0, 0, 60, 25, 0, 40, 26, 36, 2, 1012]`，只有 bin 9 达到 count>=100；
- 其余 15 个范围通过全部数值与支持度护栏，但不能抵消该失败。

#### J-D1c3b2：支持度扩容复验

状态：已完成，判定 `policy_diverse_calibration_verified`。运行中未修改实现、测试、docs、策略、分桶、支持阈值或数值护栏。

- seed `8000..8119`，四策略各 120 局，完整运行两次；
- seed `7000..7049` 只用于样本量规划，不进入新报告或判定；
- 运行前后工作区必须干净；
- 定向 187 项、全量 311 项测试和 `git diff --check` 必须通过；
- 两次报告、`to_dict()` 和 canonical JSON SHA-256 必须完全一致；
- 每个策略 120/120 局完成，无 incomplete、invalid、skip 或 diagnostics；
- 每个策略三个 external bucket 各至少 800 个 valid 样本；
- 策略行为边界和实际主动 pass 比例严格递增；
- certainty、ECE、Brier skill、supported MCE 门槛与 J-D1c3b 完全相同；
- overall 仍以 count>=200、external 仍以 count>=100 定义支持 bin；
- 每个策略、每个聚合范围仍至少需要两个支持 bin；
- 任一完整性或支持度失败判定 `benchmark_invalid`；有效 benchmark 的任一数值护栏失败判定 `reject_runtime_confidence`；全部通过才判定 `policy_diverse_calibration_verified`。

正式结果：

- 双运行耗时约 790.2s / 785.0s，报告完全相等；
- SHA-256 均为 `425bf197c7642894ebb6a0293383b94c160bdddb9dc44c180216278e200e113e`；
- 定向 187 项、全量 311 项测试通过；
- 四策略各 120/120 局完成，无 invalid、skip 或 diagnostics；
- 有效样本为 3260 / 3399 / 3531 / 2997；
- 每个策略的三个 external bucket 均至少 984 个有效样本；
- 主动 pass 比例为 0、约 0.357、约 0.546、1.0；
- 16 个范围支持 bin 数均至少为 4；
- 16 个范围全部通过 certainty、ECE、Brier skill 和 supported MCE 护栏。

#### J-D1c3c1：runtime confidence 数据契约

状态：已完成；J-D1c3c1a 已补齐 malformed 边界。未接入任何决策消费者。

- available 只允许 `critical_endgame`、精确牌池、精确一致约束和完整有解 allocation；
- `physical_assignment_count` 必须为非 `bool` 正整数；
- belief、constraints、allocation 的 phase、外部牌数、玩家集合和容量必须一致；
- rank key 必须与正数 `unseen_cards_by_rank` 完全一致；
- presence 分子必须位于 `[0, denominator]`；
- copy 分子必须满足逐玩家范围与跨玩家 `rank_count * denominator` 守恒；
- 输出只使用整数分子/分母，`to_dict()` 可 JSON 序列化；
- certainty 只允许 `presence_numerator == denominator`；
- 阶段外、不精确、不一致、截断、无解、跳过、诊断或 malformed 手工夹具都整体 unavailable；
- unavailable 状态必须零分母、无玩家结果，不泄露部分边际；
- frozen/slots、稳定顺序和不可变结构必须有测试；
- `agents/card_confidence.py` 不得导入 `evaluation/`，也不得读取 observation、history 或 ground truth；
- `deepseek_ai.py`、`deepseek_client.py`、RAG、CLI、剪枝和动作选择在本步骤保持不变；
- 先运行 `tests.test_card_confidence` 及 J-A/J-B/J-D1 allocation 相关定向测试，再运行全量 `python -m unittest discover -q`。

J-D1c3c1a 已补测：

- exact/consistent/search-complete 字段为 `1`、字符串或其他 truthy 非布尔值；
- constraints 中存在公开 active external 集合之外的额外玩家；
- copy mapping 值为字符串、`None`、float 或 `bool` 时不得在守恒求和中抛异常。

#### J-D1c3c1a：fail-closed 边界封板

状态：已完成。只修改 `agents/card_confidence.py` 与 `tests/test_card_confidence.py`。

- `token_pool_exact`、`token_constraints_exact`、`is_consistent`、`search_complete` 必须用严格布尔检查；
- truthy 非布尔值必须 unavailable 并输出对应既有诊断；
- 额外、重复、不可哈希或缺失的 constraint/allocation 玩家必须 `player_set_mismatch`；
- copy 原始值在进入加法前必须验证为非 `bool` 非负整数；
- 字符串、`None`、float、`bool`、负数和越界 copy 均返回 `invalid_copy_numerator`；
- 非法 copy mapping 不得抛 `TypeError`，不得输出部分 players；
- copy 守恒只基于全部通过类型/范围校验的规范化整数；
- 合法输入的 `to_dict()` snapshot 与 J-D1c3c1 保持一致；
- 定向和全量回归通过，decision path 仍无 `card_confidence` 引用。

验证结果：单文件 11 项、相关 80 项、全量 322 项通过；`git diff --check` 与边界扫描通过；合法 available snapshot 不变。

#### J-D1c3c2a：runtime confidence shadow 装配

状态：已完成。只建立 orchestration 与审计，prompt 或动作未消费。

- pipeline 使用调用方传入的统一 `GamePhaseContext`，不得重复分类阶段；
- 非 critical 阶段不调用 allocation 枚举；
- critical 阶段按 J-A -> J-B1 -> J-D1b -> confidence 顺序各调用一次；
- 任一层异常转为规范 unavailable，不向 agent 抛出；
- agent 开关默认 `False`，关闭时不得调用 pipeline；
- 每次 `select_action()` 开始将 `last_card_confidence` 清空，避免跨步复用陈旧状态；
- local only-pass、一次出完和 opening shortcut 不调用 pipeline；
- shadow 开启只写审计字段，不改变 prune、RAG、prompt builder、client 参数或合法动作校验；
- 固定 observation、legal actions 和 client 返回下，shadow off/on action ID 与 decision source 相同；
- pipeline unavailable 或内部异常时，原 DeepSeek/fallback 行为保持不变；
- 不修改 `config.py`、`.env.example`、CLI 或 AppConfig；
- 全量回归和 `git diff --check` 必须通过。

验证结果：定向 40 项、相关 124 项、全量 331 项通过；off/on client 参数、动作、fallback 与 decision source 一致；边界扫描和 `git diff --check` 通过。

#### J-D1c3c2b1：confidence prompt 序列化

状态：已完成。只新增 formatter 和测试，DeepSeekClient、agent 或动作路径未修改。

- unavailable 或 source/scope 不符时返回 omitted payload；
- available 的 denominator 和全部分子必须再次验证为非 `bool` 合法整数；
- presence 和 expected-copy 分数分别用 `gcd` 约分；
- 0 输出 `0`，等于 1 输出 `1`，其他输出 `n/d`；
- 不输出 float、百分比或置信度等级；
- 所有玩家和 rank 按输入已封板顺序稳定输出；
- 文本包含“公开硬约束组合边际、不是隐藏牌事实”的边界说明；
- 固定最大字符数；超限整体 omitted 且文本为空，不允许部分截断；
- malformed 玩家、rank、分母、分子或重复项整体 omitted；
- payload frozen/slots、JSON 友好且调用稳定；
- formatter 不读取 observation/history、ground truth、evaluation 或 engine；
- 现有 DeepSeek prompt snapshot 和 action path 必须完全不变。

验证结果：formatter/confidence 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项通过；`git diff --check` 与边界扫描通过。

#### J-D1c3c2b2：默认关闭的 confidence prompt 消费

状态：已完成。只修改 agent、client 与对应测试，配置、RAG、剪枝和 engine 未修改。

- `card_confidence_prompt_enabled` 默认 False；prompt=True 且 shadow=False 时构造失败；
- 每次决策同时重置 confidence state 与 prompt payload 审计字段；
- shadow-only 不调用 formatter，client kwargs 与 J-D1c3c2a 完全一致；
- prompt 模式只格式化本步 `last_card_confidence`；
- ready 时 client kwargs 只新增一个类型化 payload；
- omitted/unavailable 时不传新 keyword，prompt 与 shadow-only 完全一致；
- `_build_structured_prompt()` 默认参数为 None，所有旧调用 snapshot 逐字不变；
- ready payload 新增且只新增一个 `【残局牌面信念】` 章节；
- client 必须复核 payload status/source/scope/diagnostics/char_count/预算；malformed payload 整体省略；
- 新章节位于 `【记牌信息】` 后、`【场景标签】` 前；
- section 文本不得二次改写、截断或重新计算概率；
- legal actions、剪枝、RAG、输出格式、fallback 和 decision source 保持不变；
- local shortcuts 不计算 state 或 payload；
- 不修改 AppConfig、环境变量、CLI 或默认运行行为；
- 定向、相关和全量测试以及 `git diff --check` 必须通过。

验证结果：confidence/pipeline/DeepSeek 定向 54 项、RAG/剪枝/开局/DeepSeek 相关 48 项、全量 345 项通过；禁止引用扫描和 `git diff --check` 通过。

#### J-D1c3c2c1：配对 prompt 覆盖与成本开发基准

状态：已完成。只新增 evaluation collector 与测试，runtime 未修改。

- 使用公开 game observation、legal actions 和统一 phase；
- 只采集 `critical_endgame`，按 external 0..4、5..8、9..12 分桶；
- 复用 0/25/50/100 strategic-pass evaluation agent，四策略对局隔离；
- 每个样本只运行一次 runtime confidence pipeline 和 formatter；
- off/on 共用相同 my_info、current_round、other_players、history、pruned actions 和 phase；
- 不调用 `suggest_action_id()`、HTTP transport 或真实 DeepSeek；
- confidence available/unavailable 与 payload ready/omitted 计数守恒；
- ready 时 on prompt 必须等于向 off prompt单次插入固定章节；
- omitted 时 on prompt 必须与 off prompt 完全相同；
- 记录 payload char 和 prompt delta 的 sum/min/max，不平均单样本均值；
- diagnostics 按冒号前类别聚合，同一样本同类只计一次；
- 报告 frozen/slots、mapping 不可变且 JSON 友好；
- 报告不含 seed、样本 ID、observation、prompt、手牌或玩家明细；
- 同参数双运行报告与 canonical JSON hash 必须一致；
- 开发试验只验证容量和覆盖，不形成动作质量或胜率结论。

验证结果：collector/formatter/pipeline 28 项、DeepSeek/策略/RAG/剪枝 77 项、全量 351 项通过；边界扫描和 `git diff --check` 通过。

开发双运行：seed `80..89`，四策略各 10 局；报告完全一致，SHA-256 为 `15370d48a49a8067d9790bbd89b54431c54e6a4dd5d5403a3b2ec23d10ccfd6b`；1084 个样本全部 ready，零 omitted/mismatch/diagnostics；判定 `confidence_prompt_coverage_capacity_verified`。

#### J-D1c3c2c2：独立正式 prompt coverage

状态：已完成但无效。唯一判定 `benchmark_invalid`；不是 coverage 数值失败，而是完整聚合证据未留存。

- HEAD `bc689a37f462672033d754cce7060897d70c7612`；运行前后工作区干净；
- 提交前后定向 28 项、相关 77 项、全量 351 项通过，`git diff --check` 通过；
- seed `10000..10049`，四策略各 50 局，完整运行两次；
- 两次耗时 344.621s / 342.153s；
- 两份 report、`to_dict()`、canonical JSON 完全一致，SHA-256 均为 `1d6506250def487c16d4da2c4fcf1aed2cdfd13231a6096347b768e0c8680a8f`；
- 边界扫描未发现网络、DeepSeek、ground truth 或 `game._state`；
- 工具层截断 stdout，未保留 4 策略 x 4 范围的完整数据；
- 按预注册约束未第三次运行、补采或改参；局部 `strategic_pass_50` 输出不参与正式通过判定。

#### J-D1c3c2c2a：可持久化恢复验收

状态：已完成。唯一判定 `confidence_prompt_coverage_verified`。

- HEAD `6b62156a98cfb97dd11e30df5f95a62dba99accd`，实现检查点 `bc689a37f462672033d754cce7060897d70c7612`；
- 仓库外审计目录为 `C:\Users\86166\AppData\Local\Temp\guandan-confidence-prompt-jd1c3c2c2a-6b62156a98cf`，runner SHA-256 为 `61ac8e55fdc57e58ee09a6af80972f1dea67bcfddd413a0f02ecb29ce6b76202`；
- 运行前后工作区干净；定向 28 项、相关 77 项、全量 351 项和 `git diff --check` 全部通过；
- seed `11000..11049`，四策略各 50 局，完整运行两次；
- 两次耗时 321.921s / 321.047s；
- 两份 JSON 均为 9218 bytes，逐字节与 canonical SHA-256 完全一致：`679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- recovered 审计摘要为 19833 bytes，SHA-256 为 `fc8e9f3d7aa016e4772350834039b4780eccf3d9330c5315eae77c9c8eac33d7`；
- 四策略 games 均为 50/50/0，样本分别为 1380 / 1469 / 1510 / 1374；
- 各策略 external 0-4 / 5-8 / 9-12 样本为 461/443/476、489/490/490、475/530/505、473/444/457；
- 5733 个样本全部 available=ready=exact insertion，零 invalid/skipped/diagnostics/unavailable/omitted/budget omitted/pair mismatch；
- 16 个范围 payload 最大 683，全部低于 2400；delta sum/min/max 精确满足每样本 +11；
- forced/25/50/100 主动 pass 为 0/498、196/547、318/557、609/609，比例严格递增；
- 原始摘要曾把 canonical JSON 键顺序误当调用顺序；只读恢复解析器按策略名/rate 复核原文件，未重跑或改 corpus；
- 未调用 DeepSeek、网络、ground truth 或 `game._state`。

字符成本 `payload sum/min/max -> prompt delta sum/min/max`：

| 策略 | overall | external_0_4 | external_5_8 | external_9_12 |
|---|---|---|---|---|
| forced | 447781/106/683 -> 462961/117/694 | 75258/106/296 -> 80329/117/307 | 143478/139/476 -> 148351/150/487 | 229045/162/683 -> 234281/173/694 |
| pass-25 | 462156/106/677 -> 478315/117/688 | 78728/106/296 -> 84107/117/307 | 153981/139/476 -> 159371/150/487 | 229447/161/677 -> 234837/172/688 |
| pass-50 | 475768/106/639 -> 492378/117/650 | 73658/106/296 -> 78883/117/307 | 165464/139/476 -> 171294/150/487 | 236646/162/639 -> 242201/173/650 |
| pass-100 | 371715/106/662 -> 386829/117/673 | 64873/106/296 -> 70076/117/307 | 111541/128/482 -> 116425/139/493 | 195301/161/662 -> 200328/172/673 |

#### J-D1c3c2c3a：无网络成对动作消融载体

状态：已完成。唯一开发判定 `confidence_action_ablation_harness_verified`。

- 只新增 `evaluation/confidence_action_ablation.py` 和对应测试；
- 单文件 6 项、相关 76 项、全量 357 项通过，`git diff --check` 通过；
- provider 显式注入，无默认 client、配置、环境或网络读取；
- critical/public-only、SHA-256 固定样本、shortcut 排除、off/on 唯一差异、AB/BA 平衡和 fail-closed 分类均已覆盖；
- 报告 frozen/slots、不可变、JSON 友好且只含聚合数据；
- 边界扫描未发现 runtime 反向导入、配置、`.env`、API key、网络、ground truth 或 `game._state`。

开发双运行：seed `120..129`、四策略、每桶 4 个样本：

- 两次耗时 39.795s / 40.446s；
- report、`to_dict()` 完全相等，canonical SHA-256 为 `ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095`；
- 四策略均 10/10/0 games、零 diagnostics；
- 每策略 12 selected/both-valid，三个桶各 4，AB/BA 各 2；
- 每轮 off/on 各 48 次，异常、malformed、no-action、错误类型、outside legal/prompt 均为 0；
- 每策略 same=0、changed=12；该结果由假 provider 首/末候选规则刻意构造，只验证载体；
- off pass 分别为 7/9/11/9，on pass 与双方 pressure 均为 0。

#### J-D1c3c2c3b：真实 DeepSeek 响应安全 live pilot

状态：下一步。网络调用前必须获得用户明确授权。

- 先将 c3a 两个文件单独提交并确认工作区干净；
- 回归必须保持单文件 6、相关 76、全量 357 项通过；
- 只检查 API key 是否存在，不输出、散列或持久化 key；
- 显示并记录实际 base URL host、model、timeout=60、max_retries=0 和最大 48 次请求，等待用户授权；
- 使用 seed `13000..13009`、四策略、每桶 2 个样本，共 24 pair；
- 每桶 off-first/on-first 各 1，off/on 各 24 次；
- 外部 JSONL 每次调用后 flush/fsync，记录序号、condition、耗时和非敏感 outcome，不含 prompt、action ID、reasoning 或响应原文；
- aggregate canonical JSON 和门槛摘要写入仓库外目录并重新解析、哈希；
- max retries=0，逻辑与物理请求都不得超过 48；
- 任一传输异常、中断、审计缺口或 corpus 不完整均不得重跑/补采；
- 完整数据要求四策略 10/10/0、每桶 2 selected、零 diagnostics，24 pair/48 calls 守恒；
- 响应安全要求 exception/malformed/no-action/错误类型/outside legal/prompt 均为 0，24 pair 全部 both-valid；
- same/changed、pass/pressure 仅报告，不设置事后收益阈值；
- changed=0 表示该 pilot 未观察到动作差异；changed>0 只允许进入质量评估，不构成 confidence 因果效果；
- 不运行完整 DeepSeek 对局，不形成胜率结论。

#### 暂停：校准

- pass 只保留为公开行为事实，不作为默认软持牌证据或确定无牌；
- 所有 `likely` 结论带置信度和证据来源；
- 软信号不能覆盖 J-A 公开事实或 J-B 硬约束。

### 离线准确率

测试和评测环境可读取预设完整手牌作为 ground truth，但这些牌不能进入 AI runtime observation。

至少记录：

- 未见牌池准确率；
- 逐玩家 Top-K 点数召回率；
- 错误确认数；
- 外部剩余 20 / 12 / 8 张三个区间的推断准确率。

## 5. Step K：策略测试

- 固定 observation 的策略路由结果可复现；
- 队友少牌时可进入 `support_teammate`；
- 危险对手少牌时可进入 `block_opponent`；
- 弱牌优先 `run_out`；
- 强牌且无紧急威胁时可进入 `control`；
- RAG 只为已选策略提供证据；
- 近似明牌残局不能把低置信度猜测写成确定事实。

## 6. 对局评测

单元测试不能代替策略评测。每次策略改动应使用固定种子进行 A/B 对局，并轮换座位，至少记录：

- 胜 / 负 / 平；
- 平均完赛名次；
- 非法动作数；
- API 调用数和失败数；
- 开局高价值牌消耗；
- 近似明牌阶段的猜牌准确率。

在没有 A/B 数据前，只能声明“功能已接入”，不能声明“策略已提升”。

## 7. 测试失败说明

如果测试无法运行，最终说明必须包含：

- 实际运行的命令；
- 失败测试名；
- 是实现失败、环境问题还是外部 API 问题；
- 未验证的剩余风险。
