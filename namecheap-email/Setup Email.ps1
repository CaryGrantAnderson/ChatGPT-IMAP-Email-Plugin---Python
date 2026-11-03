param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\find_runtime.ps1')
$runtimePython = Find-NamecheapEmailPython
if ($CheckOnly) {
    & $runtimePython -B -c "import mcp, keyring; print('Email setup runtime is ready.')"
    exit $LASTEXITCODE
}
& $runtimePython -B (Join-Path $PSScriptRoot 'scripts\setup_email.py')
$setupExit = $LASTEXITCODE
Read-Host 'Press Enter to close' | Out-Null
exit $setupExit
