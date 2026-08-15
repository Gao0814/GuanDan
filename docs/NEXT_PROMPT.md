# 下一步实施提示词

## Step L5-A4c：Botzone 小容量成对赛程离线准入与授权准备

L5-A4b 已完成并独立封存，唯一判定：

```text
botzone_paired_policy_benchmark_harness_verified
```

实现检查点：

```text
e1b4e14f2806b962c16a08434f8fef589bf9630b
```

`evaluation/botzone_policy_benchmark.py` 已提供确定性的 seed × 四座位 × `rule/deepseek` 成对赛程和严格 v7 audit 微聚合；定向 8 项、全量 612 项与 `git diff --check` 已通过。该载体尚未经过真实人工桌的操作容量验证。

本步骤只做离线准入、仓库外操作清单和后续授权准备。不得启动 live connector、创建 Botzone 测试桌、调用 DeepSeek 或发送任何网络请求。

### 固定容量设计

使用两个从未用于本项目 Botzone 正式评估的新 seed：

```text
24001
24002
```

固定条件：

- profile：`botzone_no_tribute_level_2/v1`
- `no_tribute=True`
- 当前级牌：2
- 上轮头游：0
- 上轮末游：3
- `0/2` 位置等级：2
- `1/3` 位置等级：2
- 同一组三个对手 Bot 及同一版本贯穿全部 16 局
- 本家座位轮换 `0..3`
- 每个 `(seed, seat)` 各运行一局 `rule` 与一局 `deepseek`

总量固定为：

```text
2 seeds × 4 seats = 8 pairs
8 pairs × 2 strategies = 16 games
rule games = 8
deepseek games = 8
AB pairs = 4
BA pairs = 4
```

该规模只验证人工流程、固定条件、audit 采集和配对聚合是否可执行，不用于策略优劣、显著性或胜率结论。

### 前置复核

只读确认：

1. HEAD 包含 L5-A4a `31e2fa5a...` 与 L5-A4b `e1b4e14f...` 检查点。
2. L5-A4b 提交范围精确为 benchmark 模块和对应测试。
3. 工作区除项目所有者既有改动外没有本任务改动；不得读取、修改、暂存或提交既有 `README.md` 改动。
4. 无残留 Botzone connector/Python 进程。
5. 项目所有者确认全部历史本地 AI 测试桌已结束。
6. 项目所有者提供一个已存在、为空、仓库外的容量试验根目录；其下可预建 16 个互相隔离的 state 子目录和一个 audit 子目录。
7. 三个对手 Bot 及版本只在人工操作时确认；不得写入仓库、操作清单、audit 或最终报告。

复跑：

```text
python -m unittest tests.test_botzone_policy_benchmark -q
python -m unittest discover -q
git diff --check
```

任何检查点、回归、工作区、进程或外部目录门槛失败都返回 `precondition_failed`，不继续创建清单或运行 preflight。

### 赛程清单

必须直接调用现有：

```python
BenchmarkConditions(
    profile_version=PROFILE_VERSION,
    seed_contract_confirmed=True,
    opponent_profile_confirmed=True,
)
build_paired_schedule((24001, 24002), conditions)
```

不得手工重新实现排序或 AB/BA 逻辑。生成结果必须为 8 个 pair、16 个 game，并满足：

- 每个 seed 精确覆盖 seat `0..3`；
- 每个 pair 精确包含 `rule` 与 `deepseek`；
- 每个 seat 精确 2 个 pair / 4 个 game；
- AB/BA 为 `4/4`；
- rule/deepseek game 为 `8/8`。

在仓库外容量根目录写入一个 canonical JSON 操作清单。允许清单保存本次非敏感 seed、seat、策略顺序、game/pair 序号、相对 state 子目录和相对 audit 文件名；禁止保存：

- Bot ID、账号、match/session/player 标识；
- Botzone URL、local-AI key、DeepSeek key 或 Header；
- 手牌、history、action、prompt、RAG、模型响应或 reasoning；
- 真实 audit 内容。

