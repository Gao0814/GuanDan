# 下一步实施提示词

## Step L4-A2c4a：Botzone preflight 超时纯离线分阶段诊断

请在 GuanDan 项目中执行 Step L4-A2c4a。本步只诊断 L4-A2c3a 中既有 `python -m integrations.botzone --preflight-only` 为何在 30 秒内未返回。不得再次对真实环境/state dir 运行该命令，不得启动 live launcher、connector 或网络请求，也不得修改仓库文件。

### 已封板事实

- L4-A2c2 检查点：`30d9b5897d97939f64dab32b97772118c72ef3d1`，只含 `live_launcher.py` 与对应测试；
- L4-A2c2 复核：定向 5、相关 17、全量 520 项及 `git diff --check` 通过；
- L4-A2c3a 判定：`botzone_live_launcher_recovery_preflight_invalid`；
- 实际环境 metadata、空 state dir、无残留进程和干净工作区门槛均通过；
- 第一项零网络检查在 30 秒上限内没有返回 `preflight_ready`；
- 第二项 launcher offline probe 未执行；
- 未重试、未启动 connector/live launcher，request/GET/network/connector count 均为 0；
- L4-A2b 的 `botzone_no_tribute_local_ai_smoke_invalid` 永久保留。

L4-A2c3a 证据文件：`C:\Users\86166\AppData\Local\Temp\guandan-botzone-launcher-recovery-82a5c4c7321b420fa233cfbdffe1a333\preflight_summary.json`，522 bytes，SHA-256 `9c4ed8010a950f11bedae92e5784118f080a5ee95f0bfb8087638f896fbc00b2`。只允许只读解析该脱敏 JSON 和复核 metadata/hash，不得修改或补写。

### 启动前门槛

1. 工作区干净；
2. `30d9b5897d97939f64dab32b97772118c72ef3d1` 是当前 HEAD 的祖先；
3. 该检查点之后只允许五份规划 docs 变化；
4. 上述 summary 的 bytes/hash 不变；
5. 没有正在运行的 `integrations.botzone` 或 `live_launcher` 进程。

任一失败即 `precondition_failed`。不得清理 state、重跑 preflight 或修改代码。

### 安全边界

- 不读取 `.env`、真实 `BOTZONE_LOCAL_AI_URL` 值、密钥、Cookie、Header、账号信息或浏览器存储；
- 不使用实际 `BOTZONE_STATE_DIR`；
- 所有诊断只使用固定合成 URL（`.invalid` 域名）和仓库外全新临时 state/audit 目录；
- 不构造 `LocalAIHttpTransport`、opener、socket 或请求；
- 不调用 RuleBasedAI、adapter、session 或 connector；
- 不修改仓库，不提交诊断脚本或证据。

### 分阶段诊断

在仓库外创建标准库诊断脚本。每个阶段都在独立 Python 子进程运行，开始/结束写入原子 heartbeat，单阶段上限 10 秒；超时后只终止该子进程并记录最后完成阶段。禁止执行真实 preflight 命令。

按顺序运行：

1. `python_startup`：仅启动 Python、输出固定标记并退出；
2. `runtime_config_import`：只导入 `integrations.botzone.runtime_config`；
3. `main_import`：只导入 `integrations.botzone.__main__`，用于覆盖其顶层 transport/runner/adapter import graph；
4. `config_load`：以显式合成 HTTPS URL、显式临时 state path 和空 mapping 调用 `load_runtime_config()`；
5. `state_preflight_steps`：在临时 state 目录逐项执行并打点 `resolve → project-boundary-check → mkdir → NamedTemporaryFile → write → flush → fsync → replace → unlink → exit`；
6. `state_preflight_function`：直接调用 `preflight_state_directory()`，前后目录必须为空；
7. `main_function`：直接调用 `integrations.botzone.__main__.main()`，显式传入合成 `--url`、`--state-dir` 与 `--preflight-only`，并传空环境 mapping；预期退出码 0、输出精确为 `preflight_ready`；
8. `module_subprocess`：独立执行 `python -m integrations.botzone`，同样只传显式合成 URL/state 与 `--preflight-only`；预期 10 秒内退出 0。

每一步最多运行一次；只有在全部步骤成功后，才允许用全新临时目录把第 8 步再运行一次作为确定性复验。不得对真实环境/state 路径重试。

### 超时证据

诊断子脚本启用 `faulthandler.dump_traceback_later()` 或等价标准库机制，在超时前写入仅含模块/函数/阶段的脱敏栈证据。最终报告和 JSON 不得保留绝对用户路径、命令行、合成 URL 全文或环境值；只保留规范化 stage/category。

根因类别只能是：

- `python_startup`
- `runtime_config_import`
- `main_import_graph`
- `config_load`
- `path_resolve`
- `state_mkdir`
- `tempfile_open`
- `file_write`
- `file_flush`
- `file_fsync`
- `file_replace`
- `file_unlink`
- `main_function`
- `module_process_exit`
- `parent_wait`
- `not_reproduced`
- `unknown`

不得仅凭一次 30 秒超时猜测 fsync、杀毒软件、环境变量或 launcher 是根因。

### 判定

若某一阶段稳定给出足够证据，并能明确最小后续修复/测试范围：

```text
botzone_preflight_timeout_diagnosis_verified
```

若全部合成阶段通过、原问题不可复现，或证据不足以区分类别：

```text
botzone_preflight_timeout_diagnosis_inconclusive
```

无论哪种结果，都不得在本步形成 preflight ready、请求 live 授权或运行 launcher probe。

### 最终报告

报告必须包含：

- HEAD、工作区与 L4-A2c2 检查点范围；
- L4-A2c3a invalid 和 L4-A2b invalid 保留声明；
- 原 summary bytes/hash 复核；
- 八阶段 success/timeout/exit/duration 范围及最后 heartbeat；
- 规范化根因类别；
- 若可复现，最小修复文件和测试建议；若不可复现，明确不能直接提高 timeout 或重试 live；
- 新诊断证据目录及非敏感文件 bytes/SHA-256；
- request/GET/network/connector/live-launcher count 均为 0。
