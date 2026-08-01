# 下一步实施提示词

## Step J-D1c3c2c3a：无网络成对动作消融载体

请在 GuanDan 项目中实现 Step J-D1c3c2c3a。任务是新增一个 evaluation-only、provider 可注入、固定样本、顺序平衡的 confidence-off/on 动作消融载体，并用确定性假 provider 完成单元测试和小型开发双运行。

本步骤不得调用真实 DeepSeek、HTTP 或其他网络，不得读取 `.env` / API key，不得评价动作质量或胜率。它只证明后续真实 API 实验的采样、配对、合法性分类和聚合载体可信。

## 一、前置结论

J-D1c3c2c2a 已正式通过：

- 运行 HEAD `6b62156a98cfb97dd11e30df5f95a62dba99accd`；
- 实现检查点 `bc689a37f462672033d754cce7060897d70c7612`；
- seed `11000..11049`，四策略各 50 局；
- 两份 9218-byte JSON 逐字节一致；
- SHA-256 为 `679f1f4b7f33fc821cdda4725681abbf86a3204c3b03775c0b2858ce2df9d37b`；
- 四策略共 5733 个 critical 样本；
- 16 个范围全部 available、ready、exact insertion，零 omitted/mismatch/diagnostics；
- payload 最大 683 字符，全部满足 2400 预算和固定 +11 字符关系；
- 唯一判定 `confidence_prompt_coverage_verified`。

原 seed `10000..10049` 的 J-D1c3c2c2 仍保持 `benchmark_invalid`，不得改写历史结论。

## 二、允许修改范围

只允许新增：

- `evaluation/confidence_action_ablation.py`
- `tests/test_confidence_action_ablation.py`

不得修改：

- `agents/`
- `engine/`
- `cli/`
- `rag/`
- `config.py`
- `.env` / `.env.example`
- 既有 `evaluation/` 文件
- 既有测试
- `docs/`

不要扩展到真实 API、默认开关、策略接入、RAG、剪枝或对局胜率评测。

## 三、核心公开 API

在 `evaluation/confidence_action_ablation.py` 中新增：

- `ActionAblationBucket`
- `PolicyActionAblationReport`
- `ConfidenceActionAblationReport`
- 必要的 provider Protocol/类型别名
- `run_confidence_action_ablation(...)`

建议函数签名至少包含：

```python
run_confidence_action_ablation(
    seeds,
    *,
    suggestion_provider,
    strategic_pass_rates=(0, 25, 50, 100),
    samples_per_bucket=4,
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
)
```

`suggestion_provider` 必须显式传入，无默认实现。载体不得创建 `DeepSeekClient`、读取环境配置或自行发网络请求。后续真实实验可以显式传入 `client.suggest_action_id`，但本步骤不这样做。

## 四、输入校验

沿用现有 benchmark 的严格风格：

- seeds 必须为非空、唯一、非 bool 整数序列；
- rates 必须为非空、唯一、0..100 的非 bool 整数序列；
- `samples_per_bucket`、`max_steps`、`max_samples_per_game`、搜索上限必须为非 bool 正整数；
- `max_external_cards` 不得超过 12；
- current level rank 必须为合法普通 rank；
- provider 必须 callable；
- 不得静默纠正非法参数。

非法输入显式抛出 `ValueError`。

## 五、公开样本采集

复用现有公开轨迹边界：

- 每个 strategic-pass rate 创建独立游戏和 `StrategicPassAIAgent`；
- 只读取 `game.observe()` 与 `game.legal_actions()`；
- 只采集统一阶段为 `critical_endgame` 的局面；
- 按 `external_0_4`、`external_5_8`、`external_9_12` 三个互斥桶处理；
- 样本身份仅在内存使用 `(seed, step_no, observer_player_id)`；
- 重复样本、步数上限、每局样本上限和异常 external count 都必须诊断；
- 不读取 ground truth、`game._state` 或任何隐藏手牌。

仅保留符合真实模型调用路径的样本：

- legal actions 非空；
- 不是 only-pass；
- 不存在可一次出完的非 pass action；
- phase 为 critical，因此不得额外运行 opening formula；
- `build_runtime_card_confidence()` 返回 available；
- `build_card_confidence_prompt_payload()` 返回 ready；
- off/on prompt 精确满足已封板的单章节插入关系；
- pruned prompt candidates 非空。

