# 下一步实施提示词

## Step L5-A4b：Botzone RuleBased / DeepSeek 成对评估协议与离线聚合载体

L5-A4a 已完成并独立封存，唯一判定：

```text
botzone_finished_score_observability_verified
```

实现检查点：

```text
31e2fa5a474a377baa3fb80a4a427766623b96c7
```

v7 audit 已能在 `finished_qualified` 路径安全聚合本家团队的正常胜负、`score_0..score_3`、平台违规与非法分数形状，并保持 v6 的协议和 DeepSeek 路径观测字段。该能力仍只提供单局聚合结果，尚未定义 RuleBased / DeepSeek 的成对赛程、有效 audit 门槛、配对守恒或比较报告。

本步骤只实现 evaluation-only 的离线协议与聚合载体。不得运行 preflight、connector、runmatch、人工测试桌、DeepSeek 或任何网络请求。

### 目标

建立一个最小、确定、可审计的 Botzone 策略成对评估载体：

- 同一评估条件下分别运行 `rule` 与 `deepseek`；
- 固定 seed、座位、对手版本和全部桌面设置；
- 只消费调用方传入的脱敏 v7 audit 与非敏感赛程条件；
- 缺少任一侧、audit 无效、结果非正常或条件不匹配时，整对 fail-closed；
- 输出配对后的原始整数统计与精确有理数，不输出逐局、seed、Bot ID、match、牌或模型正文；
- 不做显著性、因果或胜率提升宣称。

### 建议范围

优先新增：

- `evaluation/botzone_policy_benchmark.py`
- `tests/test_botzone_policy_benchmark.py`

只有现有 evaluation 导出风格明确要求时，才最小更新：

- `evaluation/__init__.py`

禁止修改：

- `integrations/botzone/` 的 runtime、协议、transport、connector、session、adapter 与 audit 写入；
- `engine/`、`agents/`、CLI、RAG、配置和 `.env`；
- 上传 Bot ZIP；
- `docs/`；
- 任何真实 state/audit、密钥、URL 或账号数据。

### 固定策略与赛程模型

策略名只允许：

```text
rule
deepseek
```

新增 frozen/slots、JSON 友好的赛程条件与报告对象。实现可以在内存中保留用于配对的 seed，但最终聚合报告和 `to_dict()` 不得包含 seed 列表或逐对标识。

赛程生成必须满足：

1. seed 由调用方显式传入，必须是唯一、严格非 bool 整数；不得使用时间、全局随机数或 `hash()`。
2. 每个 seed 固定覆盖本家座位 `0..3`。
3. 每个 `(seed, seat)` 精确生成一对：一局 `rule`、一局 `deepseek`。
4. AB/BA 顺序稳定交替；每个 seat 的两种顺序数量差不超过 1。
5. 每个条件必须显式携带固定桌面 profile 版本。首版只允许：无贡、当前级牌 2、相同的上轮名次设置、相同对手 Bot/版本集合。
6. 对手 Bot ID/版本由 live 调用方在仓库外管理；不得写入源码、测试、文档或最终报告。离线载体只接受固定、非敏感的 opponent-profile digest 或调用方确认标记，不得反向保存原始 ID。
7. 赛程顺序和输入 audit 顺序不得影响聚合结果。

人工网页“随机种子”到官方裁判 initdata 的映射尚未通过成对实局证明。载体必须把 `seed_contract_confirmed` 作为严格布尔前置；为 false 时不得形成可执行赛程。该字段只表示调用方已按官方源码/UI 契约确认固定 seed，不得由载体猜测。

### v7 audit 输入门槛

聚合器只消费调用方已加载到内存的 mapping，不读取文件、state、环境变量或网络。每个 audit 必须严格满足：

- schema 精确为 `botzone_local_smoke_audit`，version 精确为 `7`；
- 与预期策略条件的 `agent_mode` 一致；
- `exit_code=0`、`stop_reason=finished_target`；
- `requests_seen`、`responses_prepared`、`headers_sent` 均为正数且彼此一致；
- `finished_qualified=1`，其余 finished 分类与总数满足 v7 守恒；
- transport failure、timeout、协议 diagnostics/detail/profile 均为 0 或空；
- `normal_result_count=1`；结果类别精确为一个 `local_team_win` 或 `local_team_loss`；
- `platform_error=0`、`invalid_score_shape=0`；
- `score_0..score_3` 精确一个桶为 1，其余为 0，并与胜负一致；
- v6 Agent/模型观测字段类型、allowlist 和守恒全部有效。

策略特定门槛：

