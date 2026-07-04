# Windows installer: build (if needed), copy to a per-user location, and create
# Desktop + Start Menu shortcuts. Run from a normal (non-admin) PowerShell:
#
#     powershell -ExecutionPolicy Bypass -File packaging\install.ps1
#
$ErrorActionPreference = "Stop"

$AppName   = "ZLibraryWrapper"
$Root      = Split-Path -Parent $PSScriptRoot
$DistDir   = Join-Path $Root "dist\$AppName"
$ExeName   = "$AppName.exe"

# 1. Build with PyInstaller if the dist output isn't there yet.
if (-not (Test-Path (Join-Path $DistDir $ExeName))) {
    Write-Host "Build output not found. Building with PyInstaller..." -ForegroundColor Cyan
    Push-Location $Root
    try {
        python -m PyInstaller "packaging\app.spec" --noconfirm
    } finally {
        Pop-Location
    }
}
if (-not (Test-Path (Join-Path $DistDir $ExeName))) {
    throw "Build did not produce $ExeName in $DistDir"
}

# 2. Copy the built app into %LOCALAPPDATA%\Programs\ZLibraryWrapper.
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
Write-Host "Installing to $InstallDir ..." -ForegroundColor Cyan
if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
Copy-Item (Join-Path $DistDir "*") $InstallDir -Recurse -Force

$ExePath = Join-Path $InstallDir $ExeName

# 3. Create Desktop + Start Menu shortcuts.
$WScript = New-Object -ComObject WScript.Shell
foreach ($dir in @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs")
)) {
    $lnk = Join-Path $dir "Z-Library.lnk"
    $sc = $WScript.CreateShortcut($lnk)
    $sc.TargetPath = $ExePath
    $sc.WorkingDirectory = $InstallDir
    $sc.IconLocation = $ExePath
    $sc.Description = "Search and download books from Z-Library"
    $sc.Save()
    Write-Host "Created shortcut: $lnk" -ForegroundColor Green
}

# 4. Seed a config template if the user doesn't have one yet.
$ConfigDir  = Join-Path $env:APPDATA $AppName
$ConfigFile = Join-Path $ConfigDir "config.ini"
if (-not (Test-Path $ConfigFile)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
    Copy-Item (Join-Path $Root "config.ini.example") $ConfigFile
    Write-Host ""
    Write-Host "A config file was created at:" -ForegroundColor Yellow
    Write-Host "    $ConfigFile"
    Write-Host "Open it and enter your Z-Library email and password before first launch."
}

Write-Host ""
Write-Host "Done. Launch 'Z-Library' from your Desktop." -ForegroundColor Green
