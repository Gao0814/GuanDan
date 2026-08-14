# 下一步实施提示词

## Step L5-A2b3b：子进程显式锁定 DeepSeek 预算

本任务只用子进程环境显式锁定 `DEEPSEEK_TIMEOUT=60` 与 `DEEPSEEK_MAX_RETRIES=0`，再执行一次最小零网络配置探测和一次零网络 preflight。不得启动 live connector。

### 已确认结果

- L5-A2b2 检查点 `37bdd0d`、工作区、24 项定向、endpoint/model/key/URL 和残留进程门槛通过。
- 项目所有者已设置 Windows 用户环境变量并重新启动 Codex，但当前 Codex 执行宿主仍未继承 timeout/retries。
- L5-A2b3a 规范化结果：

```text
precondition_failed: deepseek_budget_mismatch_after_restart
```

- 未创建 state，未运行 preflight，未启动 connector，Botzone/DeepSeek/network request 为 0，授权未消耗。

### 修正原则

- 不再要求 Codex 父进程的 timeout/retries 必须匹配。
- 在执行配置探测和 preflight 的同一个 PowerShell 子环境中，显式设置：

```powershell
$env:DEEPSEEK_TIMEOUT = "60"
$env:DEEPSEEK_MAX_RETRIES = "0"
```

- 这些设置只作用于本任务子进程，不修改 Windows 用户/系统环境，不修改 `.env`。
- 不人工打开、读取或输出 `.env`。现有 `AppConfig.from_env()` 会按项目既有行为调用 dotenv；由于 `override=False`，子进程显式值必须保持 60/0。
- 不输出 API key、Botzone URL 或任何配置正文。

### 固定前置

1. HEAD 包含 `37bdd0d`，七个实现/测试文件无差异，工作区干净。
2. Botzone URL/key present，endpoint/model 精确匹配；只报告布尔值。
3. 无本项目残留 connector。
4. 运行 24 项定向测试和 `git diff --check`。

父进程 timeout/retries 不再作为门槛；其他任一失败输出 `precondition_failed`。

### 子进程预算探测

在已注入 60/0 的 PowerShell 子环境中，启动恰好一个短 Python 配置探测：

- 调用现有 `AppConfig.from_env()`；
- 严格确认 timeout 是非 bool 数值 60，retries 是非 bool 整数 0；
- 同时确认 endpoint/model/key 仍满足门槛；
- 成功只输出固定 `deepseek_budget_ready`；
- 失败只输出固定 `deepseek_budget_invalid` 并停止；
- 不构造 client、Agent、transport 或 connector，网络计数为 0。

探测不得重试。

### 唯一零网络 preflight

预算探测通过后，在同一个已注入 60/0 的 PowerShell 子环境中，使用全新系统临时 state，恰好执行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-state>
```

- 30 秒硬上限，不重试；
- 必须 exit 0、stdout 单行 `preflight_ready`、stderr 空；
- state 最终为空并删除，无残留进程；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle 和 `suggest_action_id()` 均为 0。

失败判：

```text
botzone_deepseek_connector_v3_preflight_invalid
```

通过判：

```text
botzone_deepseek_connector_v3_preflight_ready
```

### preflight 通过后的人工门槛

只要求项目所有者确认，不执行 live：

```text
我已结束或关闭所有历史 Botzone 本地 AI 测试桌；下一次只会在 connector 显示已连接后创建一个全新的“需要进贡=否”测试桌，不会同时保留或创建第二个活动桌。
```

确认后再提出 L5-A2b4 的新敏感出站/live 授权问题。本任务不得顺带执行 L5-A2b4。

### 结论边界

该恢复只证明显式子进程预算和 v3 本地组合可用，不证明 Botzone 信封兼容、DeepSeek 可达、模型有效动作、动作质量或胜率提升。
