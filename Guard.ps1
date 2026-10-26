param(
    [Parameter(Position=0)]
    [ValidateSet('check','apply','status','restore','watch')]
    [string]$Command = 'status',
    [Parameter(Position=1)][string]$Draft,
    [switch]$Seed
)
$ErrorActionPreference = 'Stop'
$runtimeFile = Join-Path $PSScriptRoot 'runtime.json'
if (Test-Path -LiteralPath $runtimeFile) {
    $runtime = Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json
    $pythonExe = $runtime.python
} else {
    $pythonExe = (Get-Command python.exe -ErrorAction Stop).Source
}
$guardArgs = @((Join-Path $PSScriptRoot 'guard.py'), $Command)
if ($Command -eq 'apply') {
    if (-not $Draft) { throw 'apply requires a draft TOML file path.' }
    $guardArgs += (Resolve-Path -LiteralPath $Draft).Path
}
if ($Seed) {
    if ($Command -ne 'check') { throw '-Seed is supported only for check.' }
    $guardArgs += '--seed'
}
& $pythonExe @guardArgs
exit $LASTEXITCODE
