@echo off
REM 每日 git 同步（登录自启动入口，无需管理员）
REM 保险丝：存在 STOP_GIT 则退出（删文件即恢复）
REM 行为：登录后立即同步一次，之后每 24 小时同步一次
:loop
if exist "E:\迅雷下载\harmony-login-benchmark\STOP_GIT" exit /b 0
"C:\python312\python.exe" "E:\迅雷下载\harmony-login-benchmark\scripts\git_sync.py"
timeout /t 86400 /nobreak >nul
goto loop