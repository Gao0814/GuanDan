# 下一任务提示词

## Step L5-A4h2：原子 manifest 恢复后的 2 seed × 4 seat 自动成对容量批次

### 已封板前置

L5-A4g2 唯一判定：

```text
botzone_single_pair_capacity_recovery_verified
```

恢复聚合 requested/valid=`1/1`，invalid/incomplete/duplicate=`0/0/0`，diagnostics 为空；RuleBased 与 DeepSeek 均为正常团队负、`score_0`，pair delta=`0`。DeepSeek 暴露 1 局、8 次 success、无 fallback。该结果只证明只读聚合链有效，不构成策略收益或胜率结论。

实现基线：

- 自动 UI RuleBased 基线已通过；
- `569d5431a83e98a2f32928ded7fcda8846e5a8f0` 已支持严格 idle-timeout 守恒和 selected-seat schedule；
- 正式 `build_paired_schedule()` 仍固定生成每 seed 四座位的完整 AB/BA 赛程；
- 当前全量基线为 624 项。

L5-A4f8 原 `botzone_codex_verified_ui_single_pair_capacity_invalid` 永久保留；`36001` 及其 root 不再使用。

L5-A4h1 原判定同样永久保留：

```text
botzone_verified_ui_paired_capacity_invalid
```

L5-A4h1 只创建了离线布局，但 manifest 写入没有取得可验证的 `flush/fsync` 原子写入证据；preflight、connector、网页桌、Botzone/DeepSeek 请求均为 0。`37001/37002` 与旧 root 永久封存，不得读取、清理、修复或复用。

### 目标

使用全新 seed `38001`、`38002`，在同一个任务内完成：

1. 仓库外 manifest、16 个隔离 state/audit 布局与双模式零网络准入；
2. 通过已验证的 Botzone GuanDan UI，按正式 schedule 串行执行 8 对、16 局；
3. 每局保存独立 v8 completion audit 与 v4 finished tombstone；
4. 全部完成后使用现有 `aggregate_policy_audits()` 聚合完整四座位报告。

本步骤不新增代码或诊断载体。项目计划内操作沿用常驻默认授权，不再询问项目授权；工具系统或网页平台若要求权限/动作确认，直接使用其正常确认流程。

### 固定批次

- seeds：`(38001, 38002)`
- local seats：`0,1,2,3`
- pairs/games：`8 / 16`
- profile：GuanDan、需要进贡=`否`、级牌=`2`、上轮头游/末游=`0/3`
- opponents：16 局使用同一组三个既有 Bot，只在内存中核对相等，不输出或持久化 ID
- schedule：必须直接调用 `build_paired_schedule((38001, 38002), conditions)`；不得手写、删减或重排
- 每对按 schedule 的 `first_strategy → second_strategy` 执行；预期 AB/BA=`4/4`
- 每局唯一 32 位小写 hex run token；16 个 token 互异，不输出
- 每局 local-AI GET 上限 `100`、poll timeout `120` 秒、wall `3600` 秒、finished target `1`
- DeepSeek timeout/retries=`60/0`
- 同一时刻最多一个 connector、一个活动网页桌；runmatch=`0`、失败局重试=`0`

### 仓库外根目录

```text
D:\VsCodeProject\BotzoneVerifiedUiCapacity-38001-38002
```

开始时该路径必须不存在或为全新空目录。若非空，立即判 invalid，不读取、删除或复用其中内容。

固定布局：

```text
capacity-manifest.json
progress.json
preflight-summary.json
games/game-01-<mode>/state/
games/game-01-<mode>/audit/completion.json
...
games/game-16-<mode>/state/
games/game-16-<mode>/audit/completion.json
final-report.json
batch-summary.json
```

manifest 仅保存 schema/version、pair/game index、seed、seat、AB/BA 顺序、agent mode、相对 state/audit 路径、run token、固定 profile 和预算。不得保存 Bot ID、URL、Header、Cookie、账号、match/player ID、手牌、history、prompt、RAG 或模型响应。

manifest 使用 UTF-8 canonical JSON。必须由一个仓库外、仅使用标准库的 writer 完成以下顺序，且每一步失败立即停止：

1. 以 `os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)` 独占创建同目录临时文件；临时文件必须此前不存在。
2. 通过 `os.fdopen(fd, "wb")` 一次写入完整 canonical UTF-8 bytes。
3. 在同一打开文件对象上依次执行 `flush()` 和 `os.fsync(file.fileno())`；不得捕获后忽略异常。
4. 文件关闭成功后执行一次 `os.replace(temp_path, manifest_path)`。
5. 重新以二进制只读方式读取正式 manifest，要求 bytes 与预计算 payload 逐字节相等、JSON 可解析、canonical 重编码相等。
6. 要求临时文件不存在；记录正式文件 bytes/SHA-256，批次期间不得改写。

禁止使用 `Path.write_text()`、`Path.write_bytes()`、`json.dump()` 直接写目标文件、普通覆盖写、shell 重定向或先写正式文件再补做 fsync。Windows 不要求目录 fd 的 fsync；本契约要求临时文件本身在 replace 前完成并成功返回 `flush + os.fsync`。

writer 运行后立即自检：记录固定布尔阶段 `exclusive_create/write/flush/fsync/close/replace/readback/canonical/temp_absent`，全部为 true 才可继续；自检不得保存 token 或 payload。16 个 state 目录必须为空，16 个 completion 目标必须不存在。

### 离线准入

1. HEAD 必须包含 `569d5431...`，提交范围保持两个 benchmark 文件；工作区不得有本任务造成的修改。
2. 运行：

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

