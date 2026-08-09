# 下一步实施提示词

## Step L4-A2c5b1：真实 state 目录临时文件创建边界诊断

请在 GuanDan 项目中执行 Step L4-A2c5b1。本轮只做离线、只读源码和仓库外诊断，不修改仓库文件，不重复运行任何既有 preflight，不启动 live launcher/connector，不发送 GET，也不请求 live 授权。

### 已封板事实

- L4-A2c5a 检查点：`8ceb038d3dc6d6a4cfae3525b2bc92b2cc6da78c`，范围精确为：
  - `integrations/botzone/live_preflight.py`
  - `integrations/botzone/runtime_config.py`
  - `tests/test_botzone_instrumented_preflight.py`
- L4-A2c5a 回归：定向 10、相关 23、全量 526 项及 `git diff --check` 均通过；
- L4-A2c5b 唯一判定：`botzone_instrumented_live_preflight_invalid`；
- 唯一真实环境 preflight 已在 30 秒超时后终止且未重试；
- 最后 audit 为 `status=running`、最后完成阶段 `directory_ready`、diagnostic 为空；
- `temporary_opened` 未出现；源码顺序表明阻塞区间位于 `NamedTemporaryFile(...)` 返回之前，但根因仍未知；
- state 目录事后为空，request/GET/network/connector/live-launcher 均为 0；
- L4-A2b、L4-A2c3a 的 invalid 与 L4-A2c4a/L4-A2c4b 的 inconclusive 永久保留。

原 L4-A2c5b 证据必须只读保留：

- `preflight.json`：262 bytes，SHA-256 `770f567b94da9db29ec82ba8f3742f129e698514196c9bd86e4b5bf36a4365b2`；
- `stdout.txt`：0 bytes，SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`；
- `stderr.txt`：0 bytes，同一空文件 SHA-256。

### A. 前置门槛

1. HEAD 包含 L4-A2c5a 检查点，工作区干净；
2. 复核上述三个源证据的 bytes/SHA-256，不修改、移动、补写或删除；
3. 只确认 `BOTZONE_STATE_DIR` 为 present，不读取 `.env`，不输出、复制或散列真实路径；
4. 不读取 `BOTZONE_LOCAL_AI_URL` 的值，仅确认本任务不会使用它；
5. 确认 state 目录存在且为空，只报告 `exists/empty`；
6. 确认没有残留的 `integrations.botzone`、`live_preflight`、`live_launcher` 或本任务诊断进程；
7. 新建仓库外、全新且为空的诊断目录。

任一门槛失败即 `precondition_failed`，不得创建或运行诊断子进程。

### B. 仓库外诊断载体

只在新诊断目录创建标准库脚本，不写入仓库。父进程负责硬超时、终止和证据汇总；子进程只读取当前进程中的 `BOTZONE_STATE_DIR`，不得读取 `.env`、URL、密钥、Cookie、Header、账号信息或仓库配置。

子进程必须：

1. 在接触 state 目录前，向仓库外 audit 原子写入 `bootstrapping`；
2. 不导入 `integrations.botzone`，以避免重复正式 preflight；
3. 对以下操作分别在调用前、成功后写入累计 stage：
   - `state_resolve_started/completed`
   - `directory_stat_started/completed`
   - `candidate_name_started/completed`
   - `exclusive_open_started/completed`
   - `fdopen_started/completed`
   - `write_started/completed`
   - `flush_started/completed`
   - `fsync_started/completed`
   - `close_started/completed`
   - `replace_started/completed`
   - `unlink_started/completed`
   - `diagnosis_completed`
4. 候选名只能由标准库生成，并以本任务固定前缀标识；使用 `os.open(..., O_CREAT|O_EXCL|O_RDWR)` 将候选名生成与文件创建拆开；
5. 只操作本任务创建的精确 probe/replacement 路径，不使用通配符，不扫描或删除未知文件；
6. 开启脱敏 `faulthandler` 定时栈转储；不得记录局部变量、环境值或真实 state 路径；
7. audit 只保留 schema、状态、累计阶段、规范化诊断、退出码和四个固定零网络计数。

父进程必须把 stdout/stderr 分开写入仓库外新文件，不使用 PowerShell `Start-Process` 重定向参数。

### C. 载体资格验证

先用全新临时目录运行同一子脚本恰好一次，10 秒上限。资格验证必须满足：

- 退出码 0；
- 全部阶段到 `diagnosis_completed`；
- 临时目录事后为空；
- stdout/stderr 不含敏感形态；
- request/GET/network/connector/live-launcher 均为 0。

资格验证失败时，唯一判定为 `botzone_state_tempfile_diagnosis_harness_invalid`，不得接触真实 state 目录。

### D. 真实 state 目录诊断

资格验证通过后，使用同一脚本、同一调用形状，对真实 state 目录执行恰好一次，30 秒硬上限，不重试、不补采。

- 正常完成：保留完整 audit，确认 state 目录为空；结论为 `botzone_state_tempfile_diagnosis_not_reproduced`。
- 超时：终止唯一子进程，保留最后 started/completed stage 和 faulthandler 栈；只把阻塞边界归到最后未完成的原子操作，不推断权限、杀毒软件、磁盘、Python 或操作系统根因。
- 非零退出：记录规范化异常类别和最后阶段，不输出异常链中的真实路径。
- 如留下本任务拥有的精确 probe 文件，只能在记录其存在且唯一归属后删除该精确路径；不得删除其他内容。清理失败必须报告，不能宣称 state 为空。

若证据完整并把阻塞定位到单个原子操作，判定：

```text
botzone_state_tempfile_operation_boundary_verified
```

若正常完成、未复现，判定：

```text
botzone_state_tempfile_diagnosis_not_reproduced
```

若 audit、进程、清理、敏感扫描或守恒不完整，判定：

```text
botzone_state_tempfile_diagnosis_invalid
```

### 禁止事项

- 不运行 `python -m integrations.botzone.live_preflight` 或旧 `--preflight-only`；
- 不修改 `runtime_config.py`、`live_preflight.py`、测试或任何仓库文件；
- 不启动 launcher、connector、transport 或 opener；
- 不发送任何网络请求；
- 不读取或显示真实 URL、密钥、state 路径；
- 不因本次诊断成功而直接进入 live。

### 最终报告

报告必须包含：

- HEAD、工作区与 L4-A2c5a 检查点范围；
- 原 L4-A2c5b 证据复核结果；
- 资格验证和真实目录诊断各自的退出码、耗时、最后阶段；
- timeout/termination/cleanup 情况；
- audit、stdout、stderr、runner、summary 的 bytes/SHA-256；
- state 目录前后 `empty` 状态；
- request/GET/network/connector/live-launcher count=0；
- 唯一判定和明确的结论边界。

本任务只定位本地文件操作边界。后续是否修改 preflight、调整 state 目录或恢复 launcher 准入，必须根据该证据另开任务规划。
