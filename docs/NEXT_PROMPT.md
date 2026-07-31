# 下一步实施提示词

## Step J-D1c3c2a：默认关闭的 runtime confidence shadow 装配

请在 GuanDan 项目中实现 Step J-D1c3c2a。任务是把已封板的 J-A -> J-B1 -> J-D1b -> confidence 流水线装配到一个独立 runtime orchestration 模块，并在 `DeepSeekAIAgent` 中增加默认关闭的 shadow 审计开关。

本步骤不得让 confidence 进入 prompt、RAG、剪枝、策略或动作选择。目标是先证明装配安全、失败关闭以及 shadow off/on 的决策等价性。

## 一、前置状态

J-D1c3c1/J-D1c3c1a 已完成：

- `agents/card_confidence.py` 提供 frozen runtime confidence 契约；
- available 仅限 `critical_endgame`、1..12 张外部未知牌和完整精确分配；
- malformed 输入整体 unavailable；
- 单文件 11 项、相关 80 项、全量 322 项测试通过；
- 当前 DeepSeek、RAG、CLI 和 engine 尚未引用 confidence。

`agents/card_confidence.py` 与 `tests/test_card_confidence.py` 当前可能尚未提交或未跟踪。保留这些文件，不要删除或还原。

## 二、修改范围

允许新增：

- `agents/card_confidence_pipeline.py`
- `tests/test_card_confidence_pipeline.py`

允许最小修改：

- `agents/deepseek_ai.py`
- `tests/test_deepseek_prompt_step_h.py`

不要修改：

- `agents/card_confidence.py`
- `agents/card_belief.py`
- `agents/card_constraints.py`
- `agents/card_allocations.py`
- `agents/deepseek_client.py`
- `config.py`、`.env.example`、CLI
- RAG、opening、剪枝或 engine
- evaluation 或 docs

不得新增依赖，不扩展到 J-D1c3c2b。

## 三、独立 pipeline

在 `agents/card_confidence_pipeline.py` 提供：

```python
build_runtime_card_confidence(
    observation: dict[str, object],
    phase_context: GamePhaseContext,
    *,
    max_external_cards: int = 12,
    max_search_nodes: int = 1_000_000,
    max_solutions: int = 100_000,
) -> CardConfidenceState
```

行为必须为：

1. 使用调用方传入的 `GamePhaseContext`，不得再次调用 `classify_game_phase()`；
2. phase 不是 `critical_endgame` 时立即返回 unavailable；
3. 非 critical 路径不得调用 `build_card_belief()`、`build_card_constraints()` 或 `enumerate_card_allocations()`；
4. critical 路径严格按以下顺序各调用一次：

```text
build_card_belief(observation, phase_context)
  -> build_card_constraints(card_belief)
  -> enumerate_card_allocations(card_belief, constraints, locked limits)
  -> build_card_confidence(card_belief, constraints, allocation)
```

5. `max_external_cards` 不得允许超过已验证上限 12；
6. 参数必须为非 `bool` 正整数；非法参数显式抛 `ValueError`，这是调用方编程错误；
7. 公开流水线任一内部异常必须被规范为 unavailable，不向 agent 传播；
8. 不读取 ground truth、`game._state` 或任何 engine 内部状态。

pipeline 生成的 unavailable 状态必须：

- `status="unavailable"`；
- `source="none"`；
- `calibration_scope="none"`；
- `physical_assignment_count=0`；
- `players=()`；
- diagnostics 使用稳定类别，不包含异常文本或 observation 内容。

至少使用：

- `invalid_phase_context`
- `unsupported_phase`
- `pipeline_error`

正常 builder 返回的 unavailable 状态应原样返回，不要覆盖其诊断。

## 四、DeepSeek shadow 开关

在 `DeepSeekAIAgent` 增加：

```python
card_confidence_shadow_enabled: bool = False
last_card_confidence: CardConfidenceState | None = field(
    default=None,
    init=False,
    repr=False,
)
```

为避免默认路径加载新流水线：

- 类型注解可使用 `TYPE_CHECKING` 和字符串前向引用；
- 仅在开关为真且需要 shadow 计算时 lazy-import pipeline；
- 不向 `AppConfig` 增加字段，不读取环境变量。

`select_action()` 必须满足：

