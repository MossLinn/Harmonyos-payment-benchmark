# -*- coding: utf-8 -*-
"""
黑帧影响分层分析（纯测量，不改被测对象）

交叉统计：任务是否需要输入支付密码 × 该 run 是否出现黑帧 × 任务是否成功。
用于量化验证一个论断：**纯视觉 agent 在鸿蒙支付密码环节会被平台防截屏致盲**，
因此支付类成绩必须按"是否需要输密码"分层解读。

黑帧判定直接对 run 目录里保存的截图逐张计算（复用 runner.is_black_frame：
灰度均值<=8 或暗像素占比>=98%）。

用法:
  python scripts/analyze_blackframe.py --runs runs/MAV3_pay768,runs/D3_qwen38lowres_dev
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from runner import is_black_frame  # noqa: E402


def needs_password(task_dir: Path) -> bool:
    for name in ("task.json",):
        p = task_dir / name
        if p.exists():
            try:
                t = json.loads(p.read_text(encoding="utf-8"))
                return bool((t.get("creds") or {}).get("pay_pwd"))
            except Exception:
                pass
    return False


def analyze(run: Path, apps: Path) -> list:
    rows = []
    for td in sorted(p for p in run.iterdir() if p.is_dir()):
        rp = td / "result.json"
        if not rp.exists():
            continue
        r = json.loads(rp.read_text(encoding="utf-8"))
        shots = sorted((td / "shots").glob("*.png")) if (td / "shots").exists() else []
        black = sum(1 for s in shots if is_black_frame(str(s)))
        task_dir = apps / td.name
        rows.append({
            "run": run.name,
            "task_id": td.name,
            "agent": r.get("agent") or "?",
            "needs_pwd": needs_password(task_dir),
            "shots": len(shots),
            "black": black,
            "success": bool(r.get("success")),
            "fail": r.get("fail_reason"),
            "steps": r.get("steps"),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--apps", default="apps")
    ap.add_argument("--out", default="docs/blackframe_impact.md")
    args = ap.parse_args()
    apps = Path(args.apps)
    rows = []
    for r in [x.strip() for x in args.runs.split(",") if x.strip()]:
        rp = Path(r)
        if not rp.is_absolute():
            rp = ROOT / rp
        if rp.exists():
            rows += analyze(rp, apps)
    if not rows:
        raise SystemExit("没有可分析的 run（需要 result.json 与 shots/）")

    L = ["# 黑帧影响分层分析", "",
         "黑帧判据：灰度均值 ≤8 或暗像素占比 ≥98%（`runner.is_black_frame`，真机标定）。", "",
         "| run | agent | 任务 | 需输密码 | 截图数 | 黑帧数 | 结果 | 步数 |",
         "|---|---|---|---|---|---|---|---|"]
    for x in rows:
        L.append(f"| {x['run']} | {x['agent']} | {x['task_id']} | {'是' if x['needs_pwd'] else '否'} | "
                 f"{x['shots']} | {x['black']} | {'✅' if x['success'] else '❌ ' + str(x['fail'])} | "
                 f"{x['steps']} |")

    # 交叉表
    def bucket(pred):
        sub = [x for x in rows if pred(x)]
        n = len(sub)
        ok = sum(1 for x in sub if x["success"])
        blk = sum(1 for x in sub if x["black"] > 0)
        return n, ok, blk

    L += ["", "## 交叉汇总", "",
          "| 分层 | 任务数 | 出现黑帧的任务 | 成功 | 成功率 |", "|---|---|---|---|---|"]
    for label, pred in [
        ("需要输密码", lambda x: x["needs_pwd"]),
        ("不需要输密码", lambda x: not x["needs_pwd"]),
        ("需要输密码 且 出现黑帧", lambda x: x["needs_pwd"] and x["black"] > 0),
        ("需要输密码 且 无黑帧", lambda x: x["needs_pwd"] and x["black"] == 0),
    ]:
        n, ok, blk = bucket(pred)
        rate = f"{ok / n:.0%}" if n else "-"
        L.append(f"| {label} | {n} | {blk} | {ok} | {rate} |")

    # 按 agent 是否具备组件树通道分组
    L += ["", "## 按 agent 类型", "",
          "| agent | 任务数 | 黑帧任务数 | 成功率 | 是否有组件树通道 |", "|---|---|---|---|---|"]
    agents = sorted({x["agent"] for x in rows})
    tree_capable = {"rules": "是（纯树）", "vlm": "是（树+图，黑帧自动降级）",
                    "mav3": "**否（纯视觉）**", "random": "是（纯树）"}
    for a in agents:
        n, ok, blk = bucket(lambda x, a=a: x["agent"] == a)
        L.append(f"| {a} | {n} | {blk} | {ok / n:.0%} | {tree_capable.get(a, '?')} |" if n else
                 f"| {a} | 0 | 0 | - | {tree_capable.get(a, '?')} |")

    out = ROOT / args.out
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[-14:]))
    print(f"\n[blackframe] 已写出 {out}")


if __name__ == "__main__":
    main()
