# 下一步实施提示词

## Step K-A3d3c1：真实质量 runner 离线启动审计与 bootstrap 加固

请在 GuanDan 项目中完成 Step K-A3d3c1。本步只做 K-A3d3b 失败证据的只读审计、启动故障边界分析和仓库外 runner 的离线 bootstrap 加固。不得发送 DNS、HTTP、DeepSeek 或其他外部请求，不得创建第二个 live 进程，不得读取 `.env` 或 API key 内容。

### 背景与唯一结论

K-A3d3a 已完成，判定：

```text
strategy_intent_live_quality_preflight_ready
```

唯一 K-A3d3b live 运行异常退出，正式判定必须永久保留为：

```text
strategy_intent_live_quality_benchmark_invalid
```

失败事实：

- checkpoint HEAD：`f0a087a4146b0950764b8b08bf03ff6c15723d98`；
- 唯一后台 PID：`33612`，当前已退出；
- 请求数和 ledger 条目均为 0；
- 没有 `process_state.json`、heartbeat、ledger、report、summary 或 completion；
- 没有启动第二个进程、重跑或补采；
- 仓库保持干净，没有仓库文件修改；
- 失败目录只保留 runner：

```text
C:\Users\86166\AppData\Local\Temp\guandan-strategy-intent-quality-k-a3d3b-f0a087a-d7bb2d2fc94b4633a03d4b7253187b4d
```

- runner SHA-256：

```text
a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd
```

本步唯一目标是确保下一次独立恢复实验在任何项目 import、参数解析、配置检查或模型调用之前，已经留下可审计的父进程启动状态与子进程 bootstrap 状态。不得从本步产生动作质量或胜率结论。

K-A3d3c1 首次尝试仅完成原失败证据的只读复核，随后因四份规划文档未提交、工作区不干净而判定 `strategy_intent_live_startup_hardening_invalid`。该次没有创建 recovery candidate、第二个 live 进程或任何网络请求。项目所有者已将这四份文档形成独立检查点；重试时应以新的干净 HEAD 为准，不得再次把已处理的文档状态当作阻塞。

### 仓库与证据前置

1. 记录当前 HEAD 和 `git status --short`；工作区必须干净。
2. 复核 K-A3d1/K-A3d2 检查点和固定 hash 仍存在，但不重复耗时 live 或质量实验。
3. 对上述失败目录只读；不得修改、重命名、补写或删除任何文件。
4. 复核 runner bytes 与 SHA-256，不输出 runner 中可能的敏感内容。
5. 确认 PID `33612` 已退出，不得恢复该进程。
6. 不得把 K-A3d3b 改判为部分成功；零 ledger 不允许解释 pair、rollout 或质量。

### 失败边界审计

只读检查原 runner 的启动顺序，并报告精确行号：

- 顶层 project imports；
- `main()` 入口；
- audit directory 参数读取与目录校验；
- 首次 `process_state.json` 写入；
- `try/except` 保护边界；
- 环境元数据检查；
- client 构造与首次可能网络调用。

已知首次 state 写入位于异常保护之前。若没有 stdout/stderr、exit code 或 traceback 证据，只能报告：

```text
startup_failure_before_state_write
```

并列出仍可能的类别，例如顶层 import、缺失/错误参数、目标目录校验或首次原子写入。不得从“最可能”升级为已确认根因。

### 仓库外 bootstrap 加固

在全新的仓库外临时目录创建 recovery candidate，不修改失败目录。candidate 至少拆成父启动器与子 runner 两层：

#### 父启动器

- 在创建子进程前写入 `launch_state.json`，包含 schema、run ID、checkpoint、非敏感参数摘要和 `status=spawning`；
- 使用显式 Python executable、仓库根目录和 audit directory 参数；
- 捕获子进程 PID、exit code，以及经过敏感字段过滤的 stdout/stderr；
- 子进程创建成功后原子更新 `status=spawned`；结束后更新 `status=exited`；
- 不记录环境变量值、Header、prompt、action、response 或 reasoning。

#### 子 runner

- 顶层只允许 Python 标准库和 bootstrap 辅助；项目 imports 必须延迟到 `main()` 的受保护区域；
- 参数解析、目录检查和首次 state 写入均必须被最外层异常处理覆盖；
- 在任何项目 import、配置检查或 client 构造前写入 `process_state.json` 的 `status=bootstrapping`；
- import 成功后写入 `status=imports_ready`；
- 只检查 endpoint/model 精确值和 key presence，不输出、散列或持久化 key；
- 写入 `startup_ready.json` 后才能进入 provider 或采样路径；
- 所有失败只持久化规范化 failure class/stage，不落盘 traceback、环境、请求或响应正文。

### 离线 self-check

candidate 必须提供显式 `--offline-self-check`，并满足：

- 强制禁止创建 `DeepSeekClient` 和调用 `suggest_action_id()`；
- 不发送 DNS/HTTP 或任何网络请求；
- request count 始终为 0；
- 验证父启动状态、子 bootstrap、延迟 imports、audit directory、原子写入、heartbeat 和 completion 链；
- 至少覆盖：正常启动、缺失参数、无效目录、project import 失败和原子写入失败；
- 每种失败都必须有父级 launch 证据；只要 audit directory 可写，就必须有规范化子级 failure 证据；
- 正常路径执行两次独立离线 self-check，结构化结果一致；PID/时间等易变字段不进入 canonical 等价比较。

不得为了 self-check 调用真实配置加载器，不得打开 `.env`。当前进程中的 key 即使 present，也不能被读取到报告或测试输出。

### 后续恢复实验预注册

本步不执行恢复实验，只锁定候选 K-A3d3c2：

```text
endpoint = https://api.deepseek.com
model = deepseek-v4-flash
seeds = 700..709
strategic_pass_rates = (0, 50, 100)
samples_per_phase = 2
current_level_rank = "2"
max_steps = 5000
max_samples_per_phase_per_game = 128
max_rollout_steps = 5000
paired samples = 24
logical/physical request cap = 48/48
request timeout = 60 seconds
retries = 0
persistent background wall-clock cap = 65 minutes
```

seed `600..609` 已永久归属于无效 K-A3d3b，不得复用。K-A3d3c2 必须使用全新 seed，并在 K-A3d3c1 离线验收通过后重新向用户请求一次明确授权；K-A3d3b 的历史授权不得沿用。

### 验收判定

只有以下条件全部满足，唯一判定才是：

```text
strategy_intent_live_startup_hardening_verified
```

- 原失败证据保持未改动，hash 一致；
- 失败边界被准确限制在首次 state 写入之前，未编造根因；
- 父启动器在 spawn 前落盘；
- 子 runner 在 project import 前落盘；
- 正常与失败 self-check 均产生完整、脱敏、可审计状态；
- 两次正常离线 self-check 结构结果一致；
- 网络/client/request count 均为 0；
- 仓库仍干净，未修改 runtime、engine、agent、client 或原 harness。

任一条件失败，判定：

```text
strategy_intent_live_startup_hardening_invalid
```

不得请求 live 授权。

### 最终报告

必须包含：

- 唯一判定；
- HEAD、工作区和原 K-A3d3b invalid 保留声明；
- 原 runner 路径、bytes、SHA-256 和只读复核；
- 首次 state、异常保护和 import/参数边界行号；
- 能确认的失败边界与不能确认的根因；
- 新 candidate 目录和各文件 bytes/SHA-256；
- 离线 self-check 场景、两次正常结构 hash、exit code 和状态链；
- 明确说明 request count=0、未联网、未调用模型、未读取 `.env`；
- K-A3d3c2 的全新 seed、模型、预算和必须重新授权的边界。
