# Cattle & Horse Dashboard - one-click start
param([switch]$NoHerdr)

$Root = Split-Path $MyInvocation.MyCommand.Path -Parent
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$HerdrBin = Join-Path $Root "herdr.exe"
$NpxBin = "D:\program\npx.cmd"

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  Dashboard starting..." -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan

# 0) codex-relay (DeepSeek V4 proxy)
Write-Host "[0/4] codex-relay..." -ForegroundColor Yellow
$relayProc = Get-Process -Name "codex-relay" -ErrorAction SilentlyContinue
if (-not $relayProc) {
    $env:DEEPSEEK_API_KEY = "sk-REDACTED"
    Start-Process -FilePath "codex-relay" -ArgumentList @(
        "--upstream", "https://api.deepseek.com/v1",
        "--api-key", "sk-REDACTED",
        "--port", "4444"
    ) -NoNewWindow
    Start-Sleep 2
    Write-Host "  [0/4] done" -ForegroundColor Green
} else {
    Write-Host "  [0/4] already running" -ForegroundColor Green
}
setx DEEPSEEK_API_KEY "sk-REDACTED" | Out-Null

# 1) herdr daemon
if (-not $NoHerdr -and (Test-Path $HerdrBin)) {
    Write-Host "[1/4] herdr..." -ForegroundColor Yellow
    $proc = Get-Process -Name "herdr" -ErrorAction SilentlyContinue
    if (-not $proc) {
        Start-Process -FilePath $HerdrBin -ArgumentList "start" -NoNewWindow
        Write-Host "  [1/4] done" -ForegroundColor Green
    } else {
        Write-Host "  [1/4] already running" -ForegroundColor Green
    }
} else {
    Write-Host "[1/4] skip herdr" -ForegroundColor Yellow
}

# 2) Flask backend
Write-Host "[2/4] backend..." -ForegroundColor Yellow
$BackendPidFile = Join-Path $Root "backend.pid"
$oldPid = $null
if (Test-Path $BackendPidFile) {
    $content = Get-Content $BackendPidFile -Raw
    if ($content) { $oldPid = $content.Trim() }
}
if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
    Write-Host "  [2/4] already running (pid: $oldPid)" -ForegroundColor Green
} else {
    $p = Start-Process -FilePath "python" -ArgumentList "app.py" -WorkingDirectory $Backend -NoNewWindow -PassThru
    if ($p) { $p.Id | Out-File -FilePath $BackendPidFile -Encoding ascii }
    Write-Host "  [2/4] done (pid: $($p.Id))" -ForegroundColor Green
}

# 3) Vue frontend
Write-Host "[3/4] frontend..." -ForegroundColor Yellow
$FrontendPidFile = Join-Path $Root "frontend.pid"
$oldFPid = $null
if (Test-Path $FrontendPidFile) {
    $content = Get-Content $FrontendPidFile -Raw
    if ($content) { $oldFPid = $content.Trim() }
}
if ($oldFPid -and (Get-Process -Id $oldFPid -ErrorAction SilentlyContinue)) {
    Write-Host "  [3/4] already running (pid: $oldFPid)" -ForegroundColor Green
} else {
    if (Test-Path $NpxBin) {
        $p = Start-Process -FilePath $NpxBin -ArgumentList "vite --port 5401 --host" -WorkingDirectory $Frontend -NoNewWindow -PassThru
        if ($p) { $p.Id | Out-File -FilePath $FrontendPidFile -Encoding ascii }
        Write-Host "  [3/4] done (pid: $($p.Id))" -ForegroundColor Green
    } else {
        Write-Host "  [3/4] FAIL: npx not found at $NpxBin" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  All services started!" -ForegroundColor Green
Write-Host "  Dashboard: http://localhost:5401" -ForegroundColor White
Write-Host "  Backend:   http://localhost:5400/api/agents" -ForegroundColor White
Write-Host "  Relay:     http://localhost:4444 (DeepSeek V4)" -ForegroundColor White
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Stop all: Stop-Process -Name codex-relay,herdr,python,node -Force" -ForegroundColor DarkYellow
