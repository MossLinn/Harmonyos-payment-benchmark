# 端侧对照 Runbook（设备上线后照此执行）

目标：把模拟器赛道的成绩平移到真实鸿蒙设备，并量化「模拟 vs 真机」的漂移。

## 设备上线前（已完成）

- [x] 构建：11/11 BUILD OK（`C:\benchdata\apps\*`，hvigor 6.x）
- [x] 签名：11/11（`C:\benchdata\signed\com.bench.*-signed.hap`，本地 ECC 自签）
- [x] 预演基线：`runs/baseline_for_device/`（glm 文本 + doubao 视觉 × 11 任务，sim 后端）

## 设备上线（用户 GUI，一次）

1. DevEco → Device Manager → 新建 Phone 模拟器 → 下载系统镜像（同意协议）→ 启动；
   或 USB 连接 HarmonyOS NEXT 真机（开发者模式 + USB 调试）。
2. 校验：`hdc list targets` 非空。

## 我方的下一步（自动）

```powershell
# 1) 校准 TODO-verify + pilot + rules 全量（验收总闸）
python scripts/device_acceptance.py --hap-dir C:/benchdata/apps --tasks apps --out runs/device_acceptance

# 2) 三路真机对照（rules / glm 文本 / doubao 视觉）
python harness/runner.py --tasks apps --agent rules  --backend hdc --config harness/config.json        --out runs/device_rules
python harness/runner.py --tasks apps --agent vlm   --backend hdc --config harness/config_fast.json    --out runs/device_glm
python harness/runner.py --tasks apps --agent vlm   --backend hdc --config harness/config_vision.json  --out runs/device_doubao

# 3) 漂移分析：真机结果 vs runs/baseline_for_device 逐任务对比（SR/步数/行为指标）
```

## 判定与收官

- 三路真机结果写入 `docs/leaderboard.md`「真机榜」分栏；
- 逐任务 sim/真机 差异自动归档 `docs/device_drift.md`；
- 全部通过后 objective 标记完成。