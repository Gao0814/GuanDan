# 下一步实施提示词

## Step J-D1c3c2b1：有界、确定的 confidence prompt 序列化契约

请在 GuanDan 项目中实现 Step J-D1c3c2b1。任务是把已封板的 `CardConfidenceState` 转换成一个独立、精确、有界、可审计的 prompt payload。

本步骤只建立 formatter 和测试，不修改 DeepSeekClient 或 agent，不让模型、RAG、剪枝或动作选择消费 confidence。

## 一、前置状态

J-D1c3c2a 已完成：

- runtime pipeline 只在 `critical_endgame` 运行公开 J-A -> J-B1 -> J-D1b -> confidence 链；
- `DeepSeekAIAgent.card_confidence_shadow_enabled` 默认关闭；
- 开启后只写 `last_card_confidence`；
- shadow off/on 的 client kwargs、动作、fallback 和 decision source 一致；
- 定向 40 项、相关 124 项、全量 331 项测试通过。

现有 confidence/shadow 文件可能尚未提交。保留全部现有改动，不要删除、还原或重写。

## 二、修改范围

只允许新增：

- `agents/card_confidence_prompt.py`
- `tests/test_card_confidence_prompt.py`

不要修改任何现有文件，包括：

- `agents/card_confidence.py`
- `agents/card_confidence_pipeline.py`
- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- 现有测试
- config、CLI、RAG、engine、evaluation 或 docs

不得新增依赖，不扩展到 J-D1c3c2b2。

## 三、公共契约

在 `agents/card_confidence_prompt.py` 定义：

```python
CARD_CONFIDENCE_PROMPT_MAX_CHARS = 2400
```

新增 frozen、slots dataclass：

```python
CardConfidencePromptPayload
```

至少包含：

- `status: str`，只能为 `ready` 或 `omitted`
- `text: str`
- `char_count: int`
- `source: str`
- `calibration_scope: str`
- `diagnostics: tuple[str, ...]`

提供 JSON 友好的 `to_dict()`。

新增纯函数：

```python
build_card_confidence_prompt_payload(
    confidence: CardConfidenceState,
    *,
    max_chars: int = CARD_CONFIDENCE_PROMPT_MAX_CHARS,
) -> CardConfidencePromptPayload
```

`max_chars` 必须为 1..2400 的非 `bool` 整数；非法调用参数显式抛 `ValueError`。

## 四、ready 前置条件

只有以下条件全部满足才能返回 `status="ready"`：

1. 输入是 `CardConfidenceState`；
2. `confidence.status == "available"`；
3. `phase == "critical_endgame"`；
4. `source == "physical_assignment_marginal_v1"`；
5. `calibration_scope == "critical_endgame_policy_diverse_v1"`；
6. confidence diagnostics 为空；
7. `external_unknown_count` 为 1..12 的非 `bool` 整数；
8. `physical_assignment_count` 为非 `bool` 正整数；
9. players 为包含 1..3 项的非空 tuple；
10. 玩家 ID 为 1..4 的非 `bool` 整数且不重复；
11. remaining capacity 为 1..12 的非 `bool` 整数；
12. 所有玩家 remaining capacity 之和等于 `external_unknown_count`；
13. ranks 为非空 tuple；
14. rank 只来自 canonical `3..10,J,Q,K,A,2,SJ,BJ`；
15. 每位玩家 rank 不重复且顺序严格遵循 canonical 顺序；
16. 所有玩家的 rank 集合和顺序完全相同；
17. 每个 rank marginal 的 denominator 与全局物理分母相同；
18. presence numerator 为 `[0, denominator]` 内的非 `bool` 整数；
19. expected-copy numerator 为 `[0, remaining_capacity * denominator]` 内的非 `bool` 整数。

不要信任手工构造的 frozen dataclass；formatter 必须再次 fail-closed 校验。

## 五、精确分数格式

使用标准库 `math.gcd` 分别约分 presence 和 expected-copy：

- 分子为 0 输出 `0`；
- 约分后分母为 1 输出整数，例如 `1`、`2`；
- 其他输出 `n/d`；
- 不输出 float、科学计数法、百分比或小数；
- 不生成 high/medium/low、likely/unlikely 等主观标签。

不得使用 `Fraction` 的 float 转换。

## 六、固定文本结构

ready 文本固定为：

```text
范围：critical_endgame_policy_diverse_v1
说明：以下是公开硬约束下等权物理分配的组合边际，不是隐藏牌事实；P=至少持有一张，E=期望张数。
玩家2（余4张）：3[P=1/2,E=1/2]；4[P=0,E=0]
玩家3（余4张）：3[P=1/2,E=1/2]；4[P=1,E=1]
```

要求：

