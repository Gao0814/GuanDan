# 下一步实施提示词

## Step L4-A2c5b2：独占创建错误分类与目录范围对照

请在 GuanDan 项目中执行 Step L4-A2c5b2。本轮只做仓库外、标准库、零网络的文件系统诊断；不修改仓库文件，不重跑任何既有 preflight，不启动 launcher/connector，不永久修改环境变量，也不请求 live 授权。

### 已封板事实

- L4-A2c5b1 执行时 HEAD：`8a535724bebc880cd54309c06bb663ba09f59d13`；
- L4-A2c5a 检查点：`8ceb038d3dc6d6a4cfae3525b2bc92b2cc6da78c`，范围仍精确为三个文件；
- L4-A2c5b：`botzone_instrumented_live_preflight_invalid`，最后阶段 `directory_ready`；
- L4-A2c5b1：`botzone_state_tempfile_operation_boundary_verified`；
- L4-A2c5b1 临时目录资格验证成功；
- 真实 state 目录诊断只执行一次，exit code 5，最后阶段 `exclusive_open_started`，没有 `exclusive_open_completed`，规范化诊断为 `operation_error`；
- 失败边界已限定为 `os.open(..., O_CREAT|O_EXCL|O_RDWR)`，但尚无脱敏 `errno/winerror` 和目录范围对照，不能归因于权限、杀毒、磁盘、Python 或操作系统；
- 清理仅针对任务登记的候选文件，exit code 0；真实 state 目录前后均存在且为空；
- request/GET/network/connector/live-launcher 均为 0。

L4-A2c5b1 仓库外证据必须只读保留：

- `state_probe.py`：6,192 bytes，SHA-256 `f86ea0c6c076ba0cf40398ea72f73ad3253e0ca5091c3decc085ac551468c320`；
- `driver.py`：4,587 bytes，SHA-256 `ba34fd1d89c5ddfff365705671af7cfea2a2aea407439e363e0f7257a5434488`；
- `summary.json`：3,127 bytes，SHA-256 `0851b694c26ed5dd215914092bf0df507d8d2c89b96ec52e89737ab03752bbc1`；
- qualification audit/stdout/stderr：714 / 23 / 0 bytes；
- real audit/stdout/stderr：432 / 0 / 0 bytes；
- cleanup audit/stdout/stderr：452 / 0 / 0 bytes。

### A. 前置门槛

1. 工作区干净，L4-A2c5a 检查点存在且范围不变；
2. 复核 L4-A2c5b 与 L4-A2c5b1 已列证据的 bytes/SHA-256，源证据不得修改、移动、补写或删除；
3. 只确认 `BOTZONE_STATE_DIR` 为 present；不得读取 `.env`；
4. 当前 state 目录存在且为空，只报告 `exists/empty`；
5. 没有残留 Botzone、preflight、launcher 或诊断进程；
6. 新建仓库外、全新且为空的本次诊断目录；
7. 预先锁定三个目标标签，不在审计中保存真实路径：
   - `configured_state`：当前配置目录；
   - `same_volume_fresh`：与当前目录同卷、仓库外的全新诊断目录；
   - `local_appdata_fresh`：用户本地应用数据区域中的全新诊断目录。

任一门槛失败即 `precondition_failed`。不得显示、复制或散列真实 URL、密钥或三个目录的绝对路径。

### B. 新诊断载体

只在仓库外诊断目录创建标准库脚本。不得复用或改写旧证据，不得导入 `integrations.botzone`。

每次探测只执行一个独占创建调用：

```text
os.open(candidate, O_CREAT | O_EXCL | O_RDWR, 0o600)
```

每个目标必须使用独立、随机、带本任务固定前缀的候选名，并执行恰好一次。调用前后原子记录：

- `exclusive_open_started`
- `exclusive_open_completed` 或 `exclusive_open_failed`
- `close_completed`
- `cleanup_completed`

异常只允许持久化以下脱敏字段：

- 固定白名单中的异常类型名；
- `errno`：严格整数或 null；
- `winerror`：严格整数或 null；
- `filename_present`：严格 bool；
- `filename2_present`：严格 bool；
- `candidate_exists_after`：严格 bool。

禁止持久化 `str(exc)`、`repr(exc)`、`exc.args`、`strerror`、filename 值、环境值或路径。stdout/stderr 也不得输出异常原文。

父进程对每次子进程设置 15 秒硬上限；超时只终止对应子进程，不重试。只清理本任务登记的精确候选文件和两个全新诊断目录，不使用通配符，不扫描或删除未知文件。

### C. 载体资格验证

先在第四个全新临时目录运行同一探针恰好一次。必须满足：

- exit code 0；
- `exclusive_open_completed`、`close_completed`、`cleanup_completed` 全部出现；
- 目录事后为空；
- 脱敏 schema、严格类型和零网络计数通过；
- stdout/stderr 无敏感形态。

失败则判定 `botzone_exclusive_open_scope_harness_invalid`，不得运行三目标矩阵。

### D. 三目标矩阵

资格验证通过后，严格按以下顺序各执行一次：

1. `configured_state`
2. `same_volume_fresh`
3. `local_appdata_fresh`

前一目标无论成功、规范化失败或超时，都要在确认其子进程退出并完成任务自有清理后再运行下一目标。不得因观察到结果而改顺序、改 flags、补采或重复某个目标。

每个目标报告：exit code、耗时、最后阶段、脱敏异常字段、候选文件事后存在性和目录最终空状态。对三者只使用固定标签，不记录真实路径。

### E. 判定规则

资格验证和三目标证据完整、守恒且至少稳定区分出失败/成功范围：

```text
botzone_exclusive_open_failure_scope_verified
```

三目标均成功，未复现既有失败：

```text
botzone_exclusive_open_scope_diagnosis_not_reproduced
```

结果混杂但不能形成目录范围、异常字段缺失、超时无法清理，或任何审计/敏感/进程守恒失败：

```text
botzone_exclusive_open_scope_diagnosis_invalid
```

即使形成 `scope_verified`，也只能陈述以下范围之一：

- 当前配置目录特异；
- 当前卷或父级范围相关；
- 三个目录均失败的进程级/更广范围；
- 其他由矩阵直接支持的范围。

不得把范围结论升级为权限、杀毒、磁盘、Python、Windows 或安全软件根因。

### 禁止事项

- 不运行任何 preflight；
- 不修改 `BOTZONE_STATE_DIR` 的用户/系统配置；
- 不修改 runtime、测试或其他仓库文件；
- 不启动 launcher、connector、transport 或 opener；
- 不发送网络请求；
- 不读取或显示真实 URL、密钥、目录路径；
- 不因某个新目录成功而直接恢复 live。

### 最终报告

报告必须包含：

- HEAD、工作区和 L4-A2c5a 检查点范围；
- L4-A2c5b/L4-A2c5b1 证据只读复核；
- 资格验证与三个固定标签的完整矩阵；
- 每项的 exit code、耗时、阶段、errno/winerror、候选存在性和清理结果；
- runner、audit、stdout、stderr、summary、manifest 的 bytes/SHA-256；
- 所有测试目录和 configured state 的最终 empty 状态；
- request/GET/network/connector/live-launcher count=0；
- 唯一判定及不归因声明。

后续是否建议更换 state 目录或修改 preflight，必须依据该矩阵另开任务；本步不做永久环境变更。
