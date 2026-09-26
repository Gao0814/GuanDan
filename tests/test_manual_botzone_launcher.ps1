$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$modulePath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/manual_botzone_workspace.psm1'
$launcherPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/run_manual_botzone.ps1'
$commandPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'scripts/run_manual_botzone.cmd'
Import-Module -Name $modulePath -Force -WarningAction SilentlyContinue
$testRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$scratchName = '.manual-launcher-scratch-' + [guid]::NewGuid().ToString('N')
$scratchRoot = Join-Path $testRoot $scratchName
$assertionCount = 0
$testCount = 0

function Assert-ManualTest {
  param([bool]$Condition, [string]$Name)
  if (-not $Condition) { throw "assertion_failed:$Name" }
  $script:assertionCount++
}

function Assert-ManualFailureCode {
  param([scriptblock]$Action, [string]$ExpectedCode, [string]$Name)
  $caught = $null
  try { & $Action } catch { $caught = [string]$_.Exception.Message }
  Assert-ManualTest -Condition ($caught -ceq $ExpectedCode) -Name $Name
}

function New-ManualTestPreflight {
  param([hashtable]$State, [string]$Output = 'preflight_ready', [int]$ExitCode = 0)
  return {
    param([string[]]$Arguments)
    $State.PreflightCalls++
    $State.Events.Add('preflight')
    if ($State.OnPreflight) { & $State.OnPreflight $Arguments }
    return [pscustomobject]@{ ExitCode = $ExitCode; Output = @($Output) }
  }.GetNewClosure()
}

function New-ManualTestProcessProvider {
  param([hashtable]$State)
  return {
    $State.ProcessChecks++
    return @($State.Processes)
  }.GetNewClosure()
}

function New-ManualTestState {
  return @{
    Events = [System.Collections.Generic.List[string]]::new()
    PreflightCalls = 0
    ProcessChecks = 0
    Processes = @()
    OnPreflight = $null
  }
}

function New-ManualTestRoot {
  param([string]$Path)
  [void](New-ManualWorkspaceRoot -WorkspaceRoot $Path -ExpectedRoot $Path)
  return $Path
}

function Add-ManualTestArtifacts {
  param([string]$Root)
  $stateFile = Join-Path (Join-Path $Root 'state') (('a' * 64) + '.json')
  [System.IO.File]::WriteAllText($stateFile, '{}')
  [System.IO.File]::WriteAllText((Join-Path $Root 'audit\completion-audit.json'), '{}')
  [System.IO.File]::WriteAllText((Join-Path $Root 'history.txt'), 'private history fixture')
  [System.IO.File]::WriteAllText((Join-Path $Root 'decision-trace.json'), '{}')
  [System.IO.File]::WriteAllText((Join-Path $Root 'streams\stdout.txt'), '')
  [System.IO.File]::WriteAllText((Join-Path $Root 'streams\stderr.txt'), '')
}

function Invoke-ManualTest {
  param([string]$Name, [scriptblock]$Body)
  & $Body
  $script:testCount++
  Write-Output "PASS $Name"
}

