# -*- coding: utf-8 -*-
"""
端侧验收总闸：设备一上线，一条命令完成全部收尾。

流程:
  0) 定位 hdc、探测设备（无设备 → 打印待办清单退出码 2）
  1) 校准 5 处 TODO-verify：dumpLayout / click / inputText / keyEvent / screenshot
  2) 安装 HAP(pilot) + 拉起 + 截图/树探测
  3) 11 任务 × rules 基线真机跑一遍（自动调用 runner，backend=hdc）
  4) 产出 acceptance_report.md

用法:
  python scripts/device_acceptance.py --hap-dir C:/benchdata/apps --tasks apps --out runs/device_acceptance
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))

from hos_device import HOSDevice, _find_hdc  # noqa: E402
from runner import load_config, run_task  # noqa: E402

PILOT = "privacy-full"


def hdc(raw_args: list, timeout: int = 30):
    h = _find_hdc()
    if not h:
        raise RuntimeError("未找到 hdc")
    return subprocess.run([h] + raw_args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def calibrate(dev: HOSDevice, report: list):
    probes = []
    for name, fn in [
        ("dumpLayout", lambda: dev.dump_tree()),
        ("screenshot", lambda: dev.screenshot(Path("_acc_shot.png"))),
        ("click", lambda: (dev.click(1, 1), "dry-run")),
        ("inputText", lambda: (dev.input_text("0"), "dry-run")),
        ("keyEvent", lambda: (dev.key("back"), "dry-run")),
    ]:
        try:
            r = fn()
            ok = True
            detail = (str(r)[:200] if name == "dumpLayout" else ("dry-run" if isinstance(r, tuple) else "OK"))
        except Exception as e:
            ok, detail = False, str(e)[:200]
        probes.append((name, ok, detail))
        report.append(f"- {name}: {'✅' if ok else '❌'} {detail}")
    return probes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hap-dir", default="C:/benchdata/apps")
    ap.add_argument("--tasks", default="apps")
    ap.add_argument("--out", default="runs/device_acceptance")
    ap.add_argument("--config", default="harness/config.json")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = [f"# 端侧验收报告（{datetime.now().isoformat(timespec='minutes')}）", ""]

    # 0) 设备探测
    try:
        listed = hdc(["list", "targets"]).stdout.strip()
    except RuntimeError as e:
        print(f"[acceptance] 未找到 hdc：{e}")
        sys.exit(3)
    if not listed or listed.startswith("[Empty]"):
        print("[acceptance] 设备未在线。待办：DevEco Device Manager → 创建并启动手机模拟器（或连接真机）→ 再跑本脚本。")
        sys.exit(2)
    sn = listed.splitlines()[0].split()[0]
    report.append(f"- 设备: {sn}")
    dev = HOSDevice(hdc="auto", sn=sn)

    # 1) 命令校准
    report.append("## 命令校准")
    calibrate(dev, report)
    try:
        dev.wake()
    except Exception:
        pass

    # 2) pilot 安装与观测
    report.append("## Pilot 安装与观测")
    hap_dir = Path(args.hap_dir)
    haps = sorted(hap_dir.rglob("*.hap"))
    if not haps:
        report.append("- ❌ 无 HAP（先构建：gen_hap.py --build，路径用 ASCII 目录如 C:/benchdata/apps）")
    else:
        pilot_hap = next((p for p in haps if PILOT in str(p)), haps[-1])
        try:
            dev.install(str(pilot_hap))
            dev.start("com.bench.privacyfull", "EntryAbility")
            time.sleep(3)
            tree = dev.dump_tree()
            n = len(tree.get("nodes", []))
            shot = dev.screenshot(out / "_acc_pilot.png")
            report.append(f"- ✅ install+launch；树节点 {n}；截图 {shot.name}")
        except Exception as e:
            report.append(f"- ❌ pilot: {e}")

    # 3) rules 基线真机跑 11 任务
    report.append("## rules 基线真机跑")
    cfg = load_config(args.config if Path(args.config).exists() else None)
    task_paths = sorted(Path(args.tasks).glob("*/task.json"))
    summary = []
    for tp in task_paths:
        try:
            r = run_task(tp, hap_dir, "rules", cfg, out, shots=True, seed=0, backend="hdc")
            summary.append(f"{r['task_id']}: {'✅' if r['success'] else '❌ ' + str(r['fail_reason'])} {r['steps']}步")
        except Exception as e:
            summary.append(f"{tp.parent.name}: ❌ {e}")
    report.append("")
    report.extend(f"- {s}" for s in summary)

    (out / "acceptance_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    print(f"\n[acceptance] 报告: {out / 'acceptance_report.md'}")


if __name__ == "__main__":
    main()