# 下一步实施提示词

## Step K-A3d3a：真实模型动作质量试验前置审计与授权请求

请在 GuanDan 项目中完成 Step K-A3d3a。本步只做检查点、回归、确定性兼容、安全预算和非敏感配置元数据审计，最后向用户请求一次明确的外部联网授权。不得创建 live runner、不得发送 probe、不得调用 DeepSeek/HTTP 或其他网络。

### 本次重试上下文

K-A3d3a 已连续两次停在配置快速门槛，当前唯一判定仍为 `precondition_failed`。首次在 HEAD `a450fd2367b53ba455e904e1361422f9f965eb58` 上完成离线前置；第二次按快速门槛执行，没有重复运行回归。已确认：

- 工作区干净，K-A3d1/K-A3d2 检查点及提交范围正确；
- 7 / 80 / 446 项回归、`git diff --check`、两个固定 canonical hash 与兼容性复核均通过；
- 调用进程未显式提供 `DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL` 和 `DEEPSEEK_API_KEY`；
- 未读取 `.env`、未创建 runner、未联网、未调用模型或发送探测请求。

不要在相同启动环境中再次执行本提示词。下一次仍是 K-A3d3a 重试，不是 K-A3d3b；只有在任务调用方确认已从带有三项变量的新进程启动任务后才执行。不得把变量值写入提示词、`.env.example`、仓库、测试、日志或审计文件。若任一变量仍缺失，应立即报告 `precondition_failed`，不要重复运行完整回归。

`.env.example` 不属于进程环境，不能满足本门槛；不得读取它来获取配置。若工作区存在其未提交改动，应由项目所有者先自行确认不含真实密钥并处理，执行方不得读取、提交、还原或清理该文件。

### 背景与唯一目标

已完成：

- K-A3d1：`strategy_intent_action_ablation_harness_verified`
- K-A3d2：`strategy_intent_action_quality_harness_verified`

K-A3d2 的 on/off/tie=`5/11/16` 来自 deterministic fake provider 的“首候选 vs 末候选”，只验证 RuleBased 分支续局载体，不能用于判断 strategy intent prompt。

本步唯一目标是把下一次小规模真实模型试验的代码基线、样本、请求数、时间、审计和解释门槛在联网前锁定，并停下来请求用户授权。

### 仓库与检查点前置

1. 记录当前 HEAD 和 `git status --short`。
2. 确认 K-A3d1 检查点精确为：

```text
b75dace33d399704e45909ce31c339a7a7e14226
```

3. 确认 K-A3d2 检查点精确为：

```text
415c86dc5034ca85862f52e94d1406aa58042b98
```

并确认该提交只包含：

- `evaluation/strategy_intent_action_quality.py`
- `tests/test_strategy_intent_action_quality.py`

4. 确认 K-A3d1 两个文件相对其检查点无差异，K-A3d2 两个文件相对其检查点无差异。
5. 工作区必须干净。若 docs 或其他改动仍未由项目所有者处理，本步只能报告 `precondition_failed`，不得自行提交、stash、还原、清理或覆盖。

本步不允许修改或提交任何仓库文件。

### 配置元数据快速门槛

在运行耗时回归前，先只检查当前进程环境：

- `DEEPSEEK_BASE_URL`：必须显式存在且非空，可报告其值；
- `DEEPSEEK_MODEL`：必须显式存在且非空，可报告其值；
- `DEEPSEEK_API_KEY`：必须显式存在且非空，只报告 `present/missing`。

禁止打开或解析 `.env`，禁止调用会加载 `.env` 的配置入口。任一变量缺失时立即停止；不得创建 runner、联网或重复执行后续回归。三项均满足后，才继续下面的回归与确定性复核。

### 回归与确定性复核

运行并报告实际数量：

```text
python -m unittest tests.test_strategy_intent_action_quality -q
python -m unittest tests.test_strategy_intent_action_quality tests.test_strategy_intent_action_ablation tests.test_strategy_intent_prompt tests.test_strategy_intent_prompt_wiring tests.test_strategy_intent_prompt_benchmark tests.test_strategy_router tests.test_strategy_router_shadow tests.test_strategy_router_benchmark tests.test_confidence_action_quality -q
python -m unittest discover -q
git diff --check
```

预期基线为 7 / 80 / 446 项；以实际结果为准，任一失败均停止。

使用 deterministic fake provider 复核但不改变参数：

- K-A3d1 seed `400..409` canonical SHA-256 必须仍为 `8ec3a766852237e07a1185c0d9de98da71a66fe5d6746b76e580fb4e439e2844`；
- K-A3d2 seed `500..509` canonical SHA-256 必须仍为 `a8c907489b8d913e2b2e4838ffaa2b477285cf098328786b07dd6064b8a5e557`；
- K-A3d1/K-A3d2 的 selected、AB/BA、provider validity 与 phase pair digest 兼容检查继续通过。

复核不得联网，不得读取 `_state`、ground truth 或真实对局日志。

### 锁定后续真实试验参数

以下参数用于后续 K-A3d3b，K-A3d3a 不执行：

```text
seeds = 600..609
strategic_pass_rates = (0, 50, 100)
samples_per_phase = 2
current_level_rank = "2"
max_steps = 5000
max_samples_per_phase_per_game = 128
max_rollout_steps = 5000
paired samples = 3 policies * 4 phases * 2 = 24
logical/physical request cap = 48/48
request timeout = 60 seconds
retries = 0
persistent background wall-clock cap = 65 minutes
```

