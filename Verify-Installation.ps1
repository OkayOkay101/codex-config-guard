$ErrorActionPreference = 'Stop'
$taskName = 'Codex Config Guard'
$heartbeatPath = Join-Path $PSScriptRoot 'state\watcher.json'
$before = Get-Content -LiteralPath $heartbeatPath -Raw | ConvertFrom-Json
Stop-ScheduledTask -TaskName $taskName
$stopDeadline = [DateTime]::UtcNow.AddSeconds(20)
while ((Get-ScheduledTask -TaskName $taskName).State -eq 'Running') {
    if ([DateTime]::UtcNow -gt $stopDeadline) { throw 'Scheduled Task failed to stop.' }
    Start-Sleep -Milliseconds 300
}
$stoppedInfo = Get-ScheduledTaskInfo -TaskName $taskName
Start-ScheduledTask -TaskName $taskName
$deadline = [DateTime]::UtcNow.AddSeconds(60)
do {
    Start-Sleep -Milliseconds 500
    $after = Get-Content -LiteralPath $heartbeatPath -Raw | ConvertFrom-Json
    if ([DateTime]::UtcNow -gt $deadline) { throw 'No fresh watcher heartbeat after restart.' }
} while ($after.pid -eq $before.pid -or $after.time -le $before.time)
$task = Get-ScheduledTask -TaskName $taskName
$info = Get-ScheduledTaskInfo -TaskName $taskName
$runtime = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime.json') -Raw | ConvertFrom-Json
$statusText = & $runtime.python (Join-Path $PSScriptRoot 'guard.py') status
if ($LASTEXITCODE -ne 0) { throw 'Live config check failed after restart.' }
$report = [ordered]@{
    verified_at = [DateTime]::UtcNow.ToString('o')
    task_name = $taskName
    task_state = [string]$task.State
    logon_trigger = @($task.Triggers | ForEach-Object { $_.CimClass.CimClassName })
    run_level = [string]$task.Principal.RunLevel
    execution_time_limit = $task.Settings.ExecutionTimeLimit
    previous_pid = $before.pid
    restarted_pid = $after.pid
    restart_verified = ($after.pid -ne $before.pid)
    stopped_result_hex = ('0x{0:X}' -f $stoppedInfo.LastTaskResult)
    running_result_hex = ('0x{0:X}' -f $info.LastTaskResult)
    config_status = ($statusText | Out-String | ConvertFrom-Json)
}
$report | ConvertTo-Json -Depth 8
