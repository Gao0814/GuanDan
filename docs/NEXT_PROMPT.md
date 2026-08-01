# 下一步实施提示词

## Step J-D1c3c2c3c1：确定性分支续局质量载体

请在 GuanDan 项目中实现 Step J-D1c3c2c3c1。任务是建立 evaluation-only 的动作质量代理：对同一个 critical 局面复制独立游戏分支，分别执行 confidence-off/on 的合法动作，再用 RuleBasedAIAgent 推进到终局，以预注册的团队结果和团队完赛名次字典序比较两个动作。

本步骤只使用确定性假 provider，不调用 DeepSeek、HTTP 或其他网络，不读取 `.env` / API key，不修改规则引擎。它只证明质量评估载体可重复、可审计，不形成真实模型动作质量或胜率结论。

## 一、前置结论

c3a 实现检查点：

```text
e0065c6a3da70b3d4ded4b394817bfab3351c113
J-D1c3c2c3a harness
```

c3b live pilot 唯一判定：

```text
retain_for_action_quality_evaluation
```

c3b 关键事实：

- endpoint/model：`https://api.deepseek.com` / `deepseek-v4-pro`；
- seed `13000..13009`，四策略每桶 2 个样本；
- 24 pair / 48 logical/physical requests；
- 48 响应全部 valid，24 pair 全部 both-valid；
- same/changed = 13/11；
- off/on pass 均为 6，pressure 均为 0；
- 未运行完整 DeepSeek 对局；
- 11 个 changed 不能排除服务非确定性，不代表 confidence 导致变化或动作更优。

本步骤不得复用 c3b 的模型 action ID；这些 ID 没有被持久化。不要读取、恢复或推断逐样本模型选择。

## 二、允许修改范围

允许：

- 最小修改 `evaluation/confidence_action_ablation.py`
- 最小修改 `tests/test_confidence_action_ablation.py`
- 新增 `evaluation/confidence_action_quality.py`
- 新增 `tests/test_confidence_action_quality.py`

不得修改：

- `engine/`
- 其他 `agents/`
- `agents/deepseek_client.py`
- `agents/deepseek_ai.py`
- `config.py`
- CLI、RAG
- `.env` / `.env.example`
- 其他 evaluation/test 文件
- `docs/`

对 c3a 的修改只能用于复用固定样本和成对 provider 执行逻辑。不得改变现有公开 API、默认参数、报告字段或默认行为。

## 三、c3a 向后兼容硬门槛

修改前先运行并记录：

```bash
python -m unittest tests.test_confidence_action_ablation -q
python -m unittest discover -q
git diff --check
```

修改后必须证明：

- `run_confidence_action_ablation()` 签名和默认值不变；
- 三个现有 public report dataclass 的字段、`to_dict()` 和语义不变；
- 现有六项 c3a 测试继续通过；
- 使用原开发参数 seed `120..129`、四策略、每桶 4 样本和同一确定性假 provider，report 与 `to_dict()` 快照不变；
- canonical SHA-256 仍精确为：

```text
ce3262ad0e8f3e3baf0e885ad75f3a11fcc57d5b035599fdce06fe9c7d7a9095
```

任一不兼容都判定本任务失败，不得用新 hash 替代旧基线。

## 四、新模块公开 API

在 `evaluation/confidence_action_quality.py` 中新增：

- `RuleRolloutOutcome`
- `ActionQualityBucket`
- `PolicyActionQualityReport`
- `ConfidenceActionQualityReport`
- `run_confidence_action_quality(...)`

建议函数签名：

```python
run_confidence_action_quality(
    seeds,
    *,
    suggestion_provider,
    strategic_pass_rates=(0, 25, 50, 100),
    samples_per_bucket=2,
    current_level_rank="2",
    max_steps=5000,
    max_samples_per_game=128,
    max_external_cards=12,
    max_search_nodes=1_000_000,
    max_solutions=100_000,
    max_rollout_steps=5000,
)
```

provider 必须显式注入，无默认 client 或网络实现。严格输入校验沿用 c3a，新增 `max_rollout_steps` 为非 bool 正整数。

## 五、候选采集与状态分支

复用 c3a 已封板规则：

- 每策略独立 `GuanDanGame` 和 `StrategicPassAIAgent`；
- 只采集 critical/public observation/legal actions；
- external 0-4、5-8、9-12 三桶；
- 排除 only-pass、一次出完、confidence unavailable、payload omitted 和 prompt mismatch；
- 每桶按同一 SHA-256 优先级选择最小 N 个样本；
- off/on kwargs 只差 `card_confidence_prompt`；
- 每桶稳定交替 AB/BA；
- provider 结果按 c3a 的严格类型、legal/prompt candidate 域分类；
- 非 both-valid pair 不进入 rollout，只保留 fail-closed 计数。

