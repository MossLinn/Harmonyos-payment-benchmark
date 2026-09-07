# HarmonyOS 支付功能 Benchmark

衡量 VLM/Agent 在真实鸿蒙设备上「拉起并完成第三方支付」的能力与成本，含故障/风控诊断（B1~B11）与同文异色视觉门控。

- 支付模板：`app-factory/templates/PaymentPage.ets`
- 支付变体：87 个（4 渠道 × 正常 + 故障/风控 + 视觉门控，精选 + 矩阵）
- 双后端：`sim`（离线秒级）/ `hdc`（鸿蒙模拟器）
- Agent：Mobile-Agent-v3 / 规则基线 / 随机
- 判定：渠道拉起证据 + 应用侧/Agent 侧健康判定书（见 `docs/pay_verdict.md`）

## 一键跑
```bash
python scripts/pay_health_check.py            # 全渠道健康自检
python harness/runner.py --tasks apps --agent rules --backend sim   # 规则基线
python scripts/run_mav3.py --tasks apps --model qwen3.8-flash --backend sim  # MA-v3 (需 VOLC_API_KEY)
```
