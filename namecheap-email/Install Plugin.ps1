param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
if (-not $PythonExe) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $PythonExe = $bundledPython }
    else { $PythonExe = (Get-Command python -ErrorAction Stop).Source }
}
$pluginName = 'namecheap-email'
$pluginParent = Join-Path $env:USERPROFILE 'plugins'
$destination = Join-Path $pluginParent $pluginName
$runtime = Join-Path $env:LOCALAPPDATA 'NamecheapEmail\runtime'
$runtimePython = Join-Path $runtime 'Scripts\python.exe'
$marketplace = Join-Path $env:USERPROFILE '.agents\plugins\marketplace.json'
if (Test-Path -LiteralPath $destination) {
    . (Join-Path $PSScriptRoot 'scripts\find_runtime.ps1')
    $existingPython = Find-NamecheapEmailPython
    & $existingPython -B -c "import mcp, keyring"
    if ($LASTEXITCODE -ne 0) { throw 'The existing runtime needs repair. No plugin files were overwritten.' }
    Write-Host 'The plugin and runtime already exist. Run Setup Email.ps1 from this folder to connect your mailbox.'
    exit 0
}
if (Test-Path -LiteralPath $marketplace) {
    & $PythonExe (Join-Path $PSScriptRoot 'installer\read_marketplace_name.py')
    if ($LASTEXITCODE -ne 0) { throw 'Existing personal marketplace failed validation.' }
}
& $PythonExe -m venv $runtime
if ($LASTEXITCODE -ne 0) { throw 'Python runtime creation failed.' }
& $runtimePython -m pip install --disable-pip-version-check -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
$physicalPython = & $runtimePython -c "from pathlib import Path; import sys; print(Path(sys.executable).resolve())"
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve the installed runtime path.' }
$runtimePython = $physicalPython.Trim()
& $PythonExe (Join-Path $PSScriptRoot 'installer\create_basic_plugin.py') $pluginName --with-mcp --with-skills --with-scripts --with-marketplace
if ($LASTEXITCODE -ne 0) { throw 'Plugin scaffold or marketplace registration failed.' }
# The scaffold just created this destination; copying the finished implementation is intentional.
Get-ChildItem -LiteralPath $PSScriptRoot -Force | Where-Object { $_.Name -notin @('__pycache__', '.venv') } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}
$connection = @{ mcpServers = @{ 'namecheap-email' = @{
    command = $runtimePython
    args = @('-B', (Join-Path $destination 'scripts\server.py'))
    startup_timeout_sec = 30
    tool_timeout_sec = 180
} } }
[System.IO.File]::WriteAllText((Join-Path $destination '.mcp.json'), ($connection | ConvertTo-Json -Depth 8), [System.Text.UTF8Encoding]::new($false))
& $runtimePython (Join-Path $destination 'installer\validate_plugin.py') $destination
if ($LASTEXITCODE -ne 0) { throw 'Plugin validation failed.' }
$marketplaceName = & $PythonExe (Join-Path $PSScriptRoot 'installer\read_marketplace_name.py')
if ($LASTEXITCODE -ne 0) { throw 'Personal marketplace name validation failed.' }
& codex plugin add "$pluginName@$marketplaceName"
if ($LASTEXITCODE -ne 0) { throw 'Files and marketplace entry were created, but Codex activation failed. Use the plugin page to install.' }
Write-Host 'Plugin installed. Run Setup Email.ps1 to enter the mailbox login locally, then start a new Codex task.'