- 前两行文案逐字固定；
- 玩家沿 `confidence.players` 顺序；
- rank 沿已验证 canonical 顺序；
- 每个玩家输出其全部 rank，不按概率做 Top-K、过滤或重排；
- 只允许使用验证后的玩家整数 ID、容量、canonical rank 和精确分数插值；
- 不输出物理分母原始字段、diagnostics、source 内部字段或完整 `to_dict()`；
- 相同输入必须产生完全相同文本。

## 七、预算与 fail-closed

完整文本生成后使用 `len(text)` 检查字符数。

若完整文本超过 `max_chars`：

- 返回 `status="omitted"`；
- `text=""`；
- `char_count=0`；
- `source="none"`；
- `calibration_scope="none"`；
- `diagnostics=("prompt_budget_exceeded",)`；
- 不允许截断、删玩家、删 rank 或保留部分文本。

任何输入验证失败也必须整体 omitted，不抛出由 malformed dataclass 导致的异常。

diagnostics 至少覆盖：

- `invalid_confidence_state`
- `confidence_unavailable`
- `invalid_phase`
- `invalid_source`
- `invalid_calibration_scope`
- `confidence_diagnostics_present`
- `invalid_external_unknown_count`
- `invalid_denominator`
- `invalid_player`
- `duplicate_player`
- `invalid_capacity`
- `capacity_mismatch`
- `invalid_rank_order`
- `duplicate_rank`
- `rank_set_mismatch`
- `invalid_rank_marginal`
- `prompt_budget_exceeded`

omitted 一律空文本、零字符、`source/scope="none"`，不得泄露部分内容。

ready 一律复制固定 source/scope，`diagnostics=()`，且 `char_count=len(text)`。

## 八、安全边界

formatter 只能消费 `CardConfidenceState`。

禁止：

- 读取 observation 或 history；
- 读取 ground truth 或 `game._state`；
- 导入 evaluation、engine、DeepSeekClient、DeepSeekAIAgent 或 RAG；
- 调用 pipeline、belief、constraints 或 allocation；
- 修改任何动作或提示词。

本步骤完成后，现有 DeepSeek prompt 必须逐字保持不变。

## 九、测试要求

`tests/test_card_confidence_prompt.py` 至少覆盖：

### 正常格式

- 两玩家、多 rank 的完整固定 snapshot；
- presence 与 expected-copy 分别约分；
- 0、1、整数大于 1 和普通 `n/d`；
- 玩家顺序与 canonical rank 顺序；
- `char_count == len(text)`；
- frozen/slots、JSON 序列化和重复调用稳定。

### 状态边界

- unavailable；
- phase、source、scope 不符；
- confidence diagnostics 非空；
- external count、分母为 0、负数、float、`bool`；
- players 非 tuple 或为空；
- 玩家 ID 越界、`bool`、重复或非法类型；
- capacity 非法；
- ranks 非 tuple、为空、重复、未知或乱序；
- marginal denominator 不一致；
- presence/copy 分子为负、越界、float、字符串、`None`、`bool`。

所有 malformed 输入必须 omitted 且不抛异常。

### 字符预算

- 文本长度恰好等于预算时 ready；
- 比预算多 1 时整体 omitted；
- 超预算 payload 不包含任何玩家或 rank 文本；
- `max_chars` 为 0、负数、float、`bool` 或大于 2400 时抛 `ValueError`。

### 隔离

- formatter 源码不包含 observation、history、ground truth、evaluation、engine、DeepSeek 或 RAG 读取；
- `agents/deepseek_client.py` 与 `agents/deepseek_ai.py` 不导入或调用新 formatter；
- 现有 `_build_structured_prompt()` snapshot 不变。

## 十、验证命令

运行：

```bash
python -m unittest tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence -q
python -m unittest tests.test_deepseek_prompt_step_h tests.test_rag_step_h tests.test_action_pruning -q
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "observation|history|ground_truth|game\._state|evaluation|engine|deepseek|rag" agents/card_confidence_prompt.py
rg -n "card_confidence_prompt" agents/deepseek_ai.py agents/deepseek_client.py agents/rag_advisor.py cli engine
```

第二条必须无匹配；第一条不允许实际导入或读取。

## 十一、验收标准

完成后必须同时满足：

- 只新增两个文件；
- payload frozen/slots 且可 JSON 序列化；
- ready 只来自严格合法 available confidence；
- 精确分数和固定文本 snapshot 通过；
- 2400 字符硬上限生效；
- 超限和 malformed 输入整体 omitted；
- 不修改 DeepSeek prompt、agent 或动作路径；
- 定向与全量测试通过；
- `git diff --check` 通过。

## 十二、输出要求

最终报告必须包含：

1. 修改文件；
2. payload 字段和 formatter 签名；
3. 固定文本 snapshot 示例；
4. 精确分数与预算处理；
5. fail-closed diagnostics；
6. 定向和全量测试结果；
7. 边界扫描结果；
8. 明确说明 DeepSeek prompt、RAG、剪枝和动作仍未消费 confidence。

完成后停止，不扩展到 J-D1c3c2b2，不修改 docs。
