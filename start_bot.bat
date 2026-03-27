@echo off
chcp 65001 >nul
echo ========================================
echo 启动 Emos Magic Bot
echo ========================================

:: 设置代理环境变量（根据您的 Clash/V2Ray 配置修改）
:: 如果 Clash 使用不同端口，请修改以下值
set DB_PROXY_HOST=127.0.0.1
set DB_PROXY_PORT=7890

echo.
echo 代理配置: %DB_PROXY_HOST%:%DB_PROXY_PORT%
echo.

:: 检查锁文件
if exist bot.lock (
    echo 检测到锁文件，尝试清理...
    del /f bot.lock 2>nul
)

echo 启动机器人...
python main.py

pause
