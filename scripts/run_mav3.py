# -*- coding: utf-8 -*-
"""
用 Mobile-Agent-v3 作为 agent 跑本 benchmark（任务集 / 判定 / 计分仍是本仓库的）。

架构：
  - MA-v3 官方入口 `run_mobileagentv3.run_instruction`（Manager→Executor→ActionReflector[→Notetaker]）
    原样调用，不改其代码；
  - 通过两处**运行时注入**把它接进本 benchmark：
      ① `GUIOwlWrapper` 子类：放宽 OpenAI 客户端 timeout（官方 30s，本网关视觉调用 20~60s），
         并采集每次调用的 usage → token 记账；
      ② `HarmonyOSController` 子类：在每个动作后采集 UI 树，用本仓库 Judge 增量判定
         success/forbid/milestones，并写出与 runner.py 同构的 trace.jsonl；
  - 产物目录结构与 runner.py 一致，因此 scorer / pay_verdict / pay_metrics / report 全部可直接复用。

必须用装了 MA-v3 依赖的解释器运行（本机为 venv）：
  E:\\迅雷下载\\mav3env\\Scripts\\python.exe scripts/run_mav3.py --tasks _pay18 --out runs/MAV3_pay

已实测校准：
  - qwen3.8-max 输出 0-1000 相对坐标 → 默认 --coor-type qwen-vl
    （交叉验证：树内真实中心 (628,896) ↔ 模型 (500,324) → 反算 (628,894)，误差 2px）
  - MA-v3 官方 HarmonyOSController 的 get_screenshot/tap/type/slide/back 在本机 hdc 3.2.0f 全部可用
"""
import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))

import mav3_shim  # noqa: E402

DEFAULT_MAV3 = r"E:\迅雷下载\MobileAgent-src\MobileAgent-main\Mobile-Agent-v3\mobile_v3"
DEFAULT_HDC = r"G:\360downloads\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe"


def load_cfg(path: str) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    base = json.loads((ROOT / "harness" / "config.json").read_text(encoding="utf-8"))

    def merge(a, b):
        out = dict(a)
        for k, v in (b or {}).items():
            out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
        return out
    return merge(base, cfg)


def collect_tasks(tasks_arg: str) -> list:
    p = Path(tasks_arg)
    if not p.is_absolute():
        p = ROOT / p
    if p.is_file():
        return [p]
    hits = []
    for d in sorted(x for x in p.iterdir() if x.is_dir()):
        f = d / "task.json"
        if f.exists():
            hits.append(f)
    if not hits and (p / "task.json").exists():
        hits = [p / "task.json"]
    return hits


def build_add_info(task: dict) -> str:
    """把凭据/前置条件转成 MA-v3 的 add_info（补充知识）。"""
    parts = []
    creds = task.get("creds") or {}
    label = {"phone": "手机号", "code": "验证码", "password": "密码", "pay_pwd": "支付密码",
             "captcha_answer": "验证码算式答案"}
    for k, v in creds.items():
        parts.append(f"{label.get(k, k)}={v}")
    for pre in task.get("preconditions") or []:
        parts.append(str(pre))
    parts.append("本任务运行在鸿蒙(HarmonyOS)模拟器上，界面文案为简体中文。")
    return "；".join(parts)


