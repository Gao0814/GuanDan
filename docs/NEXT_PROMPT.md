# 下一步实施提示词

## Step J-D1b：精确 rank 边际整数聚合

请在 GuanDan 项目中实现 Step J-D1b。目标是在 J-D1a 的完整物理分配权重基础上，聚合逐玩家、逐 rank 的精确整数边际。

本步骤只建立 rank 级分子，不计算浮点概率、不命名置信度、不做离线校准，也不接入 RAG、DeepSeek 或策略主链。

## 一、开始前检查

先阅读：

- `agents/card_allocations.py`
- `agents/card_belief.py`
- `agents/card_constraints.py`
- `tests/test_card_allocations.py`
- `docs/BELIEF_STATE.md`
- `docs/PROJECT_STATUS.md`

确认当前 J-D1a 契约存在：

- `CardAllocationResult.physical_assignment_count`
- `PlayerAllocationBounds.holding_assignment_count_by_token`
- `PlayerAllocationBounds.copy_assignment_count_by_token`
- 只有 `status="complete"`、`search_complete=True` 且至少有一个可行解时才暴露权重；
- 截断、无效、跳过和无解结果的物理总数为 0，token 边际为空。

开始前运行：

```bash
python -m unittest tests.test_card_allocations tests.test_belief_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
python -m unittest discover -q
```

当前已复核基线为定向 132 项、全量 256 项通过。若数量或结果不同，先报告实际状态，不要覆盖不明改动。

## 二、允许修改范围

只修改：

- `agents/card_allocations.py`
- `tests/test_card_allocations.py`

不要修改：

- `engine/`
- J-A/J-B1 数据契约
- `agents/card_ranker.py`
- `evaluation/`
- RAG、DeepSeek、CLI
- docs
- 依赖配置

不要新增第三方依赖。

## 三、核心语义

J-D1a 已为每个完整 count matrix 计算物理权重：

```text
matrix_weight = product_t(c_t! / product_p(k_(p,t)!))
```

对每个完整 matrix、每个玩家、每个 rank：

1. 先把该 rank 下所有 token 分配给该玩家的副本数相加，得到 `rank_copy_count`；
2. 若 `rank_copy_count > 0`，则该玩家该 rank 的持有分子增加一次 `matrix_weight`；
3. 该玩家该 rank 的副本数分子增加
   `matrix_weight * rank_copy_count`。

必须区分两个量：

- rank 副本数分子可以等于同 rank 的 token 副本数分子之和；
- rank“至少持有一张”的分子是多个 token 持有事件的并集，不能直接相加 token 持有分子。

例如同一玩家在一个 matrix 中同时持有 `3S` 和 `3H` 时，rank `3` 的持有事件只计一次。

## 四、输出契约

在 `PlayerAllocationBounds` 中新增：

```python
holding_assignment_count_by_rank: Mapping[str, int]
copy_assignment_count_by_rank: Mapping[str, int]
```

要求：

- 使用安全默认值，保持旧的手工 `PlayerAllocationBounds` 构造兼容；
- complete 且有解时输出不可变整数 mapping；
- key 只包含外部未见数量大于 0 的合法 rank；
- `to_dict()` 输出普通 JSON 友好 dict；
- 不改变现有字段名称、顺序语义或类型；
- 不向 `CardAllocationResult` 新增概率字段。

## 五、token 到 rank 的映射与校验

使用 J-A 已定义的公开常量语义：

- 普通 token：末位是 `SUITS`，前缀属于 `NORMAL_RANKS`；
- joker token：`SJ`、`BJ`，rank 与 token 相同。

不要按字符串首字符猜 rank，例如 `10S` 必须映射为 `10`。

在搜索前校验：

- 每个正数 token 都能映射到合法 rank；
- 按 token 聚合的逐 rank 副本数与
  `card_belief.unseen_cards_by_rank` 的正数项完全一致；
- 缺失 rank、多余 rank或数量不一致都 fail closed；
- 非法 token 产生稳定诊断，例如 `invalid_token_rank:<token>`；
- rank 牌池不一致产生稳定诊断，例如 `rank_pool_mismatch:<rank>`；
- 这些情况返回既有 `invalid_input` 状态，不启动搜索，不输出任何 token/rank 权重。

可以复用 `agents.card_belief` 中的 rank/suit 常量，但不要让 J-B2 重新读取 observation，也不要访问引擎隐藏状态。

现有测试夹具的 `unseen_cards_by_rank` 若使用虚构 rank，需要改为从真实 token 正确聚合；不要通过放宽生产校验保留错误夹具。

## 六、完整搜索聚合

rank 聚合必须与 J-D1a 使用完全相同的：

- count matrix；
- `matrix_weight`；
- 玩家容量；
- token 域；
- 完整搜索判定。

