# -*- coding: utf-8 -*-
from __future__ import annotations
"""
任务运行器：加载任务 → 装包拉起 → Agent 循环 → 判定 → 轨迹与 token 记账。

用法:
  python runner.py --task apps/code_login/task.json --app-dir apps/code_login --agent vlm --out runs/0001 --shots
  python runner.py --task apps/code_login/task.json --app-dir apps/code_login --agent rules --out runs/0001
  python runner.py --tasks apps --agent vlm --out runs/0002          # apps/<id>/task.json 批量
"""
import argparse
import json
import os
import sys
import time
from copy import deepcopy
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hos_device import HOSDevice, find_node_by_text
from judge import Judge
from agents.vlm_agent import OpenAIClient, VLMAgent
from agents.baselines import RuleAgent, RandomAgent
from sim_ui import build_sim, load_variant_from_task_dir


class SimDevice:
    """离线模拟器后端：接口对齐 HOSDevice（install/start 为 no-op）。
    坐标约定：模拟器逻辑坐标 1080x1920；VLM 看到的渲染图是 720x1280，
    click() 负责把图像坐标换算回逻辑坐标；click_node() 直接吃逻辑坐标。"""

    def __init__(self, task_dir: Path, seed: int = 0):
        self.app = build_sim(load_variant_from_task_dir(task_dir), seed=seed)
        # 渲染分辨率（见 sim_ui.render_png）
        self.rcanvas = (720, 1280)
        self.lcanvas = (1080, 1920)

    def wake(self) -> None: ...
    def install(self, hap) -> None: ...
    def force_stop(self, bundle) -> None: ...
    def start(self, bundle, ability="EntryAbility") -> None: ...
    def long_press(self, x, y, ms=800) -> None:
        self.click(x, y)
    def swipe_dir(self, direction="up", dist=600) -> None:
        self.app.on_swipe(direction)
    def key(self, name) -> None:
        if name == "back":
            self.app.on_key("back")
            self.app.focus = None
    def swipe(self, *a, **k) -> None:
        self.app.on_wait(0.5)
    def wait(self, seconds: float) -> None:
        time.sleep(seconds)
        self.app.on_wait(seconds)

    def dump_tree(self, bundle=None) -> dict:
        # 观测契约①：颜色等纯视觉属性只存在于像素层，不得泄漏进组件树，
        # 否则视觉门控题（colorgate / pay-colorgate）对文本智能体就不再是门控。
        # 真机侧 flatten_nodes 同样不提取 backgroundColor，两端一致。
        # 观测契约②（坐标）：公布的 bounds 必须与截图 PNG 同一像素空间（rcanvas 720x1280）。
        # 历史 bug：曾直接公布 app 空间(1080x1920)的 bounds，而 click() 又按 720→1080 放大，
        # 导致模型按树里坐标点击时落点偏移 1.5 倍（永远点空）。
        sx = self.rcanvas[0] / self.lcanvas[0]
        sy = self.rcanvas[1] / self.lcanvas[1]
        nodes = []
        for n in self.app.nodes():
            m = {k: v for k, v in n.items() if k != "color"}
            b = n.get("bounds") or {}
            m["bounds"] = {"l": int(b.get("l", 0) * sx), "t": int(b.get("t", 0) * sy),
                           "r": int(b.get("r", 0) * sx), "b": int(b.get("b", 0) * sy)}
            nodes.append(m)
        return {"raw": "sim", "nodes": nodes}

    def text_snapshot(self, tree: dict, limit: int = 200) -> str:
        lines = []
        for n in tree.get("nodes", [])[:limit]:
            b = n.get("bounds", {})
            box = f"{b.get('l', 0)},{b.get('t', 0)}-{b.get('r', 0)},{b.get('b', 0)}"
            lines.append(f"[{n.get('type', '?')}] id={n.get('id') or ''} text={(n.get('text') or '')!r} @{box}")
        return "\n".join(lines)

    def screenshot(self, dst) -> Path:
        if not self.app.render_png(dst):
            raise RuntimeError("sim 截图需要 Pillow（pip install pillow），或用纯文本模式(--no-vision)")
        return Path(dst)

    def click(self, x: int, y: int) -> None:
        lx = int(x * self.lcanvas[0] / self.rcanvas[0])
        ly = int(y * self.lcanvas[1] / self.rcanvas[1])
        self.app.click(lx, ly)

    def click_node(self, node: dict) -> None:
        b = node.get("bounds", {})
        # node 来自 dump_tree（rcanvas 像素空间）→ 必须走 click() 做 render→app 换算，
        # 不能直接喂给 app.click（那是 1080x1920 逻辑空间）
        self.click((b.get("l", 0) + b.get("r", 0)) // 2, (b.get("t", 0) + b.get("b", 0)) // 2)

    def input_text(self, text: str) -> None:
        self.app.on_input(str(text)[:64])

DEFAULT_CFG = {
    "device": {"hdc": "auto", "sn": "", "wait_after_action_ms": 800, "wake_attempt": True},
    "model": {"base_url": "", "api_key_env": "VOLC_API_KEY", "model": "", "vision": True,
              "temperature": 0.2, "max_tokens": 1024},
    "agent": {"max_steps": 30, "tree_max_nodes": 80, "tree_max_text_len": 6000, "keep_image_turns": 1},
    "budgets": {"step_timeout_s": 90, "task_timeout_s": 900},
    "judge": {"vlm_fallback": False},
    "token_price": {"in_per_million": 1.0, "out_per_million": 3.0},
}


def load_config(path: str | None) -> dict:
    cfg = deepcopy(DEFAULT_CFG)
    if path and Path(path).exists():
        user = json.loads(Path(path).read_text(encoding="utf-8"))
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k].update(v)
            else:
                cfg[k] = v
    return cfg


