#Requires -Version 5.1
[CmdletBinding()]
param([string]$PythonExecutable = (Get-Command python.exe -CommandType Application | Select-Object -First 1).Source)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install-monitoring-auto-deploy.ps1'
$tokens = $null
$parseErrors = $null
[Management.Automation.Language.Parser]::ParseFile($installer, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$testPython = $PythonExecutable
. $installer
$PythonExecutable = $testPython
$nativeProtectPath = ${function:Protect-MonitoringControllerPath}

function Assert-True { param([bool]$Condition, [string]$Message); if (-not $Condition) { throw $Message } }
function Assert-Rejected {
    param([scriptblock]$Action, [string]$Message)
    $rejected = $false
    try { & $Action | Out-Null } catch { $rejected = $true }
    Assert-True $rejected $Message
}

# Only scheduler and ACL system calls are mocked. Git, controller bytes, Python,
# path checks and file-lock/atomic replacement operations run for real.
$script:ExistingTask = $null
$script:RegisteredTasks = @{}
$script:RegistrationCount = 0
$script:ProtectedPaths = @()
function Protect-MonitoringControllerPath { param([string]$Path); $script:ProtectedPaths += $Path }
function Get-ScheduledTask { param($TaskName, $TaskPath, $ErrorAction); return $script:ExistingTask }
function New-ScheduledTaskAction { param($Execute, $Argument, $WorkingDirectory); return [pscustomobject]@{ Execute = $Execute; Arguments = $Argument; WorkingDirectory = $WorkingDirectory } }
function New-ScheduledTaskTrigger { param([switch]$AtLogOn, $User, [switch]$Once, $At, $RepetitionInterval); return [pscustomobject]@{ AtLogOn = [bool]$AtLogOn; User = $User; Once = [bool]$Once; At = $At; RepetitionInterval = $RepetitionInterval } }
function New-ScheduledTaskPrincipal { param($UserId, $LogonType, $RunLevel); return [pscustomobject]@{ UserId = $UserId; LogonType = $LogonType; RunLevel = $RunLevel } }
function New-ScheduledTaskSettingsSet { param($MultipleInstances, [switch]$Hidden, [switch]$StartWhenAvailable, $ExecutionTimeLimit); return [pscustomobject]@{ MultipleInstances = $MultipleInstances; Hidden = [bool]$Hidden; StartWhenAvailable = [bool]$StartWhenAvailable; ExecutionTimeLimit = $ExecutionTimeLimit; Enabled = $true } }
function Register-ScheduledTask {
    param($TaskName, $TaskPath, $Action, $Trigger, $Principal, $Settings, $Description, [switch]$Force)
    $script:RegistrationCount++
    $script:ExistingTask = [pscustomobject]@{ Name = $TaskName; Path = $TaskPath; Actions = @($Action); Triggers = $Trigger; Principal = $Principal; Settings = $Settings; Description = $Description }
    $script:RegisteredTasks[$TaskName] = $script:ExistingTask
    return $script:ExistingTask
}

$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('monitoring-installer-' + [guid]::NewGuid().ToString('N'))
$base = Join-Path $testRoot "instance with spaces and ' apostrophe"
$source = Join-Path $base 'source'
$configPath = Join-Path $base 'monitoring-instance.json'
$git = (Get-Command git.exe -CommandType Application | Select-Object -First 1).Source
$initialPrompt = [Environment]::GetEnvironmentVariable('GIT_TERMINAL_PROMPT', 'Process')
New-Item -ItemType Directory -Path (Join-Path $source 'deploy') -Force | Out-Null
function Test-Git { param([string[]]$Arguments); & $git -C $source @Arguments 2>&1 | Out-Null; if ($LASTEXITCODE -ne 0) { throw "Test Git command failed: $($Arguments[0])" } }
function Write-TestConfig { param($Value); [IO.File]::WriteAllText($configPath, ($Value | ConvertTo-Json -Depth 5) + "`r`n", (New-Object Text.UTF8Encoding($false))) }
try {
    $aclFixture = Join-Path $testRoot 'acl-fixture'
    New-Item -ItemType Directory -Path $aclFixture | Out-Null
    & $nativeProtectPath $aclFixture
    $acl = Get-Acl -LiteralPath $aclFixture
    Assert-True $acl.AreAccessRulesProtected 'Controller ACL still inherits broad access.'
    $rules = @($acl.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    Assert-True ($rules.Count -eq 2 -and @($rules | Where-Object { $_.IdentityReference.Value -notin @($currentSid, 'S-1-5-18') }).Count -eq 0) 'Controller ACL grants an unexpected identity.'
    Test-Git @('init', '-q')
    Test-Git @('config', 'user.name', 'Installer Test')
    Test-Git @('config', 'user.email', 'installer-test@example.invalid')
    Test-Git @('config', 'core.autocrlf', 'false')
    Test-Git @('remote', 'add', 'origin', 'https://github.com/HappyMiha/helvetic-lens.git')
    $managerText = "#!/usr/bin/env python3`nimport json, os, pathlib, sys`nassert os.environ['GIT_TERMINAL_PROMPT'] == '0'`nassert sys.argv[1] == '--config' and sys.argv[3] == '--poll'`nassert json.loads(pathlib.Path(sys.argv[2]).read_text())['instance'] == 'monitoring-v2'`nprint('reviewed test controller')`n"
    [IO.File]::WriteAllText((Join-Path $source 'deploy\release_manager.py'), $managerText, (New-Object Text.UTF8Encoding($false)))
    Test-Git @('add', 'deploy/release_manager.py')
    Test-Git @('commit', '-qm', 'Test reviewed controller')
    $revision = (& $git -C $source rev-parse HEAD).Trim()
    Test-Git @('update-ref', 'refs/remotes/origin/codex/HappyDucky02/monitoring-v2', $revision)
    $config = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'monitoring-instance.example.json') -Raw | ConvertFrom-Json
    $config.base_dir = $base
    foreach ($entry in @{ source_repo = 'source'; control_dir = 'controller'; releases_dir = 'releases'; state_dir = 'state'; env_file = 'private\monitoring.env'; tunnel_dir = 'private\cloudflared' }.GetEnumerator()) {
        $config.($entry.Key) = Join-Path $base $entry.Value
    }
    Write-TestConfig $config
    $originalHash = (Get-FileHash -LiteralPath $configPath).Hash
    $env:GIT_TERMINAL_PROMPT = 'test-original-value'
    Install-MonitoringAutoDeploy $configPath $PythonExecutable $revision -ValidateOnly
    Assert-True (-not (Test-Path -LiteralPath $config.control_dir)) 'ValidateOnly wrote a controller directory.'
    Assert-True ($script:RegistrationCount -eq 0) 'ValidateOnly registered a task.'
    Assert-True ($env:GIT_TERMINAL_PROMPT -ceq 'test-original-value') 'Validation changed the caller environment.'

    $junctionTarget = Join-Path $testRoot 'junction-target'
    New-Item -ItemType Directory -Path $junctionTarget | Out-Null
    $junction = Join-Path $base 'unexpected-junction'
    New-Item -ItemType Junction -Path $junction -Target $junctionTarget | Out-Null
    $savedState = $config.state_dir
    $config.state_dir = Join-Path $junction 'state'
    Write-TestConfig $config
    Assert-Rejected { Get-MonitoringInstallPlan $configPath $PythonExecutable $revision } 'A junction escaping the dedicated root was accepted.'
    $config.state_dir = $savedState
    Write-TestConfig $config

    foreach ($bad in @(
        @{ key = 'version'; value = $true },
        @{ key = 'version'; value = '1' },
        @{ key = 'branch'; value = 'main' },
        @{ key = 'compose_project'; value = 'helvetic-lens' },
        @{ key = 'docker_context'; value = 'default' },
        @{ key = 'public_url'; value = 'https://helveticlens.ch' },
        @{ key = 'self_update'; value = $true },
        @{ key = 'self_update'; value = 'false' },
        @{ key = 'state_dir'; value = $source },
        @{ key = 'env_file'; value = (Join-Path $source '.env.production') },
        @{ key = 'releases_dir'; value = (Join-Path $testRoot 'outside') },
        @{ key = 'qa_cpus'; value = '0' },
        @{ key = 'qa_memory'; value = 'unlimited' },
        @{ key = 'qa_user'; value = '0:0' },
        @{ key = 'api_test_timeout_seconds'; value = 1 },
        @{ key = 'api_test_timeout_seconds'; value = $true },
        @{ key = 'api_test_timeout_seconds'; value = '7200' }
    )) {
        $saved = $config.($bad.key)
        $config.($bad.key) = $bad.value
        Write-TestConfig $config
        Assert-Rejected { Get-MonitoringInstallPlan $configPath $PythonExecutable $revision } "Unsafe configuration accepted: $($bad.key)"
        $config.($bad.key) = $saved
    }
    Write-TestConfig $config
    Assert-Rejected { Get-MonitoringInstallPlan $configPath $PythonExecutable 'main' } 'A moving controller ref was accepted.'
    Test-Git @('remote', 'set-url', 'origin', 'https://example.invalid/untrusted.git')
    Assert-Rejected { Get-MonitoringInstallPlan $configPath $PythonExecutable $revision } 'An untrusted repository was accepted.'
    Test-Git @('remote', 'set-url', 'origin', 'https://github.com/HappyMiha/helvetic-lens.git')
    Test-Git @('update-ref', '-d', 'refs/remotes/origin/codex/HappyDucky02/monitoring-v2')
    Assert-Rejected { Get-MonitoringInstallPlan $configPath $PythonExecutable $revision } 'An unfetched branch was accepted.'
    Test-Git @('update-ref', 'refs/remotes/origin/codex/HappyDucky02/monitoring-v2', $revision)

    Install-MonitoringAutoDeploy $configPath $PythonExecutable $revision -StartDisabled
    Assert-True (-not $script:ExistingTask.Settings.Enabled) 'StartDisabled registered an enabled task.'
    Install-MonitoringAutoDeploy $configPath $PythonExecutable $revision
    Assert-True (-not $script:ExistingTask.Settings.Enabled) 'Reinstallation unexpectedly resumed a paused task.'
    Assert-True ($script:RegisteredTasks.Count -eq 1) 'Repeated installation created more than one task.'
    Assert-True ((Get-FileHash -LiteralPath $configPath).Hash -ceq $originalHash) 'Installation rewrote persistent configuration.'
    Assert-True ([IO.File]::ReadAllText((Join-Path $config.control_dir 'release_manager.py')) -ceq $managerText) 'Controller bytes did not match the reviewed object.'
    $record = Get-Content -LiteralPath (Join-Path $config.control_dir 'controller.json') -Raw | ConvertFrom-Json
    Assert-True ($record.commit -ceq $revision) 'Controller revision was not recorded.'
    Assert-True ($record.config_path -ceq $configPath -and $record.python_executable -ceq $PythonExecutable) 'Exact runtime paths were not preserved.'
    $task = $script:ExistingTask
    Assert-True ($task.Principal.LogonType -ceq 'Interactive' -and $task.Principal.RunLevel -ceq 'Limited') 'Task uses an unsafe principal.'
    Assert-True ($task.Principal.UserId -ne 'S-1-5-18') 'Task runs as SYSTEM.'
    Assert-True ($task.Settings.MultipleInstances -ceq 'IgnoreNew' -and $task.Settings.Hidden) 'Task overlap or visibility setting is incorrect.'
    Assert-True ($task.Triggers[1].RepetitionInterval.TotalMinutes -eq 2 -and $task.Triggers[0].AtLogOn) 'Task triggers are incorrect.'
    Assert-True ($task.Actions[0].Arguments.Contains('-WindowStyle Hidden')) 'PowerShell action is not hidden.'
    $launcher = Join-Path $config.control_dir 'poll-monitoring.ps1'
    $launcherContent = [IO.File]::ReadAllText($launcher)
    Assert-True ($launcherContent.Contains('--config') -and $launcherContent.Contains('--poll') -and $launcherContent.Contains("`$env:GIT_TERMINAL_PROMPT = '0'")) 'Launcher lacks persistent arguments or noninteractive Git.'
    [Management.Automation.Language.Parser]::ParseFile($launcher, [ref]$tokens, [ref]$parseErrors) | Out-Null
    Assert-True ($parseErrors.Count -eq 0) 'Launcher path quoting produced invalid PowerShell.'
    $invocation = New-Object Diagnostics.ProcessStartInfo
    $invocation.FileName = $task.Actions[0].Execute
    $invocation.Arguments = $task.Actions[0].Arguments
    $invocation.WorkingDirectory = $task.Actions[0].WorkingDirectory
    $invocation.UseShellExecute = $false
    $invocation.CreateNoWindow = $true
    $invocation.RedirectStandardOutput = $true
    $invocation.RedirectStandardError = $true
    $process = [Diagnostics.Process]::Start($invocation)
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    Assert-True ($process.ExitCode -eq 0 -and $stdout.Contains('reviewed test controller')) "Exact scheduled invocation failed: $stderr"
    $process.Dispose()
    $task.Description = 'Another application owns this name'
    $before = $script:RegistrationCount
    $beforeManagerHash = (Get-FileHash -LiteralPath (Join-Path $config.control_dir 'release_manager.py')).Hash
    Assert-Rejected { Install-MonitoringAutoDeploy $configPath $PythonExecutable $revision } 'A foreign scheduled task was overwritten.'
    Assert-True ($script:RegistrationCount -eq $before) 'Foreign task collision still mutated the scheduler.'
    Assert-True ((Get-FileHash -LiteralPath (Join-Path $config.control_dir 'release_manager.py')).Hash -ceq $beforeManagerHash) 'Foreign task collision changed the controller.'
    Write-Output 'PASS: parsing, native directory ACL, read-only validation, 17 unsafe configurations, junction escape, pinned provenance, config preservation, exact extraction, idempotence, paused-task preservation, task scope and exact hidden scheduled invocation.'
} finally {
    [Environment]::SetEnvironmentVariable('GIT_TERMINAL_PROMPT', $initialPrompt, 'Process')
    # Only the verified GUID-named disposable directory created by this test.
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $tempParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
    if ($resolved.StartsWith($tempParent, [StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved) -match '^monitoring-installer-[0-9a-f]{32}$') {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    } else { throw 'Refusing test cleanup outside the expected temporary directory.' }
}