质量模式需要在选中局面的动作执行前保留 evaluation-only 游戏快照。可使用 `copy.deepcopy(game)`，但必须满足：

- 不直接读取或写入 `game._state`；
- 不修改 `GuanDanGame` 或 engine API；
- clone 前后原 game observation/legal actions 不变；
- clone 的 observation 与 legal actions 和原 game 完全相等；
- clone 与原 game 的后续 step 互不影响；
- action ID 在 clone 的当前 legal actions 中仍对应同一 public action；
- 只为最终入选 reservoir 的样本保留 clone，避免保存所有合格局面；
- clone 仅存在于内存，不进入 report。

如果无法在不读 `_state` 的情况下满足上述契约，停止并报告 blocker，不要修改 engine。

## 六、确定性 RuleBased rollout

对每个 both-valid pair：

1. 校验 observer player ID 为 1..4；
2. 若 off/on action 相同，只复制并运行一个分支，结果同时复用于 off/on；
3. 若动作不同，创建两个彼此独立的 snapshot clone；
4. 每个分支先执行对应模型 action ID；
5. 若未终局，为玩家 1..4 创建该分支独立的 `RuleBasedAIAgent`；
6. 每步只调用 clone 的 `observe()`、`legal_actions()`、agent `select_action()` 和 `step()`；
7. 每个动作都通过 `require_legal_action_id()`；
8. 最多执行 `max_rollout_steps`，包含最初模型动作；
9. 达到终局后只读取最终 `step()` 结果和 terminal public observation；
10. rollout 不使用 DeepSeek、confidence、RAG、ground truth 或隐藏状态。

一条分支失败不能抛出并丢失整个 report；按类别记录：

- `clone_mismatch`
- `initial_action_invalid`
- `rollout_action_invalid`
- `rollout_exception`
- `rollout_step_limit_reached`
- `invalid_terminal_winner`
- `invalid_finish_order`

失败分支不输出部分质量结论。

## 七、终局公开结果规范化

winner 只允许：

- `team_13`
- `team_24`
- `draw`

finish order 从 terminal public observation 的 `history.finish_order` 读取：

- 玩家 ID 必须为严格非 bool 整数 1..4；
- 不得重复；
- 长度为 4 时直接使用；
- 长度为 3 时补入唯一未出现玩家为末游；
- 其他长度、多个缺失或非法玩家均 fail-closed；
- 不读取引擎内部 final order。

`RuleRolloutOutcome` 至少包含聚合所需的：

- observer team outcome：win/draw/loss；
- observer team outcome score：2/1/0；
- team placement sum；
- rollout step count；
- complete 状态与 diagnostics。

该对象不得包含整手牌、隐藏状态或逐步轨迹。

## 八、质量比较规则

只对 off/on 两个 rollout 都 complete 的 pair 比较，固定字典序：

1. observer team outcome score 更高者更优；
2. outcome score 相同时，observer team 两位玩家 finish positions 之和更小者更优；
3. 两者仍相同则 tie。

不得使用以下内容作为事后 tie-break：

- rollout 步数；
- 是否 pass；
- 是否 pressure；
- 手牌张数；
- 模型 reasoning；
- 人工主观评分。

same action 且 rollout complete 必须得到 tie；不能重复运行制造差异。

## 九、聚合报告

每个策略 overall 和三个 external bucket 至少聚合：

- selected pair、provider off/on attempted 与 valid；
- both-valid、same/changed；
- rollout branch attempted/completed/failed；
- same-action reused rollout count；
- quality evaluable / unevaluable pair count；
- on-better / off-better / tie；
- changed-on-better / changed-off-better / changed-tie；
- off/on team win/draw/loss；
- off/on team placement sum total；
- off/on rollout step total；
- clone/initial/rollout/terminal diagnostics；
- corpus/prompt-pair digest；
- provider 和 strategic-pass 完整性计数。

守恒至少包括：

- same + changed = both-valid；
- quality evaluable + unevaluable = both-valid；
- on-better + off-better + tie = quality evaluable；
- changed 三种比较结果合计 = complete changed pairs；
- off win + draw + loss = quality evaluable；
- on win + draw + loss = quality evaluable；
- branch attempted = changed * 2 + same；
- branch completed + branch failed = branch attempted；
- overall 为三桶原始计数之和，不平均比例。

若 same action 复用一次 rollout，off/on outcome 和 placement/steps 聚合仍各计一次，以保持 condition 对称；实际 branch attempted 只计一次。

## 十、报告安全边界

所有 report 使用 frozen/slots dataclass；mapping 不可变；`to_dict()` 可由 `json.dumps(..., allow_nan=False)` 序列化。

