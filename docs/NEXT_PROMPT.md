# 下一步实施提示词

## Step J-D1c3c1a：runtime confidence fail-closed 边界封板

请在 GuanDan 项目中完成 Step J-D1c3c1a。J-D1c3c1 的正常路径和多数异常路径已经通过测试，但代码审阅发现三个 malformed 输入边界不满足原预注册的整体 fail-closed 契约。本步骤只修复这些边界并补回归测试，不接入任何决策消费者。

## 一、当前基线

当前 J-D1c3c1 已新增：

- `agents/card_confidence.py`
- `tests/test_card_confidence.py`

已验证：

- 定向 76 项通过；
- 全量 318 项通过；
- `git diff --check` 通过；
- 新模块不读取 evaluation、ground truth、engine state、observation/history、DeepSeek 或 RAG；
- 现有 decision path 未引用 `card_confidence`。

这两个实现文件当前可能仍未提交或未跟踪。不要因此删除、还原或重写已有实现；在现有内容上做最小修复。

## 二、修改范围

只允许修改：

- `agents/card_confidence.py`
- `tests/test_card_confidence.py`

不要修改：

- `engine/`
- 其他 `agents/` 模块
- `evaluation/`
- CLI、RAG、DeepSeek、提示词或动作剪枝
- docs

不得新增依赖，不扩展到 J-D1c3c2。

## 三、必须修复的问题

### 1. 布尔语义必须严格

当前 `bool(getattr(...))` 会让 `1`、非空字符串或其他 truthy 非布尔值通过。

以下字段只有值为实际 `True` 时才可通过：

- `card_belief.token_pool_exact`
- `constraints.token_constraints_exact`
- `constraints.is_consistent`
- `allocation.search_complete`

使用严格判断，例如 `value is True`，不要使用 `bool(value)`。

沿用既有诊断：

- 非严格 true 的 `token_pool_exact` -> `token_pool_inexact`
- 非严格 true 的 `token_constraints_exact` -> `constraints_inexact`
- 非严格 true 的 `is_consistent` -> `constraints_inconsistent`
- 非严格 true 的 `search_complete` -> `allocation_not_complete`

### 2. 玩家集合必须严格一致

当前 constraint 玩家遍历会忽略不在公开 active external 集合中的额外玩家。

必须满足：

- belief active external 玩家集合；
- `constraints.players` 玩家集合；
- `allocation.players` 玩家集合；

三者严格一致。

以下情况都必须诊断 `player_set_mismatch` 并整体 unavailable：

- 额外 constraint 玩家；
- 额外 allocation 玩家；
- 缺失玩家；
- 重复玩家 ID；
- 不可哈希玩家 ID；
- constraint 玩家不是公开 active external 玩家。

容量不一致继续使用 `capacity_mismatch`。不要静默过滤额外玩家后再比较集合。

### 3. 非法 copy 分子不得进入原始求和

当前 copy 守恒直接对 allocation 原始 mapping 求和。若值为字符串或 `None`，可能抛出 `TypeError`。

必须：

- 在任何加法前验证每个 copy 分子；
- 只接受非 `bool` 非负整数；
- 同时验证玩家容量/rank 总副本上界；
- 守恒求和只使用已经规范化并验证通过的整数；
- 若任一 copy 值非法，诊断 `invalid_copy_numerator` 并整体 unavailable；
- 不得抛出由 malformed copy mapping 导致的 `TypeError`、`ValueError` 或部分输出。

可以在进入守恒检查前对已发现的结构/类型诊断提前返回 unavailable，也可以保存独立的验证后整数表；不要再次读取未经验证的原始值参与 `sum()`。

## 四、保持不变的契约

- available 仍只覆盖 `critical_endgame`；
- 外部未知牌仍必须为 1..12；
- source 仍为 `physical_assignment_marginal_v1`；
- calibration scope 仍为 `critical_endgame_policy_diverse_v1`；
- presence/copy 仍使用精确整数分子和共同物理分母；
- 玩家顺序仍沿用 allocation；
- rank 仍使用 canonical 顺序；
- unavailable 仍为零分母、空 players，且不保留部分边际；
- 合法输入的 `CardConfidenceState.to_dict()` 输出必须与 J-D1c3c1 完全一致。

不要改字段名、状态名、来源字符串或校准范围字符串。

## 五、测试要求

在 `tests/test_card_confidence.py` 增加至少以下测试：

### 严格布尔

分别将四个布尔语义字段替换为：

- `1`
- 非空字符串

每种情况都必须：

- 不抛异常；
- `status == "unavailable"`；
- `physical_assignment_count == 0`；
- `players == ()`；
- 包含对应既有诊断。

### 玩家集合

覆盖：

- constraints 额外合法形状玩家；
- allocation 额外合法形状玩家；
- constraints/allocation 重复玩家；
- constraint 玩家 ID 不在 belief active external 集合；
- 不可哈希玩家 ID。

全部必须 fail-closed，至少包含 `player_set_mismatch`。

### malformed copy

分别把一个 rank 的 copy 分子替换为：

- 字符串；
- `None`；
- float；
- `True`；
- 负整数；
- 超过容量/rank 上界的整数。

每项都必须：

- 调用不抛异常；
- 返回整体 unavailable；
- 包含 `invalid_copy_numerator`；
- 不输出部分玩家或部分 rank。

### 回归不变性

- 保存一个合法输入在修复前已有的完整 `to_dict()` 期望；
- 修复后 snapshot 必须逐字段相同；
- 现有 certainty、impossible、rank 顺序、JSON 和不可变测试继续通过；
- decision path 继续不引用 `card_confidence`。

测试名称不要依赖执行顺序。

## 六、验证命令

先运行：

```bash
python -m unittest tests.test_card_confidence -q
```

再运行相关回归：

```bash
python -m unittest tests.test_card_confidence tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_game_phase -q
```

最后运行：

```bash
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "evaluation|ground_truth|game\._state|observation|history|deepseek|rag" agents/card_confidence.py
rg -n "card_confidence" agents/deepseek_ai.py agents/deepseek_client.py agents/rag_advisor.py cli engine
```

第二条必须无匹配。第一条不允许出现实际导入或读取。

## 七、验收标准

完成后必须同时满足：

- 只改两个约定文件；
- 四个布尔语义字段严格拒绝 truthy 非布尔值；
- 三层玩家集合严格一致；
- malformed copy 分子不会触发异常；
- copy 守恒只使用验证后整数；
- 所有失败整体 unavailable；
- 合法输入输出完全不变；
- 定向、相关和全量测试通过；
- `git diff --check` 通过；
- 现有决策路径仍未接入新模块。

## 八、输出要求

最终报告必须包含：

1. 修改文件；
2. 三类修复的实际实现方式；
3. 新增 malformed 测试矩阵；
4. 单文件、相关和全量测试结果；
5. `git diff --check` 与边界扫描结果；
6. 明确说明合法 available 输出未变；
7. 明确说明未接入 DeepSeek、RAG、提示词、剪枝或动作决策。

完成后停止，不扩展到 J-D1c3c2，不修改 docs。
