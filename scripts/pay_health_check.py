# -*- coding: utf-8 -*-
"""
支付功能健康体检（一条命令出判定书）

把「跑支付探针套件 → 采集渠道拉起证据 → 与注入故障真值对比 → 出双侧判定」串成单命令：

  # 离线模拟器（零 token，秒级；用于环境自检）
  python scripts/pay_health_check.py --backend sim --agent rules

  # 真机 + 视觉模型（消融胜出档：768px 降采样）
  python scripts/pay_health_check.py --backend hdc --agent vlm --config harness/config_vision_lowres.json

  # 只重新分析已有 run（不重跑）
  python scripts/pay_health_check.py --analyze runs/D3_rules_dev

输出：
  runs/healthcheck_<ts>_<agent>/…      轨迹与结果
  docs/reports/pay_health_<ts>.md      支付功能健康判定书（应用侧 + Agent 侧）
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def sh(cmd: list, **kw) -> subprocess.CompletedProcess:
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=str(ROOT), **kw)


def discover_pay_tasks(apps: Path) -> list:
    out = []
    for d in sorted(apps.iterdir()):
        if not d.is_dir() or not d.name.startswith("pay-"):
            continue
        if (d / "task.json").exists() and (d / "variant.json").exists():
            out.append(d)
    return out


def stage(task_dirs: list, stage_dir: Path) -> int:
    import shutil
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    for d in task_dirs:
        tgt = stage_dir / d.name
        tgt.mkdir()
        shutil.copy2(d / "task.json", tgt / "task.json")
        shutil.copy2(d / "variant.json", tgt / "variant.json")
    return len(task_dirs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="sim", choices=["sim", "hdc"])
    ap.add_argument("--agent", default="rules", choices=["rules", "vlm", "random"])
    ap.add_argument("--config", default="harness/config.json")
    ap.add_argument("--apps", default="apps")
    ap.add_argument("--only", default="", help="逗号分隔的任务 id 子集（默认全部 pay-* ）")
    ap.add_argument("--analyze", default="", help="跳过跑测，直接分析已有 run 目录")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.analyze:
        run_dir = Path(args.analyze)
        if not run_dir.is_absolute():
            run_dir = ROOT / run_dir
    else:
        apps = ROOT / args.apps
        tasks = discover_pay_tasks(apps)
        if args.only:
            want = {x.strip() for x in args.only.split(",") if x.strip()}
            tasks = [t for t in tasks if t.name in want]
        if not tasks:
            raise SystemExit("未发现支付任务（apps/pay-*）")
        stage_dir = ROOT / "_paycheck"
        n = stage(tasks, stage_dir)
        run_dir = ROOT / "runs" / f"healthcheck_{ts}_{args.agent}_{args.backend}"
        print(f"[health] 支付探针 {n} 个 | backend={args.backend} agent={args.agent} config={args.config}")
        r = sh([PY, "harness/runner.py", "--tasks", str(stage_dir), "--agent", args.agent,
                "--backend", args.backend, "--config", args.config, "--out", str(run_dir)])
        if r.returncode != 0:
            print(f"[health] runner 退出码 {r.returncode}（仍尝试出判定书）")

    # 判定书 + 指标
    rep = ROOT / "docs" / "reports" / f"pay_health_{ts}.md"
    sh([PY, "scripts/pay_verdict.py", "--run", str(run_dir), "--out", str(rep)])
    sh([PY, "scripts/pay_metrics.py", "--runs", str(run_dir)])

    # 一屏摘要
    vj = run_dir / "verdict.json"
    print("\n" + "=" * 62)
    if vj.exists():
        v = json.loads(vj.read_text(encoding="utf-8"))
        chs = v.get("channels", {})
        launch_ok = sum(x[0] for x in chs.values())
        launch_n = sum(x[1] for x in chs.values())
        f = v.get("faults", {})
        tasks = v.get("tasks", [])
        sr = sum(1 for t in tasks if t.get("success"))
        print(f"支付功能健康体检  run={run_dir.name}")
        print(f"  渠道拉起 : {launch_ok}/{launch_n} "
              f"({', '.join(f'{k} {x[0]}/{x[1]}' for k, x in chs.items() if x[1])})")
        print(f"  故障识别 : {f.get('detected', 0)}/{f.get('injected', 0)}　"
              f"识别且恢复: {f.get('recovered', 0)}")
        print(f"  任务通过 : {sr}/{len(tasks)}")
        print(f"  判定书   : {rep}")
    else:
        print(f"未生成 verdict.json，请检查 {run_dir}")
    print("=" * 62)


if __name__ == "__main__":
    main()
