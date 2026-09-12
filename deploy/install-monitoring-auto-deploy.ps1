#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ConfigPath,
    [string]$PythonExecutable,
    [string]$ControllerCommit,
    [switch]$ValidateOnly,
    [switch]$StartDisabled
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:MonitoringTaskName = 'HelveticLens-Monitoring-v2-AutoDeploy'
$script:MonitoringTaskDescription = 'Helvetic Lens Monitoring v2; managed by install-monitoring-auto-deploy.ps1; current-user instance only.'

function Get-MonitoringAbsolutePath {
    param([string]$Value, [string]$Name, [string]$Boundary)
    if ([string]::IsNullOrWhiteSpace($Value) -or -not [IO.Path]::IsPathRooted($Value) -or $Value.StartsWith('\\')) {
        throw "$Name must be an absolute local Windows path."
    }
    $full = [IO.Path]::GetFullPath($Value).TrimEnd('\', '/')
    if ($full -match '[\r\n"]') { throw "$Name contains an unsupported path character." }
    $current = $full
    # The explicitly chosen root may itself sit below a redirected Documents
    # directory. Reject links within that root, not trusted ancestor redirects.
    while ($Boundary -and $current -and $current -ine $Boundary) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "$Name must not traverse a symbolic link or junction."
            }
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if ($parent -eq $current) { break }
        $current = $parent
    }
    return $full
}

function Test-MonitoringDescendant {
    param([string]$Path, [string]$Directory)
    return $Path.StartsWith($Directory.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)
}

function Invoke-MonitoringGit {
    param([string]$GitExecutable, [string]$Source, [string[]]$Arguments)
    $result = & $GitExecutable -C $Source @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Git validation failed: $($Arguments[0])." }
    return ($result -join "`n").Trim()
}

