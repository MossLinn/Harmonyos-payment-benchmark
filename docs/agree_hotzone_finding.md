# 重大发现：支付协议勾选框「文字标签不可点」会让视觉智能体彻底卡死（B11 的由来）

## 现象

真机 D2 复验中，`pay-refund`（支付 + 风控二次确认 + 退款闭环）对两个 VLM 都是 22 步耗尽，
但**失败原因完全不同**，且都不是模型"不会做"。

## 分层取证（同一任务、同一设备、三个 Agent）

| Agent | 点击"我已阅读并同意《支付协议》"**文字标签** | 点击 **Checkbox 本体** | 树中出现"请先阅读并同意《支付协议》"报错的步数 | 结果 |
|---|---|---|---|---|
| 规则基线 | 0 | **1** | 0 | ✅ 7 步通过 |
| qwen3.8-max（视觉） | **6** | **0** | **4** | ❌ 22 步耗尽 |
| qwen3.7-max（文本） | 1 | 0 | 0 | ❌ 22 步耗尽（另有死因，见下） |

取证脚本口径：统计轨迹中 `action.node_text == "我已阅读并同意《支付协议》"` 的点击次数、
`action.node.type == "Checkbox"` 的点击次数、以及观测文本里出现协议未勾选报错的步数。

## 根因

模板里的协议行长这样：

```ts
Row({ space: 6 }) {
  Checkbox().select(this.agree).onChange((v: boolean) => { this.agree = v })
  Text('我已阅读并同意《支付协议》').fontSize(12)     // ← 没有 onClick
}
```

- 只有 `Checkbox` 本体（约 60×60px 的小方块）能切换状态；
- 旁边的**文字标签没有任何点击处理**，点它等于点空白；
- 规则基线靠 `type == "Checkbox"` 精确命中小方块 → 一次成功；
- 视觉模型看截图时，自然语言描述"点击协议文字"更符合直觉 → **反复点标签、状态永不变**，
  然后不断触发"请先阅读并同意《支付协议》"报错，直到步数耗尽。

这是真实 App 里极其常见的一类可用性/无障碍缺陷：**勾选热区过小、标签未与勾选框关联**。

## 处置（两手）

### 1) 修好基准默认布局（避免不公平题）

```ts
Row({ space: 6 }) { … }.width('100%')
  .onClick(() => { if (this.AGREE_TRAP !== 'true') { this.agree = true } })
```

整行可点、幂等置真（不与 Checkbox 的 onChange 互相抵消）；同时把勾选状态写进标签文本
（`✓ / 〇` 前缀），使**状态在组件树里可观测**，与 sim 的表示保持一致。

### 2) 固化为故意注入的故障类 B11「协议热区陷阱」

- 变体 `pay-agree-trap`：`AGREE_TRAP=true` → 只有小方块可点，标签点了没反应；
- 正确行为 = 精确点击勾选框本体；任务提示里明确告知"若反复出现协议未勾选提示，
  说明你点到的是文字标签"；
- milestone `agreed` 用 `✓` 取证（勾选状态真的变了，而不是点过了）；
- sim 侧同构建模：trap 模式下把该行拆成 `Checkbox(〇/✓, 可点)` + `Text(标签, 不可点)` 两个节点，
  与真机树结构一致；
- 规则基线新增兜底：`type=="Checkbox" 且文本含 〇 → 点击本体`，sim 实测 **5 步通过**。

## 另一个尚未定性的失败（诚实记录）

qwen3.7-max（文本）在同一任务上**没有**协议报错（0 步），却 8 次点击"确认支付"而无状态推进。
说明它的死因不是热区问题，候选解释：① 二次确认弹窗与原弹窗的按钮同文案，模型无法从纯文本
区分当前处于哪一层；② 中途出现输入法裁剪（本 run 的裁剪检测口径只看末步观测，可能漏记）。
修复模板后的 D3 真机复验会重新观察该题；若仍失败，将单独立项定性。

## 复现

```powershell
python - <<'PY'
import json
from pathlib import Path
for run in ["D2_rules_dev", "D2_qwen37_dev", "D2_qwen38_dev"]:
    p = Path("runs")/run/"pay-refund"/"trace.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    label = sum(1 for r in rows if (r.get("action") or {}).get("node_text") == "我已阅读并同意《支付协议》")
    box   = sum(1 for r in rows if ((r.get("action") or {}).get("node") or {}).get("type") == "Checkbox")
    err   = sum(1 for r in rows if "请先阅读并同意" in (r.get("obs") or ""))
    print(run, "点标签", label, "点勾选框", box, "报错步", err)
PY
```
