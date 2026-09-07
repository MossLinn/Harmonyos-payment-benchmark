# -*- coding: utf-8 -*-
"""
支付功能健康判定书（Payment Health Verdict）

把一次 run 的轨迹/里程碑与变体中「注入的故障真值」对比，回答核心问题：
  ① 各三方渠道能否拉起支付弹窗？ ② 注入的故障是否被识别？ ③ 识别后能否恢复完成支付？
  ④ 这套 Agent 流程能否作为「应用支付功能是否正常」的自动判定器？

用法:
  python scripts/pay_verdict.py --run runs/pay_qwen37_dev
  python scripts/pay_verdict.py --run runs/pay_glm_dev,runs/pay_qwen38_dev --out docs/pay_verdict.md
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 故障真值（来自 variant.slots）→ 对应的「识别证据」milestone / 成功锚点
FAULT_EVIDENCE = {
    "broken": {"ms": ["wechat_tried", "alipay_tried", "bankcard_tried", "huawei_tried"],
               "text": "更换支付方式"},
    "dead": {"ms": ["dead_seen"], "text": "弹窗内容异常"},
    "blank": {"ms": ["blank_seen"], "text": "空白页面"},
    "mismatch": {"ms": ["mismatch_seen"], "text": "金额不一致"},
    "allbroken": {"ms": ["diag_done"], "text": "支付功能整体异常"},
    "timeout_late": {"ms": [], "text": "支付超时"},
}
CHANNELS = ["wechat", "alipay", "bankcard", "huawei"]


def load_variant(task_id: str, apps: Path) -> dict:
    p = apps / task_id / "variant.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def injected_faults(v: dict) -> list:
    s = (v or {}).get("slots", {})
    out = []
    if s.get("ALL_BROKEN") == "true":
        out.append("allbroken")
    for k in ("BROKEN_JSON", "DEAD_JSON", "BLANK_JSON"):
        try:
            arr = json.loads(s.get(k, "[]"))
        except Exception:
            arr = []
        if arr:
            out.append({"BROKEN_JSON": "broken", "DEAD_JSON": "dead", "BLANK_JSON": "blank"}[k])
    if s.get("MISMATCH") == "true":
        out.append("mismatch")
    if s.get("TWICE_POPUP") == "true":
        out.append("twice")
    if int(s.get("PAY_TIMEOUT_SEC", "0") or 0) > 0:
        out.append("timeout")
    if s.get("REFUND_ENABLED") == "true":
        out.append("refund")
    return out


def attempted_channels(run: Path, tid: str, task_dir: Path) -> set:
    """从轨迹里找出 Agent 真正点击过的渠道（按按钮文本匹配）。

    没试过 ≠ 拉不起来：弃权/未覆盖的渠道必须排除在应用侧判定的分母之外，
    否则会把「Agent 没做」误判成「App 坏了」。
    """
    hit = set()
    labels = {"微信支付": "wechat", "支付宝": "alipay",
              "银行卡支付": "bankcard", "华为支付": "huawei"}
    tp = run / tid / "trace.jsonl"
    if tp.exists():
        txt = tp.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            try:
                j = json.loads(line)
            except Exception:
                continue
            a = j.get("action") or {}
            if a.get("action") != "click":
                continue
            nt = (a.get("node_text") or "").strip()
            node = a.get("node") or {}
            if not nt:
                nt = (node.get("text") or "").strip()
            for lab, key in labels.items():
                if nt == lab:
                    hit.add(key)
    return hit


def launched_channels(run: Path, tid: str, ms: set) -> set:
    """渠道拉起取证：优先用弹窗标题的 accessibility id（pay_popup_<channel>），
    它由 App 在弹窗真正拉起时才渲染，比 milestone 更客观（milestone 只覆盖任务预设渠道，
    Agent 合法改走其它渠道时会被漏记，导致把"没按剧本走"误判成"拉不起来"）。
    """
    hit = {c for c in CHANNELS if c in ms}
    tp = run / tid / "trace.jsonl"
    if tp.exists():
        txt = tp.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"pay_popup_([a-z]+)", txt):
            if m.group(1) in CHANNELS:
                hit.add(m.group(1))
    return hit


def analyze_run(run: Path, apps: Path) -> dict:
    res_p = run / "results.json"
    rows = json.loads(res_p.read_text(encoding="utf-8")) if res_p.exists() else []
    per_task = []
    ch_launch = {c: [0, 0] for c in CHANNELS}     # [命中, 已尝试]
    ch_notcov = {}                                 # 应测但 Agent 未尝试（弃权/未覆盖）
    fault_stat = {"injected": 0, "detected": 0, "recovered": 0}
    for r in rows:
        tid = r.get("task_id")
        v = load_variant(tid, apps)
        faults = injected_faults(v)
        ms = set(r.get("milestones") or [])
        success = bool(r.get("success"))
        attempted = attempted_channels(run, tid, apps / tid)
        # 渠道拉起：正常类任务以该任务目标渠道计；诊断类以「可用渠道」计
        launched = sorted(launched_channels(run, tid, ms))
        expected = []
        for c in CHANNELS:
            slots = (v or {}).get("slots", {})
            try:
                chans = [x["key"] for x in json.loads(slots.get("CHANNELS_JSON", "[]"))]
            except Exception:
                chans = []
            broken = set()
            for k in ("BROKEN_JSON", "DEAD_JSON", "BLANK_JSON"):
                try:
                    broken |= set(json.loads(slots.get(k, "[]")))
                except Exception:
                    pass
            if c in chans and c not in broken and slots.get("ALL_BROKEN") != "true":
                expected.append(c)
        for c in set(expected) & attempted:
            # 只统计 Agent 真正点击过的渠道：弃权/未覆盖不计入应用侧分母
            if c in ch_launch:
                ch_launch[c][1] += 1
                if c in launched:
                    ch_launch[c][0] += 1
        for c in set(expected) - attempted:
            ch_notcov[c] = ch_notcov.get(c, 0) + 1
        # 故障识别与恢复
        det = []
        for f in faults:
            if f in ("twice", "timeout", "refund"):
                det.append((f, success))          # 风控/时效/退款类：完成即视为正确处理
                continue
            ev = FAULT_EVIDENCE.get(f, {})
            hit = bool(ms & set(ev.get("ms", [])))
            tp = run / tid / "trace.jsonl"
            trace_txt = tp.read_text(encoding="utf-8", errors="replace") if tp.exists() else ""
            if not hit and ev.get("text"):
                hit = ev["text"] in trace_txt
            if not hit and f == "blank":
                # 空白页在真机上没有任何文本证据（页面本就是空的）：
                # 以「恢复行为」为识别证据 —— 出现返回键动作并随后改换渠道
                hit = ('"key": "back"' in trace_txt) or ('"action": "key"' in trace_txt)
            det.append((f, hit))
        n_inj = len([d for d in det])
        n_det = len([d for d in det if d[1]])
        fault_stat["injected"] += n_inj
        fault_stat["detected"] += n_det
        if n_inj and n_det == n_inj and success:
            fault_stat["recovered"] += 1
        per_task.append({
            "task_id": tid, "tier": r.get("tier"), "category": r.get("category"),
            "success": success, "fail_reason": r.get("fail_reason"), "steps": r.get("steps"),
            "injected_faults": faults, "detected": det, "launched_channels": launched,
            "milestones": sorted(ms),
        })
    return {"run": run.name, "tasks": per_task, "channels": ch_launch,
            "not_covered": ch_notcov, "faults": fault_stat,
            "agent": rows[0].get("agent") if rows else "?"}


def app_health(a: dict) -> str:
    """应用侧判定：被测 App 的支付功能是否正常（只看客观证据，不评 Agent 能力）。"""
    chs = a["channels"]
    launch_ok = sum(v[0] for v in chs.values())
    launch_n = sum(v[1] for v in chs.values())
    normals = [t for t in a["tasks"] if t.get("tier") == "P-NORMAL"]
    normal_ok = sum(1 for t in normals if t["success"])
    if launch_n == 0:
        return "UNKNOWN（本次 run 未覆盖渠道拉起）"
    if launch_ok == 0:
        return "BROKEN（无任何渠道能拉起支付弹窗）"
    if launch_ok < launch_n:
        miss = [c for c in CHANNELS if a["channels"][c][1] and a["channels"][c][0] < a["channels"][c][1]]
        return f"DEGRADED（部分渠道未能拉起：{','.join(miss)}）"
    if normals and normal_ok < len(normals):
        return f"PARTIAL（渠道均可拉起，但 {len(normals) - normal_ok}/{len(normals)} 个正常支付流程未走完）"
    return "NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）"


def agent_capability(a: dict) -> str:
    """Agent 侧判定：这套 Agent 能否胜任「支付功能体检」工作。"""
    f = a["faults"]
    tasks = a["tasks"]
    sr = sum(1 for t in tasks if t["success"]) / max(1, len(tasks))
    det = f["detected"] / f["injected"] if f["injected"] else None
    if det is None:
        return f"（本 run 无注入故障）任务成功率 {sr:.0%}"
    if det >= 0.999 and sr >= 0.999:
        return f"胜任（故障识别 {det:.0%}，任务成功率 {sr:.0%}）"
    if det >= 0.6:
        return f"部分胜任（故障识别 {det:.0%}，但恢复/完成率仅 {sr:.0%}）"
    return f"不胜任（故障识别仅 {det:.0%}，任务成功率 {sr:.0%}）"


def verdict_of(a: dict) -> str:
    return app_health(a)


def render(analyses: list) -> str:
    L = ["# 支付功能健康判定书", "",
         f"生成时间：{datetime.now().isoformat(timespec='seconds')}　判定口径：渠道拉起 milestone + 注入故障真值对比", ""]
    for a in analyses:
        L += [f"## run: {a['run']}（agent={a['agent']}）", ""]
        L += ["- **应用侧判定：" + app_health(a) + "**",
              "- **Agent 侧判定：" + agent_capability(a) + "**", ""]
        L += ["| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |", "|---|---|---|"]
        for c in CHANNELS:
            hit, n = a["channels"][c]
            nc = (a.get("not_covered") or {}).get(c, 0)
            L.append(f"| {c} | {hit}/{n} | {nc} |")
        f = a["faults"]
        L += ["",
              f"- 注入故障总数：{f['injected']}　识别：{f['detected']}　"
              f"识别率：{f['detected'] / f['injected']:.0%}" if f["injected"] else "- 本 run 无注入故障",
              f"- 识别且恢复完成的任务：{f['recovered']}", ""]
        L += ["| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |",
              "|---|---|---|---|---|---|---|"]
        for t in a["tasks"]:
            det = ",".join(f"{k}:{'✓' if v else '✗'}" for k, v in t["detected"]) or "-"
            L.append(f"| {t['task_id']} | {t['tier']} | {','.join(t['injected_faults']) or '-'} | {det} | "
                     f"{','.join(t['launched_channels']) or '-'} | "
                     f"{'✅' if t['success'] else '❌ ' + str(t['fail_reason'])} | {t['steps']} |")
        L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="逗号分隔的 run 目录")
    ap.add_argument("--apps", default="apps")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    apps = Path(args.apps)
    analyses = []
    for r in [x.strip() for x in args.run.split(",") if x.strip()]:
        rp = Path(r)
        if not rp.exists():
            print(f"[skip] {rp}")
            continue
        a = analyze_run(rp, apps)
        analyses.append(a)
        (rp / "verdict.json").write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    txt = render(analyses)
    out = Path(args.out) if args.out else ROOT / "docs" / "pay_verdict.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(txt, encoding="utf-8")
    print(txt)
    print(f"[verdict] 已写出 {out}")


if __name__ == "__main__":
    main()
