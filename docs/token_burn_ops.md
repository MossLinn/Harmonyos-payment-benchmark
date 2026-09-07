# 每日 Token 常驻燃烧器（C 套餐运维手册）

## 一句话

`scripts/daily_burn.py` 按**日预算**自动轮转模型跑评测任务，写账本 + 晨报；
默认**处于保险丝状态（不燃烧）**，删掉一个文件即启用。

## 当前部署状态（本机已就位）

| 项 | 状态 |
|---|---|
| 燃烧脚本 | `scripts/daily_burn.py`（已实测：单片 128,017 tokens，账本+晨报正常） |
| 开机自启入口 | `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\daily_burn.cmd`（已放置） |
| **保险丝** | `E:\迅雷下载\harmony-login-benchmark\STOP_BURN` **当前存在 → 不会燃烧** |
| 计划任务（可选，需管理员） | 未注册（当前会话无提权权限）；用 `scripts\install_daily_burn.ps1` 以管理员身份运行即可注册每日 03:00 |
| 账本 | `runs/ledger.json`（按日期累计每片 tokens 与模型） |
| 晨报 | `docs/reports/burn_YYYY-MM-DD.md` |

## 启用 / 停用

```powershell
# 启用自动燃烧（删除保险丝）
Remove-Item E:\迅雷下载\harmony-login-benchmark\STOP_BURN

# 立刻停用（放回保险丝；已在跑的片会自然收尾）
Set-Content E:\迅雷下载\harmony-login-benchmark\STOP_BURN 'stop'

# 手动烧一片（不依赖自启）
python scripts/daily_burn.py --once --slice-tokens 5000000 --workers 12 --backend sim
```

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--daily-budget` | 300,000,000 | 当日 token 上限（达到即停）。你的额度是 4 亿/日，默认留 25% 余量给交互使用 |
| `--slice-tokens` | 5,000,000 | 单片上限（`burn.py --max-tokens` 透传），片间可中断 |
| `--models` | `glm-5.3-flash:6,qwen3.7-max:3,doubao-seed-2.1-pro:1` | `模型:权重` 轮转（便宜模型多烧、视觉模型少烧） |
| `--backend` | `sim` | `sim` 不占设备；`hdc` 需模拟器在线且串行 |
| `--workers` | 12 | 任务级并行 |
| `--once` | 关 | 只烧一片（适合计划任务分次调度） |

## 密钥处理

脚本优先读环境变量 `VOLC_API_KEY`，否则从 DSH 凭据文件
`%USERPROFILE%\.dsh\.credentials.yaml` 读取；**密钥不写入任何产物或日志**。

## 建议节奏

- 白天：`--backend sim --workers 12`（不抢设备，速率 ~150K tok/min）；
- 夜间：若要真机轨迹语料，改 `--backend hdc --workers 1`（设备串行，产出带截图样本，直接喂 B 的语料管线）；
- 每天看一眼 `docs/reports/burn_<date>.md` 与 `runs/ledger.json` 对账。