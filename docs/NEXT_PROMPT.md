# 下一步实施提示词

## Step L5-A2b12d：项目所有者准备独立 audit 目录

上一轮结果：

```text
precondition_failed: separate_repository_external_audit_path_unavailable
```

既有 `D:\VsCodeProject\BotzoneState` 存在且为空，但无法创建或保证独立仓库外 audit 位置，因此在 connector 首次 GET 前停止。runmatch/local-AI/DeepSeek 请求均为 0。

state 与 audit 不得共用目录：SessionStore 会管理 state 根目录中的 JSON，v5 audit 必须写入独立位置。只读检查确认 `D:\VsCodeProject\BotzoneAudit` 当前不存在。

下一步由项目所有者在本机 **PowerShell** 中创建该固定目录，并执行一次无敏感内容的本地原子写探针。该步骤不运行项目代码、不读取配置、不联网。

### 手动命令

```powershell
$auditDir = "D:\VsCodeProject\BotzoneAudit"

if (Test-Path -LiteralPath $auditDir) {
    throw "audit_directory_already_exists"
}

New-Item -ItemType Directory -Path $auditDir -ErrorAction Stop | Out-Null

$token = [guid]::NewGuid().ToString("N")
$temporary = Join-Path $auditDir ("probe-" + $token + ".tmp")
$final = Join-Path $auditDir ("probe-" + $token + ".json")

[System.IO.File]::WriteAllText($temporary, "{}", [System.Text.Encoding]::UTF8)
Move-Item -LiteralPath $temporary -Destination $final -ErrorAction Stop
Remove-Item -LiteralPath $final -ErrorAction Stop

$auditCount = @(Get-ChildItem -LiteralPath $auditDir -Force -ErrorAction Stop).Count

"audit_exists=$(Test-Path -LiteralPath $auditDir -PathType Container)"
"audit_empty=$($auditCount -eq 0)"
"audit_probe=passed"
```

### 固定边界

- 必须在宿主机 PowerShell 执行，不由 Codex 沙箱创建。
- 只创建固定 audit 目录和随机探针；不递归删除、不触碰已有目录。
- 探针内容固定为 `{}`，不含 URL、key、match、牌、Header 或配置。
- 不运行 preflight、connector、runmatch 或 DeepSeek。
- 若任一步失败，只报告固定失败阶段，不改路径、不重试、不放宽到仓库内。

### 只需回复

```text
audit_exists：<True|False>
audit_empty：<True|False>
audit_probe：<passed|failed>
```

三项分别为 True / True / passed 后，下一步才复核既有 state + audit 两个目录，并运行一次零网络准入；live 仍需新的明确授权。
