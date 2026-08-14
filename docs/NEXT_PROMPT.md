# 下一步实施提示词

## Step L5-A2b3a：DeepSeek 固定预算配置恢复

本任务只恢复当前 Codex 进程可继承的 DeepSeek timeout/retry 配置，并重新执行最小零网络准入。不得启动 live connector，不得 poll Botzone，不得调用 DeepSeek。

### 已确认结果

- L5-A2b2 实现检查点：`37bdd0d`。
- L5-A2b3 启动门槛中 endpoint/model 匹配，但当前配置不满足授权预算：

```text
DEEPSEEK_TIMEOUT=60
DEEPSEEK_MAX_RETRIES=0
```

- 规范化结果：

```text
precondition_failed: deepseek_budget_mismatch
```

- connector 未启动，Botzone/DeepSeek/network request 均为 0，授权未消耗；工作区干净，无残留 connector。

### 项目所有者先执行的环境操作

在 Windows PowerShell 中设置用户环境变量：

```powershell
[Environment]::SetEnvironmentVariable("DEEPSEEK_TIMEOUT", "60", "User")
[Environment]::SetEnvironmentVariable("DEEPSEEK_MAX_RETRIES", "0", "User")
```

然后完全退出所有 Codex 窗口和后台进程，再重新打开 Codex 与本项目。已有 Codex 进程不会自动获得新变量；不得把值只设置在一个与 Codex 无关的临时终端中。

不得修改或读取 `.env`，不得输出 API key、Botzone URL 或其他配置正文。

### 新进程确认门槛

只有项目所有者明确回复“已从设置好 60/0 的新进程重新启动”后，才执行以下检查：

1. HEAD 包含 `37bdd0d`，七个 L5-A2b2 文件无差异，工作区干净；
2. 只报告以下布尔结果，不输出原值：
   - Botzone URL present；
   - DeepSeek key present；
   - endpoint 精确匹配 `https://api.deepseek.com`；
   - model 精确匹配 `deepseek-v4-flash`；
   - timeout 为非 bool 数值且精确等于 60；
   - retries 为非 bool 整数且精确等于 0；
3. 无本项目残留 connector；
4. 运行 24 项定向测试与 `git diff --check`。

任一失败继续输出 `precondition_failed`，不得重查环境、创建 state 或启动子进程。

### 唯一零网络 preflight

全部门槛通过后，使用全新系统临时 state 目录，恰好执行一次：

```text
python -m integrations.botzone --agent deepseek --preflight-only --state-dir <fresh-temp-state>
```

- 30 秒硬上限，不重试；
- 必须 exit 0、stdout 单行 `preflight_ready`、stderr 空、state 最终为空并删除、无残留；
- Botzone GET、DeepSeek request、DNS/socket/HTTP、connector cycle、`suggest_action_id()` 均为 0。

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

配置恢复和 preflight ready 只证明固定 60/0 预算在新进程中可被本地组合读取，不证明 Botzone 信封兼容、DeepSeek 可达、模型有效动作、动作质量或胜率提升。
