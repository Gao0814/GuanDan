# 下一步实施提示词

## Step K-A3d3c2：独立恢复 live 实验前置复核与重新授权

请在 GuanDan 项目中完成 K-A3d3c2 的授权前置。本轮只复核检查点、离线 bootstrap 证据、配置元数据、全新 seed、请求预算和审计边界，最后向用户请求一次新的明确联网授权。不得创建 live runner、启动后台进程、发送 probe、调用 DeepSeek/HTTP 或其他网络。

### 已完成结论

- K-A3d3a：`strategy_intent_live_quality_preflight_ready`；
- K-A3d3b：`strategy_intent_live_quality_benchmark_invalid`；
- K-A3d3c1：`strategy_intent_live_startup_hardening_verified`。

K-A3d3b 永久保持无效：唯一 PID `33612` 在首次状态写入前退出，request/ledger count=0，没有模型、pair、rollout 或质量结果。seed `600..609` 永久停用，旧授权不得沿用。

### K-A3d3c1 离线证据

checkpoint：

```text
cf9d29cb31fcff2e9b3401b6d68a2db5fe1a37fd
```

candidate 目录：

```text
C:\Users\86166\AppData\Local\Temp\guandan-strategy-intent-quality-k-a3d3c1-cf9d29c-9b21a36e
```

锁定文件：

```text
bootstrap_runner.py
bytes = 5502
sha256 = 776f45040a9acab40f575262bd53a249738e6a9c3487eca40884c6039b01e445

launch_bootstrap.py
bytes = 7269
sha256 = 6a186d7c024bccd89d98a2156bf53e89c8503d6b6c80546648e472fe8e5ca84a

offline_audit_final/offline_self_check.json
bytes = 1281
sha256 = aabebaeb5da15caf9b35a96c919157dd5c88b7cbbbab14c7d0119dc8fb59af6e
```

正常 offline self-check 两次结构 hash：

```text
ede8bfc3c69443f65b0d8cbac578fdefb8565dcb7b97d0c3c422c40cf41e80ec
```

K-A3d3c1 已覆盖正常、缺失参数、无效目录、project import 失败和原子写入失败；request/network/client/suggest counts 均为 0。

### 仓库与证据前置

1. 记录当前 HEAD 和 `git status --short`；工作区必须干净。
2. 确认 K-A3d1 `b75dace...`、K-A3d2 `415c86d...`、K-A3d3b `f0a087a...` 和 K-A3d3c1 docs checkpoint 均存在。
3. 只读复核 K-A3d3b 原失败目录仍未改变，原 runner SHA-256 仍为 `a390ce8bc98aa92592f046c425ec9d0fe7c2313c5727dbd48918f2350033ffbd`。
4. 只读复核 K-A3d3c1 三个文件的 bytes/hash 和 offline 结构 hash。
5. 不得删除、改写、补写、重命名或清理 K-A3d3b/K-A3d3c1 证据目录。
6. 本轮不得修改或提交仓库文件。

### 配置元数据门槛

只检查当前进程环境：

- `DEEPSEEK_BASE_URL` 必须精确为 `https://api.deepseek.com`；
- `DEEPSEEK_MODEL` 必须精确为 `deepseek-v4-flash`；
- `DEEPSEEK_API_KEY` 只检查非空并报告 `present/missing`。

禁止打开 `.env`、调用会加载 `.env` 的配置入口、输出或持久化 key 内容/长度/hash/前后缀。任一条件不满足立即报告 `precondition_failed` 并停止。

### 独立恢复参数

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
formal live runs = exactly 1
```

不得复用 `600..609`、补采、换 seed、加入 25% 策略、减少样本、重试失败请求或运行第二份 live 报告。

### 授权后 runner 强制边界

授权后的 live runner 必须在全新的仓库外目录构建，并继承 K-A3d3c1 已验证架构：

- 父启动器在 spawn 前写 `launch_state.json`，记录 spawning/spawned/exited、PID、exit code 和脱敏 stdout/stderr；
- 子 runner 在 project import 前写 `process_state.json` 的 bootstrapping；
- 项目 imports 延迟到受保护区域；
- 状态链至少覆盖 imports_ready、startup_ready、running、completed/failed；
- heartbeat 在首次请求前存在，并随每次请求更新；
- ledger 在每个物理请求前先写 started，返回后写 returned/failed；
- 所有 48 次请求使用同一 endpoint 与 `deepseek-v4-flash`，禁止模型替换或 fallback；
- 不保存 prompt、action ID、response body、reasoning、observation、手牌、玩家、样本 ID、Header 或 key；
- 任一启动/请求/rollout 失败仍必须留下父级和子级规范化失败证据。

### 正式完整性与描述性门槛

完整性优先级不变：三策略 10/10/0、每 policy×phase selected=2 和 AB/BA=1/1、24 pair/48 ledger、全部 provider valid、全部必要 rollout branch complete、所有计数守恒、零未解释 diagnostics。任一失败只能判定：

```text
strategy_intent_live_quality_recovery_invalid
```

完整性全部通过后才按顺序解释：

1. changed pair < 8：`no_observed_strategy_intent_action_quality_gain`；
2. `on_better_count <= off_better_count`：同上；
3. on team wins < off team wins：同上；
4. 否则：`retain_for_expanded_strategy_intent_quality_evaluation`。

这是小样本描述性门槛，不是显著性检验，不授权默认启用、完整 DeepSeek 对局或胜率声明。

### 本轮唯一判定与授权问题

全部前置满足时判定：

```text
strategy_intent_live_quality_recovery_preflight_ready
```

然后必须停在以下问题，不得继续执行：

```text
已完成 K-A3d3c2 独立恢复前置审计。API key present，Endpoint=https://api.deepseek.com，Model=deepseek-v4-flash。
拟使用全新 seed 700..709、策略 0/50/100、每阶段 2 对执行恰好一次恢复实验，共最多 48 次外部请求；单次 timeout 60 秒、零重试、持久后台最长 65 分钟，并使用已验证的父/子 bootstrap 状态链。是否明确授权向该 endpoint 的 deepseek-v4-flash 发起本次请求？
```

只有用户后续明确授权，才允许执行 live 恢复。历史 K-A3d3b 授权无效。

任一前置失败且未联网时判定 `precondition_failed`。

### 最终报告

必须包含：

- 唯一判定、HEAD 和工作区；
- K-A3d3b invalid 与 seed 禁用声明；
- K-A3d3c1 文件 bytes/hash、offline 结构 hash 和 request=0 复核；
- endpoint/model 和 key presence，不含 key 内容；
- 全新 seed、pair/request、timeout/retries/时间预算；
- 父/子 bootstrap、ledger、隐私和完整性门槛摘要；
- 明确说明本轮未创建 runner、未联网、未调用模型；
- ready 时输出上述授权问题。