报告不得包含：

- seed 或 seed 列表；
- 样本 ID、step/player；
- observation、history、prompt；
- legal/prompt actions 或 action ID；
- game/clone/state；
- 手牌或 ground truth；
- provider 响应或 reasoning；
- 逐分支 winner/finish order；
- API key、URL 或模型配置。

runtime agents、CLI、RAG 和 engine 不得导入新 evaluation 模块。

## 十一、测试要求

`tests/test_confidence_action_quality.py` 至少覆盖：

1. 新参数严格校验，包括 bool；
2. deepcopy 后 observation/legal actions 相等且状态推进独立；
3. clone action ID/public action 对应一致；
4. same action 只运行一次并复用；
5. changed action 运行两个独立分支；
6. 四个 RuleBased agent 每分支独立；
7. rollout max steps 边界；
8. clone mismatch、非法初始动作、后续非法动作和异常 fail-closed；
9. winner 三种合法值与非法值；
10. finish order 长度 3 补末游、长度 4、重复、非法和缺失；
11. observer 为 team 13 / team 24 的 win/draw/loss 映射；
12. team outcome 优先于 placement sum；
13. outcome 相同时 placement sum 比较；
14. 完全相同为 tie，步数不得打破 tie；
15. provider 非 both-valid 不 rollout；
16. 三桶到 overall 的全部守恒；
17. report frozen/slots、mapping 不可变、JSON 和隐私扫描；
18. 双运行报告确定性；
19. 源码不含 `game._state`、ground truth、AppConfig、`.env`、API key、HTTP/urlopen；
20. runtime 不反向导入 evaluation。

测试可使用小型真实 seed 游戏、preset hands 或测试替身，但不得为通过测试修改 engine。

## 十二、开发双运行

使用确定性假 provider：off 选 prompt candidates 第一个，on 选最后一个。

锁定参数：

```text
seeds = 140..149
strategic_pass_rates = 0,25,50,100
samples_per_bucket = 2
current_level_rank = 2
max_steps = 5000
max_samples_per_game = 128
max_external_cards = 12
max_search_nodes = 1,000,000
max_solutions = 100,000
max_rollout_steps = 5000
```

完整运行两次，要求：

- report、`to_dict()` 和 canonical JSON 完全相等；
- canonical SHA-256 相同；
- 四策略均 10/10/0 games；
- 每策略每桶 selected=2，overall=6，总计 24 pair；
- off/on provider attempted 各 24；
- provider 异常、malformed、no-action、非法类型、outside legal/prompt 均为 0；
- 24 pair 全部 both-valid；
- 所有 rollout complete，无 clone/step/terminal diagnostics；
- quality evaluable=24；
- on-better + off-better + tie = 24；
- 所有整数守恒通过；
- 不要求 on-better 大于 off-better；
- 运行前后无本任务范围外改动。

同时重跑 c3a 原 seed `120..129` 开发基线，确认 canonical hash 仍为 `ce3262ad...a9095`。

## 十三、验证命令

至少运行：

```bash
python -m unittest tests.test_confidence_action_quality -q
python -m unittest tests.test_confidence_action_quality tests.test_confidence_action_ablation tests.test_confidence_prompt_benchmark tests.test_card_confidence_prompt tests.test_card_confidence_pipeline tests.test_card_confidence tests.test_deepseek_prompt_step_h tests.test_pass_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

并运行边界扫描，确认没有 engine 修改、runtime 反向导入、网络、配置、真值或直接 `_state` 访问。

## 十四、唯一开发判定

严格只输出一个：

1. c3a 兼容性、clone 独立性、rollout、终局规范化、质量比较、守恒、双运行、隐私或边界任一失败：`confidence_action_quality_harness_invalid`；
2. 全部通过：`confidence_action_quality_harness_verified`。

通过只授权下一步预注册真实模型动作质量评估，不授权默认开启 confidence，不代表真实动作质量或胜率提升。

## 十五、最终报告

完成后报告：

1. 修改文件；
2. c3a 兼容性与原 canonical hash；
3. clone 捕获、独立性与仅公开接口续局边界；
4. terminal finish order 规范化和固定质量字典序；
5. provider、rollout 与质量计数守恒；
6. 定向、相关、全量测试和 `git diff --check`；
7. 开发双运行参数、耗时、相等性和 SHA-256；
8. 四策略/三桶 selected、same/changed、branch complete；
9. on-better/off-better/tie、win/draw/loss、placement/steps 聚合；
10. 边界扫描；
11. 唯一开发判定；
12. 明确说明未调用 DeepSeek、未形成真实动作质量或胜率结论。

完成后停止，不修改 docs，不扩展到 J-D1c3c2c3c2。