def install_image_downscale(cmae, max_side: int, quality: int = 82) -> str:
    """可选：把 MA-v3 发往模型的截图降采样（默认 0 = 完全按官方原样发全分辨率）。

    官方 `image_to_base64` 用 smart_resize(MAX_PIXELS=10035200)，本机 1256×2760（3.47M 像素）
    不会被缩小，实测每步 Manager+Executor 就要 73s+109s。
    依据本仓库 A 消融结论（768 降采样：SR 不降、tokens −80%、步均墙钟 30.6s→9.1s），
    这里提供同款开关。注意：qwen3.8-max 输出 0-1000 **相对坐标**，且 MA-v3 的坐标换算
    用的是磁盘原图尺寸（`Image.open(local_image_dir).size`），因此降采样不影响点击精度。
    """
    if max_side <= 0:
        return "official(全分辨率)"
    import base64
    from io import BytesIO
    from PIL import Image
    smart = cmae.smart_resize

    def image_to_base64(image_path):
        img = Image.open(image_path)
        w, h = img.size
        scale = max_side / float(max(w, h))
        if scale < 1.0:
            img = img.convert("RGB").resize((max(28, int(w * scale)), max(28, int(h * scale))))
        rh, rw = smart(img.height, img.width, factor=28,
                       min_pixels=28 * 28, max_pixels=img.width * img.height + 28 * 28)
        img = img.convert("RGB").resize((rw, rh))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=quality)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")

    cmae.image_to_base64 = image_to_base64
    return f"降采样(长边<={max_side}, JPEG q{quality})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--config", default="harness/config_mav3.json")
    ap.add_argument("--mav3-dir", default=DEFAULT_MAV3)
    ap.add_argument("--hdc", default=DEFAULT_HDC)
    ap.add_argument("--target", default="127.0.0.1:5555")
    ap.add_argument("--coor-type", default=None, choices=["qwen-vl", "abs"],
                    help="默认取模型注册表；手动覆盖用显式值")
    ap.add_argument("--model", default="",
                    help="直接按模型名（models_registry.json）查表取 coor_type/image_max_side/是否多模态")
    ap.add_argument("--registry", default="harness/models_registry.json")
    ap.add_argument("--notetaker", action="store_true")
    ap.add_argument("--max-step", type=int, default=0, help="0=用任务自带 step_budget")
    ap.add_argument("--only", default="", help="逗号分隔任务 id 子集")
    ap.add_argument("--timeout", type=float, default=180.0, help="网关单次调用超时（官方默认 30s）")
    ap.add_argument("--image-max-side", type=int, default=None,
                    help="None=取注册表；0=官方全分辨率；>0 按长边降采样")
    ap.add_argument("--jpeg-quality", type=int, default=82)
    ap.add_argument("--settle", type=float, default=5.0, help="冷启动等待秒数")
    args = ap.parse_args()

    print("qwen_vl_utils:", mav3_shim.install())
    cfg = load_cfg(args.config)
    mcfg = cfg["model"]
    # 模型注册表：--model 一键查表，免手选 coor_type / image_max_side / 是否多模态
    coor_type = args.coor_type
    image_max_side = args.image_max_side
    registry_note = ""
    if args.model:
        reg = json.loads((ROOT / args.registry).read_text(encoding="utf-8"))
        ent = reg["models"].get(args.model)
        if ent is None:
            raise SystemExit(f"模型 {args.model} 不在 {args.registry}")
        if not ent.get("multimodal", True):
            raise SystemExit(f"{args.model} 为纯文本模型（不支持图片），不能用于 MA-v3 多模态 agent")
        mcfg = dict(mcfg, model=args.model)
        mcfg["vision"] = True
        if coor_type is None:
            coor_type = ent.get("coor_type", "qwen-vl")
        if image_max_side is None:
            image_max_side = ent.get("image_max_side", 0)
        registry_note = ent.get("note", "")
        if "gateway" in reg:
            mcfg["base_url"] = reg["gateway"].get("base_url", mcfg["base_url"])
    coor_type = coor_type or "qwen-vl"
    image_max_side = image_max_side if image_max_side is not None else 0
    cfg["model"] = mcfg
    api_key = os.environ.get(mcfg.get("api_key_env", "VOLC_API_KEY"), "")
    if not api_key:
        raise SystemExit(f"缺少环境变量 {mcfg.get('api_key_env')}")
    base_url = mcfg["base_url"]
    model = mcfg["model"]
    if registry_note:
        print(f"模型注册表命中 {model}：coor_type={coor_type} image_max_side={image_max_side}（{registry_note}）")

    # ---- 导入 MA-v3（先装垫片，再注入两处 instrumentation）----
    sys.path.insert(0, args.mav3_dir)
    import utils.call_mobile_agent_e as cmae  # noqa: E402
    import utils.harmonyos_controller as hctl  # noqa: E402
    from hos_device import HOSDevice  # noqa: E402
    from judge import Judge  # noqa: E402

    usage_log: list = []
    call_lat: list = []

    class InstrumentedWrapper(cmae.GUIOwlWrapper):
        """放宽 timeout（默认 30s）+ 采集 usage + 缩短重试（官方 10 次 ×20s 会令单次调用
        楔死 40 分钟：双分片压测触发网关限流时正是卡死主因）。"""

        def __init__(self, api_key, base_url, model_name, max_retry=2, temperature=0.0):
            super().__init__(api_key, base_url, model_name, max_retry=max_retry,
                             temperature=temperature)
            self.bot = self.bot.with_options(timeout=args.timeout)

        def predict_mm(self, text_prompt, images, messages=None):
            t0 = time.time()
            out = super().predict_mm(text_prompt, images, messages)
            call_lat.append(round(time.time() - t0, 1))
            raw = out[2] if len(out) > 2 else None
            u = getattr(raw, "usage", None) if raw is not None else None
            if u is not None:
                usage_log.append({"prompt": int(getattr(u, "prompt_tokens", 0) or 0),
                                  "completion": int(getattr(u, "completion_tokens", 0) or 0)})
            else:
                usage_log.append({"prompt": 0, "completion": 0, "estimated": 1})
            return out

    cmae.GUIOwlWrapper = InstrumentedWrapper
    img_mode = install_image_downscale(cmae, image_max_side, args.jpeg_quality)
    print(f"图像通道: {img_mode} | 坐标制式: {coor_type} | 网关 timeout: {args.timeout}s")

    dev = HOSDevice(hdc=args.hdc, sn=args.target)
    trace_state = {"rows": [], "judge": None, "bundle": "", "milestones": set(),
                   "shots": None, "step": 0, "finished": False}

    class InstrumentedController(hctl.HarmonyOSController):
        """MA-v3 的每个设备动作之后：采集 UI 树 → 用本仓库 Judge 增量判定 → 记轨迹。"""

        def _record(self, act: dict, shot: str = None):
            if trace_state["finished"]:
                return
            trace_state["step"] += 1
            st = trace_state["step"]
            try:
                nodes = dev.dump_tree(bundle=trace_state["bundle"]).get("nodes", [])
            except Exception as e:
                nodes, _ = [], str(e)
            j = trace_state["judge"]
            v = j.verdict(nodes, screenshot=None) if j else None
            ms = j.milestone_hits(nodes, trace_state["milestones"]) if j else []
            for m in ms:
                trace_state["milestones"].add(m)
            snap = dev.text_snapshot({"nodes": nodes})[:4000] if nodes else ""
            trace_state["rows"].append({
                "step": st, "time_s": round(time.time() - trace_state["t0"], 2),
                "obs": snap, "action": act, "exec": json.dumps(act, ensure_ascii=False),
                "verdict_success": bool(v.success) if v else False,
                "verdict_forbid": bool(v.forbid) if v else False,
                "verdict_reasons": v.reasons if v else [],
                "milestones": ms, "shot": shot,
            })
            if v is not None and (v.success or v.forbid):
                trace_state["finished"] = True

        def get_screenshot(self, save_path):
            ok = super().get_screenshot(save_path)
            if ok and trace_state.get("shots") is not None:
                try:
                    import shutil
                    dst = Path(trace_state["shots"]) / f"step_{trace_state['step'] + 1:03d}.png"
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(save_path, dst)
                except Exception:
                    pass
            return ok

        def tap(self, x, y):
            super().tap(x, y)
            time.sleep(cfg["device"].get("wait_after_action_ms", 300) / 1000.0)
            self._record({"action": "click", "x": int(x), "y": int(y), "by": "mav3"})

        def slide(self, x1, y1, x2, y2):
            super().slide(x1, y1, x2, y2)
            time.sleep(cfg["device"].get("wait_after_action_ms", 300) / 1000.0)
            self._record({"action": "swipe", "from": [int(x1), int(y1)], "to": [int(x2), int(y2)],
                          "by": "mav3"})

        def type(self, text):
            super().type(text)
            time.sleep(cfg["device"].get("wait_after_action_ms", 300) / 1000.0)
            self._record({"action": "input", "text": str(text), "by": "mav3"})

        def back(self):
            super().back()
            time.sleep(cfg["device"].get("wait_after_action_ms", 300) / 1000.0)
            self._record({"action": "key", "key": "back", "by": "mav3"})

        def home(self):
            super().home()
            time.sleep(cfg["device"].get("wait_after_action_ms", 300) / 1000.0)
            self._record({"action": "key", "key": "home", "by": "mav3"})

    hctl.HarmonyOSController = InstrumentedController

    import run_mobileagentv3 as mav3  # noqa: E402  （此时已绑定被注入的两个类）
    mav3.GUIOwlWrapper = InstrumentedWrapper

    # MA-v3 提前终止：judge 判 success/forbid 后，下一次 Manager 规划直接返回 Finished，
    # 优雅断出官方主循环。真机上 MA-v3 不看我们的 judge，执行到目标后仍会空转多步，
    # 该补丁把"已成功却空转"从十几步压到最多一步规划。
    _orig_mgr_parse = mav3.Manager.parse_response

    def _mgr_parse(self, output):
        if trace_state.get("finished"):
            return {"completed_subgoal": "（评判器已判成功，提前终止）",
                    "plan": "Finished", "thought": ""}
        return _orig_mgr_parse(self, output)

    mav3.Manager.parse_response = _mgr_parse

    # ---- 逐任务执行 ----
    task_paths = collect_tasks(args.tasks)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    out_root = Path(args.out)
    if not out_root.is_absolute():
        out_root = ROOT / out_root
    out_root.mkdir(parents=True, exist_ok=True)
    hdc_path = f'"{args.hdc}" -t {args.target}'
    results = []

    for tp in task_paths:
        task = json.loads(tp.read_text(encoding="utf-8"))
        tid = task["id"]
        if only and tid not in only:
            continue
        ws = out_root / tid
        (ws / "mav3_logs").mkdir(parents=True, exist_ok=True)
        shots_dir = ws / "shots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        judge = Judge(task)
        usage_log.clear()
        call_lat.clear()
        trace_state.update({"rows": [], "judge": judge, "bundle": task["app_bundle"],
                            "milestones": set(), "shots": str(shots_dir), "step": 0,
                            "finished": False, "t0": time.time()})
        max_step = args.max_step or int(task.get("step_budget", 25))
        print(f"\n=== [MA-v3] {tid} | {task.get('category')} | max_step={max_step} "
              f"| coor={coor_type} | model={model} ===", flush=True)
        err = None
        _r = {}
        def _run():
            try:
                mav3.run_instruction(None, hdc_path, api_key, base_url, model,
                                     task["instruction"], build_add_info(task),
                                     coor_type, bool(args.notetaker),
                                     max_step, str(ws / "mav3_logs"))
                _r["ok"] = True
            except Exception as e:
                _r["err"] = f"{type(e).__name__}: {e}"
        try:
            dev.force_stop(task["app_bundle"])
            dev.start(task["app_bundle"], task.get("ability", "EntryAbility"))
            time.sleep(args.settle)
            # 看门狗：run_instruction 内部既无 hdc 超时也无墙钟上限，用线程 join 兜底
            _t = threading.Thread(target=_run, daemon=True)
            _t.start()
            _t.join(cfg["budgets"].get("task_timeout_s", 900))
            if _t.is_alive():
                err = f"task_timeout(>{cfg['budgets'].get('task_timeout_s', 900)}s 无响应)"
            elif "err" in _r:
                err = _r["err"]
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            print(f"   运行错误: {err}", flush=True)

        # 收尾判定（MA-v3 停止后再看一次终态）
        try:
            nodes = dev.dump_tree(bundle=task["app_bundle"]).get("nodes", [])
        except Exception:
            nodes = []
        v = judge.verdict(nodes, screenshot=None)
        for m in judge.milestone_hits(nodes, trace_state["milestones"]):
            trace_state["milestones"].add(m)
        tr_json = (ws / "mav3_logs")
        hit_limit = not any(tr_json.rglob("task_result.json"))
        tok = {"prompt_tokens": sum(u.get("prompt", 0) for u in usage_log),
               "completion_tokens": sum(u.get("completion", 0) for u in usage_log),
               "calls": len(usage_log),
               "estimated": sum(1 for u in usage_log if u.get("estimated"))}
        steps = trace_state["step"]
        result = {
            "task_id": tid, "tier": task.get("tier"), "category": task.get("category"),
            "success": bool(v.success and not v.forbid),
            "fail_reason": (None if (v.success and not v.forbid) else
                            ("forbid_misclick" if v.forbid else
                             ("mav3_error" if err else
                              ("steps_exhausted" if hit_limit else "goal_not_reached")))),
            "steps": steps, "time_s": round(time.time() - trace_state["t0"], 1),
            "tokens": tok, "milestones": sorted(trace_state["milestones"]),
            "agent": "mav3", "model": model, "coor_type": coor_type,
            "image_mode": img_mode,
            "mav3_call_latency_s": call_lat, "hit_step_limit": 1.0 if hit_limit else 0.0,
            "finished_at": datetime.now().isoformat(timespec="seconds"),
        }
        (ws / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                        encoding="utf-8")
        with open(ws / "trace.jsonl", "w", encoding="utf-8") as f:
            for r in trace_state["rows"]:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        results.append(result)
        print(f"[{tid}] success={result['success']} fail={result['fail_reason']} "
              f"steps={steps} time={result['time_s']}s tokens={tok}", flush=True)

    (out_root / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    ok = sum(1 for r in results if r["success"])
    tot_tok = sum(r["tokens"]["prompt_tokens"] + r["tokens"]["completion_tokens"] for r in results)
    print(f"\n==== MA-v3 汇总 ====\n任务 {len(results)} | 通过 {ok} "
          f"({ok / max(1, len(results)):.1%}) | tokens 合计 {tot_tok:,} | 结果目录 {out_root}")


if __name__ == "__main__":
    main()
