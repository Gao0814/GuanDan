[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$expectedWorkspace = 'D:\VsCodeProject\GuanDanManualWorkspace'
$modulePath = Join-Path $PSScriptRoot 'manual_botzone_workspace.psm1'
$exitCode = 2
$locationPushed = $false

try {
  if (-not (Test-Path -LiteralPath $modulePath -PathType Leaf)) {
    throw 'launcher_module_missing'
  }
  Import-Module -Name $modulePath -Force -ErrorAction Stop

  $projectPython = Join-Path $repositoryRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
    $pythonPath = [System.IO.Path]::GetFullPath($projectPython)
  } else {
    $pythonCommand = Get-Command -Name 'python' -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) { throw 'python_not_found' }
    $pythonPath = $pythonCommand.Source
  }

  Assert-NoManualBotzoneConnector
  Push-Location -LiteralPath $repositoryRoot
  $locationPushed = $true

  # Read-only CLI qualification: argparse exits before configuration or transport setup.
  $helpOutput = @(& $pythonPath -B -m integrations.botzone --help 2>$null)
  $helpExitCode = $LASTEXITCODE
  $helpText = $helpOutput -join "`n"
  $requiredOptions = @(
    '--agent', '--state-dir', '--preflight-only', '--timeout-seconds',
    '--max-cycles', '--max-wall-seconds', '--stop-after-finished',
    '--audit-file', '--history-file', '--decision-trace-file', '--run-token'
  )
  if ($helpExitCode -ne 0) { throw 'cli_help_failed' }
  foreach ($option in $requiredOptions) {
    if ($helpText -notmatch [regex]::Escape($option)) { throw 'cli_arguments_unavailable' }
  }

  $preflightInvoker = {
    param([string[]]$Arguments)
    try {
      $output = @(& $pythonPath -B -m integrations.botzone @Arguments 2>$null)
      $code = $LASTEXITCODE
      return [pscustomobject]@{ ExitCode = $code; Output = $output }
    } catch {
      return [pscustomobject]@{ ExitCode = 1; Output = @() }
    }
  }.GetNewClosure()

  # Existing evidence is not recycled until the private-config preflight succeeds.
  Assert-NoManualBotzoneConnector
  $paths = Initialize-ManualBotzoneWorkspace `
    -WorkspaceRoot $expectedWorkspace `
    -ExpectedRoot $expectedWorkspace `
    -PreflightInvoker $preflightInvoker `
    -ProcessProvider { Get-CimInstance -ClassName Win32_Process -ErrorAction Stop }

  Assert-ManualWorkspaceInventory -WorkspaceRoot $expectedWorkspace -ExpectedRoot $expectedWorkspace | Out-Null
  Assert-ManualBotzoneFreshOutputs -WorkspaceRoot $expectedWorkspace

  foreach ($streamPath in @($paths.Stdout, $paths.Stderr)) {
    $stream = [System.IO.File]::Open(
      $streamPath,
      [System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::None
    )
    $stream.Dispose()
  }

  # Recheck immediately before creating the single foreground connector process.
  Assert-NoManualBotzoneConnector
  Assert-ManualWorkspaceInventory -WorkspaceRoot $expectedWorkspace -ExpectedRoot $expectedWorkspace | Out-Null

  $runToken = [guid]::NewGuid().ToString('N').ToLowerInvariant()
  $connectorArguments = @(Get-ManualBotzoneArguments -WorkspaceRoot $expectedWorkspace -RunToken $runToken)
  Write-Host '零网络配置预检通过。连接器将在前台运行；请等待 Botzone 本地 AI 页面显示“已连接”，再手动建桌并开始。'
  if ($paths.PreviousRunRotated) {
    Write-Host '上次个人证据已移入 Windows 回收站；本次证据将保留在个人 workspace。'
  }

  $connectorExit = Invoke-ManualBotzoneConnectorProcess -Invoker {
    & $pythonPath -B -m integrations.botzone @connectorArguments 1> $paths.Stdout 2> $paths.Stderr
    return $LASTEXITCODE
  }.GetNewClosure()
  if ($null -eq $connectorExit) { throw 'connector_exit_unavailable' }
  $exitCode = [int]$connectorExit
  Write-Host "连接器已退出（exit $exitCode）。本次个人证据保留在 $expectedWorkspace。"
} catch {
  $safeCode = [string]$_.Exception.Message
  if ($safeCode -notmatch '^(workspace|connector|preflight|run_token|launcher|python|cli)_[a-z_]+$') {
    $safeCode = 'launcher_failed'
  }
  Write-Host "启动器已停止（$safeCode）。没有输出连接配置或异常正文。若本次运行有问题，请不要再次启动，以免下一次启动回收当前个人证据。"
  $exitCode = 2
} finally {
  if ($locationPushed) { Pop-Location }
  Remove-Module -Name manual_botzone_workspace -ErrorAction SilentlyContinue
}

exit $exitCode