1. 每次调用开始先把 `last_card_confidence` 重置为 `None`；
2. only-pass shortcut 不计算 confidence；
3. 一次出完 shortcut 不计算 confidence；
4. opening formula 本地命中时不计算 confidence；
5. 默认关闭时不导入、不调用 pipeline；
6. 开启后只调用一次 pipeline，并把结果保存到 `last_card_confidence`；
7. 不把结果传给 prune、RAG、prompt builder 或 `suggest_action_id()`；
8. 不新增 verbose 输出；
9. pipeline 返回 unavailable 或内部失败时，原有模型调用和 fallback 继续执行；
10. 不改变 `last_decision_source` 语义。

## 五、严格等价边界

本步骤禁止修改 `DeepSeekClient` 方法签名或 prompt 文本。

对于相同的：

- observation；
- legal actions；
- agent 配置；
- RAG/hand evaluation/card tracker 输入；
- client 返回或异常；

shadow off/on 必须得到相同：

- pruned action IDs；
- `suggest_action_id()` keyword 参数；
- 最终 action ID；
- `last_decision_source`；
- fallback 行为。

唯一允许差异是开启态的 `last_card_confidence`。

## 六、测试要求

### Pipeline 单元测试

`tests/test_card_confidence_pipeline.py` 至少覆盖：

- critical 正常路径按顺序各调用一次并返回 available；
- pipeline 把同一个 `phase_context` 传给 J-A；
- opening/midgame/endgame/near-open 均立即 unavailable；
- 非 critical 不调用 J-A/J-B1/allocation/confidence；
- J-A、J-B1、allocation、confidence 每一层分别抛异常时返回 `pipeline_error`；
- builder 自身返回 unavailable 时保持原对象或完整内容；
- `max_external_cards > 12`、0、负数、float、`bool` 非法；
- search nodes/solutions 的 0、负数、float、`bool` 非法；
- 不重复调用阶段分类器；
- 输出可 JSON 序列化且不包含输入 observation。

### Agent shadow 测试

在 `tests/test_deepseek_prompt_step_h.py` 或新测试文件覆盖：

- 默认构造时开关为 False、审计值为 None；
- 关闭态不导入/调用 pipeline；
- 每次决策重置旧审计值；
- 三类 local shortcut 不调用 pipeline；
- 开启 critical 时 pipeline 恰好调用一次，返回值保存为最后审计状态；
- 开启非 critical 时可保存 unavailable，但不得启动 allocation；
- pipeline unavailable 不改变模型动作；
- pipeline 抛出意外异常时 agent 仍按原路径决策，不传播异常；
- client 成功和 client 失败 fallback 两种情况下，shadow off/on action 与 decision source 相同；
- 捕获并比较 off/on 传给 client 的完整 keyword 参数，必须相等；
- `_build_structured_prompt()` 输出 snapshot 不变且不包含 confidence 新标题或字段。

不要通过真实 DeepSeek 网络调用测试。

## 七、验证命令

先运行：

```bash
python -m unittest tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h -q
```

再运行相关回归：

```bash
python -m unittest tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_card_allocations tests.test_card_constraints tests.test_card_belief tests.test_game_phase tests.test_action_pruning tests.test_opening_strategy tests.test_rag_step_h -q
```

最后运行：

```bash
python -m unittest discover -q
git diff --check
```

边界扫描：

```bash
rg -n "card_confidence" agents/deepseek_client.py agents/rag_advisor.py cli engine
rg -n "ground_truth|game\._state|evaluation" agents/card_confidence_pipeline.py
```

两条均不得出现实际导入或读取。

## 八、验收标准

完成后必须同时满足：

- 只修改四个约定文件，并保留既有两个 confidence 文件；
- pipeline 只复用公开推断层和统一 phase；
- 非 critical 不启动枚举；
- 默认关闭路径不调用 pipeline；
- shadow 开启只写审计状态；
- prompt、client 参数、action ID 和 decision source off/on 等价；
- pipeline 失败不影响原决策或 fallback；
- 不修改 AppConfig、环境变量、CLI、RAG 或 engine；
- 定向、相关和全量测试通过；
- `git diff --check` 通过。

## 九、输出要求

最终报告必须包含：

1. 修改文件；
2. pipeline 调用顺序和 fail-closed 诊断；
3. shadow 字段、默认值和实际插入位置；
4. off/on 等价性测试覆盖；
5. 定向、相关和全量测试结果；
6. 边界扫描结果；
7. 明确说明 prompt、RAG、剪枝和动作选择没有消费 confidence；
8. 明确说明本步骤不构成策略收益或胜率结论。

完成后停止，不扩展到 J-D1c3c2b，不修改 docs。
