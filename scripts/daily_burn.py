# -*- coding: utf-8 -*-
"""
每日 token 常驻燃烧器（C 套餐）

按日预算自动轮转模型/任务批次烧 token，写账本与晨报；支持随时用 STOP 文件叫停。

用法:
  python scripts/daily_burn.py --daily-budget 300000000 --workers 12 --backend sim
  python scripts/daily_burn.py --once --slice-tokens 5000000     # 只烧一片，便于计划任务分次调度

安全阀:
  - 每片(slice)上限 --slice-tokens，片间 sleep --sleep-s 秒；
  - 存在 STOP_BURN 文件（工作目录下）立刻停止；
  - 账本 ledger.json 按日期累计，达 --daily-budget 后当日不再启动新片。
"""
import argparse
import datetime as dt
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "runs" / "ledger.json"
REPORT_DIR = ROOT / "docs" / "reports"
CRED_FILE = Path(os.environ.get("DSH_HOME", str(Path.home() / ".dsh"))) / ".credentials.yaml"


def load_key() -> str:
    """优先环境变量；否则从 DSH 凭据文件读取（不把密钥写进任何产物）。"""
    k = os.environ.get("VOLC_API_KEY", "")
    if k:
        return k
    if CRED_FILE.exists():
        for line in CRED_FILE.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("VOLC_API_KEY:"):
                return line.split(":", 1)[1].strip()
    raise SystemExit("未找到 VOLC_API_KEY（环境变量或 DSH 凭据文件）")


def ledger_load() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    return {}


def ledger_save(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def today() -> str:
    return dt.date.today().isoformat()


def run_slice(model: str, cfg: str, tasks: str, workers: int, backend: str,
              slice_tokens: int, out: Path, seed: int) -> dict:
    env = dict(os.environ)
    env["VOLC_API_KEY"] = load_key()
    env["PYTHONIOENCODING"] = "utf-8"
    cmd = [sys.executable, str(ROOT / "scripts" / "burn.py"),
           "--tasks", tasks, "--agents", "vlm", "--models", model,
           "--seeds", "1", "--workers", str(workers), "--backend", backend,
           "--config", cfg, "--max-tokens", str(slice_tokens), "--out", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env, cwd=str(ROOT))
    tail = (r.stdout or "")[-1500:]
    used = 0
    for res in out.rglob("result.json"):
        try:
            j = json.loads(res.read_text(encoding="utf-8"))
            used += j.get("tokens", {}).get("prompt_tokens", 0) + j.get("tokens", {}).get("completion_tokens", 0)
        except Exception:
            pass
    return {"model": model, "tokens": used, "tail": tail, "rc": r.returncode}


def append_pay_verdict(day: str, report_path: Path) -> None:
    """若当日 run 覆盖支付任务，则把「支付功能健康判定」追加进晨报（C×D 联动）。"""
    runs = [p for p in (ROOT / "runs").glob(f"daily_{day.replace('-', '')}_*") if p.is_dir()]
    if not runs:
        return
    try:
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "pay_verdict.py"),
                            "--run", ",".join(str(x) for x in runs),
                            "--out", str(ROOT / "docs" / "reports" / f"pay_verdict_{day}.md")],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(ROOT), timeout=600)
        if r.returncode != 0:
            return
        lines = [ln for ln in (r.stdout or "").splitlines()
                 if "应用侧判定" in ln or "Agent 侧判定" in ln or ln.startswith("## run")]
        if lines:
            with open(report_path, "a", encoding="utf-8") as f:
                f.write("\n## 支付功能健康判定（当日 run）\n\n" + "\n".join(lines) + "\n")
    except Exception:
        pass


def morning_report(led: dict, day: str) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = led.get(day, {}).get("slices", [])
    tot = sum(r["tokens"] for r in rows)
    by_model = {}
    for r in rows:
        by_model[r["model"]] = by_model.get(r["model"], 0) + r["tokens"]
    L = [f"# 每日燃烧晨报 {day}", "",
         f"- 当日消耗: **{tot:,} tokens**（预算 {led.get(day, {}).get('budget', 0):,}，"
         f"占比 {tot / max(1, led.get(day, {}).get('budget', 1)):.1%}）",
         f"- 片数: {len(rows)}", "", "| 模型 | tokens |", "|---|---|"]
    for m, v in sorted(by_model.items(), key=lambda kv: -kv[1]):
        L.append(f"| {m} | {v:,} |")
    p = REPORT_DIR / f"burn_{day}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily-budget", type=int, default=300_000_000)
    ap.add_argument("--slice-tokens", type=int, default=5_000_000)
    ap.add_argument("--sleep-s", type=int, default=30)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--backend", default="sim", choices=["sim", "hdc"])
    ap.add_argument("--tasks", default="apps")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--models", default="glm-5.3-flash:6,qwen3.7-max:3,doubao-seed-2.1-pro:1",
                    help="model:weight 逗号列表")
    ap.add_argument("--once", action="store_true", help="只跑一片后退出（供计划任务分次调度）")
    ap.add_argument("--stop-file", default=str(ROOT / "STOP_BURN"))
    args = ap.parse_args()

    weights = []
    for part in args.models.split(","):
        if ":" in part:
            m, w = part.split(":", 1)
            weights.append((m.strip(), int(w)))
        else:
            weights.append((part.strip(), 1))
    cfg_map = {
        "glm-5.3-flash": "harness/config_fast.json",
        "qwen3.7-max": "harness/config_qwen37.json",
        "qwen3.8-max": "harness/config_qwenmax.json",
        "doubao-seed-2.1-pro": "harness/config_vision.json",
    }
    led = ledger_load()
    day = today()
    ent = led.setdefault(day, {"budget": args.daily_budget, "slices": []})
    stop = Path(args.stop_file)

    while True:
        if stop.exists():
            print(f"[burn] 检测到 {stop.name}，停止。")
            break
        used = sum(r["tokens"] for r in ent["slices"])
        if used >= args.daily_budget:
            print(f"[burn] 当日预算已达成 {used:,} / {args.daily_budget:,}，停止。")
            break
        model = random.choices([m for m, _ in weights], weights=[w for _, w in weights])[0]
        cfg = cfg_map.get(model, "harness/config_fast.json")
        stamp = dt.datetime.now().strftime("%H%M%S")
        out = ROOT / "runs" / f"daily_{day.replace('-', '')}_{stamp}"
        print(f"[burn] slice → {model} ({cfg}) 目标≤{args.slice_tokens:,} tokens", flush=True)
        res = run_slice(model, cfg, args.tasks, args.workers, args.backend,
                        args.slice_tokens, out, 0)
        ent["slices"].append({"model": model, "tokens": res["tokens"], "run": out.name,
                              "ts": dt.datetime.now().isoformat(timespec="seconds")})
        ledger_save(led)
        print(f"[burn] slice 完成: {res['tokens']:,} tokens（累计 {used + res['tokens']:,}）", flush=True)
        if args.once:
            break
        time.sleep(args.sleep_s)

    rep = morning_report(led, day)
    append_pay_verdict(day, rep)
    print(f"[burn] 晨报: {rep}")


if __name__ == "__main__":
    main()
