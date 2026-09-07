# -*- coding: utf-8 -*-
"""MA-v3 横评聚合：读取 runs/MAV3EVAL_*，写 docs/mav3_eval_board.md。

对未跑满 16 题的模型标「进行中」，并统计 fail_reason 分布与 tokens。
"""
import glob
import json
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = ["qwen38max", "qwen38flash", "qwen37plus", "minimax", "hy3",
          "doubao", "glm53flash", "kimi"]
N_TASKS = 16


def load(name):
    rs = []
    for p in sorted(glob.glob(str(ROOT / "runs" / f"MAV3EVAL_{name}" / "*" / "result.json"))):
        try:
            rs.append(json.loads(open(p, encoding="utf-8").read()))
        except Exception:
            pass
    return rs


def render():
    rule = load("rules_dev")
    rows = [("规则基线(真机)", rule)]
    for m in MODELS:
        rows.append((m, load(m)))
    L = ["# MA-v3 真机横评结果（8 个多模态模型 × 新登录方式）", "",
         "> 由 `scripts/mav3_board.py` 聚合；未列全 16 题的模型仍在跑。", "",
         "| 模型 | SR | 步均 | tokens/题 | 状态 |", "|---|---|---|---|---|"]
    for name, rs in rows:
        if not rs:
            L.append(f"| {name} | — | — | — | 未开始 |")
            continue
        ok = sum(1 for r in rs if r.get("success"))
        steps = sum(r.get("steps", 0) for r in rs)
        tok = sum((r.get("tokens") or {}).get("prompt_tokens", 0) +
                  (r.get("tokens") or {}).get("completion_tokens", 0) for r in rs)
        stat = "完成" if len(rs) >= N_TASKS else f"进行中 {len(rs)}/{N_TASKS}"
        L.append(f"| {name} | {ok}/{len(rs)} | {steps / max(1, len(rs)):.1f} | "
                 f"{tok // max(1, len(rs)):,} | {stat} |")

    # fail_reason 分布
    L += ["", "## 失败原因分布（按模型）", "", "| 模型 | fail_reason | 计数 |", "|---|---|---|"]
    fr = Counter()
    for m in MODELS:
        for r in load(m):
            if not r.get("success"):
                fr[(m, r.get("fail_reason") or "?")] += 1
    for (m, f), c in fr.most_common():
        L.append(f"| {m} | {f} | {c} |")
    out = ROOT / "docs" / "mav3_eval_board.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return "\n".join(L)


if __name__ == "__main__":
    print(render())
    print("\n[board] 已写出 docs/mav3_eval_board.md")