预期 13 / 624 项通过。
3. 仅以 present/match 复核 Botzone URL、DeepSeek key、endpoint、model、timeout=`60`、retries=`0`；不得输出或持久化值。
4. 使用不会匹配检查命令自身的进程枚举确认无残留 connector。
5. 对 16 个 state 目录分别做仓库外原子创建/替换/清理资格探针，探针后全部为空。
6. 使用 manifest 中首个 rule game 与首个 deepseek game 的 state 目录，各运行一次现有 `--preflight-only`；均须 exit `0`、stdout=`preflight_ready`、stderr 为空、state 仍为空。
7. `preflight-summary.json` 只保存固定布尔值、退出分类和零网络计数，不保存配置或路径正文。

任一离线门槛失败：

```text
botzone_verified_ui_paired_capacity_recovery_invalid
```

立即停止，不进入 live、不修改代码、不另建诊断载体。全部通过后在同一任务中直接进入 live，不另行询问项目授权。

### 每局自动 UI 流程

严格串行执行 manifest 的 game 1..16：

1. 确认上一局 connector 已退出、网页桌已结束；首局确认没有旧活动桌。
2. 从 Botzone 主页面按已验证契约进入：创建游戏桌 → 唯一可见游戏选择控件选 GuanDan → 唯一“创建”按钮 → GuanDan 表单。
3. 若出现验证码，暂停并让项目所有者人工完成；不得识别、求解或绕过。验证码完成后从当前页面继续，不把等待视为实验失败。
4. 点击唯一 `载入上次配置`，设置本局 seed、local seat 和固定无贡 profile；对手使用已锁定的同一组三槽。
5. 第一次 DOM readback 必须精确验证：game、tribute、seed、seat、level、first/last、三个 opponent-selected、local-AI replacement。Bot ID 仅内存比较，输出只给布尔值。
6. 只有 readback 全部通过，才用该局 state/audit/token 在统一 TTY session 中直接启动现有 connector。禁止 launcher、Start-Process、detached/background 或第二个 connector。
7. 初次启动必须返回持续 session ID 且无 exit code；等待页面显示本地 AI 已连接。若 connector 在最终提交前退出或 completion audit 提前出现，该批次 invalid。
8. 执行第二次完整 DOM readback，必须与 manifest 和第一次 readback 一致。
9. 仅点击一次唯一 `开始游戏！`。点击后 Browser 完全只读，只允许 snapshot、URL/title、screenshot 和 connector polling；不得点击、输入、刷新、返回、关闭或退出。
10. 等待 connector 自行结束，再验收本局 evidence；通过后原样保留 tombstone/audit并原子更新 `progress.json`，再进入下一局。

页面 locator 必须每局从最新 DOM 重新取得，不复用 stale locator。只读 snapshot/poll 可重复；禁止盲目重复任何写动作。

### 单局验收

每局必须满足：

- 两次 readback 精确一致，且与 manifest 条件匹配；
- connector 在提交前持续运行，开始按钮只点击一次，提交后 browser writes=`0`；
- exit `0`、stop reason=`finished_target`；
- requests=responses=Headers 且大于 0；
- qualified finished=`1`、normal result=`1`；
- transport failures=`0`、failure categories 为空；
- timeout 为 0 时 diagnostics 为空；timeout 大于 0 时仅有与其计数相同的 `transport_timeout`；
- detail/profile 为空；
- v8 audit、v4 最小 tombstone、manifest token 和 agent mode 精确匹配；
- 无 active/pending/inflight/effect/handler/cache state，无残留 connector。

策略门槛：

- rule：全部 Agent 决策均为 `rule_primary`，model attempts/outcomes/fallback=`0`；
- deepseek：至少一次 `model` success；model outcomes 只允许 success，RuleBased fallback=`0`，decision/attempt/outcome 守恒。

任一局失败立即：

- 终止当前唯一 connector（若仍运行）；
- 原样保留 manifest、progress、已完成局和失败局 evidence；
- 不重试、不补采、不继续后续局、不复用 seed/root；
- 输出 `botzone_verified_ui_paired_capacity_recovery_invalid`。

### 最终聚合

16 局全部通过后：

1. 重新验证 manifest bytes/SHA-256 未变，16 份 v8 audit 与 16 份 v4 tombstone逐局 token 匹配。
2. 将 16 份 audit 作为带 run token 的 `PolicyAuditSubmission` 在内存中提交给 manifest 对应的正式 schedule。
3. 调用 `aggregate_policy_audits()`，要求：

- requested/valid pair=`8/8`
- invalid/incomplete/duplicate=`0/0/0`
- diagnostics 为空
- 四个 seat 各 requested/valid=`2/2`
- AB/BA=`4/4`
- rule/deepseek 各 8 个正常结果
- score、胜负、模型暴露、fallback 与 Fraction 全部守恒

4. `final-report.json` 只保存现有 benchmark `to_dict()` canonical JSON；不得包含 seed、token、路径或逐局内容。
5. `batch-summary.json` 只保存固定完成计数、manifest/report bytes/SHA-256、零敏感扫描结果和唯一判定。

### 唯一通过判定

```text
botzone_verified_ui_paired_policy_capacity_verified
```

只报告 8 对样本中的描述性胜负、score bucket、paired score 比较与 DeepSeek 模型暴露。不得宣称统计显著性、因果收益、DeepSeek 更优或胜率提升。

### 后续边界

本批次通过后，下一步才根据 8 对结果决定扩大样本、调整策略或维持现状。不要在本任务中默认启用任何新策略或修改 runtime。
