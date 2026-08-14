# 下一步实施提示词

## Step L5-A2b：Botzone DeepSeek connector 单局无贡 live smoke

本任务包含真实外部网络请求。未获得项目所有者针对下述 endpoint、模型、预算和运行边界的明确授权前，只能做只读前置审计，不得启动 connector、发送探测请求、创建 runner 或连接 Botzone。

### 已确认基线

- L5-A1：`71d9119`，判定 `botzone_deepseek_connector_offline_wiring_verified`。
- L5-A1a：`aac59d5`，判定 `botzone_deepseek_connector_hardening_verified`。
- L5-A2a 首次前置因 `%LOCALAPPDATA%` 写权限在子进程启动前 `precondition_failed`；网络计数为 0。
- L5-A2a1 已使用系统临时目录完成唯一零网络 preflight：
  - exit 0；
  - stdout=`preflight_ready`；
  - stderr 为空；
  - 约 190 ms；
  - state 前后为空并删除；
  - 无残留进程；
  - Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 与 `suggest_action_id()` 均为 0。
- 当前唯一判定：

```text
botzone_deepseek_connector_live_preflight_ready
```

### 固定授权参数

- Botzone endpoint：当前进程已配置的 `BOTZONE_LOCAL_AI_URL`，不得输出其值。
- DeepSeek endpoint：`https://api.deepseek.com`。
- Model：`deepseek-v4-flash`。
- Agent mode：`deepseek`。
- Botzone poll timeout：120 秒。
- DeepSeek request timeout：60 秒。
- DeepSeek retries：0。
- Connector process：恰好 1 个前台进程。
- Test table：恰好 1 个全新手动测试桌，明确设置“需要进贡=否”。
- `max_cycles=100`。
- `max_wall_seconds=3600`。
- `stop_after_finished=1`。
- 进程级重启/重试：0。
- state/audit：系统临时目录下两个全新、随机、仓库外路径。

预算解释：在只有一个活动测试桌、每次 poll 至多包含该桌一个待决策请求的前提下，最多 100 次 Botzone GET，且每次需要模型决策时最多 1 次 DeepSeek physical request。当前 runtime 没有独立的模型请求总计数器，因此本任务不能宣称精确 DeepSeek 调用次数；若发现多个活动 match、批量请求异常或无法维持单桌前提，立即判 invalid，不继续运行。

### 明确授权文本

只有用户在当前任务中明确回复等价于以下内容，才允许执行：

```text
我明确授权执行 L5-A2b：向当前已配置的 BOTZONE_LOCAL_AI_URL 发起最多 100 次 GET，并在单个全新无贡测试桌的模型决策中向 https://api.deepseek.com 的 deepseek-v4-flash 发起单次 60 秒超时、零重试的请求；只启动一个 connector 进程，最长运行 3600 秒，完成一局即停。
```

历史 Botzone 或 DeepSeek 授权不得复用。

### 授权前只读门槛

1. HEAD 必须包含 `aac59d5`，且 L5-A1/L5-A1a 实现文件相对检查点无差异。
2. `git status --short` 必须为空。
3. 不重复全量回归；只运行 23 项定向回归与 `git diff --check`。
4. 只以 present/match 复核：Botzone URL、DeepSeek key、endpoint、model、timeout=60、retries=0；不得输出值或读取 `.env` 内容。
5. 无本项目残留 connector/Python 进程；不得终止归属不明的进程。
6. 用户确认 Botzone 本地 AI 配置页可用，并承诺 connector 启动后只创建一个全新无贡桌。

任一门槛失败，输出 `precondition_failed`，不得请求授权或联网。

### 启动准备

获得授权后：

1. 在系统临时目录创建全新随机 state 目录与 audit 文件路径；不得复用历史目录。
2. 确认 state 初始为空，audit 文件尚不存在，路径均位于仓库外。
3. 只为本次子进程显式锁定 `DEEPSEEK_TIMEOUT=60`、`DEEPSEEK_MAX_RETRIES=0`；不修改系统环境或 `.env`。
4. 不输出完整启动命令，因为环境中包含敏感 URL。

### 唯一 live 运行

等价参数：

```text
python -m integrations.botzone \
  --agent deepseek \
  --state-dir <fresh-temp-state> \
  --timeout-seconds 120 \
  --max-cycles 100 \
  --max-wall-seconds 3600 \
  --stop-after-finished 1 \
  --audit-file <fresh-temp-audit>
```

执行要求：

1. 只启动一个前台进程，不使用 `Start-Process`，不创建第二个 connector。
2. 进程运行后通知用户检查 Botzone 页面连接状态；只有用户确认“已连接”后才创建全新无贡测试桌。
3. 用户创建桌后继续等待同一进程；每 30 秒提供简短状态，不输出敏感信息。
4. 不因暂时无请求、模型超时或 fallback 重启进程。
5. 进程自行退出、达到 3600 秒、用户中断或出现固定失败门槛后结束；不得重跑或补采。

### 成功门槛

必须全部满足：

- 用户确认连接后创建了恰好一个全新无贡桌；
- connector 自行以 exit 0、`finished_target` 停止；
- `finished_qualified >= 1`；
- `requests_seen > 0`、`responses_prepared > 0`、`headers_sent > 0`；
- `transport_failures=0`；
- diagnostics 为空；
- Botzone 裁判没有非法动作或决策超时；
- state 最终为安全 tombstone/按既有 finished 契约清理，不含敏感对局内容；
- audit schema 可解析且不含 URL、key、Header、match ID、牌、request/response、prompt、reasoning 或模型正文；
- 进程已退出且无残留。

唯一成功判定：

```text
botzone_deepseek_connector_no_tribute_smoke_verified
```

### 失败门槛

以下任一情况均判：

```text
botzone_deepseek_connector_no_tribute_smoke_invalid
```

- 未连接、配置错误、transport failure、协议诊断、unsupported stage；
- 多个活动 match 或无法证明只有一个新桌；
- cycle/wall limit、用户中断、进程异常退出；
- request/response/header/qualified finished 任一闭环计数缺失；
- Botzone 非法动作或决策超时；
- audit 缺失/非法、state 敏感残留或进程残留。

失败后不得重试、延长预算、补采或在同一授权下启动第二个进程。

### 结论边界

本 smoke 的通过只证明：显式 deepseek 模式下，Botzone 协议闭环和 RuleBased 安全降级足以完成一局无贡对局。

由于当前 audit 没有独立模型调用/成功/fallback 计数，即使通过也不能证明 DeepSeek 实际返回过有效 action，更不能形成动作质量或胜率结论。下一步 L5-A3 必须先增加脱敏模型调用与 fallback 聚合，再做稳定性实验。

完成后请报告：

1. HEAD、工作区、定向回归与配置元数据门槛；
2. 用户连接/建桌确认；
3. connector exit、stop reason 和聚合 audit；
4. Botzone 裁判结果；
5. state/audit/残留进程安全检查；
6. 唯一判定与结论边界。
