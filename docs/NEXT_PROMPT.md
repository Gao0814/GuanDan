# 下一步实施提示词

## Step L5-A2b12b：项目所有者手动执行宿主机零网络 preflight

L5-A2b12 与 L5-A2b12a 均在子进程启动前返回：

```text
precondition_failed: temporary_state_directory_unavailable
```

普通沙箱权限和受限提升权限都无法创建新的系统临时 state 目录。两次均未启动 preflight，全部网络/模型/connector 计数为 0。这是 Codex 文件权限边界，不是代码、配置或 connector 结论；不再从 Codex 内重复该路径。

下一步由项目所有者在本机 **PowerShell** 中手动运行一次零网络 preflight。不要在 `cmd.exe` 中运行以下命令。

### 手动命令

```powershell
cd D:\VsCodeProject\GuanDan

$env:PYTHON_DOTENV_DISABLED = "1"
$state = Join-Path "D:\VsCodeProject" ("BotzoneState-preflight-" + [guid]::NewGuid().ToString("N"))

New-Item -ItemType Directory -Path $state -ErrorAction Stop | Out-Null

& ".\.venv\Scripts\python.exe" -m integrations.botzone `
  --agent deepseek `
  --preflight-only `
  --state-dir $state

$preflightExit = $LASTEXITCODE
$stateCount = @(Get-ChildItem -LiteralPath $state -Force -ErrorAction Stop).Count

"preflight_exit=$preflightExit"
"state_empty=$($stateCount -eq 0)"

if ($stateCount -eq 0) {
    Remove-Item -LiteralPath $state -ErrorAction Stop
} else {
    "state_cleanup_skipped_nonempty"
}
```

### 安全边界

- 该命令使用项目 `.venv` 并在 dotenv 解析前禁用 `.env` 加载。
- state 位于仓库外且使用全新随机目录；不删除任何已有目录，也不递归删除。
- `--preflight-only` 不构造 transport，不启动 connector，不发送 Botzone 或 DeepSeek 请求。
- 不要输出或粘贴 URL、API key、完整环境变量、state 实际随机路径或其他配置值。
- 不要添加其他参数、提高 timeout、重试或在失败后直接运行 live。

### 项目所有者只需回复

请只回复固定输出与观察结果：

```text
preflight stdout：<固定单行输出>
preflight_exit：<整数>
state_empty：<True|False>
stderr：<空|非空，不粘贴敏感正文>
```

### 判定

只有 stdout 为单行 `preflight_ready`、exit=0、state_empty=True、stderr 空，才能判定：

```text
botzone_long_poll_deepseek_local_preflight_ready
```

通过后再提出 L5-A2b13 的完整 live 授权问题；本步骤不联网，也不延续旧授权。若失败，只报告现有固定 preflight 类别，不再创建诊断载体或自行重试。
