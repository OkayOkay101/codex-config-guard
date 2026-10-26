$ErrorActionPreference = 'Stop'
$taskName = 'Codex Config Guard'
$pythonExe = (Get-Command python.exe -ErrorAction Stop).Source
$pythonwExe = Join-Path (Split-Path $pythonExe) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwExe)) { throw 'pythonw.exe is required for an invisible watcher.' }
& $pythonExe -c 'import sys,tomllib; assert sys.version_info >= (3,11); print(sys.version.split()[0])'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ with tomllib is required.' }
$stateDir = Join-Path $PSScriptRoot 'state'
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
# Snapshots can contain credentials: restrict the whole state directory first.
$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$acl = New-Object System.Security.AccessControl.DirectorySecurity
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner($currentIdentity.User)
foreach ($sid in @($currentIdentity.User.Value, 'S-1-5-18', 'S-1-5-32-544')) {
    $identity = New-Object System.Security.Principal.SecurityIdentifier($sid)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $stateDir -AclObject $acl
$runtime = @{python=$pythonExe; pythonw=$pythonwExe; task=$taskName}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'runtime.json'), ($runtime | ConvertTo-Json), $utf8)
& $pythonExe (Join-Path $PSScriptRoot 'guard.py') check --seed
if ($LASTEXITCODE -ne 0) { throw 'Initial config validation/backup failed. Task was not installed.' }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $expectedScript = Join-Path $PSScriptRoot 'guard.py'
    if ($existing.Actions.Arguments -notcontains ('"' + $expectedScript + '" watch')) {
        throw 'An unrelated scheduled task already uses this name. It was not changed.'
    }
    Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath (Join-Path $stateDir 'previous-task.xml') -Encoding Unicode
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
}
$action = New-ScheduledTaskAction -Execute $pythonwExe -Argument ('"' + (Join-Path $PSScriptRoot 'guard.py') + '" watch') -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $currentIdentity.Name
$principal = New-ScheduledTaskPrincipal -UserId $currentIdentity.Name -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Validate Codex config syntax every 2 seconds; preserve invalid files and recover verified snapshots after stability debounce.' -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Write-Output 'Installed and started Codex Config Guard (current user, limited privileges).'
