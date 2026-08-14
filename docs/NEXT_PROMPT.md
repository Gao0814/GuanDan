# 下一步实施提示词

## Step L5-A2b12e：使用既有 state/audit 资源完成宿主机零网络 preflight

L5-A2b12d 已由项目所有者完成：

```text
audit_exists=True
audit_empty=True
audit_probe=passed
```

既有 `D:\VsCodeProject\BotzoneState` 也已确认存在且为空。state 与 audit 两个仓库外宿主机资源现已准备好；不再创建或删除目录。

本步骤由项目所有者在本机 **PowerShell** 中运行一次现有 DeepSeek connector preflight。preflight 不使用 audit 文件，但执行前后都要确认两个目录保持为空。

### 手动命令

```powershell
cd D:\VsCodeProject\GuanDan

$state = "D:\VsCodeProject\BotzoneState"
$auditDir = "D:\VsCodeProject\BotzoneAudit"

foreach ($path in @($state, $auditDir)) {
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "required_directory_missing"
    }
    if (@(Get-ChildItem -LiteralPath $path -Force -ErrorAction Stop).Count -ne 0) {
        throw "required_directory_not_empty"
    }
}

$env:PYTHON_DOTENV_DISABLED = "1"

& ".\.venv\Scripts\python.exe" -m integrations.botzone `
  --agent deepseek `
  --preflight-only `
  --state-dir $state

$preflightExit = $LASTEXITCODE
$stateEmpty = @(Get-ChildItem -LiteralPath $state -Force -ErrorAction Stop).Count -eq 0
$auditEmpty = @(Get-ChildItem -LiteralPath $auditDir -Force -ErrorAction Stop).Count -eq 0

"preflight_exit=$preflightExit"
"state_empty=$stateEmpty"
"audit_empty=$auditEmpty"
```

### 固定边界

- 仅执行一次，不修改代码、不重复 80/587 测试。
- 使用项目 `.venv`，并在 dotenv 文件解析前禁用 `.env` 加载。
- `--preflight-only` 不构造 transport，不启动 connector，不调用 runmatch，不发送 Botzone/DeepSeek 请求。
- 不创建 audit 文件，不删除 state/audit 目录，不输出 URL、key、路径以外的配置值。
- 30 秒内未自行返回则终止并报告 invalid；不得重试或直接 live。

### 只需回复

```text
preflight stdout：<固定单行输出>
preflight_exit：<整数>
state_empty：<True|False>
audit_empty：<True|False>
stderr：<空|非空，不粘贴敏感正文>
```

### 判定

只有 stdout 为单行 `preflight_ready`、exit=0、state_empty=True、audit_empty=True、stderr 空，才能判定：

```text
botzone_long_poll_deepseek_local_preflight_ready
```

通过后再准备 L5-A2b13 的完整 live 授权问题；本步骤不联网，也不延续旧授权。若失败，只报告现有固定类别，不再创建目录、诊断载体或自行重试。
