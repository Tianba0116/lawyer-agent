# AI 法律助手 — PowerShell 启动入口
# 自动调用 Git Bash 执行 start.sh，避免 WSL 冲突

$GitBash = "C:\Program Files\Git\bin\bash.exe"

if (-not (Test-Path $GitBash)) {
    Write-Host "未找到 Git Bash: $GitBash" -ForegroundColor Red
    Write-Host "请安装 Git for Windows: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

& $GitBash "start.sh"
