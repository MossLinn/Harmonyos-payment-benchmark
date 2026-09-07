# -*- coding: utf-8 -*-
"""
汇总计分：读取 runs/<run>/results.json，输出分层成功率/步数/误点率/token 成本。
"""
import argparse
import json
import statistics
from pathlib import Path


def price(cfg: dict, r: dict) -> float:
    p = {"in_per_million": 1.0, "out_per_million": 3.0}
    p.update(cfg.get("token_price", {}))
    tok = r.get("tokens", {})
    return tok.get("prompt_tokens", 0) / 1e6 * p["in_per_million"] + \
        tok.get("completion_tokens", 0) / 1e6 * p["out_per_million"]


def analyze_trace(path: Path) -> dict:
    """从 trace.jsonl 提取行为指标：
    repeats=与上一步完全相同动作的步数（停滞）；wander=操作已填写输入框的步数（徘徊）；
    unparseable=动作解析失败的步数。"""
    m = {"steps": 0, "repeats": 0, "wander": 0, "unparseable": 0, "wall_s": 0.0, "black": 0}
    if not path.exists():
        return m
    prev = None
    prev_t = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "action" not in j:
            continue
        m["steps"] += 1
        t = j.get("time_s")
        if isinstance(t, (int, float)) and prev_t is not None:
            m["wall_s"] += max(0.0, t - prev_t)
        prev_t = t if isinstance(t, (int, float)) else prev_t
        a = j.get("action") or {}
        sig = (a.get("action"), a.get("node_text") or "", str(a.get("text") or ""))
        if prev is not None and sig == prev:
            m["repeats"] += 1
        prev = sig
        nt = a.get("node_text") or ""
        if nt.startswith("请输入") and "（" in nt:
            m["wander"] += 1
        if (a.get("reason") or "") == "unparseable":
            m["unparseable"] += 1
        if j.get("shot_black"):
            m["black"] += 1
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="runs/<run> 目录")
    ap.add_argument("--config", default="harness/config.json")
    args = ap.parse_args()
    run = Path(args.run)
    results = json.loads((run / "results.json").read_text(encoding="utf-8"))
    cfg = {}
    if Path(args.config).exists():
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    # 行为指标：从每任务 trace 中统计
    traces = {r["task_id"]: analyze_trace(run / r["task_id"] / "trace.jsonl") for r in results}
    agg = {}
    for m in traces.values():
        for k, v in m.items():
            agg[k] = agg.get(k, 0) + v

    ok = [r for r in results if r["success"]]
    tiers = sorted({r.get("tier") or "?" for r in results})
    lines = [f"# Benchmark 报告：{run.name}", ""]
    lines.append(f"- 任务数: {len(results)} | 成功: {len(ok)} ({len(ok)/max(1,len(results)):.1%})")
    lines.append(f"- 误点(forbid)失败: {sum(1 for r in results if r.get('fail_reason')=='forbid_misclick')}")
    if ok:
        lines.append(f"- 成功任务平均步数: {statistics.mean(r['steps'] for r in ok):.1f} "
                     f"(下界=1，越低越好)")
        lines.append(f"- 成功任务平均耗时: {statistics.mean(r['time_s'] for r in ok):.1f}s")
    tot_in = sum(r.get("tokens", {}).get("prompt_tokens", 0) for r in results)
    tot_out = sum(r.get("tokens", {}).get("completion_tokens", 0) for r in results)
    lines.append(f"- tokens 总消耗: in={tot_in:,} out={tot_out:,} （含网关缺 usage 时的估算）")
    lines.append(f"- 估算成本: ${sum(price(cfg, r) for r in results):.2f}")
    lines.append(f"- 行为指标（trace 汇总）: 重复步 {agg.get('repeats', 0)} | 徘徊步 {agg.get('wander', 0)} | "
                 f"unparseable {agg.get('unparseable', 0)} | 实跑步 {agg.get('steps', 0)} | "
                 f"步均墙钟 {agg.get('wall_s', 0) / max(1, agg.get('steps', 0) - 1):.1f}s | "
                 f"黑帧(防截屏) {agg.get('black', 0)}")
    lines.append("")
    lines.append("## 分层成功率")
    lines.append("| 层级 | 成功/总数 | SR |")
    lines.append("|---|---|---|")
    for t in tiers:
        subset = [r for r in results if r.get("tier") == t]
        lines.append(f"| {t} | {sum(1 for r in subset if r['success'])}/{len(subset)} | "
                     f"{sum(1 for r in subset if r['success'])/max(1,len(subset)):.1%} |")
    cats = sorted({r.get("category") or "?" for r in results})
    lines.append("")
    lines.append("## 类别明细")
    lines.append("| 类别 | SR | 均步 | 失败原因分布 |")
    lines.append("|---|---|---|---|")
    for c in cats:
        subset = [r for r in results if r.get("category") == c]
        fails = {}
        for r in subset:
            if not r["success"]:
                fails[r.get("fail_reason") or "?"] = fails.get(r.get("fail_reason") or "?", 0) + 1
        okc = [r for r in subset if r["success"]]
        steps = f"{statistics.mean(r['steps'] for r in okc):.1f}" if okc else "-"
        lines.append(f"| {c} | {sum(1 for r in subset if r['success'])}/{len(subset)} "
                     f"({sum(1 for r in subset if r['success'])/max(1,len(subset)):.1%}) | {steps} | {fails} |")

    # Milestone（阶段证据）聚合：支付渠道拉起、风控弹窗、故障识别等
    ms_count: dict = {}
    ms_tasks: dict = {}
    for r in results:
        for m in r.get("milestones", []) or []:
            ms_count[m] = ms_count.get(m, 0) + 1
            ms_tasks.setdefault(m, set()).add(r["task_id"])
    if ms_count:
        lines.append("")
        lines.append("## Milestone 阶段证据（渠道拉起 / 风控 / 故障识别）")
        lines.append("| milestone | 命中次数 | 覆盖任务数 |")
        lines.append("|---|---|---|")
        for m in sorted(ms_count, key=lambda k: -ms_count[k]):
            lines.append(f"| {m} | {ms_count[m]} | {len(ms_tasks[m])} |")

    report = "\n".join(lines) + "\n"
    (run / "report.md").write_text(report, encoding="utf-8")

    rows = [{"task_id": r["task_id"], "tier": r.get("tier"), "category": r.get("category"),
             "success": r["success"], "fail_reason": r.get("fail_reason"), "steps": r["steps"],
             "time_s": r["time_s"], "prompt_tokens": r.get("tokens", {}).get("prompt_tokens", 0),
             "completion_tokens": r.get("tokens", {}).get("completion_tokens", 0),
             "repeats": traces[r["task_id"]]["repeats"],
             "wander": traces[r["task_id"]]["wander"],
             "unparseable": traces[r["task_id"]]["unparseable"],
             "black_frames": traces[r["task_id"]]["black"],
             "wall_avg_s": round(traces[r["task_id"]]["wall_s"] / max(1, traces[r["task_id"]]["steps"] - 1), 1),
             "est_cost_usd": round(price(cfg, r), 4)} for r in results]
    (run / "summary.csv").write_text(
        ",".join(rows[0].keys()) + "\n" +
        "\n".join(",".join(str(r[k]) for k in rows[0]) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(report)
    print(f"已写出 {run / 'report.md'} 与 {run / 'summary.csv'}")


if __name__ == "__main__":
    main()