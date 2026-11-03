function Find-NamecheapEmailPython {
    # Windows packaged apps redirect LocalAppData. Normal PowerShell must use
    # the physical package path to find a runtime installed from inside Codex.
    $localRoot = Join-Path $env:USERPROFILE 'AppData\Local'
    $packagesRoot = Join-Path $localRoot 'Packages'
    $candidates = @()
    if (Test-Path -LiteralPath $packagesRoot) {
        Get-ChildItem -LiteralPath $packagesRoot -Directory -Filter 'OpenAI.Codex_*' -ErrorAction SilentlyContinue | ForEach-Object {
            $candidates += Join-Path $_.FullName 'LocalCache\Local\NamecheapEmail\runtime\Scripts\python.exe'
        }
    }
    $candidates += Join-Path $env:LOCALAPPDATA 'NamecheapEmail\runtime\Scripts\python.exe'
    $candidates += Join-Path $localRoot 'NamecheapEmail\runtime\Scripts\python.exe'
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
    throw 'The Namecheap Email runtime is missing from both the normal and Codex app folders. Run Install Plugin.ps1 to install the runtime.'
}
