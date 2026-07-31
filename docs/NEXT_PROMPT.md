# 下一步实施提示词

## Step J-D1c3c2b2：默认关闭的 DeepSeek confidence prompt 接入

请在 GuanDan 项目中实现 Step J-D1c3c2b2。任务是在现有 shadow 装配之上增加第二个默认关闭的 prompt 消费开关，并让 DeepSeekClient 只接受已经封板的类型化 `CardConfidencePromptPayload`。

本步骤只验证接线、边界和默认兼容性，不做动作收益结论，不开启默认配置。

## 一、前置状态

J-D1c3c2b1 已完成：

- `CardConfidencePromptPayload` 为 frozen/slots；
- formatter 只消费 `CardConfidenceState`；
- ready 文本使用约分精确分数；
- 固定 2400 字符预算，超限或 malformed 整体 omitted；
- formatter/confidence 相关 22 项、DeepSeek/RAG/剪枝 52 项、全量 338 项测试通过；
- 当前 agent、client、RAG、CLI、engine 尚未引用 formatter。

现有 confidence/shadow/formatter 文件可能尚未提交。保留所有已有改动，不要删除、还原或重写。

## 二、修改范围

只允许修改：

- `agents/deepseek_ai.py`
- `agents/deepseek_client.py`
- `tests/test_deepseek_prompt_step_h.py`
- `tests/test_card_confidence_prompt.py`

不要修改：

- confidence contract、pipeline 或 formatter 实现
- config.py、`.env.example`、CLI
- RAG、opening、剪枝、engine、evaluation 或 docs

不得新增文件或依赖，不扩展到 J-D1c3c2c。

## 三、三态开关契约

在 `DeepSeekAIAgent` 增加：

```python
card_confidence_prompt_enabled: bool = False
last_card_confidence_prompt: "CardConfidencePromptPayload | None" = field(
    default=None,
    init=False,
    repr=False,
)
```

保留现有：

```python
card_confidence_shadow_enabled: bool = False
last_card_confidence: CardConfidenceState | None
```

有效模式只有：

| shadow | prompt | 模式 |
|---|---|---|
| False | False | off |
| True | False | shadow-only |
| True | True | prompt |

要求：

- 两个开关都必须是实际 `bool`，拒绝 `1`、字符串等值；
- `prompt=True, shadow=False` 在 `__post_init__` 显式抛 `ValueError`；
- 不增加 AppConfig 字段；
- 不读取环境变量；
- CLI 不暴露该开关；
- 默认构造仍为 off。

## 四、Agent 接线

每次 `select_action()` 开始：

- `last_card_confidence = None`；
- `last_card_confidence_prompt = None`。

local only-pass、一次出完和 opening formula 命中时：

- 不运行 pipeline；
- 不运行 formatter；
- 两个审计字段保持 None。

模型路径：

1. shadow=False：不导入 pipeline 或 formatter；
2. shadow=True：保持 J-D1c3c2a pipeline 行为；
3. prompt=False：不导入、不调用 formatter；
4. prompt=True：仅对本步 `last_card_confidence` 调用一次 `build_card_confidence_prompt_payload()`；
5. formatter 返回值写入 `last_card_confidence_prompt`；
6. 只有 `status == "ready"` 时才向 client 传入新 keyword；
7. omitted、unavailable、pipeline 异常或 formatter 异常时不传新 keyword；
8. formatter 异常不得中断原模型调用或 fallback。

继续使用 lazy import，默认 off 路径不加载 confidence pipeline/formatter。

## 五、Client 类型化参数

为以下方法增加末尾可选参数：

```python
card_confidence_prompt: CardConfidencePromptPayload | None = None
```

- `DeepSeekClient._build_structured_prompt()`
- `DeepSeekClient.suggest_action_id()`

旧调用不传参数时，输出必须逐字不变。

DeepSeekClient 必须再次复核 payload：

- 实例类型正确；
- `status == "ready"`；
- `source == "physical_assignment_marginal_v1"`；
- `calibration_scope == "critical_endgame_policy_diverse_v1"`；
- diagnostics 为空 tuple；
- text 为非空字符串；
- char_count 为非 `bool` 正整数；
- `char_count == len(text)`；
- `char_count <= CARD_CONFIDENCE_PROMPT_MAX_CHARS`。

任一不满足时整体忽略 payload，不抛异常，不输出部分文本。

client 不得重新计算、约分、截断或修改 payload text。

## 六、Prompt 章节

合法 ready payload 新增且只新增：

```text
【残局牌面信念】
<payload.text 原文>
```

章节位置严格为：

```text
【记牌信息】
...

【残局牌面信念】
...

【场景标签】
...
```

要求：

