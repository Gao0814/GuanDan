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

状态：下一步。

- 只消费 J-A 的 `CardBeliefState`；
- 自己、已完赛和零容量玩家不进入外部未知牌归属域；
- token/点数归属域覆盖全部仍可持牌的外部玩家；
- 玩家公开剩余容量总和与未见牌总数一致；
- 输入不精确、容量冲突或空归属域产生诊断；
- 多个候选玩家存在时不产生 `confirmed_cards`；
- 只有硬约束唯一且输入一致时才允许确认；
- pass 次数不能缩小硬归属域。

### J-B2：有限残局分配

- 只在受控规模下枚举完整可行分配；
- 截断搜索不得输出唯一性结论；
- `confirmed` 只能来自所有完整可行解的一致归属。

### J-C：软推断与校准

- pass 只作为软信号，不作为确定无牌；
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
