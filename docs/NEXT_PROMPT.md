# 下一任务提示词

## Step L5-A4g1：Botzone benchmark 空闲超时与显式赛程范围契约

### 背景

L5-A4f8 唯一判定保持：

```text
botzone_codex_verified_ui_single_pair_capacity_invalid
```

两局 live evidence 各自完整，但现有离线 benchmark 契约无法接纳：

- RuleBased：exit `0`、`finished_target`、requests/responses/Headers=`30/30/30`、qualified finished=`1`，仅有 1 次 long-poll idle timeout；
- DeepSeek：exit `0`、`finished_target`、requests/responses/Headers=`21/21/21`、qualified finished=`1`，仅有 2 次 long-poll idle timeout；20 次决策为 local shortcut `12`、model `8`，8 次模型结果均为 success，fallback=`0`；
- 两局均无非 timeout transport failure，无协议 detail/profile，无残留 connector；
- `aggregate_policy_audits()` 当前把任何非零 `transport_timeouts` 或非空 diagnostics 判为无效；
- 调用方使用完整四座位 schedule 聚合只采集的 seat 0，因而另外三个未采样 seat 被正确但不适用于本次容量试验地标为 incomplete。

本步骤只修正离线 evaluation 契约，不读取或改写 `36001` live evidence，不联网，不重跑对局，也不改变原 invalid 判定。

### 目标

1. 保持正式 benchmark 的默认 `seed × 4 seats` 赛程不变。
2. 提供显式、严格、确定性的 selected-seat schedule 构造入口，使单座位容量试验只对声明的 seat 判定完整性。
3. 在 v8 audit 的其余完成门槛全部通过时，允许守恒一致的 long-poll idle timeout；真实 transport failure 或任何不一致仍 fail-closed。
4. 保持现有报告 schema、序列化字段、隐私边界和网络隔离不变。

### 修改范围

仅允许修改：

- `evaluation/botzone_policy_benchmark.py`
- `tests/test_botzone_policy_benchmark.py`

不得修改 connector、transport、runner、session、Agent、DeepSeek、engine、CLI、其他 tests、docs 或任何仓库外 evidence。

### 赛程范围契约

- 保持 `build_paired_schedule()` 的现有行为和排序：每个 seed 固定生成 seat `0..3` 的四对赛程。
- 新增一个名称清晰的显式 selected-seat builder，例如 `build_selected_paired_schedule(seeds, local_seats, conditions)`；不要通过隐藏全局状态或推断已存在 audit 来缩小范围。
- `local_seats` 必须是严格 tuple、非空、元素为非 bool 的整数、范围 `0..3`、不得重复。
- 输出顺序必须由 seed tuple 顺序和 seat tuple 顺序唯一决定；同一输入逐字段相等。
- AB/BA 分配必须复用现有正式 builder 的确定性规则，不能为单对另造策略顺序。
- `aggregate_policy_audits()` 仍只对传入 schedule 判定 requested/complete/incomplete；不得静默补齐或删除 schedule 项。
- 使用单 seed、单 seat 的 selected schedule 时，只要求这一对的 rule/deepseek 两侧，不得把其他三个 seat 计为 incomplete。

### 空闲超时契约

先阅读 v8 audit 的当前字段和既有测试，再集中实现严格复核。仅当以下条件全部成立时，允许 `transport_timeouts > 0`：

- `transport_failures == 0`；
- `transport_failure_categories` 为空；
- diagnostics 只包含与 `transport_timeouts` 数值精确相等的一项固定 `transport_timeout` 聚合；
- 没有其他 diagnostic、detail 或 profile；
- 既有 exit、stop reason、request/response/Header、finished、result、agent observability 和 provenance 门槛全部通过。

`transport_timeouts == 0` 时 diagnostics 必须为空。以下情况继续判 invalid：

- timeout 非零但缺少对应 diagnostic；
- diagnostic count 与 timeout count 不一致；
- timeout 为零却存在 timeout diagnostic；
- timeout diagnostic 与其他 diagnostic 并存；
- 任意非零 transport failure 或非空 failure category；
- bool、负数、错误容器、未知枚举或其他 malformed 值。

不要把 timeout 次数新增到 benchmark 报告，除非现有 schema 已有该字段；本步骤默认保持所有报告 dataclass、`to_dict()` 和 canonical JSON 字段不变。

### 测试要求

至少覆盖：

1. timeout=`0` 且 diagnostics 为空仍有效；
2. timeout=`N>0` 且唯一匹配的 `transport_timeout=N` 有效；
3. timeout 非零但 diagnostics 为空无效；
4. timeout 与 diagnostic count 不一致无效；
5. timeout 为零但存在 timeout diagnostic 无效；
6. timeout diagnostic 与其他 diagnostic 并存无效；
7. transport failure 或 failure category 非空无效；
8. 单 seed、单 seat selected schedule 只请求一对，完整两侧后 incomplete=`0`；
9. selected seats 多座位顺序稳定，AB/BA 与正式 builder 对应项一致；
10. 空 tuple、list、bool、重复 seat、越界 seat 均 fail-closed；
11. 原 `build_paired_schedule()` 仍为每 seed 四座位；
12. 原报告字段、canonical JSON 和敏感内容边界保持不变。

既有“只把 `transport_timeouts` 改为 1、但不补匹配 diagnostic”的反例必须继续无效，不能放宽成只看 timeout 数值。

### 验证

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

静态确认 evaluation 模块没有 connector、transport、DeepSeek client、配置、环境变量、网络或仓库外 evidence 读取。

### 唯一判定

全部实现与验证通过：

```text
botzone_policy_benchmark_idle_timeout_scope_contract_verified
```

否则给出一个精确失败判定并停止，不修改 runtime，不读取 live evidence，不运行网络。

### 后续边界

本步骤通过后，下一步 L5-A4g2 才能对已封存的 `36001` 两局做独立、只读恢复聚合。恢复结论必须与原 `botzone_codex_verified_ui_single_pair_capacity_invalid` 并存，不得改写或追认原判定；不得重跑、补采或复用 seed/root。
