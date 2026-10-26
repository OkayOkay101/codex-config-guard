param([ValidateSet('restored','no_backup','attention')][string]$Kind)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$messages = @{
    restored = 'Invalid Codex config was preserved and restored from a verified syntax backup. See Codex Config Guard logs.'
    no_backup = 'Codex config is invalid. No verified backup is available. No file was overwritten. Check Codex Config Guard status.'
    attention = 'Codex Config Guard could not access or recover the configuration. Check its status and Windows file permissions.'
}
$tray = New-Object System.Windows.Forms.NotifyIcon
try {
    $tray.Icon = [System.Drawing.SystemIcons]::Warning
    $tray.Visible = $true
    $tray.BalloonTipTitle = 'Codex Config Guard'
    $tray.BalloonTipText = $messages[$Kind]
    $tray.ShowBalloonTip(10000)
    $until = [DateTime]::UtcNow.AddSeconds(12)
    while ([DateTime]::UtcNow -lt $until) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 200
    }
} finally {
    $tray.Dispose()
}