清单必须在任何 live 授权前生成并记录 bytes 与 SHA-256。后续不得改写顺序、seed、seat、模式或文件绑定；若需要修改，整个容量任务作废并重新规划，不得现场调整。

### 每局操作契约

后续 live 阶段必须严格按清单串行执行，每次只允许一个 connector 和一个人工测试桌：

1. 对应 state 子目录必须全新且为空；audit 文件必须不存在。
2. 按清单以 `--agent rule` 或 `--agent deepseek` 启动 connector。
3. 页面显示本地 AI 已连接后，人工创建唯一新桌并设置清单中的 seat、seed 和固定 profile。
4. `需要进贡=否`；任何非零 tribute、`tribute` 或 `return` 立即停止整个容量任务且不重试。
5. 每局必须 `exit=0 / finished_target`，生成一份 v7 audit，并保留该局独立最小 tombstone 供后续统一清理。
6. 不在容量任务中重试失败局、替换 seed、交换座位、替换对手或补采。
7. 任一局协议失败、异常分数、平台违规、audit 缺失、页面设置无法确认或人工操作偏离清单，立即停止剩余赛程并判容量无效。

正式聚合只允许在 16 局全部结束后，由调用方按清单构造 `PolicyAuditSubmission` 并调用 `aggregate_policy_audits()`。不得按结果选择 audit、跳过失败 pair 或修改提交顺序来改变结论。

### 零网络双模式 preflight

在两个独立、全新、空的仓库外 preflight state 目录中，分别执行恰好一次：

```text
python -m integrations.botzone --agent rule --preflight-only ...
python -m integrations.botzone --agent deepseek --preflight-only ...
```

要求：

- 使用项目 `.venv` 解释器；
- `PYTHON_DOTENV_DISABLED=1` 在子进程环境中生效；
- Botzone URL / DeepSeek key 只检查 `present`；
- endpoint/model/timeout/retries 只检查是否精确匹配 `https://api.deepseek.com`、`deepseek-v4-flash`、60、0，不输出正文；
- 每次 exit 0、stdout 单行 `preflight_ready`、stderr 空、state 最终为空、无残留进程；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 与 Agent action 全部为 0。

任一 preflight 失败即停止；不得重试、换目录或进入 live。

### 授权准备

全部离线门槛通过后，唯一判定：

```text
botzone_paired_policy_capacity_preflight_ready
```

随后只向项目所有者提出一次新的 L5-A4c-live 批量授权问题，不得在本步骤联网。授权文本必须完整列明：

- 16 个串行 connector / 人工无贡桌，8 局 rule、8 局 deepseek；
- 当前 Botzone local-AI endpoint 每局最多 100 次 GET，总上限 1600 次；
- DeepSeek 只在 8 个 deepseek game 中调用，单次 timeout 60 秒、retries 0，模型请求总上限 800 次；
- 每局最长 3600 秒，完成一局即停；任何失败立即停止整批且不重试；
- DeepSeek 局会发送本家未公开手牌、公开局面、engine 合法候选、手牌评估、记牌摘要、场景标签和本地 RAG 片段到 `https://api.deepseek.com` 的 `deepseek-v4-flash`；
- 不发送 Botzone URL/key、match/session、实体牌 ID、其他玩家隐藏牌或 `.env` 内容；
- 只使用 seed `24001/24002`、四座位轮换、固定对手版本与固定无贡 profile；
- runmatch 请求数为 0，只允许人工网页建桌。

没有项目所有者对该完整批量预算和敏感出站范围的明确授权，不得启动第一局。

### 边界

本步骤不得修改仓库文件、不得提交代码或 docs、不得读取 `.env` 或输出配置值。仓库外操作清单只用于后续人工执行，不是 benchmark 报告。

即使 preflight ready，也只证明 16 局容量流程已准备，不证明 Botzone/DeepSeek 可达、配对完成、动作质量或胜率提升。