try {
  [void][System.IO.Directory]::CreateDirectory($scratchRoot)
  $scratchAttributes = (Get-Item -LiteralPath $scratchRoot).Attributes
  Assert-ManualTest -Condition ((($scratchAttributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0)) -Name 'scratch_is_ordinary'

  Invoke-ManualTest 'first_creation_and_personal_paths' {
    $root = Join-Path $scratchRoot 'first'
    $state = New-ManualTestState
    $preflight = New-ManualTestPreflight -State $state
    $result = Initialize-ManualBotzoneWorkspace `
      -WorkspaceRoot $root -ExpectedRoot $root `
      -PreflightInvoker $preflight `
      -ProcessProvider (New-ManualTestProcessProvider -State $state) `
      -RecycleInvoker { throw 'unexpected_recycle' }
    Assert-ManualTest -Condition (Test-Path -LiteralPath $result.Root -PathType Container) -Name 'first_root_exists'
    Assert-ManualTest -Condition (Test-Path -LiteralPath (Join-Path $root '.manual-botzone-owner') -PathType Leaf) -Name 'owner_marker_created'
    Assert-ManualTest -Condition ($state.PreflightCalls -eq 1 -and -not $result.PreviousRunRotated) -Name 'first_preflight_once'
    $args = @(Get-ManualBotzoneArguments -WorkspaceRoot $root -RunToken ('b' * 32))
    $joined = $args -join '|'
    Assert-ManualTest -Condition ($args[0] -eq '--agent' -and $args[1] -eq 'deepseek') -Name 'explicit_deepseek'
    $personalPaths = @(
      $result.State, $result.Audit, $result.History, $result.DecisionTrace, $result.Stdout, $result.Stderr
    )
    $allPersonal = $true
    foreach ($path in $personalPaths) {
      if (-not ([System.IO.Path]::GetFullPath($path)).StartsWith($root + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { $allPersonal = $false }
    }
    Assert-ManualTest -Condition ($allPersonal -and $joined.Contains((Join-Path $root 'audit\completion-audit.json')) -and $joined.Contains((Join-Path $root 'decision-trace.json')) -and $joined.Contains((Join-Path $root 'history.txt'))) -Name 'outputs_under_personal_root'
    Assert-ManualTest -Condition (-not $joined.Contains('BotzoneWorkspace') -and -not $joined.Contains('--url') -and -not $joined.Contains('--preflight-only')) -Name 'no_codex_root_or_private_config_args'
    $expectedConnectorArguments = @(
      '--agent', 'deepseek',
      '--state-dir', (Join-Path $root 'state'),
      '--max-cycles', '80',
      '--max-wall-seconds', '1800',
      '--stop-after-finished', '1',
      '--audit-file', (Join-Path $root 'audit\completion-audit.json'),
      '--history-file', (Join-Path $root 'history.txt'),
      '--decision-trace-file', (Join-Path $root 'decision-trace.json'),
      '--run-token', ('b' * 32),
      '--stage-trace'
    )
    Assert-ManualTest -Condition (($args -join '|') -ceq ($expectedConnectorArguments -join '|')) -Name 'connector_arguments_match_shared_profile_except_paths'
    Assert-ManualTest -Condition (-not $joined.Contains('--timeout-seconds') -and -not $joined.Contains('--preflight-only')) -Name 'connector_uses_default_timeout_and_not_preflight'
    Assert-ManualTest -Condition ((@(Get-ManualBotzoneArguments -WorkspaceRoot $root -PreflightOnly) -join '|').Contains('--preflight-only')) -Name 'preflight_is_separate'
    $preflightArgs = @(Get-ManualBotzoneArguments -WorkspaceRoot $root -PreflightOnly)
    Assert-ManualTest -Condition ($preflightArgs[3] -ceq (Join-Path $root 'state')) -Name 'preflight_state_is_personal'
  }

  Invoke-ManualTest 'second_run_preflights_then_recycles_and_rebuilds' {
    $root = Join-Path $scratchRoot 'second'
    [void](New-ManualTestRoot -Path $root)
    Add-ManualTestArtifacts -Root $root
    $state = New-ManualTestState
    $state.OnPreflight = {
      param($Arguments)
      $state.PreflightSawHistory.Add([System.IO.File]::Exists((Join-Path $root 'history.txt')))
      if (($Arguments -join '|') -notmatch '--preflight-only') { throw 'wrong_preflight_args' }
    }.GetNewClosure()
    $state.PreflightSawHistory = [System.Collections.Generic.List[bool]]::new()
    $preflight = New-ManualTestPreflight -State $state
    $recycle = {
      param([string]$Path)
      $state.Events.Add('recycle')
      [System.IO.Directory]::Delete($Path, $true)
    }.GetNewClosure()
    $result = Initialize-ManualBotzoneWorkspace `
      -WorkspaceRoot $root -ExpectedRoot $root `
      -PreflightInvoker $preflight `
      -ProcessProvider (New-ManualTestProcessProvider -State $state) `
      -RecycleInvoker $recycle
    Assert-ManualTest -Condition ($result.PreviousRunRotated -and $state.Events[0] -eq 'preflight' -and $state.Events[1] -eq 'recycle') -Name 'preflight_before_recycle'
    Assert-ManualTest -Condition ($state.PreflightCalls -eq 1 -and $state.PreflightSawHistory.Count -eq 1 -and $state.PreflightSawHistory[0]) -Name 'old_evidence_checked_before_recycle'
    Assert-ManualTest -Condition (-not (Test-Path -LiteralPath (Join-Path $root 'history.txt'))) -Name 'old_evidence_not_carried_forward'
    Assert-ManualTest -Condition (Test-Path -LiteralPath (Join-Path $root '.manual-botzone-owner') -PathType Leaf) -Name 'new_marker_after_recycle'
  }

  Invoke-ManualTest 'missing_marker_fails_closed' {
    $root = Join-Path $scratchRoot 'no-marker'
    foreach ($name in @('state', 'audit', 'streams')) { [void][System.IO.Directory]::CreateDirectory((Join-Path $root $name)) }
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'workspace_inventory_incomplete' -Name 'missing_owner_marker'
    Assert-ManualTest -Condition ($state.PreflightCalls -eq 0 -and (Test-Path -LiteralPath $root)) -Name 'marker_failure_preserves_root'
  }

  Invoke-ManualTest 'invalid_marker_fails_closed' {
    $root = Join-Path $scratchRoot 'invalid-marker'
    [void](New-ManualTestRoot -Path $root)
    $marker = Join-Path $root '.manual-botzone-owner'
    [System.IO.File]::WriteAllText($marker, 'unrecognized owner')
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'workspace_owner_marker_invalid' -Name 'invalid_owner_marker'
    Assert-ManualTest -Condition ([System.IO.File]::ReadAllText($marker) -ceq 'unrecognized owner' -and $state.PreflightCalls -eq 0) -Name 'invalid_marker_preserved'
  }

  Invoke-ManualTest 'unknown_file_fails_closed' {
    $root = Join-Path $scratchRoot 'unknown'
    [void](New-ManualTestRoot -Path $root)
    [System.IO.File]::WriteAllText((Join-Path $root 'unexpected.bin'), 'x')
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'workspace_inventory_unexpected' -Name 'unknown_file_rejected'
    Assert-ManualTest -Condition ($state.PreflightCalls -eq 0 -and (Test-Path -LiteralPath (Join-Path $root 'unexpected.bin'))) -Name 'unknown_file_preserved'
  }

  Invoke-ManualTest 'reparse_point_fails_closed' {
    $root = Join-Path $scratchRoot 'linked-entry'
    [void](New-ManualTestRoot -Path $root)
    $target = Join-Path $scratchRoot 'link-target'
    [void][System.IO.Directory]::CreateDirectory($target)
    $junctionPath = Join-Path $root 'state\linked'
    [void](New-Item -ItemType Junction -Path $junctionPath -Target $target -ErrorAction Stop)
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'workspace_inventory_unexpected' -Name 'junction_rejected'
    Assert-ManualTest -Condition (Test-Path -LiteralPath $junctionPath) -Name 'junction_preserved'
  }

  Invoke-ManualTest 'path_drift_fails_closed' {
    $expected = Join-Path $scratchRoot 'expected'
    $drifted = Join-Path $scratchRoot 'drifted'
    [void][System.IO.Directory]::CreateDirectory($drifted)
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $drifted -ExpectedRoot $expected `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'workspace_path_mismatch' -Name 'path_mismatch'
    Assert-ManualTest -Condition ($state.PreflightCalls -eq 0 -and -not (Test-Path -LiteralPath $expected)) -Name 'path_failure_has_no_workspace_side_effect'
  }

  Invoke-ManualTest 'recycle_failure_preserves_previous_content' {
    $root = Join-Path $scratchRoot 'recycle-failure'
    [void](New-ManualTestRoot -Path $root)
    $history = Join-Path $root 'history.txt'
    [System.IO.File]::WriteAllText($history, 'keep this evidence')
    $state = New-ManualTestState
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $state) `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { throw 'recycle_denied' }
    } -ExpectedCode 'workspace_recycle_failed' -Name 'recycle_failure_category'
    Assert-ManualTest -Condition ([System.IO.File]::ReadAllText($history) -ceq 'keep this evidence') -Name 'recycle_failure_keeps_old_evidence'
  }

  Invoke-ManualTest 'preflight_failure_preserves_previous_content' {
    $root = Join-Path $scratchRoot 'preflight-failure'
    [void](New-ManualTestRoot -Path $root)
    $history = Join-Path $root 'history.txt'
    [System.IO.File]::WriteAllText($history, 'keep after preflight failure')
    $state = New-ManualTestState
    $failedPreflight = New-ManualTestPreflight -State $state -Output 'private error detail' -ExitCode 2
    $recycleState = [pscustomobject]@{ Called = $false }
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker $failedPreflight `
        -ProcessProvider (New-ManualTestProcessProvider -State $state) `
        -RecycleInvoker { $recycleState.Called = $true }.GetNewClosure()
    } -ExpectedCode 'preflight_failed' -Name 'preflight_failure_category'
    Assert-ManualTest -Condition (-not $recycleState.Called -and [System.IO.File]::ReadAllText($history) -ceq 'keep after preflight failure') -Name 'preflight_failure_keeps_old_evidence'
  }

  Invoke-ManualTest 'running_connector_refused_without_commandline_output' {
    $state = New-ManualTestState
    $state.Processes = @([pscustomobject]@{
      Name = 'python.exe'
      CommandLine = 'python -m integrations.botzone --url https://private.invalid DEEPSEEK_API_KEY=never-print'
    })
    $provider = New-ManualTestProcessProvider -State $state
    $failureCode = $null
    $probeOutput = @(Test-ManualBotzoneConnectorRunning -ProcessProvider $provider)
    try { Assert-NoManualBotzoneConnector -ProcessProvider $provider | Out-Null }
    catch { $failureCode = [string]$_.Exception.Message }
    Assert-ManualTest -Condition ($probeOutput.Count -eq 1 -and $probeOutput[0] -eq $true) -Name 'process_probe_has_boolean_only'
    Assert-ManualTest -Condition ($failureCode -ceq 'connector_already_running') -Name 'running_connector_rejected'
    $root = Join-Path $scratchRoot 'active-process'
    $activeState = New-ManualTestState
    $activeState.Processes = $state.Processes
    Assert-ManualFailureCode -Action {
      Initialize-ManualBotzoneWorkspace -WorkspaceRoot $root -ExpectedRoot $root `
        -PreflightInvoker (New-ManualTestPreflight -State $activeState) `
        -ProcessProvider (New-ManualTestProcessProvider -State $activeState) `
        -RecycleInvoker { throw 'must_not_recycle' }
    } -ExpectedCode 'connector_already_running' -Name 'active_connector_blocks_initialization'
    Assert-ManualTest -Condition ($activeState.PreflightCalls -eq 0 -and -not (Test-Path -LiteralPath $root)) -Name 'active_connector_has_no_workspace_side_effect'
  }

  Invoke-ManualTest 'preflight_failure_and_private_values_are_not_echoed' {
    $fakeSensitive = 'https://private.invalid?key=DO_NOT_PRINT DEEPSEEK_API_KEY=DO_NOT_PRINT'
    $captured = @(& {
      try {
        Invoke-ManualBotzonePreflight -Arguments @('--agent', 'deepseek') -Invoker {
          param($Arguments)
          [pscustomobject]@{ ExitCode = 2; Output = @($fakeSensitive) }
        } | Out-Null
      } catch { Write-Output $_.Exception.Message }
    })
    Assert-ManualTest -Condition ($captured.Count -eq 1 -and $captured[0] -ceq 'preflight_failed') -Name 'fixed_preflight_error'
    Assert-ManualTest -Condition (($captured -join '') -notmatch 'private\.invalid|DO_NOT_PRINT') -Name 'private_preflight_text_not_echoed'
  }

  Invoke-ManualTest 'connector_retry_override_is_process_scoped_and_restored' {
    $envName = 'DEEPSEEK_MAX_RETRIES'
    $oldValue = [System.Environment]::GetEnvironmentVariable($envName, [System.EnvironmentVariableTarget]::Process)
    try {
      [System.Environment]::SetEnvironmentVariable($envName, '17', [System.EnvironmentVariableTarget]::Process)
      $observed = Invoke-ManualBotzoneConnectorProcess -Invoker {
        $during = [System.Environment]::GetEnvironmentVariable('DEEPSEEK_MAX_RETRIES', [System.EnvironmentVariableTarget]::Process)
        return "during=$during"
      }
      Assert-ManualTest -Condition ($observed -ceq 'during=0') -Name 'retry_zero_during_child'
      Assert-ManualTest -Condition ([System.Environment]::GetEnvironmentVariable($envName, [System.EnvironmentVariableTarget]::Process) -ceq '17') -Name 'retry_setting_restored'
    } finally {
      [System.Environment]::SetEnvironmentVariable($envName, $oldValue, [System.EnvironmentVariableTarget]::Process)
    }
  }

  Invoke-ManualTest 'connector_exit_categories_are_fixed_and_low_risk' {
    $expectedCategories = @{
      0 = 'finished'
      2 = 'configuration_error'
      4 = 'transport_error'
      5 = 'protocol_error'
      6 = 'limit_reached'
      130 = 'interrupted'
      99 = 'other_exit'
    }
    foreach ($code in $expectedCategories.Keys) {
      Assert-ManualTest -Condition ((Get-ManualBotzoneExitCategory -ExitCode $code) -ceq $expectedCategories[$code]) -Name 'fixed_exit_category'
    }
    $launcherSource = [System.IO.File]::ReadAllText($launcherPath)
    Assert-ManualTest -Condition ($launcherSource.Contains('Get-ManualBotzoneExitCategory -ExitCode $exitCode') -and $launcherSource.Contains('exit=$exitCode') -and $launcherSource.Contains('category=$exitCategory')) -Name 'launcher_prints_fixed_exit_code_and_category'
  }

  Invoke-ManualTest 'launcher_powershell_syntax' {
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($launcherPath, [ref]$tokens, [ref]$parseErrors)
    Assert-ManualTest -Condition ($parseErrors.Count -eq 0) -Name 'launcher_parses'
    $tokens = $null
    $parseErrors = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($modulePath, [ref]$tokens, [ref]$parseErrors)
    Assert-ManualTest -Condition ($parseErrors.Count -eq 0) -Name 'module_parses'

    $windowsPowerShell = Get-Command -Name 'powershell.exe' -CommandType Application -ErrorAction Stop
    $quotedLauncher = "'" + $launcherPath.Replace("'", "''") + "'"
    $quotedModule = "'" + $modulePath.Replace("'", "''") + "'"
    $parseProbe = '$files=@(' + $quotedLauncher + ',' + $quotedModule + '); foreach ($file in $files) { ' +
      '$parseTokens=$null; $parseErrors=$null; [void][System.Management.Automation.Language.Parser]::ParseFile($file,[ref]$parseTokens,[ref]$parseErrors); ' +
      'if ($parseErrors.Count -ne 0) { exit 11 } }; Write-Output ''PS51_PARSE_OK'''
    $windowsOutput = @(& $windowsPowerShell.Source -NoLogo -NoProfile -ExecutionPolicy Bypass -Command $parseProbe 2>$null)
    $windowsExitCode = $LASTEXITCODE
    Assert-ManualTest -Condition ($windowsExitCode -eq 0 -and ($windowsOutput -join "`n").Contains('PS51_PARSE_OK')) -Name 'windows_powershell_51_parses_files'
  }

  Invoke-ManualTest 'cmd_entry_uses_process_bypass_and_propagates_exit' {
    $compatRoot = Join-Path $scratchRoot 'cmd-entry'
    $compatScripts = Join-Path $compatRoot 'scripts'
    [void][System.IO.Directory]::CreateDirectory($compatScripts)
    $testCommand = Join-Path $compatScripts 'run_manual_botzone.cmd'
    $testStub = Join-Path $compatScripts 'run_manual_botzone.ps1'
    Copy-Item -LiteralPath $commandPath -Destination $testCommand
    $stubText = "Write-Output 'UNSIGNED_TEST_STUB_RAN'`r`nif (`$args.Count -ne 0) { exit 38 }`r`nexit 37`r`n"
    [System.IO.File]::WriteAllText($testStub, $stubText, [System.Text.Encoding]::ASCII)

    $parentProcessPolicyBefore = [string](Get-ExecutionPolicy -Scope Process)
    $machinePolicyBefore = [string](Get-ExecutionPolicy -Scope LocalMachine)
    $entryText = [System.IO.File]::ReadAllText($testCommand)
    Assert-ManualTest -Condition ($entryText.Contains('-ExecutionPolicy Bypass') -and $entryText.Contains('-File "%~dp0run_manual_botzone.ps1"') -and -not $entryText.Contains('Set-ExecutionPolicy')) -Name 'cmd_uses_child_only_bypass_for_fixed_script'
    $commandLine = '""' + $testCommand + '" --no-pause"'
    $childOutput = @(& $env:ComSpec /d /c $commandLine 2>&1)
    $childExitCode = $LASTEXITCODE
    $safeOutput = $childOutput -join "`n"
    Assert-ManualTest -Condition ($childExitCode -eq 37) -Name 'cmd_returns_child_exit_code'
    Assert-ManualTest -Condition $safeOutput.Contains('UNSIGNED_TEST_STUB_RAN') -Name 'cmd_runs_unsigned_scratch_script'
    Assert-ManualTest -Condition (-not $safeOutput.Contains('Press any key')) -Name 'no_pause_switch_supports_automation'
    $defaultCommandLine = '""' + $testCommand + '" < NUL"'
    $defaultOutput = @(& $env:ComSpec /d /c $defaultCommandLine 2>&1)
    $defaultExitCode = $LASTEXITCODE
    $defaultSafeOutput = $defaultOutput -join "`n"
    Assert-ManualTest -Condition ($defaultExitCode -eq 37 -and $defaultSafeOutput.Contains('Press any key to close this window')) -Name 'double_click_mode_shows_result_and_waits'
    Assert-ManualTest -Condition ([string](Get-ExecutionPolicy -Scope Process) -ceq $parentProcessPolicyBefore -and [string](Get-ExecutionPolicy -Scope LocalMachine) -ceq $machinePolicyBefore) -Name 'cmd_does_not_change_parent_or_machine_policy'
  }

  Invoke-ManualTest 'synthetic_endpoint_and_proxy_reach_python_for_preflight_and_run' {
    $compatRoot = Join-Path $scratchRoot 'env-chain'
    $compatScripts = Join-Path $compatRoot 'scripts'
    [void][System.IO.Directory]::CreateDirectory($compatScripts)
    $testCommand = Join-Path $compatScripts 'run_manual_botzone.cmd'
    $testStub = Join-Path $compatScripts 'run_manual_botzone.ps1'
    $testHarness = Join-Path $compatRoot 'invoke-synthetic.cmd'
    $probePath = Join-Path $compatScripts 'probe.py'
    $resultPath = Join-Path $compatScripts 'probe-results.jsonl'
    $fakeWorkspace = Join-Path $compatRoot 'fake-workspace'
    $fakeState = Join-Path $fakeWorkspace 'state'
    $fakeStreams = Join-Path $fakeWorkspace 'streams'
    $fakeStdout = Join-Path $fakeStreams 'stdout.txt'
    $fakeStderr = Join-Path $fakeStreams 'stderr.txt'
    Copy-Item -LiteralPath $commandPath -Destination $testCommand
    [void][System.IO.Directory]::CreateDirectory($fakeStreams)

    $projectPython = Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $projectPython -PathType Leaf) {
      $testPython = [System.IO.Path]::GetFullPath($projectPython)
    } else {
      $pythonCommand = Get-Command -Name 'python' -CommandType Application -ErrorAction Stop
      $testPython = $pythonCommand.Source
    }

    $probeText = @'
import json
import os
import sys

mode = sys.argv[1] if len(sys.argv) > 1 else "invalid"
args = sys.argv[2:]
expected_environment = {
    "BOTZONE_LOCAL_AI_URL": "https://synthetic.botzone.invalid/poll",
    "HTTP_PROXY": "http://127.0.0.1:18765",
    "HTTPS_PROXY": "http://127.0.0.1:18765",
    "ALL_PROXY": "socks5://127.0.0.1:18766",
    "NO_PROXY": "synthetic.botzone.invalid",
}
environment_match = all(os.environ.get(key) == value for key, value in expected_environment.items())
cwd_match = os.getcwd() == os.environ.get("MANUAL_LAUNCHER_EXPECTED_CWD")
python_match = os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(os.path.abspath(os.environ.get("MANUAL_LAUNCHER_EXPECTED_PYTHON", "")))
retry_expected = "0" if mode == "connector" else "17"
retry_match = os.environ.get("DEEPSEEK_MAX_RETRIES") == retry_expected
state_dir = os.environ.get("MANUAL_LAUNCHER_EXPECTED_STATE_DIR")

def value(option):
    try:
        return args[args.index(option) + 1]
    except (ValueError, IndexError):
        return None

if mode == "preflight":
    checks = {
        "agent": args[:2] == ["--agent", "deepseek"],
        "state": value("--state-dir") == state_dir,
        "preflight": args.count("--preflight-only") == 1,
        "runtime_only_absent": all(option not in args for option in ("--timeout-seconds", "--max-cycles", "--max-wall-seconds", "--audit-file", "--history-file", "--decision-trace-file", "--run-token", "--stage-trace")),
        "exact": args == ["--agent", "deepseek", "--state-dir", state_dir, "--preflight-only"],
    }
    result = "preflight_ready"
elif mode == "connector":
    root = os.environ.get("MANUAL_LAUNCHER_EXPECTED_WORKSPACE")
    run_token = value("--run-token")
    expected_arguments = [
        "--agent", "deepseek",
        "--state-dir", state_dir,
        "--max-cycles", "80",
        "--max-wall-seconds", "1800",
        "--stop-after-finished", "1",
        "--audit-file", os.path.join(root, "audit", "completion-audit.json"),
        "--history-file", os.path.join(root, "history.txt"),
        "--decision-trace-file", os.path.join(root, "decision-trace.json"),
        "--run-token", run_token,
        "--stage-trace",
    ]
    checks = {
        "agent": value("--agent") == "deepseek",
        "state": value("--state-dir") == state_dir,
        "timeout_default": "--timeout-seconds" not in args,
        "cycles": value("--max-cycles") == "80",
        "wall": value("--max-wall-seconds") == "1800",
        "stop": value("--stop-after-finished") == "1",
        "paths": value("--audit-file") == os.path.join(root, "audit", "completion-audit.json") and value("--history-file") == os.path.join(root, "history.txt") and value("--decision-trace-file") == os.path.join(root, "decision-trace.json"),
        "token_shape": run_token is not None and len(run_token) == 32 and all(character in "0123456789abcdef" for character in run_token),
        "preflight_absent": "--preflight-only" not in args,
        "stage_trace_enabled": args.count("--stage-trace") == 1,
        "exact": args == expected_arguments,
    }
    result = "fake_connector_done"
elif mode == "after":
    checks = {"empty": not args}
    result = "post_connector_done"
else:
    checks = {"invalid_mode": False}
    result = "invalid_probe_mode"

record = {
    "mode": mode if mode in {"preflight", "connector", "after"} else "invalid",
    "environment_match": bool(environment_match),
    "cwd_match": bool(cwd_match),
    "python_match": bool(python_match),
    "retry_match": bool(retry_match),
    "argument_checks": checks,
}
with open(os.environ["MANUAL_LAUNCHER_PROBE_RESULT"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True) + "\n")
print(result)
if mode == "connector" and "--stage-trace" in args:
    print('BOTZONE_STAGE {"stage":"model_enter","seq":1,"elapsed_ms":0,"outcome":"started"}')
    print('BOTZONE_STAGE {"stage":"model_complete","seq":2,"elapsed_ms":1,"outcome":"success"}')
sys.exit(0 if environment_match and cwd_match and python_match and retry_match and all(checks.values()) else 23)
'@
    [System.IO.File]::WriteAllText($probePath, $probeText, [System.Text.Encoding]::UTF8)

    $modulePathLiteral = "'" + $modulePath.Replace("'", "''") + "'"
    $pythonPathLiteral = "'" + $testPython.Replace("'", "''") + "'"
    $probePathLiteral = "'" + $probePath.Replace("'", "''") + "'"
    $workspaceLiteral = "'" + $fakeWorkspace.Replace("'", "''") + "'"
    $fakePowerShellText = @"
Import-Module $modulePathLiteral -Force -ErrorAction Stop
`$pythonPath = $pythonPathLiteral
`$probe = $probePathLiteral
`$workspace = $workspaceLiteral
`$stateDirectory = Join-Path `$workspace 'state'
`$stdoutPath = Join-Path `$workspace 'streams\stdout.txt'
`$stderrPath = Join-Path `$workspace 'streams\stderr.txt'
`$preflightArguments = @(Get-ManualBotzoneArguments -WorkspaceRoot `$workspace -PreflightOnly)
`$connectorArguments = @(Get-ManualBotzoneArguments -WorkspaceRoot `$workspace -RunToken ('a' * 32))
`$preflightInvoker = {
  param([string[]]`$Arguments)
  `$output = @(& `$pythonPath -B `$probe preflight @Arguments)
  `$code = `$LASTEXITCODE
  return [pscustomobject]@{ ExitCode = `$code; Output = `$output }
}.GetNewClosure()
[void](Invoke-ManualBotzonePreflight -Arguments `$preflightArguments -Invoker `$preflightInvoker)
`$connectorInvoker = {
  `$output = @(& `$pythonPath -B `$probe connector @connectorArguments 1> `$stdoutPath 2> `$stderrPath)
  return `$LASTEXITCODE
}.GetNewClosure()
`$connectorExit = Invoke-ManualBotzoneConnectorProcess -Invoker `$connectorInvoker
if (`$connectorExit -ne 0) { exit 41 }
`$afterExit = & `$pythonPath -B `$probe after
if (`$LASTEXITCODE -ne 0) { exit 42 }
exit 0
"@
    [System.IO.File]::WriteAllText($testStub, $fakePowerShellText, [System.Text.Encoding]::ASCII)

    $expectedCwd = [System.IO.Path]::GetFullPath((Get-Location).Path)
    $harnessText = @"
@echo off
setlocal
set "BOTZONE_LOCAL_AI_URL=https://synthetic.botzone.invalid/poll"
set "HTTP_PROXY=http://127.0.0.1:18765"
set "HTTPS_PROXY=http://127.0.0.1:18765"
set "ALL_PROXY=socks5://127.0.0.1:18766"
set "NO_PROXY=synthetic.botzone.invalid"
set "DEEPSEEK_MAX_RETRIES=17"
set "MANUAL_LAUNCHER_EXPECTED_CWD=$expectedCwd"
set "MANUAL_LAUNCHER_EXPECTED_PYTHON=$testPython"
set "MANUAL_LAUNCHER_EXPECTED_STATE_DIR=$fakeState"
set "MANUAL_LAUNCHER_EXPECTED_WORKSPACE=$fakeWorkspace"
set "MANUAL_LAUNCHER_PROBE_RESULT=$resultPath"
call "$testCommand" --no-pause
set "_probe_exit=%ERRORLEVEL%"
endlocal & exit /b %_probe_exit%
"@
    [System.IO.File]::WriteAllText($testHarness, $harnessText, [System.Text.Encoding]::ASCII)

    $childOutput = @(& $env:ComSpec /d /c ('""' + $testHarness + '""') 2>&1)
    $childExitCode = $LASTEXITCODE
    $safeOutput = $childOutput -join "`n"
    $records = @()
    if (Test-Path -LiteralPath $resultPath -PathType Leaf) {
      $records = @(Get-Content -LiteralPath $resultPath | ForEach-Object { ConvertFrom-Json -InputObject $_ })
    }
    $capturedStageOutput = if (Test-Path -LiteralPath $fakeStdout -PathType Leaf) { [System.IO.File]::ReadAllText($fakeStdout) } else { '' }
    $productionLauncherSource = [System.IO.File]::ReadAllText($launcherPath)
    $productionModuleSource = [System.IO.File]::ReadAllText($modulePath)
    $preflightInvokeIndex = $productionLauncherSource.IndexOf('& $pythonPath -B -m integrations.botzone @Arguments 2>$null', [System.StringComparison]::Ordinal)
    $connectorInvokeIndex = $productionLauncherSource.IndexOf('& $pythonPath -B -m integrations.botzone @connectorArguments 1> $paths.Stdout 2> $paths.Stderr', [System.StringComparison]::Ordinal)
    $repositoryPushIndex = $productionLauncherSource.IndexOf('Push-Location -LiteralPath $repositoryRoot', [System.StringComparison]::Ordinal)
    $preflightArgsIndex = $productionModuleSource.IndexOf('$preflightArgs = @(Get-ManualBotzoneArguments -WorkspaceRoot $root -PreflightOnly)', [System.StringComparison]::Ordinal)
    $preflightInvokerIndex = $productionLauncherSource.IndexOf('-PreflightInvoker $preflightInvoker', [System.StringComparison]::Ordinal)
    $runtimeArgsIndex = $productionLauncherSource.IndexOf('$connectorArguments = @(Get-ManualBotzoneArguments -WorkspaceRoot $expectedWorkspace -RunToken $runToken)', [System.StringComparison]::Ordinal)
    Assert-ManualTest -Condition ($childExitCode -eq 0) -Name 'synthetic_chain_exits_successfully'
    Assert-ManualTest -Condition ($records.Count -eq 3 -and $records[0].mode -ceq 'preflight' -and $records[1].mode -ceq 'connector' -and $records[2].mode -ceq 'after') -Name 'synthetic_preflight_run_order'
    Assert-ManualTest -Condition (@($records | Where-Object { -not $_.environment_match -or -not $_.cwd_match }).Count -eq 0) -Name 'synthetic_url_proxy_and_cwd_reach_python'
    Assert-ManualTest -Condition (@($records | Where-Object { -not $_.python_match }).Count -eq 0) -Name 'same_python_executable_reaches_each_phase'
    Assert-ManualTest -Condition ($records[0].argument_checks.exact) -Name 'preflight_arguments_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.agent) -Name 'connector_agent_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.state) -Name 'connector_state_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.timeout_default) -Name 'connector_default_timeout_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.cycles) -Name 'connector_cycles_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.wall) -Name 'connector_wall_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.stop) -Name 'connector_stop_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.paths) -Name 'connector_paths_argument_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.token_shape) -Name 'connector_run_token_argument_shape_match'
    Assert-ManualTest -Condition ($records[1].argument_checks.preflight_absent) -Name 'connector_preflight_switch_absent'
    Assert-ManualTest -Condition ($records[1].argument_checks.stage_trace_enabled -and $records[0].argument_checks.runtime_only_absent) -Name 'stage_trace_is_runtime_opt_in_only'
    Assert-ManualTest -Condition ($records[1].argument_checks.exact) -Name 'connector_arguments_exact_and_ordered'
    Assert-ManualTest -Condition ($capturedStageOutput.Contains('BOTZONE_STAGE ') -and $capturedStageOutput.Contains('"stage":"model_enter"') -and $capturedStageOutput.Contains('"stage":"model_complete"')) -Name 'redirected_stage_trace_is_visible_in_personal_stdout'
    Assert-ManualTest -Condition ($capturedStageOutput -notmatch 'synthetic\.botzone|127\.0\.0\.1|18765|18766|socks5|credential|prompt|action_id') -Name 'redirected_stage_trace_contains_no_private_or_decision_fields'
    Assert-ManualTest -Condition ($records[2].argument_checks.empty) -Name 'post_probe_arguments_match'
    Assert-ManualTest -Condition ($records[0].retry_match -and $records[1].retry_match -and $records[2].retry_match) -Name 'retry_override_only_wraps_connector_process'
    Assert-ManualTest -Condition ($safeOutput -notmatch 'synthetic\.botzone|127\.0\.0\.1|18765|18766|socks5') -Name 'synthetic_private_values_not_echoed'
    Assert-ManualTest -Condition ($repositoryPushIndex -ge 0 -and $preflightInvokeIndex -gt $repositoryPushIndex -and $connectorInvokeIndex -gt $repositoryPushIndex) -Name 'production_phases_share_repository_working_directory'
    Assert-ManualTest -Condition ($preflightArgsIndex -ge 0 -and $preflightInvokerIndex -ge 0 -and $runtimeArgsIndex -ge 0) -Name 'production_builds_distinct_preflight_and_runtime_arguments'
  }

  Write-Output "SUMMARY tests=$testCount assertions=$assertionCount"
} catch {
  Write-Output "FAIL $($_.Exception.Message)"
  exit 1
} finally {
  if (Test-Path -LiteralPath $scratchRoot) {
    $junctionPath = Join-Path $scratchRoot 'linked-entry\state\linked'
    if (Test-Path -LiteralPath $junctionPath) {
      $junctionItem = Get-Item -LiteralPath $junctionPath -Force
      if (($junctionItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        [System.IO.Directory]::Delete($junctionPath, $false)
      }
    }
    $scratchItem = Get-Item -LiteralPath $scratchRoot -Force
    if ($scratchItem.PSIsContainer -and (($scratchItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -eq 0) -and
        [System.IO.Path]::GetFullPath($scratchItem.FullName).StartsWith($testRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -and
        $scratchItem.Name -ceq $scratchName) {
      [System.IO.Directory]::Delete($scratchRoot, $true)
    }
  }
  Remove-Module -Name manual_botzone_workspace -ErrorAction SilentlyContinue
}
