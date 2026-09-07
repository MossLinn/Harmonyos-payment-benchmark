# -*- coding: utf-8 -*-
"""
A 套餐消融结论生成器：读取 runs/A_* 各臂结果，自动产出对照表与结论。

用法:
  python scripts/ablation_report.py                 # 自动发现 runs/A_*
  python scripts/ablation_report.py --arms runs/A_baseline_v2,runs/A_text,runs/A_lowres,runs/A_promptv2
输出: docs/ablation_A_results.md
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from scorer import analyze_trace  # noqa: E402

ARM_LABEL = {
    "A_baseline": "基线(树+原图)",
    "A_baseline_v2": "基线v2(+黑帧降级)",
    "A_text": "纯文本(无图)",
    "A_lowres": "降采样768+短输出",
    "A_promptv2": "推进纪律v2",
}


def load_arm(arm_dir: Path) -> dict:
    out = {}
    res = arm_dir / "results.json"
    rows = []
    if res.exists():
        rows = json.loads(res.read_text(encoding="utf-8"))
    else:
        for sub in sorted(arm_dir.glob("*/result.json")):
            rows.append(json.loads(sub.read_text(encoding="utf-8")))
    for r in rows:
        tid = r.get("task_id")
        tr = analyze_trace(arm_dir / tid / "trace.jsonl")
        out[tid] = {
            "success": bool(r.get("success")),
            "fail": r.get("fail_reason"),
            "steps": r.get("steps", 0),
            "time_s": r.get("time_s", 0),
            "tok": r.get("tokens", {}).get("prompt_tokens", 0) + r.get("tokens", {}).get("completion_tokens", 0),
            "black": tr.get("black", 0),
            "repeats": tr.get("repeats", 0),
            "wander": tr.get("wander", 0),
            "wall_avg": (tr.get("wall_s", 0) / max(1, tr.get("steps", 0) - 1)) if tr.get("steps", 0) > 1 else 0,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="")
    ap.add_argument("--out", default="docs/ablation_A_results.md")
    args = ap.parse_args()

    if args.arms:
        arm_dirs = [Path(x.strip()) for x in args.arms.split(",") if x.strip()]
    else:
        arm_dirs = sorted(p for p in (ROOT / "runs").glob("A_*") if p.is_dir())
    arms = {}
    for d in arm_dirs:
        if not d.exists():
            continue
        data = load_arm(d if d.is_absolute() else ROOT / d)
        if data:
            arms[d.name] = data
    if not arms:
        raise SystemExit("未发现任何 A_* 臂结果")

    tasks = sorted({t for a in arms.values() for t in a})
    L = ["# A 套餐消融结果（自动生成）", "",
         f"臂数：{len(arms)}　题数：{len(tasks)}　来源：{', '.join(arms.keys())}", ""]

    # 逐题对照
    L += ["## 逐题对照", "", "| 任务 | " + " | ".join(ARM_LABEL.get(a, a) for a in arms) + " |",
          "|---|" + "---|" * len(arms)]
    for t in tasks:
        cells = []
        for a in arms:
            d = arms[a].get(t)
            if not d:
                cells.append("—")
            else:
                mark = "✅" if d["success"] else f"❌{d['fail'] or ''}"
                cells.append(f"{mark} {d['steps']}步 {d['tok']//1000}K 黑{d['black']}")
        L.append(f"| {t} | " + " | ".join(cells) + " |")

    # 臂级汇总
    L += ["", "## 臂级汇总", "",
          "| 臂 | SR | tokens 合计 | 步均墙钟 | 黑帧合计 | 重复步 | 徘徊步 |",
          "|---|---|---|---|---|---|---|"]
    for a in arms:
        ds = list(arms[a].values())
        sr = sum(1 for d in ds if d["success"])
        walls = [d["wall_avg"] for d in ds if d["wall_avg"]]
        L.append(f"| {ARM_LABEL.get(a, a)} | {sr}/{len(ds)} | {sum(d['tok'] for d in ds):,} | "
                 f"{statistics.mean(walls):.1f}s | {sum(d['black'] for d in ds)} | "
                 f"{sum(d['repeats'] for d in ds)} | {sum(d['wander'] for d in ds)} |")

    # 自动结论
    L += ["", "## 自动判读", ""]
    names = list(arms)
    base = next((n for n in ("A_baseline_v2", "A_baseline") if n in arms), names[0])

    def sr_of(n):
        ds = list(arms[n].values())
        return sum(1 for d in ds if d["success"]) / max(1, len(ds))

    def tok_of(n):
        return sum(d["tok"] for d in arms[n].values())

    for n in names:
        if n == base:
            continue
        d_sr = sr_of(n) - sr_of(base)
        d_tok = (tok_of(n) - tok_of(base)) / max(1, tok_of(base))
        L.append(f"- **{ARM_LABEL.get(n, n)}** vs {ARM_LABEL.get(base, base)}："
                 f"SR {d_sr:+.0%}，tokens {d_tok:+.0%}")
    black_total = sum(d["black"] for a in arms.values() for d in a.values())
    if black_total:
        L.append(f"- 全部臂累计黑帧 {black_total} 步 → 支付/密码类任务的视觉观测在真机上不可用，"
                 "必须以 UI 树为准（见 docs/blackscreen_finding.md）")
    text_arm = arms.get("A_text", {})
    if text_arm:
        gate = [t for t in text_arm if "colortext" in t or "colorgate" in t]
        if gate:
            L.append("- 图像必要性：" + "；".join(
                f"{t} 纯文本臂={'通过' if text_arm[t]['success'] else '失败'}" for t in gate))

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\n[ablation] 已写出 {out}")


if __name__ == "__main__":
    main()
