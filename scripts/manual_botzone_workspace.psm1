$script:ManualWorkspaceMarkerName = '.manual-botzone-owner'
$script:ManualWorkspaceMarkerText = "GuanDanManualWorkspace`nowner=project-owner`nschema=1`n"
$script:ManualStateFilePattern = '^[0-9a-f]{64}\.json$'

function ConvertTo-ManualWorkspaceFullPath {
  param([Parameter(Mandatory = $true)][string]$Path)

  try {
    $fullPath = [System.IO.Path]::GetFullPath($Path)
  } catch {
    throw 'workspace_path_invalid'
  }
  $pathRoot = [System.IO.Path]::GetPathRoot($fullPath)
  if ($fullPath.Length -gt $pathRoot.Length) {
    $fullPath = $fullPath.TrimEnd([char[]]@('\', '/'))
  }
  return $fullPath
}

function Get-ManualWorkspaceEntry {
  param([Parameter(Mandatory = $true)][string]$Path)

  $fullPath = ConvertTo-ManualWorkspaceFullPath -Path $Path
  $parent = [System.IO.Path]::GetDirectoryName($fullPath)
  $leaf = [System.IO.Path]::GetFileName($fullPath)
  if ([string]::IsNullOrWhiteSpace($parent) -or [string]::IsNullOrWhiteSpace($leaf)) {
    throw 'workspace_path_invalid'
  }
  if (-not [System.IO.Directory]::Exists($parent)) {
    return $null
  }
  try {
    $matches = @(Get-ChildItem -LiteralPath $parent -Force -ErrorAction Stop | Where-Object { $_.Name -ieq $leaf })
  } catch {
    throw 'workspace_inventory_unavailable'
  }
  if ($matches.Count -gt 1) {
    throw 'workspace_path_invalid'
  }
  if ($matches.Count -eq 0) {
    return $null
  }
  return $matches[0]
}

function Assert-ManualOrdinaryDirectory {
  param([Parameter(Mandatory = $true)][string]$Path)

  try {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  } catch {
    throw 'workspace_directory_invalid'
  }
  if (-not $item.PSIsContainer -or (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'workspace_directory_invalid'
  }
}

function Assert-ManualOrdinaryFile {
  param([Parameter(Mandatory = $true)][string]$Path)

  try {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
  } catch {
    throw 'workspace_file_invalid'
  }
  if ($item.PSIsContainer -or (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'workspace_file_invalid'
  }
}

function Assert-ManualWorkspacePath {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedRoot
  )

  $actual = ConvertTo-ManualWorkspaceFullPath -Path $WorkspaceRoot
  $expected = ConvertTo-ManualWorkspaceFullPath -Path $ExpectedRoot
  if (-not [string]::Equals($actual, $expected, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'workspace_path_mismatch'
  }
  $parent = [System.IO.Path]::GetDirectoryName($expected)
  try {
    Assert-ManualOrdinaryDirectory -Path $parent
  } catch {
    throw 'workspace_parent_invalid'
  }
  return $expected
}

function Assert-ManualNameSet {
  param(
    [Parameter(Mandatory = $true)][AllowEmptyCollection()][object[]]$Items,
    [Parameter(Mandatory = $true)][string[]]$AllowedNames,
    [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$RequiredNames
  )

  $allowed = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
  foreach ($name in $AllowedNames) { [void]$allowed.Add($name) }
  $actual = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
  foreach ($item in $Items) {
    if (-not $allowed.Contains([string]$item.Name) -or -not $actual.Add([string]$item.Name)) {
      throw 'workspace_inventory_unexpected'
    }
  }
  foreach ($name in $RequiredNames) {
    if (-not $actual.Contains($name)) {
      throw 'workspace_inventory_incomplete'
    }
  }
}

function Assert-ManualWorkspaceInventory {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedRoot
  )

  $root = Assert-ManualWorkspacePath -WorkspaceRoot $WorkspaceRoot -ExpectedRoot $ExpectedRoot
  $rootEntry = Get-ManualWorkspaceEntry -Path $root
  if ($null -eq $rootEntry) { throw 'workspace_missing' }
  if (-not $rootEntry.PSIsContainer -or (($rootEntry.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
    throw 'workspace_root_invalid'
  }

  try {
    $rootItems = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop)
  } catch {
    throw 'workspace_inventory_unavailable'
  }
  $rootAllowed = @($script:ManualWorkspaceMarkerName, 'state', 'audit', 'streams', 'history.txt', 'decision-trace.json')
  $rootRequired = @($script:ManualWorkspaceMarkerName, 'state', 'audit', 'streams')
  Assert-ManualNameSet -Items $rootItems -AllowedNames $rootAllowed -RequiredNames $rootRequired

  $markerPath = Join-Path $root $script:ManualWorkspaceMarkerName
  Assert-ManualOrdinaryFile -Path $markerPath
  $expectedMarker = [System.Text.Encoding]::UTF8.GetBytes($script:ManualWorkspaceMarkerText)
  try {
    $actualMarker = [System.IO.File]::ReadAllBytes($markerPath)
  } catch {
    throw 'workspace_owner_marker_invalid'
  }
  if ([Convert]::ToBase64String($actualMarker) -cne [Convert]::ToBase64String($expectedMarker)) {
    throw 'workspace_owner_marker_invalid'
  }

  foreach ($directoryName in @('state', 'audit', 'streams')) {
    Assert-ManualOrdinaryDirectory -Path (Join-Path $root $directoryName)
  }

  $stateItems = @(Get-ChildItem -LiteralPath (Join-Path $root 'state') -Force -ErrorAction Stop)
  foreach ($item in $stateItems) {
    if ($item.PSIsContainer -or $item.Name -cnotmatch $script:ManualStateFilePattern) {
      throw 'workspace_inventory_unexpected'
    }
    Assert-ManualOrdinaryFile -Path $item.FullName
  }

  $auditItems = @(Get-ChildItem -LiteralPath (Join-Path $root 'audit') -Force -ErrorAction Stop)
  Assert-ManualNameSet -Items $auditItems -AllowedNames @('completion-audit.json') -RequiredNames @()
  foreach ($item in $auditItems) { Assert-ManualOrdinaryFile -Path $item.FullName }

  $streamItems = @(Get-ChildItem -LiteralPath (Join-Path $root 'streams') -Force -ErrorAction Stop)
  Assert-ManualNameSet -Items $streamItems -AllowedNames @('stdout.txt', 'stderr.txt') -RequiredNames @()
  foreach ($item in $streamItems) { Assert-ManualOrdinaryFile -Path $item.FullName }

  foreach ($fileName in @('history.txt', 'decision-trace.json')) {
    $filePath = Join-Path $root $fileName
    $fileEntry = Get-ManualWorkspaceEntry -Path $filePath
    if ($null -ne $fileEntry) { Assert-ManualOrdinaryFile -Path $fileEntry.FullName }
  }
  return $root
}

function New-ManualWorkspaceRoot {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedRoot
  )

  $root = Assert-ManualWorkspacePath -WorkspaceRoot $WorkspaceRoot -ExpectedRoot $ExpectedRoot
  if ($null -ne (Get-ManualWorkspaceEntry -Path $root)) { throw 'workspace_already_exists' }
  try {
    [void][System.IO.Directory]::CreateDirectory($root)
    Assert-ManualOrdinaryDirectory -Path $root
    $rootContents = @(Get-ChildItem -LiteralPath $root -Force -ErrorAction Stop)
    if ($rootContents.Count -ne 0) { throw 'workspace_already_exists' }
    foreach ($directoryName in @('state', 'audit', 'streams')) {
      [void][System.IO.Directory]::CreateDirectory((Join-Path $root $directoryName))
      Assert-ManualOrdinaryDirectory -Path (Join-Path $root $directoryName)
    }
    $markerPath = Join-Path $root $script:ManualWorkspaceMarkerName
    $stream = [System.IO.File]::Open(
      $markerPath,
      [System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,
      [System.IO.FileShare]::None
    )
    try {
      $bytes = [System.Text.Encoding]::UTF8.GetBytes($script:ManualWorkspaceMarkerText)
      $stream.Write($bytes, 0, $bytes.Length)
      $stream.Flush($true)
    } finally {
      $stream.Dispose()
    }
  } catch {
    if ($_.Exception.Message -match '^workspace_[a-z_]+$') { throw }
    throw 'workspace_create_failed'
  }
  return Assert-ManualWorkspaceInventory -WorkspaceRoot $root -ExpectedRoot $ExpectedRoot
}

function Test-ManualBotzoneConnectorRunning {
  param([scriptblock]$ProcessProvider = { Get-CimInstance -ClassName Win32_Process -ErrorAction Stop })

  try {
    $processes = @(& $ProcessProvider)
  } catch {
    throw 'connector_status_unavailable'
  }
  foreach ($process in $processes) {
    $name = [string]$process.Name
    $commandLine = [string]$process.CommandLine
    if ($name -match '(?i)^(python(?:\d+(?:\.\d+)?)?w?|py)(?:\.exe)?$' -and
        $commandLine -match '(?i)(?:\s-m\s+integrations\.botzone\b|integrations[\\/]botzone[\\/]__main__\.py\b)') {
      return $true
    }
  }
  return $false
}

function Assert-NoManualBotzoneConnector {
  param([scriptblock]$ProcessProvider = { Get-CimInstance -ClassName Win32_Process -ErrorAction Stop })

  $running = Test-ManualBotzoneConnectorRunning -ProcessProvider $ProcessProvider
  if ($running) { throw 'connector_already_running' }
}

function Get-ManualBotzoneArguments {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [switch]$PreflightOnly,
    [string]$RunToken,
    [string]$DecisionTimeoutSeconds = '119',
    [string]$TableTimeoutSeconds = '120'
  )

  $root = ConvertTo-ManualWorkspaceFullPath -Path $WorkspaceRoot
  $statePath = Join-Path $root 'state'
  $arguments = [System.Collections.Generic.List[string]]::new()
  $arguments.Add('--agent'); $arguments.Add('deepseek')
  $arguments.Add('--state-dir'); $arguments.Add($statePath)
  $arguments.Add('--decision-timeout-seconds'); $arguments.Add($DecisionTimeoutSeconds)
  $arguments.Add('--table-timeout-seconds'); $arguments.Add($TableTimeoutSeconds)
  if ($PreflightOnly) {
    $arguments.Add('--preflight-only')
    return $arguments.ToArray()
  }
  if ($RunToken -notmatch '^[0-9a-f]{32}$') { throw 'run_token_invalid' }
  $arguments.Add('--max-cycles'); $arguments.Add('80')
  $arguments.Add('--max-wall-seconds'); $arguments.Add('1800')
  $arguments.Add('--stop-after-finished'); $arguments.Add('1')
  $arguments.Add('--audit-file'); $arguments.Add((Join-Path $root 'audit\completion-audit.json'))
  $arguments.Add('--history-file'); $arguments.Add((Join-Path $root 'history.txt'))
  $arguments.Add('--decision-trace-file'); $arguments.Add((Join-Path $root 'decision-trace.json'))
  $arguments.Add('--run-token'); $arguments.Add($RunToken)
  $arguments.Add('--stage-trace')
  return $arguments.ToArray()
}

function Get-ManualBotzoneExitCategory {
  param([Parameter(Mandatory = $true)][int]$ExitCode)

  switch ($ExitCode) {
    0 { return 'finished' }
    2 { return 'configuration_error' }
    4 { return 'transport_error' }
    5 { return 'protocol_error' }
    6 { return 'limit_reached' }
    130 { return 'interrupted' }
    default { return 'other_exit' }
  }
}

function Assert-ManualBotzoneFreshOutputs {
  param([Parameter(Mandatory = $true)][string]$WorkspaceRoot)

  $root = ConvertTo-ManualWorkspaceFullPath -Path $WorkspaceRoot
  $targets = @(
    (Join-Path $root 'audit\completion-audit.json'),
    (Join-Path $root 'history.txt'),
    (Join-Path $root 'decision-trace.json'),
    (Join-Path $root 'streams\stdout.txt'),
    (Join-Path $root 'streams\stderr.txt')
  )
  foreach ($target in $targets) {
    if ($null -ne (Get-ManualWorkspaceEntry -Path $target)) { throw 'workspace_outputs_not_fresh' }
  }
}

function Invoke-ManualBotzonePreflight {
  param(
    [Parameter(Mandatory = $true)][string[]]$Arguments,
    [Parameter(Mandatory = $true)][scriptblock]$Invoker
  )

  try {
    $result = & $Invoker $Arguments
    if ($null -eq $result -or $result.ExitCode -ne 0) { throw 'preflight_failed' }
    $outputLines = @($result.Output | ForEach-Object { ([string]$_).Trim() })
    if ($outputLines.Count -ne 1 -or $outputLines[0] -cne 'preflight_ready') { throw 'preflight_failed' }
  } catch {
    throw 'preflight_failed'
  }
  return $true
}

function Invoke-ManualBotzoneRecycle {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [scriptblock]$RecycleInvoker
  )

  $root = ConvertTo-ManualWorkspaceFullPath -Path $WorkspaceRoot
  try {
    if ($null -ne $RecycleInvoker) {
      [void](& $RecycleInvoker $root)
    } else {
      Add-Type -AssemblyName Microsoft.VisualBasic -ErrorAction Stop
      [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory(
        $root,
        [Microsoft.VisualBasic.FileIO.UIOption]::OnlyErrorDialogs,
        [Microsoft.VisualBasic.FileIO.RecycleOption]::SendToRecycleBin
      )
    }
  } catch {
    throw 'workspace_recycle_failed'
  }
  if ($null -ne (Get-ManualWorkspaceEntry -Path $root)) { throw 'workspace_recycle_failed' }
}

function Initialize-ManualBotzoneWorkspace {
  param(
    [Parameter(Mandatory = $true)][string]$WorkspaceRoot,
    [Parameter(Mandatory = $true)][string]$ExpectedRoot,
    [Parameter(Mandatory = $true)][scriptblock]$PreflightInvoker,
    [Parameter(Mandatory = $true)][scriptblock]$ProcessProvider,
    [string]$DecisionTimeoutSeconds = '119',
    [string]$TableTimeoutSeconds = '120',
    [scriptblock]$RecycleInvoker
  )

  $root = Assert-ManualWorkspacePath -WorkspaceRoot $WorkspaceRoot -ExpectedRoot $ExpectedRoot
  Assert-NoManualBotzoneConnector -ProcessProvider $ProcessProvider
  $existingEntry = Get-ManualWorkspaceEntry -Path $root
  $hadPreviousWorkspace = $null -ne $existingEntry
  if ($hadPreviousWorkspace) {
    [void](Assert-ManualWorkspaceInventory -WorkspaceRoot $root -ExpectedRoot $ExpectedRoot)
    $preflightArgs = @(Get-ManualBotzoneArguments -WorkspaceRoot $root -PreflightOnly -DecisionTimeoutSeconds $DecisionTimeoutSeconds -TableTimeoutSeconds $TableTimeoutSeconds)
    [void](Invoke-ManualBotzonePreflight -Arguments $preflightArgs -Invoker $PreflightInvoker)
    Assert-NoManualBotzoneConnector -ProcessProvider $ProcessProvider
    [void](Assert-ManualWorkspaceInventory -WorkspaceRoot $root -ExpectedRoot $ExpectedRoot)
    Invoke-ManualBotzoneRecycle -WorkspaceRoot $root -RecycleInvoker $RecycleInvoker
  }
  [void](New-ManualWorkspaceRoot -WorkspaceRoot $root -ExpectedRoot $ExpectedRoot)
  if (-not $hadPreviousWorkspace) {
    $preflightArgs = @(Get-ManualBotzoneArguments -WorkspaceRoot $root -PreflightOnly -DecisionTimeoutSeconds $DecisionTimeoutSeconds -TableTimeoutSeconds $TableTimeoutSeconds)
    [void](Invoke-ManualBotzonePreflight -Arguments $preflightArgs -Invoker $PreflightInvoker)
  }
  [void](Assert-ManualWorkspaceInventory -WorkspaceRoot $root -ExpectedRoot $ExpectedRoot)
  Assert-ManualBotzoneFreshOutputs -WorkspaceRoot $root
  return [pscustomobject]@{
    Root = $root
    State = Join-Path $root 'state'
    Audit = Join-Path $root 'audit\completion-audit.json'
    History = Join-Path $root 'history.txt'
    DecisionTrace = Join-Path $root 'decision-trace.json'
    Stdout = Join-Path $root 'streams\stdout.txt'
    Stderr = Join-Path $root 'streams\stderr.txt'
    PreviousRunRotated = $hadPreviousWorkspace
  }
}

function Invoke-ManualBotzoneConnectorProcess {
  param([Parameter(Mandatory = $true)][scriptblock]$Invoker)

  $variableName = 'DEEPSEEK_MAX_RETRIES'
  $previousValue = [System.Environment]::GetEnvironmentVariable($variableName, [System.EnvironmentVariableTarget]::Process)
  try {
    [System.Environment]::SetEnvironmentVariable($variableName, '0', [System.EnvironmentVariableTarget]::Process)
    return (& $Invoker)
  } finally {
    [System.Environment]::SetEnvironmentVariable($variableName, $previousValue, [System.EnvironmentVariableTarget]::Process)
  }
}

Export-ModuleMember -Function @(
  'Assert-ManualWorkspaceInventory',
  'Assert-ManualWorkspacePath',
  'Assert-NoManualBotzoneConnector',
  'Assert-ManualBotzoneFreshOutputs',
  'Get-ManualBotzoneArguments',
  'Get-ManualBotzoneExitCategory',
  'Initialize-ManualBotzoneWorkspace',
  'Invoke-ManualBotzoneConnectorProcess',
  'Invoke-ManualBotzonePreflight',
  'New-ManualWorkspaceRoot',
  'Test-ManualBotzoneConnectorRunning'
)
