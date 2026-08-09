# 下一步实施提示词

## Step L4-A2c3a：Windows launcher 零网络恢复准入审计

请在 GuanDan 项目中执行 Step L4-A2c3a。先把已验证的 L4-A2c2 两个文件独立封存为代码检查点，再使用新 launcher 做一次严格零网络的恢复准入审计。不得启动真实 Botzone connector、不得发送 GET、不得创建或加入对局。

### 已封板事实

- 文档基线：`fc5e537dc81ec17ed7605fadc766eb86ec4a5bfd`；
- L4-A2b 永久判定：`botzone_no_tribute_local_ai_smoke_invalid`；
- L4-A2c1：`botzone_launcher_environment_diagnosis_verified`；
- L4-A2c2：`botzone_windows_live_launcher_hardening_verified`；
- L4-A2c2 定向 5 项、相关 17 项、全量 520 项通过；
- 两次 Windows PowerShell 合成 probe 均为退出码 17，环境、工作目录、参数和 stdout/stderr 分流正确；
- PowerShell live 调用已移除 `RedirectStandardOutput` / `RedirectStandardError`；
- L4-A2c2 network/GET/connector count=0。

本步不继承任何 live 授权。L4-A2b invalid 不得追认、重跑或改写。

### A. 独立封存 L4-A2c2

启动时工作区必须只有以下两个未跟踪文件：

- `integrations/botzone/live_launcher.py`；
- `tests/test_botzone_live_launcher.py`。

不得存在其他修改或未跟踪文件。只读复核实现与报告一致，并重新运行：

```text
python -m unittest tests.test_botzone_live_launcher -q
python -m unittest tests.test_botzone_runtime_config tests.test_botzone_runner tests.test_botzone_live_preflight tests.test_botzone_live_launcher -q
python -m unittest discover -q
git diff --check
```

全部通过后，只提交上述两个文件为独立 L4-A2c2 检查点。提交范围必须精确，不得包含 docs、配置、日志或外部证据。提交后工作区必须干净。任一门槛失败即 `precondition_failed`，不得继续准入审计。

### B. 零网络准入前置

只检查非敏感元数据：

1. L4-A2c2 检查点存在且只包含上述两个文件；
2. `BOTZONE_LOCAL_AI_URL` 与 `BOTZONE_STATE_DIR` 在当前进程中均为 present，只输出 present/missing；
3. `CODEX_LAUNCHER_OFFLINE_PROBE`、`CODEX_LAUNCH_SENTINEL`、`CODEX_LAUNCH_EXPECTED_CWD` 在正式环境中初始均为 missing；
4. state dir 与用户此前确认的仓库外目录一致、存在且为空；只报告 matched/exists/empty，不输出 URL、目录内容或敏感值；
5. 没有正在运行的 `integrations.botzone` 或 `live_launcher` 进程；
6. 新建仓库外本次专用 audit 目录，初始为空。

不得读取 `.env`、URL 值、密钥、Cookie、Header、账号信息或浏览器存储；不得删除未知 state。任一失败即 `precondition_failed`。

### C. 恢复 preflight

正式执行恰好两项零网络检查：

1. 运行一次既有 `python -m integrations.botzone --preflight-only`，必须返回 `preflight_ready`；该路径不得构造 transport/opener 或发送请求。
2. 使用 PowerShell Desktop 5.1 `Start-Process` 启动一次 `python -m integrations.botzone.live_launcher` 的 offline probe：只使用 `-WindowStyle Hidden`、`-WorkingDirectory`、`-PassThru`、`-Wait`，不得使用两个 PowerShell Redirect 参数。

offline probe 规则：

- 仅对子进程临时注入三项合成 probe 变量，probe 结束后恢复为 missing；
- launcher 的 stdout/stderr/audit 参数指向同一个仓库外专用空目录中的三个互异路径；
- 预期退出码精确为 17；
- stdout/stderr 必须分别为固定 probe 文本；connector audit 不应生成；
- 不调用 `_connector_main`、transport、opener、session、Agent 或网络；
- 不启动第二个进程，不重试失败 probe。

### D. 结束审计

确认：

- preflight 前后 state dir 都为空；
- audit 目录只含预期的 probe stdout/stderr 与脱敏汇总；
- 没有残留 connector/launcher 进程；
- request/GET/network/connector count 均为 0；
- 工作区保持干净；
- stdout/stderr、固定输出和汇总不含 URL、密钥、Header、match ID、手牌、环境值或绝对敏感路径。

仓库外写入一个原子、确定性的 `preflight_summary.json`，只保留 schema/version、检查布尔值、退出码、计数和规范化 diagnostics，不保留命令行、PID、环境值或真实路径。

### 判定与授权边界

全部门槛通过：

```text
botzone_live_launcher_recovery_preflight_ready
```

任一门槛失败：

```text
botzone_live_launcher_recovery_preflight_invalid
```

失败不得重试、补采或转为 live。通过也不得在本任务中联网；只能在最终报告后向用户请求一次新的 L4-A2c3b 明确授权。

授权请求必须锁定并展示：RuleBasedAI、用户手动创建一局且“需要进贡=否”、最多 100 GET、最长 600 秒、timeout 30 秒、连续失败 5、finished 1、零自动重试、不使用 runmatch/DeepSeek、PowerShell 不使用 Redirect 参数。没有用户后续明确同意，不得启动 live launcher。

### 最终报告

报告必须包含：

- L4-A2c2 检查点 hash 与精确提交范围；
- 5 / 17 / 520 回归复核；
- 两项零网络检查结果；
- launcher probe 退出码和分流校验；
- state/audit/worktree 清洁性；
- request/GET/network/connector count=0；
- summary 文件 bytes/SHA-256；
- L4-A2b invalid 永久保留；
- 若 ready，附上固定预算的新授权问题，但不得自行继续 live。