推荐在 `record_solution()` 中完成 rank 聚合，因为此时：

- 当前 matrix 完整；
- 权重已精确计算；
- 不会把部分搜索状态误当作边际。

不要：

- 二次枚举物理副本排列；
- 将 `feasible_assignment_count` 当分母；
- 从 J-D1a 的 token 持有分子直接推导 rank 持有分子；
- 使用 pass、队伍关系、策略、随机数或 ground truth 改变权重；
- 改变 `max_solutions` 按 count matrix 截断的语义。

## 七、必须保持的安全行为

以下结果的两个 rank mapping 必须为空：

- `truncated`
- `invalid_input`
- `skipped_too_many_cards`
- `no_feasible_allocation`

即使部分遍历已经发现可行 matrix，也不能泄露部分 rank 边际。

保持不变：

- `feasible_assignment_count`
- `physical_assignment_count`
- search node / solution limit
- min/max token count
- `confirmed_cards`
- `possible_owners_by_token`
- J-D1a token 持有和副本数边际

## 八、整数不变量

对每个 complete 且有解的结果验证：

1. `0 <= holding_rank <= physical_assignment_count`；
2. `0 <= copy_rank <= rank_count * physical_assignment_count`；
3. 所有玩家的某 rank 副本数分子之和等于
   `rank_count * physical_assignment_count`；
4. 某玩家某 rank 的副本数分子等于该玩家同 rank token 副本数分子之和；
5. 单 token rank 的 rank 持有分子等于对应 token 持有分子；
6. 当同 rank 多 token 持有事件重叠时，rank 持有分子小于 token 持有分子之和；
7. 若玩家在所有物理分配中都至少持有该 rank，则持有分子等于全局物理分母。

所有计算使用 Python 整数，不转 float，不做除法输出。

## 九、最低测试覆盖

在 `tests/test_card_allocations.py` 至少覆盖：

1. token 到 rank 的正常映射，包括 `10S`、`SJ`、`BJ`；
2. 非法 token fail closed；
3. token 聚合 rank 与 `unseen_cards_by_rank` 不一致时 fail closed；
4. 单 token rank 的 rank/token 边际一致；
5. 同 rank 多花色但事件不重叠；
6. 同一玩家可能同时持有同 rank 多花色，证明 rank 持有分子不是 token 持有分子之和；
7. 重复 token 与多 rank 混合时副本分子精确；
8. 非对称容量和受限 domain；
9. 每个 rank 的跨玩家副本守恒；
10. complete 输出 mapping 不可变；
11. `to_dict()` 可被 `json.dumps()` 序列化，值保持整数；
12. 固定输入重复运行结果完全相等；
13. node limit 截断不泄露 rank 边际；
14. solution limit 截断不泄露 rank 边际；
15. too many cards、invalid input、no feasible allocation 的 rank mapping 为空；
16. 旧式手工 dataclass 构造仍可工作；
17. J-D1a 的物理总数和 token 边际断言保持不变。

建议重叠事件夹具：

- token：`3S`、`3H`、`4C`，各 1 张；
- 两位玩家容量分别为 2 和 1；
- 三个 token 均可由两位玩家持有；
- 对容量为 2 的玩家，rank `3` 在所有三个 matrix 中都出现；
- 其两个 token 的持有分子之和大于 rank `3` 的持有分子。

## 十、验证命令

先运行：

```bash
python -m unittest tests.test_card_allocations tests.test_belief_metrics tests.test_card_ranker tests.test_pass_policy_benchmark tests.test_rank_benchmark tests.test_ranking_metrics tests.test_card_constraints tests.test_card_belief tests.test_card_tracker tests.test_game_phase -q
```

再运行：

```bash
python -m unittest discover -q
git diff --check
```

## 十一、完成报告

报告必须包含：

- 修改文件；
- 新增字段及整数语义；
- token 到 rank 的映射和 fail-closed 规则；
- rank 持有并集计数为何不能由 token 持有分子直接相加；
- complete 与非 complete 输出边界；
- 定向和全量测试结果；
- `git diff --check` 结果；
- 明确说明 J-D1b 尚未输出概率、置信度、校准结论、策略接入或胜率提升。

## 十二、完成门槛

只有同时满足以下条件，Step J-D1b 才能标记完成：

- rank 持有与副本数整数边际来自完整 matrix；
- rank 持有事件正确处理同 rank token 重叠；
- rank/token/容量守恒均有测试；
- 非完整结果不泄露部分边际；
- 旧 J-B2/J-D1a 契约无回归；
- 全量测试通过；
- 没有修改 `engine/`、runtime 策略、evaluation 或 docs；
- 没有声称概率已经校准或策略已经提升。
