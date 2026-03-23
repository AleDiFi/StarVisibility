param(
    [switch]$Console,
    [switch]$Clean,
    # Build both EXEs + compile the Inno Setup installer (requires Inno Setup 6)
    [switch]$Installer
)

$ErrorActionPreference = 'Stop'

# Workspace root = folder containing this script
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$VenvDir    = Join-Path $Root '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'

# ---------------------------------------------------------------------------
# Helper: create / reuse venv
# ---------------------------------------------------------------------------
function Ensure-Venv {
    if (-not (Test-Path $VenvPython)) {
        Write-Host "Creating venv at $VenvDir"
        python -m venv $VenvDir
    }
}

# ---------------------------------------------------------------------------
# Helper: install / upgrade pip + project deps + PyInstaller
# ---------------------------------------------------------------------------
function Pip-Install {
    Write-Host "Upgrading pip"
    & $VenvPython -m pip install --upgrade pip

    Write-Host "Installing runtime dependencies"
    & $VenvPython -m pip install -r requirements.txt

    Write-Host "Installing PyInstaller"
    & $VenvPython -m pip install pyinstaller
}

# ---------------------------------------------------------------------------
# Helper: wipe dist\ and build\ (called once before multi-EXE builds)
# ---------------------------------------------------------------------------
function Clear-BuildDirs {
    $dist  = Join-Path $Root 'dist'
    $build = Join-Path $Root 'build'
    Write-Host "Cleaning previous build outputs"
    if (Test-Path $dist)  { Remove-Item -Recurse -Force $dist }
    if (Test-Path $build) { Remove-Item -Recurse -Force $build }
    Get-ChildItem -Path $Root -Filter '*.spec' | Remove-Item -Force -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------------------
# Core: run PyInstaller for a single EXE variant
# ---------------------------------------------------------------------------
function Invoke-PyInstaller {
    param(
        [string]$Name,
        [bool]  $ConsoleMode
    )

    $dist = Join-Path $Root 'dist'

    $modeArgs = if ($ConsoleMode) {
        @('--console')
    } else {
        @('--noconsole', '--windowed')
    }

    $piArgs = @(
        '-m', 'PyInstaller',
        '--onefile',
        '--name', $Name,
        '--paths', $Root,
        '--additional-hooks-dir', (Join-Path $Root 'pyinstaller_hooks'),
        '--exclude-module', 'astropy.visualization',
        '--exclude-module', 'matplotlib',
        '--clean'
    ) + $modeArgs + @('app.py')

    Write-Host "Running PyInstaller: $Name"
    & $VenvPython @piArgs
    Write-Host "Built: $(Join-Path $dist ($Name + '.exe'))"
}

# ---------------------------------------------------------------------------
# Build the Inno Setup installer (requires Inno Setup 6 to be installed)
# ---------------------------------------------------------------------------
function Build-Installer {
    $isccPaths = @(
        'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        'C:\Program Files\Inno Setup 6\ISCC.exe',
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    $iscc = $isccPaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $iscc) {
        Write-Error (
            "Inno Setup 6 not found.`n" +
            "Install it with:  winget install --id JRSoftware.InnoSetup`n" +
            "Then re-run:      .\build_exe.ps1 -Installer"
        )
        return
    }

    $issFile = Join-Path $Root 'installer.iss'
    Write-Host ""
    Write-Host "Compiling installer…"
    & $iscc $issFile
    Write-Host "Installer ready: dist\StarVisibility-Setup-1.0.0.exe"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
Ensure-Venv
Pip-Install

if ($Installer) {
    # Build both EXE variants, then compile the installer
    if ($Clean) { Clear-BuildDirs }
    Invoke-PyInstaller -Name 'StarVisibility'         -ConsoleMode $false
    Invoke-PyInstaller -Name 'StarVisibility-Console' -ConsoleMode $true
    Build-Installer
} else {
    # Single-EXE mode (original behaviour)
    if ($Clean) { Clear-BuildDirs }
    $name = if ($Console) { 'StarVisibility-Console' } else { 'StarVisibility' }
    Invoke-PyInstaller -Name $name -ConsoleMode $Console.IsPresent
}
