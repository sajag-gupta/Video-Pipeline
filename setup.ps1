# One-command workspace setup for Windows (PowerShell).
#   powershell -ExecutionPolicy Bypass -File setup.ps1            full setup
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -NoNode    skip Node/HyperFrames
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Skills    also install HyperFrames agent skills
param([switch]$NoNode, [switch]$NoWhisper, [switch]$Skills)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

function Find-Python {
    foreach ($v in @("3.13", "3.12", "3.11")) {
        try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() } } catch {}
    }
    foreach ($c in @("python", "python3")) {
        $cmd = Get-Command $c -ErrorAction SilentlyContinue
        if ($cmd) {
            $ver = & $cmd.Source -c "import sys;print('%d.%d'%sys.version_info[:2])"
            if ([version]$ver -ge [version]"3.11" -and [version]$ver -lt [version]"3.14") { return $cmd.Source }
        }
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "Python 3.11-3.13 not found. Install it from https://www.python.org/downloads/ (tick 'Add to PATH'), then re-run." -ForegroundColor Red
    exit 1
}
Write-Host "Using Python: $py"

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment (venv)..."
    & $py -m venv venv
}
$vpy = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip --quiet
Write-Host "Installing Python packages (first run takes a few minutes)..."
& $vpy -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) { Write-Host "pip install failed" -ForegroundColor Red; exit 1 }

$flags = @()
if ($NoNode) { $flags += "--no-node" }
if ($NoWhisper) { $flags += "--no-whisper" }
if ($Skills) { $flags += "--skills" }
& $vpy scripts\setup_workspace.py @flags
Write-Host "`nDone. Next: venv\Scripts\python.exe vp.py help" -ForegroundColor Green
