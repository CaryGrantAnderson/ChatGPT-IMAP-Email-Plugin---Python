$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'find_runtime.ps1')
$runtimePython = Find-NamecheapEmailPython
& $runtimePython -B (Join-Path $PSScriptRoot 'server.py')
exit $LASTEXITCODE