- payload text 原样插入；
- 不添加第二份解释；
- 不改变【任务与硬约束】、【候选动作】、RAG 或【输出格式】；
- 章节最多出现一次；
- None、omitted 或 malformed payload 不出现该标题。

## 七、关闭态与 omitted 等价性

### off 与历史默认

shadow=False、prompt=False 时：

- client kwargs 键集合与 J-D1c3c2a 前完全一致；
- `_build_structured_prompt()` 文本逐字一致；
- action ID、fallback 和 decision source 一致。

### shadow-only 与 J-D1c3c2a

shadow=True、prompt=False 时：

- 不调用 formatter；
- 不传 `card_confidence_prompt` keyword；
- client kwargs、prompt、action 和 decision source 与 J-D1c3c2a 一致。

### prompt omitted

shadow=True、prompt=True，但 payload omitted/unavailable 时：

- 允许 `last_card_confidence_prompt` 保存 omitted 审计对象；
- 不传新 keyword；
- client kwargs、prompt、action、fallback 与 shadow-only 完全一致。

### prompt ready

只有 ready 时：

- client kwargs 相比 shadow-only 只新增 `card_confidence_prompt`；
- legal actions、prompt actions、RAG、hand evaluation、tracker 和 phase 参数完全相同；
- 允许模型动作因新增文本而变化，但本步骤不评估好坏。

## 八、测试要求

至少覆盖：

### 开关与审计

- 默认 off；
- 两个字段传 `1` 或字符串均 `ValueError`；
- prompt=True/shadow=False 为 `ValueError`；
- 每步重置两个审计字段；
- 三个 local shortcut 均不调用 pipeline/formatter；
- shadow-only 不调用 formatter；
- prompt 模式 formatter 恰好调用一次。

### ready / omitted / 异常

- ready payload 保存并传给 client；
- unavailable confidence 产生 omitted，且不传 client keyword；
- formatter 返回 omitted 时不传 keyword；
- formatter 抛异常时审计 payload 为 None，模型与 fallback 继续；
- pipeline 抛异常时不调用 formatter。

### Client 参数和 prompt

- 捕获 off、shadow-only、prompt-omitted、prompt-ready 四种 client kwargs；
- off 与 shadow-only kwargs 相同；
- prompt-omitted 与 shadow-only kwargs 相同；
- prompt-ready 只多一个类型化 payload；
- 旧 `_build_structured_prompt()` 固定 snapshot 逐字不变；
- ready 新章节位置、标题次数和 payload 原文 snapshot；
- None/omitted/malformed payload 不出现章节；
- malformed 覆盖错误类型、status、source、scope、diagnostics、空 text、char_count 类型/不一致/超限。

### Client 请求链

- `suggest_action_id()` 把 ready payload 传给 `_build_structured_prompt()`；
- omitted payload 被 client 忽略；
- HTTP body 中 ready prompt 只出现一次新章节；
- 不进行真实网络请求。

### 隔离

- RAG、剪枝、legal actions 和输出格式 snapshot 不变；
- config、CLI、engine、evaluation 不引用 prompt 开关；
- 更新 formatter 测试中的旧隔离断言，只允许本步骤约定的 agent/client 消费，继续禁止 RAG/CLI/engine。

## 九、验证命令

运行：

```bash
python -m unittest tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h -q
python -m unittest tests.test_rag_step_h tests.test_action_pruning tests.test_opening_strategy tests.test_deepseek_step_e -q
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "card_confidence_prompt_enabled" config.py cli engine agents/rag_advisor.py
rg -n "card_confidence_prompt" agents/rag_advisor.py cli engine evaluation
```

两条均不得出现实际引用。

## 十、验收标准

完成后必须同时满足：

- 只修改四个约定文件；
- 三态开关组合严格；
- 默认 off 和 shadow-only 完全兼容；
- omitted/unavailable 不改变 client kwargs 或 prompt；
- ready payload 类型化传递且只新增一个固定章节；
- client 对 malformed payload fail-closed；
- 不修改配置、CLI、RAG、剪枝、engine 或默认行为；
- 定向、相关和全量测试通过；
- `git diff --check` 通过。

## 十一、输出要求

最终报告必须包含：

1. 修改文件；
2. 三态开关和非法组合行为；
3. formatter 调用与审计字段生命周期；
4. client payload 复核规则；
5. 新章节 snapshot 与位置；
6. off/shadow/omitted/ready kwargs 等价性结果；
7. 定向、相关和全量测试结果；
8. 边界扫描结果；
9. 明确说明默认运行仍不消费 confidence；
10. 明确说明未形成动作质量或胜率结论。

完成后停止，不扩展到 J-D1c3c2c，不修改 docs。
