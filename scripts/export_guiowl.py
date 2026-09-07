# -*- coding: utf-8 -*-
"""
GUI-Owl 训练语料适配器（B 套餐）

把 harness 的 trace（含真机/模拟器截图 + UI 树观测 + 动作）转成 GUI-Owl 风格 SFT/DPO 语料：
  - guiowl_sft.jsonl : 每步一条 {image, screen_size, query, action, action_code, ...}
  - guiowl_dpo.jsonl : 同任务「成功轨迹步」为 chosen、「失败/徘徊步」为 rejected 的偏好对
  - manifest.json    : 计数、坐标空间、来源 run、字段说明

动作代码化（action_code，GUI-Owl 常见风格）：
  click(x, y) / long_click(x, y) / type("text") / swipe(x1,y1,x2,y2) / back() / wait(s) / done()

注意：GUI-Owl 1.5 的官方样本字段名如与此不同，只需改 FIELD_MAP 一处即可对齐。
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 若内网 GUI-Owl 数据管线字段名不同，改这里
FIELD_MAP = {
    "image": "image",
    "query": "query",
    "action": "action",
    "action_code": "action_code",
    "screen_size": "screen_size",
}


def action_code(a: dict) -> str:
    k = a.get("action")
    if k == "click":
        x, y = int(a.get("x", 0) or 0), int(a.get("y", 0) or 0)
        node = a.get("node") or {}
        if not (x or y) and node:
            b = node.get("bounds", {})
            x = (b.get("l", 0) + b.get("r", 0)) // 2
            y = (b.get("t", 0) + b.get("b", 0)) // 2
        return f"click({x}, {y})"
    if k == "long_press":
        return f"long_click({int(a.get('x', 0))}, {int(a.get('y', 0))})"
    if k == "input":
        return 'type("{}")'.format(str(a.get("text", "")).replace('"', "'"))
    if k == "swipe":
        return f"swipe({a.get('direction', 'up')})"
    if k == "key":
        return f"{a.get('key', 'back')}()"
    if k == "wait":
        return f"wait({a.get('seconds', 1)})"
    if k == "done":
        return "done()"
    return f"{k}()"


def load_task(task_dir: Path) -> dict:
    p = task_dir / "task.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def process_run(run: Path, apps: Path, sft_fh, dpo_fh) -> dict:
    n_sft = n_img = 0
    per_task = {}
    for tdir in sorted(p for p in run.iterdir() if p.is_dir()):
        trace = tdir / "trace.jsonl"
        if not trace.exists():
            continue
        res_p = tdir / "result.json"
        result = json.loads(res_p.read_text(encoding="utf-8")) if res_p.exists() else {}
        task = load_task(apps / tdir.name) or {"instruction": "", "id": tdir.name}
        steps = []
        for line in trace.read_text(encoding="utf-8").splitlines():
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "action" not in j:
                continue
            steps.append(j)
        per_task[tdir.name] = {"success": bool(result.get("success")), "steps": steps,
                               "task": task, "run": run.name}
        # SFT：成功轨迹的每一步都是正样本；失败轨迹仅在显式 --include-failed 时收录
        if result.get("success"):
            for idx, j in enumerate(steps):
                shot = j.get("shot")
                img_abs = Path(shot) if shot else None
                has_img = bool(img_abs and img_abs.exists())
                if has_img:
                    n_img += 1
                rec = {
                    FIELD_MAP["image"]: str(img_abs) if has_img else None,
                    "screen_size": [1256, 2760] if has_img else None,
                    FIELD_MAP["query"]: task.get("instruction", ""),
                    "task_id": task.get("id", tdir.name),
                    "step": j.get("step"),
                    "obs_text": (j.get("obs") or "")[:2000],
                    FIELD_MAP["action"]: j.get("action"),
                    FIELD_MAP["action_code"]: action_code(j.get("action") or {}),
                    "source_run": run.name,
                    "agent": result.get("agent"),
                }
                sft_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n_sft += 1
    # DPO：同任务在不同 run 里有成功/失败时，用「成功轨迹首步 vs 失败轨迹同序步」构造偏好对
    return {"run": run.name, "sft": n_sft, "with_image": n_img, "tasks": per_task}


def build_dpo(all_tasks: list, dpo_fh) -> int:
    """同 task_id：成功轨迹的某步 = chosen；失败轨迹相同 step 的步 = rejected。"""
    bucket = {}
    for info in all_tasks:
        for tid, d in info["tasks"].items():
            b = bucket.setdefault(tid, {"ok": [], "bad": []})
            (b["ok"] if d["success"] else b["bad"]).append(d)
    n = 0
    for tid, b in bucket.items():
        if not b["ok"] or not b["bad"]:
            continue
        good = b["ok"][0]
        for bad in b["bad"]:
            for i in range(min(len(good["steps"]), len(bad["steps"]))):
                g, w = good["steps"][i], bad["steps"][i]
                if action_code(g.get("action") or {}) == action_code(w.get("action") or {}):
                    continue
                rec = {
                    "task_id": tid,
                    "step": i + 1,
                    "query": good["task"].get("instruction", ""),
                    "chosen": action_code(g.get("action") or {}),
                    "rejected": action_code(w.get("action") or {}),
                    "chosen_run": good["run"],
                    "rejected_run": bad["run"],
                }
                dpo_fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
                if n % 5000 == 0:
                    print(f"[dpo] {n} pairs...")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="逗号分隔的 run 目录（建议含真机 run，有截图）")
    ap.add_argument("--apps", default="apps")
    ap.add_argument("--out", default="data/guiowl")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    apps = Path(args.apps)
    all_infos = []
    with open(out / "guiowl_sft.jsonl", "w", encoding="utf-8") as sft, \
         open(out / "guiowl_dpo.jsonl", "w", encoding="utf-8") as dpo:
        for r in [x.strip() for x in args.runs.split(",") if x.strip()]:
            rp = Path(r)
            if not rp.exists():
                print(f"[skip] 不存在: {rp}")
                continue
            info = process_run(rp, apps, sft, dpo)
            all_infos.append(info)
            print(f"[{rp.name}] sft={info['sft']} with_image={info['with_image']}")
        n_dpo = build_dpo(all_infos, dpo)
    manifest = {
        "runs": [i["run"] for i in all_infos],
        "sft_samples": sum(i["sft"] for i in all_infos),
        "sft_with_image": sum(i["with_image"] for i in all_infos),
        "dpo_pairs": n_dpo,
        "coordinate_space": "设备物理像素（真机 run 为 1256x2760；sim run 为渲染画布坐标）",
        "field_map": FIELD_MAP,
        "note": "仅收录成功轨迹步作为 SFT 正样本；DPO 用同任务成功/失败轨迹的同序异动作步。",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[guiowl] SFT={manifest['sft_samples']}（含图 {manifest['sft_with_image']}）DPO={n_dpo} → {out}")


if __name__ == "__main__":
    main()
