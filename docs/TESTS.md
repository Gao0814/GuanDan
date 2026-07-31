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

状态：下一步。

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

#### J-C3d2/J-D1：neutral 回归与新证据

- neutral ranker 在 forced/战略 pass 策略下 soft 与 baseline 完全一致；
- pass 只作为公开行为事实，不作为默认持牌负证据；
- 新概率信号必须定义样本空间、权重和校准方式。

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
