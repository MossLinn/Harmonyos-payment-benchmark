# 以管理员身份运行本脚本，注册「每日 03:00 自动燃烧」计划任务（C 套餐的正式形态）
# 用法: 右键 PowerShell(管理员) → .\scripts\install_daily_burn.ps1
$ErrorActionPreference = 'Stop'
$py  = 'C:\python312\python.exe'
$scr = 'E:\迅雷下载\harmony-login-benchmark\scripts\daily_burn.py'
$tr  = "`"$py`" `"$scr`" --daily-budget 300000000 --workers 12 --backend sim"

schtasks /Create /TN 'DSH-DailyTokenBurn' /TR $tr /SC DAILY /ST 03:00 /F
Write-Host '已注册计划任务 DSH-DailyTokenBurn（每日 03:00）'

Write-Host ''
Write-Host '常用管理命令：'
Write-Host '  查看:  schtasks /Query /TN DSH-DailyTokenBurn /FO LIST /V'
Write-Host '  立即跑: schtasks /Run /TN DSH-DailyTokenBurn'
Write-Host '  停用:  schtasks /Change /TN DSH-DailyTokenBurn /DISABLE'
Write-Host '  删除:  schtasks /Delete /TN DSH-DailyTokenBurn /F'
Write-Host ''
Write-Host '另：无管理员权限时可用 scripts\daily_burn_loop.cmd 放入启动目录'
Write-Host "  shell:startup  （即 $env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup）"
Write-Host '  该脚本受 STOP_BURN 保险丝控制：存在该文件时不燃烧。'
