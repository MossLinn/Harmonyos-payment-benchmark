# 批量构建 variants/generated 下全部变体（并可选安装首台设备）
param(
  [switch]$Install,
  [int]$Limit = 0
)
$py = 'c:\python312\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }
$files = Get-ChildItem "app-factory/variants/generated/*.json" | Sort-Object Name
if ($Limit -gt 0) { $files = $files | Select-Object -First $Limit }
$i = 0
foreach ($f in $files) {
  $extra = ''
  if ($Install) { $extra = '--build --install' }
  & $py app-factory/gen_hap.py --variant $f.FullName --out apps $extra.Split(' ') 2>&1 | Out-Null
  $i++
}
Write-Host "built $i apps from variants/generated"