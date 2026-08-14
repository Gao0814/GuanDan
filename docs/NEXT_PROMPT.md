# 下一步实施提示词

## Step L5-A2b12c：复用既有空 state 目录执行最终零网络 preflight

L5-A2b12b 仍在资源创建阶段停止：

```text
precondition_failed: repository_external_state_directory_unavailable
```

未启动 connector，未发送 runmatch/local-AI/DeepSeek 请求，工作区未修改。至此不再尝试创建任何新的仓库外 state/audit 目录。

项目所有者此前已准备 `D:\VsCodeProject\BotzoneState`。本轮只读复核确认该目录存在且当前为空，未读取文件内容。下一步由项目所有者在本机 **PowerShell** 中直接复用该空目录运行一次最终零网络 preflight；不创建 audit、不删除目录。

### 手动命令

```powershell
cd D:\VsCodeProject\GuanDan

$state = "D:\VsCodeProject\BotzoneState"

if (-not (Test-Path -LiteralPath $state -PathType Container)) {
    throw "existing_state_directory_missing"
}

if (@(Get-ChildItem -LiteralPath $state -Force -ErrorAction Stop).Count -ne 0) {
    throw "existing_state_directory_not_empty"
}

$env:PYTHON_DOTENV_DISABLED = "1"

& ".\.venv\Scripts\python.exe" -m integrations.botzone `
  --agent deepseek `
  --preflight-only `
  --state-dir $state

$preflightExit = $LASTEXITCODE
$stateCount = @(Get-ChildItem -LiteralPath $state -Force -ErrorAction Stop).Count

"preflight_exit=$preflightExit"
"state_empty=$($stateCount -eq 0)"
```

### 固定边界

- 必须在 PowerShell 中运行，不要使用 `cmd.exe`。
- 不创建或删除目录，不使用 audit 文件，不读取仓库 `.env`。
- `--preflight-only` 不构造 transport，不启动 connector，不发送网络请求。
- 不输出 URL、API key、环境变量值或其他敏感配置。
- 只执行一次；不得在失败后改参数、改目录、提高 timeout 或直接 live。

### 只需回复

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

通过后再准备 L5-A2b13 的完整 live 授权问题，不在本步骤联网。若该既有目录仍无法完成 preflight，则本地准入标记 blocked，停止目录尝试并由项目所有者处理宿主机文件权限后再恢复。