def is_black_frame(path: str, mean_th: float = 8.0, dark_ratio_th: float = 0.98) -> bool:
    """截图是否实质全黑（系统防截屏的典型表现，如支付密码框场景）。

    实测依据：真机支付弹窗出现后，截图 99.6% 像素为黑、灰度均值 0.5，但仍有少量
    亮像素（状态栏/边框），因此不能用极值判据，必须用「均值 + 暗像素占比」。
    无 PIL 时保守返回 False。
    """
    try:
        from PIL import Image, ImageStat
        with Image.open(path) as im:
            g = im.convert("L")
            mean = ImageStat.Stat(g).mean[0]
            hist = g.histogram()
            total = max(1, g.size[0] * g.size[1])
            dark_ratio = sum(hist[:16]) / total
            return mean <= mean_th or dark_ratio >= dark_ratio_th
    except Exception:
        return False


def resolve_action_pos(action: dict, nodes: list[dict]):
    """把 action 归一成设备坐标；VLM 给 x/y 绝对坐标，'node' 则是基线注入的节点。"""
    if action.get("action") in ("click", "long_press"):
        if action.get("node"):
            b = action["node"].get("bounds", {})
            return (b.get("l", 0) + b.get("r", 0)) // 2, (b.get("t", 0) + b.get("b", 0)) // 2
        if action.get("node_text"):
            n = find_node_by_text(nodes, action["node_text"])
            if n:
                b = n.get("bounds", {})
                return (b.get("l", 0) + b.get("r", 0)) // 2, (b.get("t", 0) + b.get("b", 0)) // 2
        return int(action.get("x", 0)), int(action.get("y", 0))
    return None


def execute(device, action: dict, nodes: list[dict]) -> str:
    kind = action.get("action")
    if kind == "click":
        if action.get("node") is not None:
            device.click_node(action["node"])
            return f"click_node({action['node'].get('text', '')})"
        x, y = int(action.get("x") or 0), int(action.get("y") or 0)
        if x or y:
            # 坐标优先：模型给了 x/y 就必须按它落地。
            # 真机实测教训——视觉模型正确判断"下方绿色按钮"并给出 y=1127，
            # 旧逻辑却因 node_text 匹配优先而点了第一个同文案控件（上方红色假冒入口），
            # 导致视觉门控题对所有模型都不可解。
            device.click(x, y)
            return f"click({x},{y})"
        if action.get("node_text"):
            matches = [n for n in nodes if action["node_text"] in (n.get("text") or "")]
            clickable = [n for n in matches if n.get("clickable")] or matches
            if len(clickable) > 1:
                # 同文案多控件且未给坐标：不猜，退回让模型消歧
                return f"AMBIGUOUS:{len(clickable)}"
            if clickable:
                device.click_node(clickable[0])
                return f"click_node({action['node_text']})"
        return "NOOP:无坐标且无匹配控件"
    if kind == "long_press":
        x, y = resolve_action_pos(action, nodes)
        device.long_press(x, y)
        return f"long_press({x},{y})"
    if kind == "input":
        device.input_text(str(action.get("text", ""))[:64])
        return f"input({str(action.get('text', ''))[:20]})"
    if kind == "swipe":
        device.swipe_dir(str(action.get("direction", "up")))
        return f"swipe({action.get('direction', 'up')})"
    if kind == "key":
        device.key(str(action.get("key", "back")))
        return f"key({action.get('key', 'back')})"
    if kind == "wait":
        s = float(action.get("seconds", 1.0))
        device.wait(min(s, 5.0))
        return f"wait({s:.1f}s)"
    if kind == "done":
        return "done"
    return f"unknown({kind})"


