$ErrorActionPreference = 'Stop'
$runtimePython = Join-Path $env:LOCALAPPDATA 'NamecheapEmail\runtime\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) { throw 'Run Install Plugin.ps1 first.' }
& $runtimePython -B (Join-Path $PSScriptRoot 'scripts\setup_email.py')
$setupExit = $LASTEXITCODE
Read-Host 'Press Enter to close' | Out-Null
exit $setupExit
