# 下一步实施提示词

## Step L5-A2b6d：安全分类契约下的零网络恢复准入

本任务只使用新封存的固定诊断契约，执行恰好一次零网络 DeepSeek connector preflight。不得启动 live connector、连接 Botzone、调用 DeepSeek、创建测试桌或复用历史授权。

### 已确认基线

- L5-A2b5a profile 检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- L5-A2b6c 安全诊断检查点：`3f2cadb7f242625ca0978c5b47a5bc6f5ed299e7`。
- L5-A2b6c 提交范围精确为 runtime config、module entrypoint 和三份测试。
- 定向 26 项、全量 578 项、`git diff --check` 与边界扫描通过。
- preflight 成功仍输出 `preflight_ready`；失败 exit 2 并输出固定 allowlist 类别。
- 非 preflight 启动错误仍只输出 `configuration_error`。
- L5-A2b6 原 invalid、L5-A2b6a/b 诊断结果均永久保留，不重跑、不追认。

### 前置门槛

1. 确认 HEAD 包含两个检查点，L5-A2b6c 提交范围不变，`git status --short` 为空。
2. 运行：

```text
python -m unittest tests.test_botzone_runtime_config tests.test_botzone_deepseek_agent_runtime tests.test_botzone_preflight_output tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

3. 只检查配置元数据，不输出值：
   - `BOTZONE_LOCAL_AI_URL` 与 DeepSeek API key 为 present；
   - endpoint/model 匹配 `https://api.deepseek.com` / `deepseek-v4-flash`；
   - DeepSeek timeout/retries 为严格 60/0。
4. 确认没有残留 Botzone connector Python 进程。
5. 任一门槛失败时返回明确 `precondition_failed`，不得创建 preflight 子进程或请求 live 授权。

### 唯一 preflight

前置全部通过后：

1. 创建一个全新、随机、仓库外、初始为空的系统临时 state 目录。
2. 为唯一子进程显式注入现有进程配置，并额外设置：

```text
PYTHON_DOTENV_DISABLED=1
DEEPSEEK_TIMEOUT=60
DEEPSEEK_MAX_RETRIES=0
```

本机已安装的 `python-dotenv` 支持 `PYTHON_DOTENV_DISABLED`；必须先以纯本地源码检查确认该开关存在。不得打开、解析或读取仓库 `.env`。
3. 恰好执行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-state-dir>
```

4. 硬上限 30 秒，零重试，不换目录、不补采。
5. 捕获 exit code、规范化 stdout 类别和 stderr 是否为空；不得保存 stdout 原始 bytes 或任何配置值。
6. state 结束后必须为空并删除；不得有残留 connector 进程。
7. Botzone GET、DeepSeek request、DNS/socket/HTTP、transport、connector cycle、Agent action 和 `suggest_action_id()` 均必须为 0。

### 固定结果处理

成功必须同时满足：exit 0、stdout 单行 `preflight_ready`、stderr 空、state/进程清理完成、全部网络/动作计数为 0。唯一判定：

```text
botzone_deepseek_connector_v4_recovery_preflight_ready
```

exit 2 时只允许记录以下固定 stdout 类别之一：

```text
preflight_runtime_config_missing
preflight_runtime_config_url_invalid
preflight_runtime_config_timeout_invalid
preflight_runtime_config_response_limit_invalid
preflight_runtime_config_failure_limit_invalid
preflight_runtime_config_backoff_invalid
preflight_state_directory_invalid
preflight_state_operation_failed
preflight_agent_composition_failed
preflight_configuration_error
```

此时判定 `botzone_deepseek_connector_v4_recovery_preflight_invalid`，同时报告固定类别；不得重试或 live。其他 exit/stdout/stderr/state/网络异常同样判 invalid，但不得推测原因。

### 通过后的动作

ready 后只更新 docs，并分别取得：

1. 项目所有者确认所有历史 Botzone 本地 AI 测试桌已关闭；
2. 新的 L5-A2b7 明确授权，完整覆盖本家未公开手牌和决策上下文发送给 DeepSeek、100 次 Botzone GET、DeepSeek 60 秒/零重试、单 connector、单新无贡桌、3600 秒、一局即停。

未获得两项确认前不得启动 live。本步骤不形成 Botzone 协议闭环、DeepSeek 可达性、动作质量或胜率结论。
