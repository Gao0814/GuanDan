# 下一步实施提示词

## Step L5-A2b6c：仓库内 preflight 安全诊断契约

本任务只实现并测试一个仓库内、固定低基数的 preflight 失败分类契约。不得运行真实 preflight，不得读取真实配置或 `.env`，不得联网、启动 connector、创建对局或调用 DeepSeek。

### 已确认基线

- L5-A2b5a 检查点：`8e8d639011bd095bcf0af74816609c63e8c6199f`。
- L5-A2b6 正式 preflight 永久判定 `botzone_deepseek_connector_v4_preflight_invalid`，不得重跑或追认。
- L5-A2b6a 只定位到 `runtime_config_invalid`。
- L5-A2b6b 的仓库外载体在合成资格阶段返回 `diagnostic_harness_invalid`；真实配置子阶段未执行，不能归因任何 runtime 配置字段。
- 两次诊断均保持全部网络/模型/connector 计数为 0，state 与进程已清理。
- 现有 `integrations.botzone.__main__` 将 runtime config、state preflight、Agent composition 和其他 `ValueError` 统一输出为 `configuration_error`，无法安全定位。

### 目标

仅在 `--preflight-only` 模式下，把配置失败映射为以下固定单行输出：

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

成功输出继续精确为：

```text
preflight_ready
```

非 preflight 的 live 启动失败必须继续只输出原有 `configuration_error`，避免扩大运行时信息面。

### 实现要求

1. 只允许修改：

```text
integrations/botzone/runtime_config.py
integrations/botzone/__main__.py
tests/test_botzone_runtime_config.py
tests/test_botzone_deepseek_agent_runtime.py
tests/test_botzone_preflight_output.py
```

如确有必要新增一个专属测试文件，先说明理由；不得修改 transport、runner、connector、session、adapter、engine、agents 或 docs。
2. `RuntimeConfigError` 增加不可变/只读的固定 `category` 契约，并保持 `ValueError` 兼容；现有无参测试构造必须继续安全工作或做最小兼容更新。
3. category 只允许由代码内固定枚举产生，不得包含配置值、路径、异常正文或动态字符串。
4. `__main__` 显式记录当前本地阶段：runtime config、state preflight、agent composition。
5. 只在 `arguments.preflight_only is True` 时输出细分类；其他路径保持 `configuration_error`。
6. 未知 category、普通 `ValueError`、错误类型或意外状态统一映射 `preflight_configuration_error`。
7. Agent composition 不区分 key、RAG、client 或 Agent 子原因，统一为 `preflight_agent_composition_failed`。
8. 不输出异常对象、`str/repr`、traceback、URL、key、state 路径或配置字段值。
9. 不改变参数、退出码、成功 stdout、state preflight、Agent 构造顺序或 transport 构造边界；失败 exit code 仍为 2。

### 测试要求

至少覆盖：

- 六种 runtime-config 固定 category 到 stdout 的一一映射；
- state boundary 与 state operation 两类映射；
- agent composition 统一映射；
- 未知 category 和普通 `ValueError` 回退通用 preflight 错误；
- 同一异常在非 preflight 模式仍输出 `configuration_error`；
- 成功 `preflight_ready` 的直接调用与独立 module LF/CRLF 契约不变；
- 所有失败均 exit 2、stderr 空、transport/opener/connector/Agent action/网络计数为 0；
- 输出不包含合成 secret、URL、路径或异常正文；
- 现有 Botzone envelope、profile、pending/ack 和 DeepSeek runtime 回归通过。

最低验证：

```text
python -m unittest tests.test_botzone_runtime_config tests.test_botzone_deepseek_agent_runtime tests.test_botzone_preflight_output tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

### 验收

通过时唯一判定：

```text
botzone_preflight_safe_diagnostic_contract_verified
```

完成后创建只含允许文件的独立检查点并停止。不得顺带运行真实 preflight；下一阶段 L5-A2b6d 才能使用该契约做一次新的零网络恢复准入。
