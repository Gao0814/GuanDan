# 牌面信念状态设计

## 1. 目的

牌面信念状态用于把公开历史转换为可审计的未见牌池和逐玩家弱推断，为中局策略和残局决策提供结构化输入。

它不是规则真值，也不能访问其他玩家真实手牌。

当前状态：Step J-A 已完成并通过 31 项定向测试、141 项全量测试；下一步为 Step J-B1。

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

下一步实现：

- 玩家容量约束；
- token/点数级可能归属集合；
- 完赛玩家、零容量玩家和自己从外部归属域排除；
- 容量总和、空归属域和不精确输入诊断；
- 只有输入精确、容量一致且逻辑唯一时才能产生隐藏 `confirmed_cards`。

本阶段不使用 pass 排除归属，不输出概率，不枚举完整残局分配，不接入策略主链。

### Step J-B2：有限残局分配

在 J-B1 稳定后实现：

- 仅在 `critical_endgame` 等受控规模下枚举可行分配；
- 设置明确的搜索规模上限和截断诊断；
- 只有全部完整可行解一致时才能确认归属；
- 搜索被截断时不得输出唯一性结论。

### Step J-C：软推断层

最后实现：

- pass、首出和拆牌等软信号；
- `likely_ranks`；
- 置信度；
- 使用离线真实手牌校准 Top-K 召回和错误确认数。

J-C 不得反向污染 J-A 的公开事实或 J-B 的硬约束。
