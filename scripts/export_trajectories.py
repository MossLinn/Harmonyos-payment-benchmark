# -*- coding: utf-8 -*-
"""
轨迹语料导出器：trace.jsonl + 截图 + UI 树 → SFT/DPO 训练友好 JSONL。

产出两档：
1. `*_pairwise.jsonl`：每步一条 {messages:[system,user(观测),assistant(动作JSON)], task_id, step, images[]}
2. `*_trajectory.jsonl`：每任务一条 {task_id, success, steps:[{obs_text, obs_tree, shot_rel, action}]}

用法:
  python scripts/export_trajectories.py --run runs/burn_scale2/vlm_glm-5.3-flash --out data/trajectories
"""
import argparse
import json
from pathlib import Path

SYSTEM_TMPL = ("你是鸿蒙 UI 自动化 Agent。任务：{instruction}。动作 JSON 格式："
               "{{\"action\":\"click|input|swipe|key|wait|done\", \"node_text\":\"...\", \"text\":\"...\"}}。"
               "点击优先用 node_text 指认可见组件文本。")


def collect_task_dirs(run: Path):
    out = []
    for d in sorted(run.iterdir()):
        if (d / "trace.jsonl").exists():
            out.append(d)
    return out


def export(task_dir: Path, out_dir: Path, traj_file, pair_file) -> dict:
    task_path = task_dir / "task.json"
    try:
        task = json.loads(task_path.read_text(encoding="utf-8"))
    except Exception:
        task = {"id": task_dir.name, "instruction": ""}
    system = {"role": "system", "content": SYSTEM_TMPL.format(instruction=task.get("instruction", ""))}
    shots_dir = task_dir / "shots"
    steps = []
    n_pairs = 0
    for line in (task_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            j = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "action" not in j:
            continue
        a = j.get("action") or {}
        obs_text = j.get("obs") or "[历史 run 未记录 obs 文本]"
        shot = j.get("shot")
        shot_rel = None
        if shot:
            p = Path(shot)
            if p.exists():
                shot_rel = str(p.relative_to(task_dir.parent.parent, walk_up=True) if False else p)
        obs = {
            "tree_snapshot": (task_dir / "tree.txt").read_text(encoding="utf-8")[:4000]
            if (task_dir / "tree.txt").exists() else "",
        }
        step = {"step": j.get("step"), "obs_text": obs_text[:4000], "action": a, "exec": j.get("exec"),
                "shot": str(shot_rel) if shot_rel else None,
                "verdict_success": j.get("verdict_success"), "verdict_forbid": j.get("verdict_forbid")}
        steps.append(step)
        user_text = f"[第{j.get('step')}步观测]\n{obs_text[:2000]}"
        pair = {"task_id": task.get("id", task_dir.name), "step": j.get("step"),
                "messages": [system, {"role": "user", "content": user_text},
                             {"role": "assistant", "content": json.dumps(a, ensure_ascii=False)}]}
        if shot_rel:
            pair["images"] = [str(shot_rel)]
        pair_file.write(json.dumps(pair, ensure_ascii=False).encode("utf-8") + b"\n")
        n_pairs += 1
    # 成功轨迹标注
    result_path = task_dir / "result.json"
    success = False
    if result_path.exists():
        try:
            success = bool(json.loads(result_path.read_text(encoding="utf-8")).get("success"))
        except Exception:
            pass
    traj = {"task_id": task.get("id", task_dir.name), "app_bundle": task.get("app_bundle"),
            "tier": task.get("tier"), "category": task.get("category"), "success": success, "steps": steps}
    traj_file.write(json.dumps(traj, ensure_ascii=False).encode("utf-8") + b"\n")
    return {"task_id": task.get("id", task_dir.name), "pairs": n_pairs, "steps": len(steps), "success": success}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="含 <task>/trace.jsonl 的 run 分组目录")
    ap.add_argument("--out", default="data/trajectories")
    args = ap.parse_args()
    run = Path(args.run)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    prefix = run.name
    traj_path = out / f"{prefix}_trajectory.jsonl"
    pair_path = out / f"{prefix}_pairwise.jsonl"
    summary = []
    with open(traj_path, "wb") as tf, open(pair_path, "wb") as pf:
        for d in collect_task_dirs(run):
            summary.append(export(d, out, tf, pf))
    print(f"[export] {len(summary)} 任务 → {pair_path} / {traj_path}")
    print(f"[export] pairwise 样本: {sum(s['pairs'] for s in summary)} | trajectory: {len(summary)} 条 | "
          f"成功轨迹: {sum(1 for s in summary if s['success'])}")
    (out / f"{prefix}_manifest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()