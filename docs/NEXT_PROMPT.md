# 下一步实施提示词

## Step L5-A2a1：使用系统临时目录恢复零网络 preflight

本轮只恢复一次尚未启动的 `--preflight-only`。不得启动 connector 主循环，不得发送 Botzone GET，不得调用 DeepSeek，不得创建测试桌，也不得读取、输出、复制、散列或持久化 API key、本地 AI URL、Header、Cookie、prompt、模型响应或 `.env` 内容。

### 已确认结果

- L5-A1 检查点：`71d9119`。
- L5-A1a 检查点：`aac59d5`。
- L5-A2a 前置审计中，以下项目已通过：
  - 实现检查点与关键文件一致；
  - 工作区干净；
  - 定向 23 项通过；
  - 全量 569 项通过；
  - `git diff --check` 通过；
  - Botzone URL、DeepSeek key、endpoint 和 model 四项脱敏元数据门槛通过。
- 失败仅发生在创建 `%LOCALAPPDATA%` 下的仓库外 state 目录时；当前执行权限不允许该写入。
- preflight 子进程没有创建，Botzone/DeepSeek/DNS/socket/HTTP/connector/model request 均为 0。

规范化结果：

```text
precondition_failed: repository_external_localappdata_not_writable
```

这不是 connector、DeepSeek 配置、RAG 或 preflight 实现失败，也不消耗正式 preflight 的唯一执行次数。

### 本轮唯一调整

使用当前执行环境明确允许写入的系统临时目录，而不是 `%LOCALAPPDATA%`：

- 根目录必须来自 `[System.IO.Path]::GetTempPath()` 或等价的标准库临时目录 API；
- 在其下生成一个全新随机目录名；
- 解析后的绝对路径必须位于系统临时目录内、位于仓库外，且开始时不存在；
- 不得复用历史 state、`BOTZONE_STATE_DIR`、`D:\VsCodeProject\BotzoneState` 或任何固定目录；
- 不得请求扩大文件系统权限。

### 快速前置

1. 当前 HEAD 必须包含 `aac59d5`，L5-A1/L5-A1a 实现文件相对检查点无差异。
2. `git status --short` 必须为空。
3. 只重新确认四项环境元数据门槛，仍只报告 present/match，不输出值。
4. 不重复运行 23/569 回归；前一任务已完成且本轮没有代码变化。
5. 确认不存在可归属于本项目的残留 connector 进程；不得终止来源不明的进程。

任一门槛失败，输出固定 `precondition_failed` 并停止。

### state 目录资格

1. 使用标准库/PowerShell 在系统临时目录下创建唯一候选目录。
2. 确认：绝对路径、仓库外、目录为空、当前任务可列举。
3. 若创建失败：只报告 `temporary_state_directory_unavailable`，不尝试第二个根目录、不申请提权、不启动 preflight。
4. 不做额外独占文件探针；真正的 `preflight_state_directory()` 将负责原子文件操作验证。

### 唯一 preflight

目录资格通过后，只执行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-absolute-directory>
```

约束：

- 30 秒硬上限；
- 不重试、不延长、不启动第二进程；
- 完整捕获 exit code、stdout 类别、stderr 是否为空、耗时、state 目录最终状态与残留进程；
- stdout 只允许规范化后的单行 `preflight_ready`；其他内容只记 `unexpected_stdout`，不得复述原文；
- stderr 非空只记 `unexpected_stderr`，不得复述原文。

成功必须同时满足：

1. 30 秒内自行退出；
2. exit code 0；
3. stdout 精确为单行 `preflight_ready`；
4. stderr 为空；
5. state 目录最终为空；
6. 无残留进程；
7. Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均为 0。

结束后只删除本轮创建且已确认为空的临时 state 目录。

### 证据与隐私

- 可以在系统临时目录另建脱敏 summary，只记录布尔值、固定分类、exit code、耗时和计数。
- 不记录或散列 URL、key、环境变量值、Header、match ID、牌、request/response、prompt、reasoning 或异常正文。
- 不直接打开 `.env`，不修改仓库，不创建 runner 源码，不提交仓库外证据。

### 判定

全部成功门槛通过：

```text
botzone_deepseek_connector_live_preflight_ready
```

子进程已启动但任一门槛失败：

```text
botzone_deepseek_connector_live_preflight_invalid
```

临时目录或其他前置失败、子进程未启动：

```text
precondition_failed
```

不得重试或用推测补齐证据。

### 结论边界

即使 ready，也只证明真实本机配置、临时 state 文件操作、RAG 与 DeepSeek Agent 的零网络构造可用。它不证明 Botzone/DeepSeek 网络可达、单回合延迟、动作质量或胜率。

通过后不得立即启动 connector；下一步只能更新 docs，形成 L5-A2b 的固定 live 预算和明确授权问题。

完成后请报告：

1. HEAD、工作区和四项元数据门槛；
2. 临时 state 目录资格结果；
3. 是否实际启动 preflight；
4. exit/stdout/stderr/耗时/state/进程结果；
5. 零网络计数；
6. 唯一判定。