function Get-MonitoringInstallPlan {
    param([string]$ConfigPath, [string]$PythonExecutable, [string]$ControllerCommit)
    if ($env:OS -ne 'Windows_NT') { throw 'This installer requires native Windows.' }
    if ($ControllerCommit -cnotmatch '^[0-9a-f]{40}$') { throw 'ControllerCommit must be a reviewed full lowercase 40-character commit SHA.' }
    $configFile = Get-MonitoringAbsolutePath $ConfigPath 'ConfigPath'
    $python = Get-MonitoringAbsolutePath $PythonExecutable 'PythonExecutable'
    if (-not (Test-Path -LiteralPath $configFile -PathType Leaf)) { throw 'ConfigPath must identify an existing JSON file.' }
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or [IO.Path]::GetExtension($python) -ne '.exe') {
        throw 'PythonExecutable must identify the exact installed python.exe.'
    }
    $config = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
    $required = @('version', 'instance', 'branch', 'compose_project', 'docker_context', 'base_dir', 'source_repo', 'control_dir', 'releases_dir', 'state_dir', 'env_file', 'tunnel_dir', 'expected_repository', 'public_url', 'self_update')
    $allowed = $required + @('qa_cpus', 'qa_memory', 'qa_user', 'api_test_timeout_seconds')
    $names = @($config.PSObject.Properties.Name)
    foreach ($name in $required) { if ($name -notin $names) { throw "Required configuration key is missing: $name" } }
    foreach ($name in $names) { if ($name -notin $allowed) { throw "Unknown configuration key: $name" } }
    foreach ($name in ($required | Where-Object { $_ -notin @('version', 'self_update') })) {
        if ($config.$name -isnot [string] -or [string]::IsNullOrEmpty($config.$name) -or $config.$name -match '[\x00-\x1F]') {
            throw "Invalid deployment selector: $name"
        }
    }
    if (($config.version -isnot [int] -and $config.version -isnot [long]) -or $config.version -ne 1 -or $config.instance -cne 'monitoring-v2' -or
        $config.branch -cne 'main' -or
        $config.compose_project -cne 'helvetic-lens-v2' -or $config.docker_context -cne 'desktop-linux' -or
        $config.expected_repository -cne 'https://github.com/HappyMiha/helvetic-lens.git' -or
        $config.public_url -cne 'https://monitoring.helveticlens.ch' -or
        $config.self_update -isnot [bool] -or $config.self_update) {
        throw 'Configuration does not identify the isolated Monitoring instance and pinned controller.'
    }
    if ('qa_cpus' -in $names -and [string]$config.qa_cpus -cnotmatch '^[1-9][0-9]?(?:\.[0-9]+)?\z') { throw 'qa_cpus must be a positive bounded CPU count.' }
    if ('qa_memory' -in $names -and [string]$config.qa_memory -cnotmatch '^[1-9][0-9]{0,2}[mg]\z') { throw 'qa_memory must be an explicit Docker memory budget.' }
    if ('qa_user' -in $names -and [string]$config.qa_user -cnotmatch '^[1-9][0-9]*:[1-9][0-9]*\z') { throw 'qa_user must specify a non-root Linux UID:GID.' }
    if ('api_test_timeout_seconds' -in $names) {
        $timeout = $config.api_test_timeout_seconds
        if (($timeout -isnot [int] -and $timeout -isnot [long]) -or $timeout -lt 300 -or $timeout -gt 21600) {
            throw 'api_test_timeout_seconds must be an integer between 300 and 21600.'
        }
    }
    $base = Get-MonitoringAbsolutePath $config.base_dir 'base_dir'
    if ($base -eq [IO.Path]::GetPathRoot($base).TrimEnd('\', '/')) { throw 'base_dir must not be a drive root.' }
    if (-not (Test-MonitoringDescendant $configFile $base)) { throw 'ConfigPath must be inside base_dir.' }
    Get-MonitoringAbsolutePath $configFile 'ConfigPath' $base | Out-Null
    $directories = @{}
    foreach ($name in @('source_repo', 'control_dir', 'releases_dir', 'state_dir', 'tunnel_dir')) {
        $path = Get-MonitoringAbsolutePath $config.$name $name $base
        if (-not (Test-MonitoringDescendant $path $base)) { throw "$name must be inside the dedicated base_dir." }
        foreach ($other in $directories.Values) {
            if ($path -eq $other -or (Test-MonitoringDescendant $path $other) -or (Test-MonitoringDescendant $other $path)) {
                throw 'Instance directories must be separate and must not contain each other.'
            }
        }
        $directories[$name] = $path
        if (Test-MonitoringDescendant $configFile $path) { throw 'The persistent configuration must be outside managed instance directories.' }
    }
    $envFile = Get-MonitoringAbsolutePath $config.env_file 'env_file' $base
    if (-not (Test-MonitoringDescendant $envFile $base)) { throw 'env_file must be inside base_dir.' }
    foreach ($path in $directories.Values) {
        if ($envFile -eq $path -or (Test-MonitoringDescendant $envFile $path)) { throw 'env_file must be outside managed instance directories.' }
    }
    if ($envFile -eq $configFile) { throw 'env_file must not replace the instance configuration.' }
    $git = (Get-Command git.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
    $priorPrompt = [Environment]::GetEnvironmentVariable('GIT_TERMINAL_PROMPT', 'Process')
    try {
        $env:GIT_TERMINAL_PROMPT = '0'
        & $python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer required"' 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'The selected executable is not a working Python 3.11+ interpreter.' }
        $origin = Invoke-MonitoringGit $git $directories.source_repo @('remote', 'get-url', 'origin')
        if ($origin.TrimEnd('/') -cne $config.expected_repository) { throw 'Source origin does not match the trusted repository.' }
        Invoke-MonitoringGit $git $directories.source_repo @('cat-file', '-e', "$ControllerCommit`^{commit}") | Out-Null
        Invoke-MonitoringGit $git $directories.source_repo @('merge-base', '--is-ancestor', $ControllerCommit, "refs/remotes/origin/$($config.branch)") | Out-Null
        Invoke-MonitoringGit $git $directories.source_repo @('cat-file', '-e', "${ControllerCommit}:deploy/release_manager.py") | Out-Null
    } finally {
        [Environment]::SetEnvironmentVariable('GIT_TERMINAL_PROMPT', $priorPrompt, 'Process')
    }
    return [pscustomobject]@{
        ConfigPath = $configFile; PythonExecutable = $python; Commit = $ControllerCommit
        Config = $config; BaseDirectory = $base; Directories = $directories; GitExecutable = $git
        ManagerPath = Join-Path $directories.control_dir 'release_manager.py'
        LauncherPath = Join-Path $directories.control_dir 'poll-monitoring.ps1'
    }
}

function Protect-MonitoringControllerPath {
    param([string]$Path)
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
    if ((Get-Item -LiteralPath $Path).PSIsContainer) {
        $acl = New-Object Security.AccessControl.DirectorySecurity
        $inherit = [Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit'
    } else {
        $acl = New-Object Security.AccessControl.FileSecurity
        $inherit = [Security.AccessControl.InheritanceFlags]::None
    }
    # Preserve an already exact protected DACL. Reapplying it can require an
    # unavailable audit privilege on Windows even though no ACL change is needed.
    # Read access/owner information only; never request or change a SACL.
    $existing = Get-Acl -LiteralPath $Path
    $rules = @($existing.GetAccessRules($true, $true, [Security.Principal.SecurityIdentifier]))
    $expectedSids = @($sid.Value, 'S-1-5-18')
    $exact = $existing.AreAccessRulesProtected -and
        $existing.GetOwner([Security.Principal.SecurityIdentifier]).Value -ceq $sid.Value -and
        $rules.Count -eq 2
    foreach ($expectedSid in $expectedSids) {
        $matching = @($rules | Where-Object {
            $_.IdentityReference.Value -ceq $expectedSid -and
            -not $_.IsInherited -and
            $_.AccessControlType -eq [Security.AccessControl.AccessControlType]::Allow -and
            $_.FileSystemRights -eq [Security.AccessControl.FileSystemRights]::FullControl -and
            $_.InheritanceFlags -eq $inherit -and
            $_.PropagationFlags -eq [Security.AccessControl.PropagationFlags]::None
        })
        $exact = $exact -and $matching.Count -eq 1
    }
    if ($exact) { return }
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($identity in @($sid, (New-Object Security.Principal.SecurityIdentifier('S-1-5-18')))) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', $inherit, 'None', 'Allow')
        $acl.AddAccessRule($rule) | Out-Null
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Get-MonitoringLauncherContent {
    param($Plan)
    $python = $Plan.PythonExecutable.Replace("'", "''")
    $manager = $Plan.ManagerPath.Replace("'", "''")
    $config = $Plan.ConfigPath.Replace("'", "''")
    return "# Managed Monitoring v2 poller; controller $($Plan.Commit)`r`n`$ErrorActionPreference = 'Stop'`r`n`$env:GIT_TERMINAL_PROMPT = '0'`r`n& '$python' '$manager' --config '$config' --poll`r`nexit `$LASTEXITCODE`r`n"
}

function Resolve-MonitoringPrincipalSid {
    param([string]$UserId)
    if ([string]::IsNullOrWhiteSpace($UserId)) { return $null }
    try {
        # Task Scheduler can return a SID, qualified name or local short name.
        # Resolve names through Windows; never trust a matching username alone.
        if ($UserId -match '^S-\d+(?:-\d+)+$') {
            return ([Security.Principal.SecurityIdentifier]::new($UserId)).Value
        }
        $account = [Security.Principal.NTAccount]::new($UserId)
        return $account.Translate([Security.Principal.SecurityIdentifier]).Value
    } catch { return $null }
}

function Assert-MonitoringTaskOwnership {
    param($Plan)
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $sid = $identity.User.Value
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "' + $Plan.LauncherPath + '"'
    $existing = Get-ScheduledTask -TaskName $script:MonitoringTaskName -TaskPath '\' -ErrorAction SilentlyContinue
    if ($existing) {
        $owned = $existing.Description -ceq $script:MonitoringTaskDescription -and
            (Resolve-MonitoringPrincipalSid $existing.Principal.UserId) -ceq $sid -and
            @($existing.Actions).Count -eq 1 -and $existing.Actions[0].Execute -ieq $powershell -and
            $existing.Actions[0].Arguments -ceq $arguments
        if (-not $owned) { throw 'The fixed Monitoring task name is already owned by a different task or instance. No task was replaced.' }
    }
}

function Register-MonitoringPollingTask {
    param($Plan, [switch]$StartDisabled)
    Assert-MonitoringTaskOwnership $Plan
    $existing = Get-ScheduledTask -TaskName $script:MonitoringTaskName -TaskPath '\' -ErrorAction SilentlyContinue
    $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    $powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $arguments = '-NoLogo -NoProfile -NonInteractive -ExecutionPolicy RemoteSigned -WindowStyle Hidden -File "' + $Plan.LauncherPath + '"'
    $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $Plan.Directories.control_dir
    $triggers = @(
        (New-ScheduledTaskTrigger -AtLogOn -User $sid),
        (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2))
    )
    $principal = New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -Hidden -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 8)
    if ($StartDisabled -or ($existing -and -not $existing.Settings.Enabled)) { $settings.Enabled = $false }
    Register-ScheduledTask -TaskName $script:MonitoringTaskName -TaskPath '\' -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Description $script:MonitoringTaskDescription -Force | Out-Null
}

function Install-MonitoringAutoDeploy {
    param([string]$ConfigPath, [string]$PythonExecutable, [string]$ControllerCommit, [switch]$ValidateOnly, [switch]$StartDisabled)
    $plan = Get-MonitoringInstallPlan $ConfigPath $PythonExecutable $ControllerCommit
    if ($ValidateOnly) { Write-Output 'Monitoring installer validation passed; no files, tasks or services were changed.'; return }
    Assert-MonitoringTaskOwnership $plan
    foreach ($target in @($plan.ManagerPath, $plan.LauncherPath, (Join-Path $plan.Directories.control_dir 'deployment.lock'), (Join-Path $plan.Directories.control_dir 'controller.json'))) {
        Get-MonitoringAbsolutePath $target 'controller destination' $plan.BaseDirectory | Out-Null
    }
    foreach ($directory in $plan.Directories.Values) { New-Item -ItemType Directory -Path $directory -Force | Out-Null }
    Protect-MonitoringControllerPath $plan.Directories.control_dir
    Protect-MonitoringControllerPath $plan.ConfigPath
    $lockPath = Join-Path $plan.Directories.control_dir 'deployment.lock'
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::ReadWrite)
    $locked = $false
    $candidate = Join-Path $plan.Directories.control_dir ('.release-manager.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        try { $lock.Lock(0, 1); $locked = $true } catch { throw 'A Monitoring deployment is active; controller update was not applied.' }
        $extract = @'
import pathlib, subprocess, sys
git, source, revision, target = sys.argv[1:]
data = subprocess.run([git, '-C', source, 'show', revision + ':deploy/release_manager.py'], check=True, capture_output=True).stdout
compile(data, 'reviewed-release-manager', 'exec')
pathlib.Path(target).write_bytes(data)
'@
        & $plan.PythonExecutable -c $extract $plan.GitExecutable $plan.Directories.source_repo $plan.Commit $candidate
        if ($LASTEXITCODE -ne 0) { throw 'The reviewed controller could not be extracted and compiled.' }
        Protect-MonitoringControllerPath $candidate
        if (Test-Path -LiteralPath $plan.ManagerPath) {
            if ((Get-FileHash -LiteralPath $candidate).Hash -eq (Get-FileHash -LiteralPath $plan.ManagerPath).Hash) {
                Remove-Item -LiteralPath $candidate
            } else {
                $backup = $plan.ManagerPath + '.backup.' + [guid]::NewGuid().ToString('N')
                [IO.File]::Replace($candidate, $plan.ManagerPath, $backup)
            }
        } else { [IO.File]::Move($candidate, $plan.ManagerPath) }
        [IO.File]::WriteAllText($plan.LauncherPath, (Get-MonitoringLauncherContent $plan), (New-Object Text.UTF8Encoding($true)))
        Protect-MonitoringControllerPath $plan.LauncherPath
        $record = [ordered]@{ version = 1; instance = 'monitoring-v2'; commit = $plan.Commit; manager_sha256 = (Get-FileHash -LiteralPath $plan.ManagerPath -Algorithm SHA256).Hash.ToLowerInvariant(); config_path = $plan.ConfigPath; python_executable = $plan.PythonExecutable }
        $recordPath = Join-Path $plan.Directories.control_dir 'controller.json'
        [IO.File]::WriteAllText($recordPath, ($record | ConvertTo-Json) + "`n", (New-Object Text.UTF8Encoding($false)))
        Protect-MonitoringControllerPath $recordPath
        Register-MonitoringPollingTask $plan -StartDisabled:$StartDisabled
    } finally {
        if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate }
        if ($locked) { $lock.Unlock(0, 1) }
        $lock.Dispose()
    }
    Write-Output "Installed $script:MonitoringTaskName with controller $($plan.Commit)."
    Write-Output 'When enabled, polling runs every two minutes while this user is logged in. First deployment requires explicit --bootstrap. Existing paused tasks stay paused.'
}

if ($MyInvocation.InvocationName -ne '.') {
    Install-MonitoringAutoDeploy -ConfigPath $ConfigPath -PythonExecutable $PythonExecutable -ControllerCommit $ControllerCommit -ValidateOnly:$ValidateOnly -StartDisabled:$StartDisabled
}
