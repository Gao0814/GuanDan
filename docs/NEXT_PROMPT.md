# 下一步实施提示词

## Step L5-A2b6a：DeepSeek 本地组合阶段安全诊断

本任务只在仓库外执行一次零网络、分阶段的本地组合诊断，用固定低基数结果定位 L5-A2b6 的 exit 2。不得重跑正式 `--preflight-only`，不得修改仓库代码，不得启动 connector、连接 Botzone 或调用 DeepSeek。

### 已确认基线

- L5-A2b5a 检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- L5-A2b6 前置全部通过：36 项定向、574 项全量、补丁检查、配置元数据、工作区和残留进程门槛均通过。
- 唯一正式零网络 preflight 已执行一次：30 秒内 exit 2，stderr 空，state 前后为空并删除，全部网络/模型计数为 0。
- stdout 仅归类为 `unexpected_stdout`，未保留或复述正文。
- 判定永久为 `botzone_deepseek_connector_v4_preflight_invalid`；不得重跑或追认。
- 只读代码顺序表明 exit 2 可能来自：`load_runtime_config()`、`preflight_state_directory()` 或 `prepare_agent_factory("deepseek")`；现有入口将这些路径统一折叠为 `configuration_error`，当前证据不能继续归因。

### 目标

使用一个仓库外临时诊断载体，把本地组合拆成固定阶段：

```text
runtime_config_load
state_directory_preflight
process_app_config_load
agent_factory_build
agent_instance_create
diagnosis_completed
```

只记录阶段是否开始/完成、固定失败类别和零网络计数。不得记录异常正文、配置值、路径、对象 repr 或动态字段。

### 诊断要求

1. 先确认 HEAD 包含检查点、工作区干净、无残留 connector；不重复 36/574 回归。
2. 在系统临时目录创建全新的诊断目录、state 子目录和 audit 文件，均位于仓库外。
3. 诊断脚本顶层只使用标准库，先原子写入 `bootstrapping` audit，再延迟导入项目模块。
4. 禁止加载仓库 `.env`：调用 `AppConfig.from_env()` 时必须将 `config.load_dotenv` 临时替换为无操作函数，确保只消费当前进程环境。
5. 只检查并使用当前进程中的配置；API key 可以传入现有 client 构造，但不得输出、散列、复制或持久化。
6. 分阶段执行：
   - `load_runtime_config()`，使用全新 state；
   - `preflight_state_directory()`；
   - process-only `AppConfig.from_env()` 并复核 endpoint/model/60/0；
   - `build_agent_factory("deepseek", config_loader=lambda: config)`；
   - 调用 factory 创建一次 player 1 Agent，但不得调用 `select_action()` 或 `suggest_action_id()`。
7. 设置网络 tripwire；DNS、socket、HTTP、Botzone transport、connector cycle、DeepSeek request 和 `suggest_action_id()` 计数必须全部为 0。
8. 只允许固定结果：

```text
runtime_config_invalid
state_directory_invalid
process_app_config_invalid
agent_factory_build_invalid
agent_instance_invalid
unexpected_failure
process_only_composition_ready
```

9. 捕获异常时只记录固定结果和失败阶段，不记录异常类型、消息、链、traceback 或 repr。
10. 脚本只运行一次，不修正后重跑；state 最终必须为空并删除，不能残留 Python 进程。

### 判定

- 任一阶段失败：报告对应固定结果；原 L5-A2b6 invalid 保持不变，并为该阶段另行规划修复。
- 所有阶段通过：唯一判定为：

```text
botzone_deepseek_process_only_composition_verified
```

该结果只说明显式进程环境下的本地组合成立，不追认原 preflight，也不能直接 live。完成后只更新 docs，并根据阶段结果生成下一提示词；不得请求 live 授权。