选择 `(0,50,100)` 是为了在 48 请求预算内保留 forced、中等战略 pass、完全战略 pass 三种轨迹，同时让每个 policy×phase 都有 2 对并精确平衡 AB/BA。25% 策略只在观察到保留信号后的扩大验收中恢复，不能事后加入本次语料。

正式试验必须恰好运行一次；不得补采、换 seed、修改策略、降低样本数、重试失败请求或运行第二份 live 报告。

### 预注册真实试验完整性门槛

后续 K-A3d3b 必须先通过以下完整性门槛，才能解释质量代理：

- 三策略均 10/10/0，主动 pass 行为满足 0%、中间值、100% 边界；
- 每个 policy×phase qualified≥2、selected=2、off-first/on-first=1/1；
- 24 pair 均 off/on attempted，ledger 连续 1..48，off/on 各 24；
- timeout、retries 和物理请求数不超过锁定值；
- 所有 response 均为严格可解析 `DeepSeekSuggestion`，action ID 为非 bool 整数并位于 legal/prompt candidates；
- 24 pair 全部 both-valid；异常、malformed、no-action、非法类型、outside legal/prompt 均为 0；
- 所有需要的 rollout branch 完成，branch failed、clone mismatch、terminal diagnostic 和 step-limit 均为 0；
- 所有计数、phase-to-overall、provider、pair、branch、W/D/L 和质量比较守恒；
- 审计文件不保存 prompt、action ID、reasoning、响应正文、observation、玩家、手牌、API key 或样本身份。

任一完整性门槛失败，唯一判定只能是 `strategy_intent_live_quality_benchmark_invalid`，不得解释 on/off 质量数值。

### 预注册描述性保留门槛

只有完整性全部通过后，按以下顺序解释：

1. 若 changed pair 少于 8：`no_observed_strategy_intent_action_quality_gain`。
2. 若 `on_better_count <= off_better_count`：`no_observed_strategy_intent_action_quality_gain`。
3. 若 on team win count 小于 off team win count：`no_observed_strategy_intent_action_quality_gain`。
4. 否则：`retain_for_expanded_strategy_intent_quality_evaluation`。

这是小样本描述性准入门槛，不是显著性检验。即使 retain，也不授权默认启用、完整 DeepSeek 对局或胜率声明；只允许设计包含 25% 策略和更大独立语料的扩大验收。

### 配置与敏感信息边界

本步只允许读取调用进程中显式提供的环境变量元数据：

- `DEEPSEEK_BASE_URL`：必须显式存在，可报告值；
- `DEEPSEEK_MODEL`：必须显式存在，可报告值；
- `DEEPSEEK_API_KEY`：只报告 `present/missing`，不得读取后输出、复制、散列或持久化值。

禁止：

- 打开或解析仓库 `.env`；
- 调用 `AppConfig.from_env()`，因为它会加载 `.env`；
- 输出完整请求 Header、Authorization、key 长度、前后缀或 hash；
- 把 endpoint/model/key 写入仓库文件；
- 用 key 存在代替用户授权；
- 发送任何 DNS、HTTP、模型探测或真实请求。

若 endpoint/model 未显式提供或 key missing，报告 `precondition_failed`，列出缺失的非敏感变量名后停止。

### 后续审计设计锁定

授权后的 K-A3d3b runner 必须位于仓库外新临时目录，并使用持久后台进程，避免桌面工具 30 分钟中断导致子进程失控。K-A3d3a 只记录设计，不创建 runner。

后续证据至少包括：

- runner 源码及 SHA-256；
- process state、heartbeat、连续 call ledger；
- aggregate-only quality report；
- audit summary、completion 和 manifest；
- 每个文件 bytes 与 SHA-256。

ledger 每次请求只记录 sequence、off/on condition、started/returned/failed 状态和 latency；不得记录 prompt、action ID、response body、reasoning 或样本身份。runner 必须在每次物理请求前落盘 started，返回后原子更新状态。

### 边界扫描

确认：

- K-A3d1/K-A3d2 仅 evaluation/tests 引用，runtime 无反向导入；
- harness 没有网络 provider、配置读取、`.env`、API key、ground truth、`game._state` 或 `record.txt`；
- 工作区和 HEAD 满足前置；
- 本步没有新增 runner、审计文件或仓库修改。

### 唯一判定与授权问题

- 检查点、干净工作区、回归、hash、配置元数据和预算全部满足：`strategy_intent_live_quality_preflight_ready`
- 任一前置不满足且未联网：`precondition_failed`

达到 ready 后，最终回复必须停在以下形式的明确问题，不得继续执行：

```text
已完成 K-A3d3a 前置审计。API key present，Endpoint=<实际显式值>，Model=<实际显式值>。
拟执行一次 K-A3d3b：seed 600..609，策略 0/50/100，每阶段 2 对，共最多 48 次外部请求；单次 timeout 60 秒、零重试、持久后台最长 65 分钟。是否明确授权向该 endpoint/model 发起本次请求？
```

只有用户后续明确回答授权，才允许另行制定并执行 K-A3d3b。当前任务不得把任何历史授权视为本次授权。

### 最终报告

必须包含：

- 唯一判定；
- HEAD、K-A3d1/K-A3d2 检查点和工作区状态；
- K-A3d2 检查点与提交范围；
- 回归数量、两个 canonical hash、兼容检查和 `git diff --check`；
- 锁定 seed、策略、pair/request、timeout、retries 和时间预算；
- endpoint/model 与 key present/missing，不含 key 内容；
- 完整性门槛和描述性保留门槛摘要；
- 明确说明未创建 runner、未联网、未调用模型；
- ready 时输出上述授权问题，precondition failed 时只报告阻塞项。
