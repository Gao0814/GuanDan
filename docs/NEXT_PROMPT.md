# 下一任务提示词

## Step L5-A4g2：`36001` 单对 evidence 独立只读恢复聚合

### 已封板前置

L5-A4g1 唯一判定：

```text
botzone_policy_benchmark_idle_timeout_scope_contract_verified
```

实现检查点：

```text
569d5431a83e98a2f32928ded7fcda8846e5a8f0
```

该提交仅包含：

- `evaluation/botzone_policy_benchmark.py`
- `tests/test_botzone_policy_benchmark.py`

定向 13 项、全量 624 项和 `git diff --check` 已通过。正式四座位 builder 与报告 schema 未变；新增 `build_selected_paired_schedule()`，并只接受与固定 `transport_timeout` diagnostic 严格守恒的 idle timeout。

L5-A4f8 原判定永久保持：

```text
botzone_codex_verified_ui_single_pair_capacity_invalid
```

本步骤生成新的只读恢复结论，不追认或改写原判定。

### 目标

只读复核已封存的 `36001` RuleBased/DeepSeek 两局 evidence，使用 L5-A4g1 的显式 seat 0 schedule 和 timeout 守恒契约进行独立聚合。不得重跑、补采、清理、修复或重写任何源 evidence。

### 源目录

只读源根目录：

```text
D:\VsCodeProject\BotzoneVerifiedUiPair-36001
```

预期逻辑角色：

- `pair-manifest.json`
- game 1 RuleBased 的 v8 completion audit 与唯一 v4 finished tombstone
- game 2 DeepSeek 的 v8 completion audit 与唯一 v4 finished tombstone

不得输出 state 文件真实名称、run token、Bot/match/player ID、URL、Header、手牌、history、prompt、RAG、模型响应或逐手动作。

### 执行边界

- 不修改仓库文件，不提交 Git。
- 不运行 preflight、connector、Browser、runmatch、Botzone GET、DeepSeek 或其他网络。
- 不读取 `.env`、API key、Botzone URL、Cookie 或环境中的连接值。
- 不删除 tombstone，不更名或补写 manifest/audit/state。
- 外部 verifier 只能写入一个全新的系统临时恢复目录；源目录全程只读。
- 项目内操作使用既有默认授权；若工具系统要求仓库外只读/临时写权限，直接使用工具权限流程，不另发项目授权问题。

### 前置复核

1. 当前 HEAD 必须包含检查点 `569d5431...`，且该提交范围精确为两个文件。
2. `evaluation/botzone_policy_benchmark.py` 与对应测试相对检查点不得有差异。
3. 运行：

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

预期分别为 13 / 624 项通过。

4. 记录源 evidence 的角色级文件数量、bytes 和 SHA-256；不要在恢复输出中保存真实 state 文件名。
5. 源目录必须只有本 pair 预注册角色允许的 evidence；发现未知文件、缺失文件、多个 tombstone、临时文件或 active session 时立即 invalid。

### 严格源证据复核

#### Pair manifest

- 严格 JSON，无重复 key、NaN 或 Infinity。
- 固定为 seed `36001`、seat `0`、顺序 rule → deepseek、无贡、级牌 `2`、上轮头游/末游 `0/3`。
- 两局 agent mode、相同桌面 profile、独立合法 run token 和独立 state/audit 角色必须一致。
- 对手身份只做内存中的三槽相等验证，不输出或持久化具体值。

#### 两份 v8 audit

- schema/version、字段集合、run token、agent mode 与 manifest 精确匹配。
- 均 exit `0`、stop reason=`finished_target`、qualified finished=`1`、normal result=`1`。
- requests=responses=Headers 且大于 0。
- transport failures=`0`、failure categories 为空、detail/profile 为空。
- timeout 必须与唯一 `transport_timeout` diagnostic 精确守恒；预期 RuleBased 为 1、DeepSeek 为 2，但仍以严格源字段交叉验证，不自行修补。
- RuleBased 只允许 `rule_primary`，model/fallback=`0`。
- DeepSeek 决策、model attempt/outcome 和 fallback 守恒；预期 local shortcut=`12`、model=`8`、success=`8`、fallback=`0`，任何不一致立即 invalid。

#### 两份 v4 tombstone

- 每局 state 目录恰好一个最小 finished tombstone，无 active/pending/inflight/effect/handler/cache 字段。
- schema/version、finished 状态和 run token 与同局 manifest/audit 精确匹配。
- 不依赖文件名猜测归属；归属必须由隔离目录、manifest 角色和 token 三者共同证明。

### 聚合方式

1. 使用锁定的 `BenchmarkConditions`，要求 seed、对手 profile、无贡、级牌和 run provenance 均已确认。
2. 必须调用：

```python
build_selected_paired_schedule((36001,), (0,), conditions)
```

不得调用完整四座位 builder 后删除 seat，也不得手写或篡改 `ScheduledPair`。
3. 两份 audit 作为 `PolicyAuditSubmission` 在内存中提交，各自携带 manifest 中对应 token；token 不进入输出。
4. 调用 `aggregate_policy_audits()`，要求：

- requested pair=`1`
- valid pair=`1`
- invalid/incomplete/duplicate=`0/0/0`
- diagnostics 为空
- seat 0 requested/valid=`1/1`
- 其他 seat 不得被请求或计为 incomplete
- AB/BA 与 selected schedule 固定顺序一致
- score、胜负、模型暴露和所有分数 Fraction 守恒

5. 只报告 RuleBased/DeepSeek 的正常结果类别、固定 score bucket、pair score 比较和 DeepSeek 聚合暴露计数；不得报告 seed、token 或逐局标识。

### 可重复性与恢复输出

- 同一独立 verifier 对同一只读源执行恰好两次；两份 canonical recovery JSON 必须逐字节一致。
- 新恢复目录只保留 verifier、`run1.json`、`run2.json`、脱敏 recovery summary 和 manifest。
- 恢复 JSON 不得包含 seed、token、源绝对路径、state 文件名、Bot/match/player ID 或逐局 payload。
- 两次运行前后重新计算源角色级 inventory、bytes 和 SHA-256，必须完全一致。
- 扫描恢复输出，不得出现敏感字段或源请求内容。

### 判定

全部门槛通过：

```text
botzone_single_pair_capacity_recovery_verified
```

仅可给出“一对、同 seat、固定续局环境下的描述性结果”。不得表述为统计显著性、因果收益、DeepSeek 优于 RuleBased 或胜率提升。

任一门槛失败：

```text
botzone_single_pair_capacity_recovery_invalid
```

立即停止，不修正源 evidence、不重跑 live、不补采、不修改代码。

### 后续边界

恢复通过后，才规划全新 seed/root 的 2 seed × 4 seat 自动容量批次。`36001` 只用于本次只读恢复，之后继续封存，不进入新批次。
