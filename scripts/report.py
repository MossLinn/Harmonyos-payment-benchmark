# -*- coding: utf-8 -*-
"""
周报生成器：汇总 runs/ 下全部实验结果，产出可发给老板/同事的周报。

用法:
  python scripts/report.py --runs runs --out docs/reports/weekly.md
  python scripts/report.py --runs runs --title "鸿蒙登录 Benchmark 周报 #1" --out reports/w1.md
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


def collect_run(root: Path) -> dict:
    """一个 run 目录（或其中的分组）→ 汇总数据。"""
    summary = {"name": root.name, "results": [], "taxonomies": []}
    for res in sorted(root.rglob("results.json")):
        try:
            rows = json.loads(res.read_text(encoding="utf-8"))
        except Exception:
            continue
        summary["results"].extend(rows if isinstance(rows, list) else [rows])
    for tax in sorted(root.rglob("taxonomy*.md")):
        summary["taxonomies"].append(str(tax).replace("\\", "/"))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default="runs")
    ap.add_argument("--title", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    runs_dir = Path(args.runs)
    groups = []
    for d in sorted(runs_dir.iterdir()) if runs_dir.exists() else []:
        if d.is_dir():
            g = collect_run(d)
            if g["results"]:
                groups.append(g)

    title = args.title or f"鸿蒙 App 登录 Benchmark 周报（{datetime.now().strftime('%Y-%m-%d')}）"
    L = [f"# {title}", ""]
    L += [f"- 生成时间: {datetime.now().isoformat(timespec='seconds')}",
          f"- 实验目录: `{args.runs}`（共 {len(groups)} 个有结果的 run）", ""]

    # 总榜
    L += ["## 智能体总榜", ""]
    L += ["| run | 任务数 | SR | 平均步(成功) | in/out tokens | 备注 |", "|---|---|---|---|---|---|"]
    all_rows = []
    for g in groups:
        rows = g["results"]
        all_rows.extend(rows)
        ok = [r for r in rows if r.get("success")]
        sr = len(ok) / max(1, len(rows))
        steps = sum(r.get("steps", 0) for r in ok) / max(1, len(ok))
        tin = sum(r.get("tokens", {}).get("prompt_tokens", 0) for r in rows)
        tout = sum(r.get("tokens", {}).get("completion_tokens", 0) for r in rows)
        agent = rows[0].get("agent", "?") if rows else "?"
        L.append(f"| {g['name']} | {len(rows)} | {sr:.0%} | {steps:.1f} | {tin:,}/{tout:,} | agent={agent} |")
    L.append("")

    # token 账本
    tin = sum(r.get("tokens", {}).get("prompt_tokens", 0) for r in all_rows)
    tout = sum(r.get("tokens", {}).get("completion_tokens", 0) for r in all_rows)
    L += ["## Token 账本", ""]
    L += [f"- 累计输入 tokens: {tin:,}", f"- 累计输出 tokens: {tout:,}",
          f"- 合计: {tin + tout:,}（预算 4 亿/日 = {(tin + tout) / 4e8:.4%}）", ""]

    # 分类学链接
    L += ["## 失败分类学索引", ""]
    any_tax = False
    for g in groups:
        for t in g["taxonomies"]:
            L.append(f"- [{t}]({t})")
            any_tax = True
    if not any_tax:
        L.append("（本周期暂无分类学产出）")
    L.append("")

    out = Path(args.out) if args.out else Path("docs/reports") / f"weekly_{datetime.now().strftime('%Y%m%d')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    print(f"[report] 已写出 {out}（{len(groups)} 个 run，{len(all_rows)} 条结果）")
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()