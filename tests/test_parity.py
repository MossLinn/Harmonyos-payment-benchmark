# -*- coding: utf-8 -*-
"""
离线验收测试套件（无鸿蒙设备环境下的自动化防线）：
- 模拟器×模板 状态机闭环：规则基线在全部非视觉任务上应成功；
- 视觉门控任务：规则基线应失败（证明信息门控生效）；
- Judge 谓词、动作解析、trace 指标 单元测试。
用法: python tests/test_parity.py   （全部 PASS 退出码 0）
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))

import judge as judge_mod  # noqa: E402
from agents.vlm_agent import parse_action  # noqa: E402
from scorer import analyze_trace  # noqa: E402


RESULTS = []
def check(name, cond, detail=""):
    RESULTS.append((name, cond, detail))
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")


# 单任务闭环：sim + 规则基线 + judge
def run_task_rules(task_id: str, seed: int = 0) -> dict:
    from sim_ui import build_sim, load_variant_from_task_dir
    from agents.baselines import RuleAgent
    from judge import Judge
    task_dir = ROOT / "apps" / task_id
    v = load_variant_from_task_dir(task_dir)
    app = build_sim(v, seed)
    task = v["task"]
    agent = RuleAgent(task, {"max_steps": 40})
    jd = Judge(task)
    for step in range(1, 41):
        nodes = app.nodes()
        pre = jd.verdict(nodes)
        if pre.success:
            return {"ok": True, "steps": step - 1}
        a = agent.act("", None, step, nodes)
        if a is None:
            return {"ok": False, "reason": "agent_none", "steps": step - 1}
        if a.get("action") == "click" and a.get("node"):
            b = a["node"]["bounds"]
            app.click((b["l"] + b["r"]) // 2, (b["t"] + b["b"]) // 2)
        elif a.get("action") == "input":
            app.on_input(a.get("text", ""))
        elif a.get("action") == "swipe":
            app.on_swipe(a.get("direction", "up"))
        elif a.get("action") == "wait":
            app.on_wait(a.get("seconds", 1.0))
        # forbid 只在动作后状态上判定（与 runner 语义一致：动作前页面可见的文案不算误点）
        vd = jd.verdict(app.nodes())
        if vd.forbid:
            return {"ok": False, "reason": "forbid", "steps": step}
    return {"ok": False, "reason": "steps_exhausted", "steps": 40}


TOKEN_SOLVABLE = ["privacy-full", "privacy-mislead", "privacy-seg", "privacy-scroll",
                  "code-login", "code-nofill", "code-trap", "pwd-captcha", "pwd-lock"]
VISION_GATED = ["colorgate", "captcha-colortext"]


def main():
    for tid in TOKEN_SOLVABLE:
        r = run_task_rules(tid)
        check(f"rules 应解出 {tid}", r["ok"], f"steps={r['steps']} reason={r.get('reason')}")
    for tid in VISION_GATED:
        r = run_task_rules(tid)
        check(f"视觉门控应拦下 rules: {tid}", not r["ok"], f"reason={r.get('reason')}")

    # Judge 谓词单元测试
    nodes = [{"type": "Text", "text": "欢迎回来，您已成功登录", "id": "welcome_marker", "clickable": False}]
    check("judge success 谓词", judge_mod.evaluate({"all": [
        {"type": "text_contains", "value": "欢迎回来"},
        {"type": "id_contains", "value": "welcome_marker"}]}, nodes))
    check("judge forbid 谓词", judge_mod.evaluate({"type": "text_contains", "value": "广告"}, nodes) is False)

    # 动作解析兜底
    a = parse_action('我认为应该点击「稍后再说」跳过')
    check("中文点击兜底解析", a.get("action") == "click" and a.get("node_text") == "稍后再说", str(a))
    a2 = parse_action('{"action":"input","text":"123456"}')
    check("JSON 动作解析", a2.get("action") == "input" and a2.get("text") == "123456", str(a2))

    # trace 指标
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "trace.jsonl"
        p.write_text(json.dumps({"step": 1, "time_s": 1.0, "action": {"action": "click", "node_text": "A"}}) + "\n" +
                     json.dumps({"step": 2, "time_s": 2.0, "action": {"action": "click", "node_text": "A"}}) + "\n" +
                     json.dumps({"step": 3, "time_s": 3.0, "action": {"action": "wait", "reason": "unparseable"}}) + "\n",
                     encoding="utf-8")
        m = analyze_trace(p)
        # 子集断言：新增指标（如 black）不应导致既有断言失效
        expect = {"steps": 3, "repeats": 1, "wander": 0, "unparseable": 1, "wall_s": 2.0}
        check("trace 指标统计", all(m.get(k) == v for k, v in expect.items()), str(m))

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n==== 测试完成: {len(RESULTS) - len(failed)}/{len(RESULTS)} 通过 ====")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()