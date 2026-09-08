# -*- coding: utf-8 -*-
from __future__ import annotations
"""
真机↔模拟器 漂移分析：对比 device_* 与 baseline_for_device 的逐任务结果。

用法:
  python scripts/device_drift.py
输出: docs/device_drift.md
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(rows, list):
            rows = [rows]
        return {r.get("task_id"): r for r in rows}
    except Exception:
        return None


def main():
    base = ROOT / "runs" / "baseline_for_device"
    sim_glm = load(base / "vlm_glm-5.3-flash" / "results.json")
    sim_db = load(base / "vlm_doubao-seed-2.1-pro" / "results.json")
    dev_rules = load(ROOT / "runs" / "device_rules11c" / "results.json")
    dev_glm = load(ROOT / "runs" / "device_glm11" / "results.json")
    dev_db = load(ROOT / "runs" / "device_doubao11" / "results.json")

    agents = [("rules", None, dev_rules), ("glm", sim_glm, dev_glm), ("doubao", sim_db, dev_db)]
    table = []
    for tid in sorted((dev_rules or {}).keys()):
        row = [tid]
        for name, sim, dev in agents:
            s = sim.get(tid) if sim else None
            d = dev.get(tid) if dev else None
            sv = f"{'✓' if s and s.get('success') else '✗'}({s.get('steps', '?')}步)" if s else "—"
            dv = f"{'✓' if d and d.get('success') else '✗'}({d.get('steps', '?')}步)" if d else "未跑"
            row.append(f"sim:{sv} dev:{dv}")
        table.append(row)

    L = ["# 真机↔模拟器 漂移分析", ""]
    L.append("| 任务 | rules(sim↔dev) | glm 文本(sim↔dev) | doubao 视觉(sim↔dev) |")
    L.append("|---|---|---|---|")
    for row in table:
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("说明：sim 列来自 runs/baseline_for_device（同 seed=1）；dev 列来自 device_* 三路真机跑。")
    L.append("步数与成败逐任务对照，供定位 sim↔真机 行为差（坐标/渲染/时序）。")
    out = ROOT / "docs" / "device_drift.md"
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"[drift] 已写出 {out}")
    print("\n".join(L))


if __name__ == "__main__":
    main()