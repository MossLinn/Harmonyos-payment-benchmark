# -*- coding: utf-8 -*-
"""
支付专属指标：渠道拉起成功率（milestone 聚合）与判异常准确率。

用法:
  python scripts/pay_metrics.py --runs runs/pay_qwen37_dev,runs/pay_glm_dev,runs/pay_rules_dev,runs/pay_qwen38_dev
输出: docs/pay_metrics.md  + 控制台总表
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def collect(run_dir: str) -> dict:
    rows = []
    res = Path(run_dir) / "results.json"
    if res.exists():
        rows = json.loads(res.read_text(encoding="utf-8"))
    else:
        for sub in sorted(Path(run_dir).glob("*/results.json")):
            rows += json.loads(sub.read_text(encoding="utf-8"))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True, help="逗号分隔的 run 目录")
    args = ap.parse_args()

    table = []
    for run in [r.strip() for r in args.runs.split(",") if r.strip()]:
        rows = collect(run)
        ch_ok = defaultdict(int)
        ch_n = defaultdict(int)
        diag_ok = diag_n = 0
        norm_ok = norm_n = 0
        for r in rows:
            ok = bool(r.get("success"))
            if str(r.get("tier", "")).startswith("P-"):
                for m in r.get("milestones", []):
                    if m in {"wechat", "alipay", "bankcard", "huawei"}:
                        ch_ok[m] += 1
                    if m in {"wechat_tried", "dead_seen", "blank_seen", "diag_done"}:
                        ch_ok[m] += 1  # 诊断阶段证据也计入
                if str(r.get("tier")) == "P-NORMAL":
                    norm_n += 1
                    norm_ok += 1 if ok else 0
                    # 单渠道题：完成即该渠道拉起成功
                    for m in ("wechat", "alipay", "bankcard", "huawei"):
                        if m in r.get("milestones", []):
                            ch_n[m] += 1
                else:
                    diag_n += 1
                    diag_ok += 1 if ok else 0
                    for m in ("wechat", "alipay", "bankcard", "huawei"):
                        if m in r.get("milestones", []):
                            ch_n[m] += 1
        line = f"| {Path(run).name} | {norm_ok}/{norm_n} | {diag_ok}/{diag_n} |"
        for ch in ("wechat", "alipay", "bankcard", "huawei"):
            line += f" {ch_ok[ch]}/{ch_n.get(ch, '-') if ch_n.get(ch) else '-'} |"
        table.append(line)

    head = "| run | 完成(正常) | 判异常 | 微信拉起 | 支付宝拉起 | 银行卡拉起 | 华为拉起 |"
    sep = "|---|---|---|---|---|---|---|---|"
    print("\n".join([head, sep] + table))
    out = Path("docs/pay_metrics.md")
    out.write_text("# 支付指标（milestone 聚合）\n\n" + "\n".join([head, sep] + table) + "\n\n"
                   "渠道拉起 = 任务中出现对应品牌弹窗（确认支付按钮共存）的 milestone。", encoding="utf-8")
    print(f"[metrics] 已写出 {out}")


if __name__ == "__main__":
    main()