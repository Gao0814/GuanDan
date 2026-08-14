# 下一步实施提示词

## Step L5-A2b6b：runtime config 无敏感子阶段诊断

本任务只在仓库外对 L5-A2b6a 已定位的 `load_runtime_config()` 边界执行一次更细的零网络诊断。不得重跑正式 `--preflight-only`，不得修改仓库代码，不得启动 connector、连接 Botzone、调用 DeepSeek、读取 `.env` 或输出 URL、key、目录值、异常正文。

### 已确认事实

- L5-A2b5a 检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- L5-A2b6 正式 preflight 永久为 `botzone_deepseek_connector_v4_preflight_invalid`，不得重跑或追认。
- L5-A2b6a 唯一 process-only 诊断结果为 `runtime_config_invalid`。
- 最后已落盘阶段为 `runtime_config_load_started`；state preflight、AppConfig、agent factory 和 Agent 创建均未执行。
- L5-A2b6a audit、state 和进程已清理；网络、模型、connector 与 suggestion 计数均为 0。
- 当前证据不能归因于 URL、state 参数、数值边界、权限、Python 或平台环境。

### 目标

在不保存配置值的前提下，区分以下固定边界：

```text
harness_qualification
environment_presence
state_argument_shape
https_url_validation
numeric_limits_validation
runtime_config_object_create
diagnosis_completed
```

### 载体资格

1. 先确认工作区干净、检查点存在、无残留 connector；不重复 36/574 回归。
2. 在系统临时目录创建一个全新仓库外诊断目录；脚本顶层只使用标准库并先原子写入 `bootstrapping` audit。
3. 设置网络 tripwire，禁止 DNS、socket、HTTP、Botzone transport、connector、Agent 和模型调用。
4. 在同一个诊断进程中，先使用固定合成 URL `https://example.invalid/local-ai`、全新合成 state 路径和公开默认数值调用 `load_runtime_config()`。
5. 合成资格失败时唯一结果为：

```text
diagnostic_harness_invalid
```

此时不得检查真实进程配置，也不得修正脚本后重跑。

### 真实配置子阶段

资格通过后，仍在同一个唯一进程内执行：

1. `environment_presence`：只判断 `BOTZONE_LOCAL_AI_URL` 是否为非空字符串；不得记录值、长度或 hash。
2. `state_argument_shape`：只判断本任务新建 state 参数是否为非空绝对仓库外路径；不得记录路径文本。
3. `https_url_validation`：调用现有纯本地 `validate_https_url()`；只记录 pass/fail，不记录解析结果。
4. `numeric_limits_validation`：使用正式入口相同的公开参数/default，分别确认 timeout、response limit、failure limit 和 backoff 可被严格规范化；不记录原始值。
5. `runtime_config_object_create`：调用一次 `load_runtime_config()`；不得调用 `preflight_state_directory()`。
6. 成功后只验证结果类型、state 指向本任务目录、数值字段为正；URL 字段只能比较是否与上一步规范化对象相等，不得序列化或输出。

### 固定结果

只允许以下结果：

```text
diagnostic_harness_invalid
configured_url_missing
state_argument_invalid
configured_url_invalid
numeric_limits_invalid
runtime_config_object_invalid
runtime_config_boundary_not_reproduced
unexpected_failure
```

audit 只记录 schema/version、started/completed 阶段、固定结果和以下全零计数：DNS、socket、HTTP、Botzone GET、transport、connector cycle、DeepSeek request、Agent create、`suggest_action_id()`。不得记录异常类型、消息、traceback、配置值、路径、Header、match、牌、请求或 prompt。

脚本只运行一次；不得换目录、修正后重跑或补采。state 目录与本任务登记的探针文件必须清理，脱敏诊断 audit 和 manifest 保留，无残留进程。

### 判定与后续

- 命中单一固定失败结果：只报告该边界，原 L5-A2b6 invalid 保持不变，并为该边界另行规划最小修复。
- 全部阶段通过：报告 `runtime_config_boundary_not_reproduced`；不得因此追认原 preflight 或直接恢复 live。
- 本任务不请求 live 授权，不修改 runtime，也不形成 DeepSeek 可达性、动作质量或胜率结论。
