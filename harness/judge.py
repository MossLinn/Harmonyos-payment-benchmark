# -*- coding: utf-8 -*-
"""
任务判定器：在 UI 树快照上求值 goal.success / goal.forbid 谓词。
谓词语法见 app-factory/variants/README.md 与 docs/spec.md §4。
"""
from typing import Any


class Verdict:
    def __init__(self, success: bool, forbid: bool, reasons: list[str]):
        self.success = success
        self.forbid = forbid
        self.reasons = reasons


def _leaf(pred: dict, nodes: list[dict]) -> bool:
    t = pred.get("type")
    if t == "text_contains":
        v = pred.get("value", "")
        return any(v in (n.get("text") or "") for n in nodes)
    if t == "id_contains":
        v = pred.get("value", "")
        return any(v in (n.get("id") or "") for n in nodes)
    if t == "exists":
        return True  # 由文本/ID 谓词承载存在性；此操作符保留给扩展
    if t == "type_count":
        typ = pred.get("type_", pred.get("node_type", ""))
        op = pred.get("op", ">=")
        n = int(pred.get("n", 1))
        c = sum(1 for node in nodes if (node.get("type") or "") == typ)
        return {"==": c == n, ">=": c >= n, ">": c > n, "<=": c <= n, "<": c < n}.get(op, c >= n)
    raise ValueError(f"未知谓词类型: {t}")


def evaluate(pred: Any, nodes: list[dict]) -> bool:
    if isinstance(pred, bool):
        return pred
    if not isinstance(pred, dict):
        raise ValueError(f"谓词必须是 dict/bool，收到 {type(pred)}")
    if "all" in pred:
        return all(evaluate(p, nodes) for p in pred["all"])
    if "any" in pred:
        return any(evaluate(p, nodes) for p in pred["any"])
    if "not" in pred:
        return not evaluate(pred["not"], nodes)
    return _leaf(pred, nodes)


class Judge:
    def __init__(self, task: dict, vlm_judge=None):
        self.task = task
        self.goal = task.get("goal", {})
        self.vlm_judge = vlm_judge  # (screenshot_path, question) -> bool，可选

    def milestone_hits(self, nodes: list[dict], seen: set) -> list[str]:
        """从 goal.milestones 返回尚未达成的 milestone id 列表（渠道拉起等阶段证据）。"""
        hits = []
        for m in self.goal.get("milestones", []):
            mid = str(m.get("id", ""))
            if not mid or mid in seen:
                continue
            if evaluate(m.get("pred", {}), nodes):
                hits.append(mid)
        return hits

    def verdict(self, nodes: list[dict], screenshot: str | None = None) -> Verdict:
        reasons: list[str] = []
        success = evaluate(self.goal.get("success", True), nodes)
        forbid = False
        forbids = self.goal.get("forbid", [])
        for p in forbids:
            if evaluate(p, nodes):
                forbid = True
                reasons.append(f"forbid 命中: {p}")
                break
        if not success and not forbid and screenshot and self.vlm_judge:
            q = f"任务目标是否已完成？任务：{self.task.get('instruction', '')}"
            try:
                if self.vlm_judge(screenshot, q):
                    success = True
                    reasons.append("vlm 兜底判定成功")
            except Exception as e:  # 兜底失败不致命
                reasons.append(f"vlm 兜底出错: {e}")
        if success and not forbid:
            reasons.append("success 谓词满足")
        return Verdict(success, forbid, reasons)