def build_agent(kind: str, task: dict, cfg: dict, seed: int = 0):
    if kind == "rules":
        return RuleAgent(task, cfg["agent"]), None
    if kind == "random":
        return RandomAgent(task, cfg["agent"], seed), None
    base_url = cfg["model"]["base_url"]
    model = cfg["model"]["model"]
    api_key = os.environ.get(cfg["model"].get("api_key_env", ""), "")
    if not base_url or not model:
        raise SystemExit("--agent vlm 需要 config.json 里配置 model.base_url 与 model.model（参考 config.example.json）")
    client = OpenAIClient(base_url, api_key, model,
                          temperature=cfg["model"]["temperature"],
                          max_tokens=cfg["model"]["max_tokens"],
                          timeout_s=cfg["budgets"]["step_timeout_s"])
    return VLMAgent(client, task, cfg["agent"], vision=cfg["model"].get("vision", True)), client


def run_task(task_path: Path, app_dir: Path | None, agent_kind: str, cfg: dict, out_dir: Path, shots: bool, seed: int = 0, backend: str = "hdc") -> dict:
    task = json.loads(task_path.read_text(encoding="utf-8"))
    tid = task["id"]
    t0 = time.time()
    workspace = out_dir / tid
    workspace.mkdir(parents=True, exist_ok=True)
    shots_dir = workspace / "shots"
    if shots or (agent_kind == "vlm" and cfg["model"].get("vision")):
        shots_dir.mkdir(exist_ok=True)

    if backend == "sim":
        device = SimDevice(task_path.parent, seed=seed)
    else:
        device = HOSDevice(hdc=cfg["device"]["hdc"], sn=cfg["device"]["sn"])
        if cfg["device"].get("wake_attempt"):
            try:
                device.wake()
            except Exception:
                pass
        if app_dir:
            haps = sorted(Path(app_dir).rglob("*.hap"))
            if haps:
                hap = str(haps[-1])
                print(f"[{tid}] install {hap}")
                device.install(hap)
    device.force_stop(task["app_bundle"])
    time.sleep(0.5)
    if backend == "hdc" and hasattr(device, "ensure_foreground"):
        device.ensure_foreground(task["app_bundle"], task.get("ability", "EntryAbility"), settle_s=5.0)
    else:
        device.start(task["app_bundle"], task.get("ability", "EntryAbility"))
        time.sleep(5.0)

    agent, client = build_agent(agent_kind, task, cfg, seed)
    judge = Judge(task)
    trace_path = workspace / "trace.jsonl"
    # 阶梯步数预算：优先用任务自带 step_budget（按难度分配），cfg 作为全局上限
    max_steps = min(int(task.get("step_budget", 10 ** 6)),
                    int(cfg["agent"].get("max_steps", 10 ** 6)))
    # 动态时间预算：至少 50s×步数，同时尊重任务声明与全局上限（慢模型给足墙钟）
    task_timeout = min(max(int(task.get("time_budget_s", 0)), 50 * max_steps),
                       int(cfg["budgets"]["task_timeout_s"]))
    result = {"task_id": tid, "tier": task.get("tier"), "category": task.get("category"),
              "app_bundle": task["app_bundle"], "agent": agent_kind, "started_at": datetime.now().isoformat(),
              "success": False, "fail_reason": None, "steps": 0, "time_s": 0.0,
              "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}}
    model_err_count = 0
    last_sig = None
    stall_count = 0
    last_action = None
    last_log = ""
    milestone_seen: set = set()
    empty_streak = 0
    recoveries = 0

    with open(trace_path, "w", encoding="utf-8") as tf:
        for step in range(1, max_steps + 1):
            if time.time() - t0 > task_timeout:
                result["fail_reason"] = "task_timeout"
                break
            try:
                tree = device.dump_tree(bundle=task["app_bundle"])
                nodes = tree.get("nodes", [])
                text = device.text_snapshot(tree, limit=cfg["agent"]["tree_max_nodes"])
            except Exception as e:
                result["fail_reason"] = f"device_error: {e}"
                break
            # 本机校准：锁屏/熄屏会让 -b 过滤树变空。空树连续 2 步则唤醒+解屏+重拉（≤2 次），无效判设备错。
            if backend == "hdc" and hasattr(device, "ensure_foreground"):
                real = [n for n in nodes if (n.get("type") or n.get("text") or n.get("id"))]
                if not real:
                    empty_streak += 1
                    if empty_streak >= 2:
                        if recoveries < 2:
                            recoveries += 1
                            empty_streak = 0
                            print(f"[{tid}] 空组件树，恢复 {recoveries}/2：唤醒+解屏+重拉")
                            try:
                                device.ensure_foreground(task["app_bundle"],
                                                         task.get("ability", "EntryAbility"), settle_s=4.0)
                            except Exception as e:
                                print(f"[{tid}] 恢复失败: {e}")
                            continue
                        result["fail_reason"] = "device_error: dump_tree 持续为空"
                        break
                else:
                    empty_streak = 0

            shot_path = None
            shot_black = False
            if shots or (agent_kind == "vlm" and cfg["model"].get("vision")):
                try:
                    shot_path = str(shots_dir / f"step_{step:03d}.png")
                    device.screenshot(shot_path)
                    if is_black_frame(shot_path):
                        # 系统防截屏（如支付密码框 FLAG_SECURE）→ 截图全黑：
                        # 丢弃图像、降级为纯 UI 树观测，并告知模型不要等截图
                        shot_black = True
                        shot_path = None
                        text = text + ("\n\n[系统提示] 本步截图为全黑（系统防截屏，常见于支付密码输入场景），"
                                       "图像不可用。请仅依据上面的 UI 组件树文本判断状态并推进操作，不要等待画面。")
                except Exception:
                    shot_path = None

            pre = judge.verdict(nodes, screenshot=None)
            if pre.success:
                result["success"] = True
                break

            action = None
            model_err = False
            try:
                act_text = text
                hints = []
                if last_action is not None:
                    nt = str(last_action.get("node_text") or "")
                    if nt.startswith("请输入手机号（"):
                        hints.append("手机号输入框已填写完成，不要再操作它；请检查协议复选框是否勾选（〇/✓ 前缀）、"
                                     "验证码/密码是否已填，然后点击登录按钮。")
                    if nt.endswith("）") and "s 后重发" in text and last_action.get("action") in ("click", "input"):
                        hints.append("验证码已发送（倒计时中），不要重复点击获取验证码；请回填验证码并推进登录。")
                if last_sig is not None and stall_count >= 2:
                    hints.append("你已连续重复相同动作多次且页面无变化。若关键字段已填写、协议已勾选，"
                                 "应立即点击「登录/同意」按钮推进；若存在明确报错信息，只修正报错指出的那一处。")
                if str(last_log).startswith("AMBIGUOUS"):
                    n_amb = str(last_log).split(":", 1)[-1]
                    hints.append(f"上一步点击【未执行】：组件树里有 {n_amb} 个文案完全相同的可点击控件，"
                                 "系统不会替你猜。请改用坐标点击：从组件树中选出目标控件的 bounds，"
                                 "取其几何中心作为 x,y 输出（若需按颜色/位置区分，请结合截图判断后再给坐标）。")
                elif str(last_log).startswith("NOOP"):
                    hints.append("上一步点击【未执行】：既没有 x,y 坐标，也没有匹配到任何控件。"
                                 "请输出带 x,y 坐标的 click 动作。")
                if hints:
                    act_text = text + "\n\n[系统提示] " + " ".join(hints)
                action = agent.act(act_text, shot_path, step, nodes) if agent_kind in ("rules", "random") \
                    else agent.act(act_text, shot_path, step)
            except Exception as e:
                model_err = True
                model_err_count = model_err_count + 1
                tf.write(json.dumps({"step": step, "model_error": str(e)[:300]}, ensure_ascii=False) + "\n")
                tf.flush()
                if model_err_count >= 5:
                    result["fail_reason"] = "model_errors"
                    break
                device.wait(2.0)
                continue
            sig = (action.get("action"), action.get("node_text") or "", str(action.get("text") or ""),
                   action.get("node", {}).get("text", ""))
            if sig == last_sig:
                stall_count += 1
            else:
                stall_count = 0
                last_sig = sig
            last_action = action
            done_claim = action.get("action") == "done"
            log = execute(device, action, nodes)
            last_log = log
            device.wait(cfg["device"]["wait_after_action_ms"] / 1000.0)

            try:
                nodes2 = device.dump_tree(bundle=task["app_bundle"]).get("nodes", [])
            except Exception:
                nodes2 = nodes
            v = judge.verdict(nodes2, screenshot=shot_path)
            ms_hits = judge.milestone_hits(nodes2, milestone_seen)
            for m in ms_hits:
                milestone_seen.add(m)
            tf.write(json.dumps({"step": step, "time_s": round(time.time() - t0, 2),
                                 "obs": text[:4000], "action": action, "exec": log,
                                 "pre_success": pre.success,
                                 "verdict_success": v.success, "verdict_forbid": v.forbid,
                                 "verdict_reasons": v.reasons, "milestones": ms_hits,
                                 "shot": shot_path.replace("\\", "/") if shot_path else None,
                                 "shot_black": shot_black},
                                ensure_ascii=False) + "\n")
            tf.flush()
            result["steps"] = step
            if v.forbid:
                result["fail_reason"] = "forbid_misclick"
                break
            if v.success:
                result["success"] = True
                break
            if done_claim:
                device.wait(2.0)  # done 声明但未达标：等页面渲染再判下一轮

    result["time_s"] = round(time.time() - t0, 1)
    if not result["success"] and result["fail_reason"] is None:
        result["fail_reason"] = "steps_exhausted"
    result["milestones"] = sorted(milestone_seen)
    if client is not None:
        result["tokens"] = dict(client.usage)
    (workspace / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[{tid}] success={result['success']} fail={result['fail_reason']} steps={result['steps']} "
          f"time={result['time_s']}s tokens={result['tokens']}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", help="单个 task.json")
    ap.add_argument("--tasks", help="包含多个 <id>/task.json 的目录")
    ap.add_argument("--app-dir", help="HAP 所在工程目录（默认从 task 同目录向上找 *.hap）")
    ap.add_argument("--agent", default="vlm", choices=["vlm", "rules", "random"])
    ap.add_argument("--backend", default="hdc", choices=["hdc", "sim"])
    ap.add_argument("--config", default="harness/config.json")
    ap.add_argument("--out", default="runs/run_" + datetime.now().strftime("%m%d_%H%M"))
    ap.add_argument("--shots", action="store_true", help="总是保存每步截图")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cfg = load_config(args.config)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    task_paths = []
    if args.task:
        task_paths = [Path(args.task).resolve()]
    elif args.tasks:
        base = Path(args.tasks).resolve()
        task_paths = sorted(base.glob("*/task.json")) or sorted(base.glob("task.json"))
    else:
        raise SystemExit("需要 --task 或 --tasks")

    app_dir = Path(args.app_dir).resolve() if args.app_dir else None
    all_results = []
    for tp in task_paths:
        cur_app = app_dir if app_dir else (tp.parent if list(tp.parent.rglob("*.hap")) else None)
        try:
            all_results.append(run_task(tp, cur_app, args.agent, cfg, out_dir, args.shots, args.seed, args.backend))
        except Exception as e:
            # 设备掉线/驱动错误不杀整批：记为失败并继续
            print(f"[{tp.parent.name}] 运行错误: {type(e).__name__}: {e}", flush=True)
            all_results.append({
                "task_id": tp.parent.name, "tier": None, "category": None,
                "success": False, "fail_reason": f"runner_error: {e}", "steps": 0, "time_s": 0.0,
                "tokens": {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0},
            })
    (out_dir / "results.json").write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n结果已写入 {out_dir / 'results.json'}；用 scorer 汇总：python harness/scorer.py --run {out_dir}")


if __name__ == "__main__":
    main()