- `rule`：所有模型尝试、模型结果、DeepSeek/adapter fallback 均为 0；最终来源只能来自规则路径允许集合。
- `deepseek`：保持 v6 的模型尝试、结果、最终来源和 fallback 守恒；允许某局因本地快捷路径而模型尝试为 0，但必须单独聚合 `model_exposed_game_count`，不得把未暴露模型的局解释为模型效果。

任一字段缺失、类型错误、bool 冒充整数、未知键值、守恒失败或策略不匹配时，该局 invalid。配对的一侧 invalid、缺失或重复时，整对不得进入质量指标。

### 配对与聚合

报告至少包含：

- requested / valid / invalid / incomplete / duplicate pair count；
- rule / deepseek valid game count；
- `deepseek_score_better` / `rule_score_better` / `equal_score`；
- 两种策略的团队 win/loss 原始计数；
- 两种策略的 `score_0..score_3` 原始计数；
- 两种策略的 score sum、精确 mean；
- paired score delta sum 与精确 mean，固定为 `deepseek - rule`；
- 两种策略的精确 win rate；
- DeepSeek 的 model-exposed game、model attempt/result、最终来源与 fallback 聚合；
- seat `0..3` 的同构子聚合；
- AB / BA 顺序计数；
- 固定低基数 diagnostics 计数。

所有比例和均值使用 `Fraction` 精确累计，并以最简整数分子/分母序列化。零分母稳定输出 `0/1`；不得产生 float、NaN 或 Infinity。

必须满足：

```text
requested_pairs = valid_pairs + invalid_pairs + incomplete_pairs
valid_pairs = deepseek_score_better + rule_score_better + equal_score
valid_pairs = rule_valid_games = deepseek_valid_games
valid_pairs = sum(rule_score_counts)
valid_pairs = sum(deepseek_score_counts)
overall = seat_0 + seat_1 + seat_2 + seat_3
valid_pairs = AB_pairs + BA_pairs
```

同一条件重复 audit 只计为 duplicate，并使该 pair 无效；不得按到达顺序任选一份。invalid/incomplete pair 不得贡献胜负、score、模型或 seat 质量指标。

### 报告边界

报告必须 frozen/slots、mapping 不可变、稳定 `to_dict()` 且 canonical JSON 可序列化。不得包含：

- seed 或 seed 列表；
- Bot ID、Bot 版本原文、match/session/player 标识；
- audit 文件路径、state 路径或 URL；
- observation、手牌、history、action、prompt、RAG 片段；
- API key、Header、模型响应、reasoning 或异常正文；
- 逐局、逐对或逐样本记录。

diagnostics 按固定 allowlist 聚合，不得携带原始字段名、值、长度、hash、路径或异常正文。

### 必须新增的测试

至少覆盖：

1. 严格 seed/seat/profile 参数校验；bool、重复 seed、非法座位和未确认 seed 契约拒绝。
2. 每个 seed × 四座位 × 两策略的精确赛程，AB/BA 稳定且顺序平衡。
3. 合法 v7 rule/deepseek audit 的配对、四种 score bucket、胜负与 delta。
4. rule audit 出现模型计数、deepseek audit 观测守恒错误或 mode 不匹配时整对无效。
5. 缺侧、重复侧、未知条件、错误 schema/version、非完成协议、transport/诊断、非正常结果均 fail-closed。
6. platform error 与 invalid score shape 不进入质量指标。
7. overall 与 seat 子桶、score、胜负、AB/BA、模型结果和 fallback 的全部守恒。
8. 精确 Fraction、零分母、输入排列不变性和 canonical JSON 无 NaN/Infinity。
9. frozen/slots、不可变 mapping、输入对象不被修改。
10. 报告和模块边界扫描不包含 seed、Bot/match/player、牌、prompt、路径、URL、key 或异常正文。
11. 不导入 Botzone transport/connector/runner、DeepSeek client、engine 私有状态或配置；真实网络计数为 0。

最低验证：

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

### 验收与后续

全部门槛通过时唯一判定：

```text
botzone_paired_policy_benchmark_harness_verified
```

完成后建立仅含本步骤允许实现/测试文件的独立 Git 检查点。不得在同一步运行真实 Botzone 或 DeepSeek，不得请求 live 授权。

该判定只证明成对赛程和聚合载体成立，不证明 DeepSeek 优于 RuleBased。后续 L5-A4c 才规划容量试验：建议先使用 2 个全新固定 seed × 4 个座位，共 8 对 / 16 局，验证人工流程、配对完整性与 v7 audit 可用性；容量通过后再预注册正式样本量和判定门槛。
