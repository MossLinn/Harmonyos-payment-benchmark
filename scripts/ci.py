# -*- coding: utf-8 -*-
"""
置信区间/鲁棒性报告：对 burn 产出的多种子分组（`<base>/vlm_<model>_s<N>`）聚合：
逐任务 SR、种子间方差、Wilson 95% 置信区间、整体均值与区间。

用法:
  python scripts/ci.py --base runs/burn_robust5 --out docs/reports/robustness.md
"""
import argparse
import json
import math
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", default="docs/reports/robustness.md")
    args = ap.parse_args()
    base = Path(args.base)

    groups = sorted(base.glob("*_s*"))
    if not groups:
        raise SystemExit(f"未找到 *_s* 分组: {base}")
    per_task: dict[str, list[bool]] = {}
    model = ""
    for g in groups:
        res = g / "results.json"
        if not res.exists():
            continue
        for r in json.loads(res.read_text(encoding="utf-8")):
            model = f"{r.get('agent')}/{g.name.split('_s')[0]}"
            per_task.setdefault(r["task_id"], []).append(bool(r.get("success")))

    n_seeds = max(len(v) for v in per_task.values())
    rows = []
    for tid in sorted(per_task):
        v = per_task[tid]
        k = sum(v)
        lo, hi = wilson(k, len(v), z=1.96)
        rows.append((tid, k, len(v), lo, hi))
    total_k = sum(r[1] for r in rows)
    total_n = sum(r[2] for r in rows)
    tlo, thi = wilson(total_k, total_n)

    L = [f"# 鲁棒性/置信区间报告：{model}", ""]
    L += [f"- 种子数: {n_seeds} | 任务数: {len(rows)} | 总样本: {total_n}",
          f"- **总体 SR: {total_k}/{total_n} = {total_k / total_n:.1%}，95% 置信区间 [{tlo:.1%}, {thi:.1%}]**", ""]
    L += ["| 任务 | 成功/样本 | SR | 95% CI | 稳定性 |", "|---|---|---|---|---|"]
    for tid, k, n, lo, hi in rows:
        stable = "稳定" if (lo == hi == 1.0 or (lo > 0 and lo == hi)) else ("一致低" if hi < 0.2 else "波动")
        if k == n:
            stable = "全胜"
        elif k == 0:
            stable = "全败"
        L.append(f"| {tid} | {k}/{n} | {k / n:.0%} | [{lo:.0%}, {hi:.0%}] | {stable} |")
    txt = "\n".join(L) + "\n"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"[ci] 已写出 {out}")


if __name__ == "__main__":
    main()