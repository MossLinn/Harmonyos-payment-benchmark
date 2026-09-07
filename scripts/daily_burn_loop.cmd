@echo off
REM 每日 token 燃烧器（开机自启入口，无需管理员）
REM 保险丝：若存在 STOP_BURN 文件则直接退出（删除该文件即启用自动燃烧）
if exist "E:\迅雷下载\harmony-login-benchmark\STOP_BURN" exit /b 0
cd /d "E:\迅雷下载\harmony-login-benchmark"
"C:\python312\python.exe" scripts\daily_burn.py --daily-budget 300000000 --workers 12 --backend sim >> "E:\迅雷下载\harmony-login-benchmark\runs\daily_burn.log" 2>&1
