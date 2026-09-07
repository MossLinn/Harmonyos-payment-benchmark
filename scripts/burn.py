# -*- coding: utf-8 -*-
"""
批量烧预算驱动：任务 × 智能体 × 模型 × 种子 的矩阵运行器。

用法:
  python scripts/burn.py --tasks apps --agents rules,random --out runs/burn_20260813
  python scripts/burn.py --tasks apps --agents vlm --models doubao-seed-2.1-pro,glm-5.3-flash \
       --seeds 3 --limit 4 --out runs/burn_vlm --backend sim

每次运行都会汇总 token 记账与估算成本，并折算「如果 24h 不节流」的日消耗率，
直接对标 400M/日预算。
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))

from runner import load_config, run_task  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="apps", help="含 <id>/task.json 的目录")
    ap.add_argument("--agents", default="vlm", help="逗号分隔: vlm,rules,random")
    ap.add_argument("--models", default="", help="vlm 用的模型 id 列表（逗号分隔）")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="任务上限（0=全部）")
    ap.add_argument("--workers", type=int, default=4, help="并行任务数（sim 后端可开大；hdc 后端按设备数）")
    ap.add_argument("--max-tokens", type=int, default=0, help="累计 token 上限；达到后停止接收新任务（0=不限，用于按预算烧）")
    ap.add_argument("--config", default="harness/config.json")
    ap.add_argument("--backend", default="sim", choices=["hdc", "sim"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    base = Path(args.out) if args.out else Path("runs") / ("burn_" + datetime.now().strftime("%m%d_%H%M"))
    base.mkdir(parents=True, exist_ok=True)

    task_paths = sorted(Path(args.tasks).glob("*/task.json"))
    if args.limit:
        task_paths = task_paths[: args.limit]

    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    models = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else []
    if "vlm" in agents and not models:
        models = [cfg["model"]["model"]]

    t_start = time.time()
    jobs = []  # (agent_kind, mkey, seed, group, cfg_copy)
    for agent in agents:
        if agent == "vlm":
            combos = [(agent, m, s) for m in models for s in range(args.seeds)]
        else:
            combos = [(agent, agent, s) for s in range(args.seeds)]
        for agent_kind, mkey, seed in combos:
            slug = f"{agent_kind}"
            if agent_kind == "vlm":
                slug += f"_{mkey}"
            if args.seeds > 1:
                slug += f"_s{seed}"
            group = base / slug
            group.mkdir(parents=True, exist_ok=True)
            job_cfg = deepcopy(cfg)
            if agent_kind == "vlm":
                job_cfg["model"]["model"] = mkey
            jobs.append((agent_kind, seed, group, job_cfg))

    cancel_evt = None
    try:
        import threading as _t
        cancel_evt = _t.Event()
    except ImportError:
        pass

    def run_one(job):
        agent_kind, seed, group, job_cfg, tp = job
        if cancel_evt is not None and cancel_evt.is_set():
            return group, None
        r = run_task(tp, None, agent_kind, job_cfg, group, shots=False, seed=seed, backend=args.backend)
        return group, r

    task_jobs = []
    for agent_kind, seed, group, job_cfg in jobs:
        for tp in task_paths:
            task_jobs.append((agent_kind, seed, group, job_cfg, tp))

    group_rows: dict = {}
    all_rows = []
    budget_hit = False
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(run_one, j): j for j in task_jobs}
        for fut in as_completed(futs):
            group, r = fut.result()
            if r is not None:
                group_rows.setdefault(group, []).append(r)
                all_rows.append(r)
            if args.max_tokens > 0:
                used = sum(x.get("tokens", {}).get("prompt_tokens", 0) + x.get("tokens", {}).get("completion_tokens", 0)
                           for x in all_rows if x is not None)
                if used >= args.max_tokens:
                    if cancel_evt is not None:
                        cancel_evt.set()
                    for other in futs:
                        other.cancel()
                    budget_hit = True
                    print(f"[burn] 已达 token 上限 {args.max_tokens:,}，停止未启动任务（在途任务自然收尾）", flush=True)
                    break

    pending = [f for f in futs if not f.done() and not f.cancelled()]
    if budget_hit and pending:
        # 预算闸触发：等待在途任务自然结束，但不再提交新任务（cancel 已阻止未启动者）
        pass
    for group, rows in group_rows.items():
        rows.sort(key=lambda x: x.get("task_id", ""))
        (group / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    elapsed_s = time.time() - t_start
    minutes = max(elapsed_s / 60, 1e-6)
    total_in = sum(r.get("tokens", {}).get("prompt_tokens", 0) for r in all_rows)
    total_out = sum(r.get("tokens", {}).get("completion_tokens", 0) for r in all_rows)
    total_calls = sum(r.get("tokens", {}).get("calls", 0) for r in all_rows)
    rate_per_day = (total_in + total_out) / minutes * 1440
    print("\n==== 烧预算汇总 ====")
    print(f"运行数: {len(all_rows)} | 耗时 {elapsed_s:.0f}s")
    print(f"tokens: in={total_in:,} out={total_out:,} 合计={total_in + total_out:,} | 调用 {total_calls}")
    print(f"消耗速率: {(total_in + total_out) / minutes:,.0f} tokens/min")
    print(f"折算 24h 不节流: {rate_per_day:,.0f} tokens/日（预算 4 亿 = {rate_per_day / 4e8:.2%}）")
    print(f"结果目录: {base}")


if __name__ == "__main__":
    main()