$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "Installing build dependencies..."
python -m pip install -e . -q
python -m pip install -r requirements-dev.txt -q

$ffmpegDir = Join-Path $ProjectRoot "ffmpeg"
New-Item -ItemType Directory -Force -Path $ffmpegDir | Out-Null

$ffmpegPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
$ffprobePath = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source

if (-not $ffmpegPath -or -not $ffprobePath) {
    Write-Host "FFmpeg not found in PATH. Installing via winget..."
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements | Out-Null
    $ffmpegPath = (Get-Command ffmpeg -ErrorAction SilentlyContinue).Source
    $ffprobePath = (Get-Command ffprobe -ErrorAction SilentlyContinue).Source
}

if (-not $ffmpegPath -or -not $ffprobePath) {
    throw "FFmpeg not found. Install with: winget install Gyan.FFmpeg"
}

Write-Host "Copying FFmpeg binaries..."
Copy-Item $ffmpegPath (Join-Path $ffmpegDir "ffmpeg.exe") -Force
Copy-Item $ffprobePath (Join-Path $ffmpegDir "ffprobe.exe") -Force

Write-Host "Running GUI smoke test..."
python -m converter.gui_smoke

Write-Host "Building executable with PyInstaller..."
python -m PyInstaller VideoConverter.spec --noconfirm --clean

$distDir = Join-Path $ProjectRoot "dist\VideoConverter"
$targetFfmpeg = Join-Path $distDir "ffmpeg"
New-Item -ItemType Directory -Force -Path $targetFfmpeg | Out-Null
Copy-Item (Join-Path $ffmpegDir "ffmpeg.exe") (Join-Path $targetFfmpeg "ffmpeg.exe") -Force
Copy-Item (Join-Path $ffmpegDir "ffprobe.exe") (Join-Path $targetFfmpeg "ffprobe.exe") -Force

Write-Host ""
Write-Host "Build complete."
Write-Host "Run: $distDir\VideoConverter.exe"
