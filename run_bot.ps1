#!/usr/bin/env powershell
# 启动Bot并持续运行

$logFile = "logs\bot_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# 确保日志目录存在
if (!(Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

Write-Host "Starting bot..."
Write-Host "Log file: $logFile"

# 启动Python脚本并捕获输出
& python main.py *>&1 | Tee-Object -FilePath $logFile