only-pass、一次出完、confidence unavailable、payload omitted 和 prompt mismatch 必须分别计数，不得调用 provider。

## 六、固定样本选择

不能简单取每桶最早 N 个样本。为每个内部样本计算固定优先级：

```text
SHA-256(policy_name | bucket_name | seed | step_no | observer_player_id)
```

要求：

- 不使用 Python `hash()`、随机数或时间；
- 每策略/每桶选择优先级最小的 `samples_per_bucket` 个合格样本；
- 先完成该策略公开轨迹采集，再按 `(priority_digest, step_no, observer_player_id)` 稳定排序；
- 只在内存保留被选中的公开 observation、legal actions、phase 和 ready payload；
- report 不输出 priority、seed、step/player 或样本内容；
- 样本不足时保留实际数量并诊断 `sample_quota_not_reached`。

## 七、off/on 请求配对

为每个选中样本构造一个共同 kwargs mapping，至少包括：

- `observation`
- 完整 `legal_actions`
- 同一份 `prompt_actions`
- `rag_context=None`
- `hand_evaluation=None`
- `card_tracking_summary=None`
- 同一 `phase_context`
- `verbose=False`
- 稳定且不含样本身份的 `debug_prefix`

off 调用使用共同 mapping；on 调用只额外增加：

```python
card_confidence_prompt=ready_payload
```

硬性要求：

- off/on kwargs 的键差只能是 `card_confidence_prompt`；
- 所有共同值逐字段相等；
- 完整 legal IDs 和 prompt candidate IDs 完全相同；
- off/on 结构化 prompt 必须精确满足已验证的固定章节插入关系；
- 对 prompt pair 做 SHA-256 聚合，但 report 不保留 prompt 文本。

## 八、AB/BA 顺序

真实服务即使 `temperature=0` 也不能假设完全确定，因此调用顺序不能与条件绑定。

- 在每个策略/每个 external bucket 内按选中样本稳定序列交替 `off->on` 与 `on->off`；
- 每桶两种顺序数量差不得超过 1；
- 记录 off-first / on-first pair count；
- 一侧 provider 抛异常、返回 malformed 或无 action 时，仍必须调用另一侧；
- harness 本身不重试，provider 内部行为由后续正式步骤另行锁定。

## 九、provider 结果校验

provider 返回值按 `DeepSeekSuggestion` 契约处理，但必须 fail-closed：

- provider 抛异常：计入对应 condition exception；
- 返回对象类型错误：计入 malformed result；
- `action_id is None`：计入 no-action；
- bool、字符串、float 等非严格整数：计入 invalid action type；
- 不在完整 legal IDs：计入 outside legal；
- 在完整 legal IDs 但不在 prompt candidate IDs：计入 outside prompt；
- 只有严格非 bool 整数且同时属于 legal/prompt candidate 才是 valid response；
- reasoning 不评分、不序列化、不保留。

不得调用 fallback RuleBasedAI 替换失败结果。该实验评估模型响应本身，fallback 会掩盖失败率。

## 十、聚合指标

每个策略先聚合 requested/completed/incomplete games、strategic-pass opportunity/active pass，以及 eligible critical、duplicate、sample-limit、unexpected external 等轨迹完整性计数。

每个策略的 overall 和三个 external bucket 至少聚合：

- only-pass skip、finish-action skip；
- confidence unavailable、payload omitted、prompt mismatch；
- qualified candidate 与 quota-not-selected count；
- selected sample count；
- off-first / on-first pair count；
- off/on attempted call count；
- off/on valid response count；
- off/on no-action count；
- off/on exception count；
- off/on malformed result count；
- off/on invalid action type count；
- off/on outside-legal count；
- off/on outside-prompt count；
- both-valid pair count；
- only-off-valid / only-on-valid / neither-valid count；
- same-action / changed-action count；
- off/on pass selection count；
- off/on pressure selection count，pressure 为 bomb/straight_flush/joker_bomb；
- prompt pair digest；
- 规范化 diagnostics。

overall 必须由三个桶的原始整数计数相加，不能平均比例。所有计数必须满足守恒，例如：

- attempted = selected samples；
- off-first + on-first = selected samples；
- both-valid + only-off-valid + only-on-valid + neither-valid = selected samples；
- same-action + changed-action = both-valid；
- 各结果类别不能重复计入同一 condition。

