# 下一步实施提示词

## Step L4-A2c5b：真实环境 instrumented 零网络 preflight

请在 GuanDan 项目中执行 Step L4-A2c5b。先把 L4-A2c5a 的三个文件独立封存为代码检查点，再使用新专用入口对当前真实进程配置和用户已确认的空 state dir 执行恰好一次零网络 preflight。本步不启动 live launcher/connector，不发送 GET，不请求 live 授权。

### 已封板事实

- L4-A2c2 检查点：`30d9b5897d97939f64dab32b97772118c72ef3d1`；
- L4-A2b 与 L4-A2c3a invalid 永久保留；
- L4-A2c4a/L4-A2c4b inconclusive 永久保留；
- L4-A2c5a 判定：`botzone_instrumented_live_preflight_contract_verified`；
- L4-A2c5a 定向 10、相关 23、全量 526 项通过；
- 合成 module 在 10 秒内退出 0、state 为空、audit 阶段完整；
- L4-A2c5a request/GET/network/connector/live-launcher count=0。

### A. 独立封存 L4-A2c5a

启动时工作区只能包含：

- `M integrations/botzone/runtime_config.py`
- `?? integrations/botzone/live_preflight.py`
- `?? tests/test_botzone_instrumented_preflight.py`

不得有其他变更。重新运行：

```text
python -m unittest tests.test_botzone_instrumented_preflight tests.test_botzone_runtime_config -q
python -m unittest tests.test_botzone_live_launcher tests.test_botzone_live_preflight tests.test_botzone_runner tests.test_botzone_runtime_config tests.test_botzone_instrumented_preflight -q
python -m unittest discover -q
git diff --check
```

全部通过后只提交上述三个文件为 L4-A2c5a 检查点。提交范围必须精确，提交后工作区必须干净。任一失败即 `precondition_failed`，不得运行真实环境 preflight。

### B. 真实环境元数据门槛

只检查：

1. L4-A2c5a 检查点存在且只含上述三个文件；
2. `BOTZONE_LOCAL_AI_URL` 与 `BOTZONE_STATE_DIR` 为 present，只输出 present/missing；
3. 三项 launcher probe 变量均为 missing；
4. state dir 与用户此前确认的仓库外绝对目录一致、存在且为空，只报告 matched/exists/empty；
5. 没有 `integrations.botzone`、`live_preflight` 或 `live_launcher` 进程；
6. 新建仓库外本次专用 audit 目录，初始为空；audit 文件路径尚不存在。

不得读取、输出、复制或散列 URL/密钥值，不读取 `.env`、Cookie、Header、账号信息或 state 内容。不得删除未知 state。任一失败即 `precondition_failed`。

### C. 唯一 instrumented preflight

只执行一次：

```text
python -m integrations.botzone.live_preflight --audit-file <仓库外本次专用 preflight.json>
```

执行要求：

- 工作目录为仓库根；
- 子进程继承当前进程环境，不通过参数传 URL/state；
- 30 秒硬上限；
- 不使用 PowerShell `Start-Process`，不使用 live launcher；
- 不重试，不执行旧 `python -m integrations.botzone --preflight-only`；
- 若 30 秒仍运行，只终止该唯一 preflight 子进程一次，然后只读审计已落盘 JSON；
- 不构造 transport/opener，不发送请求。

成功要求：

- 退出码 0；
- stdout 精确为 `instrumented_preflight_ready`，stderr 为空；
- audit `status=completed`、`exit_code=0`、diagnostic 为空；
- stages 精确为：`runtime_loaded`、`config_loaded`、`resolve`、`boundary_checked`、`directory_ready`、`temporary_opened`、`written`、`flushed`、`synced`、`replaced`、`cleaned`、`state_preflight_completed`；
- request/get/network/connector count 全为 0；
- state dir 事后仍为空。

### D. 超时或失败

如果超时、非零退出、输出不符、audit 缺失/损坏、阶段不完整、state 有残留或出现敏感内容：

- 不重试、不补采、不改 audit；
- 记录最后 status/stage、稳定退出类别和规范 diagnostic；
- 确认唯一子进程已退出；
- 判定 invalid，不执行任何 launcher probe。

audit 只允许读取严格 schema 字段，不输出真实路径或环境值。对 audit/stdout/stderr 做敏感字段名和 URL 形态扫描，但不扫描或显示真实 secret 字符串。

### 判定

全部成功门槛通过：

```text
botzone_instrumented_live_preflight_ready
```

任一门槛失败：

```text
botzone_instrumented_live_preflight_invalid
```

无论结果如何，本步都不得执行 launcher offline probe、启动 connector、请求 live 授权或创建 Botzone 对局。ready 只允许进入 L4-A2c5c 的当前环境 launcher offline 准入。

### 最终报告

报告必须包含：

- L4-A2c5a 检查点 hash 和精确范围；
- 10 / 23 / 526 回归结果；
- metadata 门槛；
- 唯一 preflight 的退出码、固定输出、最终 status/stages/diagnostic；
- state/worktree/process 清洁性；
- audit/stdout/stderr bytes/SHA-256；
- request/GET/network/connector/live-launcher count=0；
- 全部既有 invalid/inconclusive 保留声明；
- 下一步只能是 L4-A2c5c，不得直接 live。