## 十一、报告安全

所有报告对象使用 frozen/slots dataclass；mapping 使用不可变副本；`to_dict()` 可被 `json.dumps(..., allow_nan=False)` 序列化。

报告不得包含：

- seed 或 seed 列表；
- 样本 ID、step/player；
- observation、history、hand；
- prompt 文本；
- legal actions、prompt actions；
- 具体 action_id；
- reasoning 或 provider 原始响应；
- API key、URL、model response；
- ground truth。

策略和 external bucket 必须按显式名称/rate 验证，不得依赖 canonical JSON 的 mapping 键顺序表达业务顺序。

## 十二、测试要求

`tests/test_confidence_action_ablation.py` 至少覆盖：

1. 全部严格输入校验；
2. external bucket 边界；
3. SHA-256 样本优先级和稳定选择；
4. duplicate、sample limit、max steps 和 quota 诊断；
5. only-pass / 一次出完不调用 provider；
6. unavailable / omitted / mismatch 不调用 provider；
7. off/on kwargs 只差 confidence key；
8. AB/BA 每桶平衡且双运行顺序稳定；
9. 第一侧异常后第二侧仍被调用；
10. malformed、None、bool、字符串、float、outside legal、outside prompt 分类；
11. valid same/changed action 聚合；
12. pass/pressure 计数；
13. 三桶到 overall 的整数守恒；
14. quota 不足 fail-closed 诊断；
15. frozen/slots、mapping 不可变、JSON 序列化与报告快照；
16. report 不含敏感逐样本字段；
17. 源码边界扫描不含 AppConfig、`.env`、API key、HTTP、ground truth 或 `game._state`；
18. `agents/`、CLI、RAG、engine 不导入新 evaluation 模块。

测试中只使用确定性假 provider。禁止 monkeypatch 真实网络。

## 十三、开发容量双运行

单元测试通过后，使用纯内存确定性假 provider 运行：

```text
seeds = 120..129
strategic_pass_rates = 0,25,50,100
samples_per_bucket = 4
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
```

假 provider 行为必须纯函数化：

- off 从 prompt candidates 选择第一个合法 action；
- on 从同一 prompt candidates 选择最后一个合法 action；
- 不读取时间、随机数、seed 或隐藏状态；
- 不模拟网络异常；
- 不保留 reasoning。

完整运行两次并要求：

- 两份 report 和 `to_dict()` 完全相等；
- canonical JSON SHA-256 相同；
- 四策略均 10/10/0 games；
- 每策略每桶恰好选择 4 个样本，如不足则不得给出通过判定；
- 总样本 48、provider 逻辑调用 96 次；
- off/on attempted 均等于 48；
- 每桶 AB/BA 各 2；
- exception/malformed/invalid/outside/no-action 均为 0；
- 所有 pair both-valid；
- 所有 diagnostics 为空；
- 运行前后工作区除本任务两个新文件外无其他变化。

开发双运行不调用真实 DeepSeek，不设置真实 API 门槛，也不形成动作质量或胜率结论。

## 十四、验证命令

至少运行：

```bash
python -m unittest tests.test_confidence_action_ablation -q
python -m unittest tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

并运行边界扫描，确认没有 runtime 反向导入或网络/真值访问。

## 十五、唯一开发判定

严格输出一个结论：

1. 实现、测试、守恒、双运行、容量、隐私或边界任一失败：`confidence_action_ablation_harness_invalid`；
2. 全部通过：`confidence_action_ablation_harness_verified`。

该判定只授权下一步预注册小规模真实 DeepSeek 响应实验，不授权默认启用 confidence，不代表动作质量或胜率提升。

## 十六、最终报告

完成后报告：

1. 修改文件；
2. 核心数据契约与 provider 边界；
3. 样本选择、shortcut 排除和 AB/BA 顺序规则；
4. 响应分类与所有守恒；
5. 定向、相关、全量测试和 `git diff --check`；
6. 开发双运行参数、耗时、报告相等性和 SHA-256；
7. 四策略/三桶样本、调用和顺序计数；
8. valid/异常/非法/same/changed/pass/pressure 聚合；
9. 边界扫描结果；
10. 唯一开发判定；
11. 明确说明未调用 DeepSeek、未形成动作质量或胜率结论。

完成后停止，不修改 docs，不扩展到 J-D1c3c2c3b。
