# -*- coding: utf-8 -*-
"""
鸿蒙设备驱动：hdc + uitest 封装。

全部设备命令集中在此文件。标注 TODO-verify 的方法需要在首次连接真实
模拟器/真机时对照 `hdc shell uitest help` 输出校正（见 docs/env-setup.md）。

无 hdc 环境下本模块可被导入（构造 HOSDevice 会延迟报错），以便离线回放开发。
"""
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ACTION_REC_RE = re.compile(r"^\s*(?:hdc\s+)?([^\s]+)")


def _find_hdc() -> str | None:
    hit = shutil.which("hdc")
    if hit:
        return hit
    roots = [Path("C:/Program Files/Huawei"), Path("D:/Program Files/Huawei"),
             Path("G:/360downloads/DevEco Studio"), Path("G:/DevEco Studio"),
             Path("C:/360downloads/DevEco Studio")]
    env_home = os.environ.get("DEVECO_HOME") or os.environ.get("DEVECO_SDK_HOME")
    if env_home:
        roots.insert(0, Path(env_home).parent if os.environ.get("DEVECO_SDK_HOME") else Path(env_home))
    for root in roots:
        if root.exists():
            hits = list(root.glob("**/openharmony/toolchains/hdc.exe"))
            if hits:
                return str(sorted(hits)[-1])
    return None


class HOSDevice:
    def __init__(self, hdc: str = "auto", sn: str = "", timeout_s: int = 30):
        self.hdc = _find_hdc() if hdc == "auto" else hdc
        if not self.hdc:
            raise RuntimeError("未找到 hdc：请安装 DevEco Studio 并把 hdc 加入 PATH（见 docs/env-setup.md）")
        self.sn = sn or self._first_target()
        self.timeout = timeout_s

    # ---------- 底层 ----------
    def _run(self, args, timeout_s: int | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [self.hdc, "-t", self.sn] + args,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout_s or self.timeout,
        )

    def _first_target(self) -> str:
        r = subprocess.run([self.hdc, "list", "targets"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15)
        for line in r.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("[Empty]"):
                return line.split()[0]
        raise RuntimeError("hdc list targets 为空：请先启动模拟器或连接真机")

    # ---------- 应用生命周期 ----------
    def install(self, hap: str | Path) -> None:
        r = self._run(["install", str(hap)], timeout_s=180)
        if r.returncode != 0 or "error" in r.stdout.lower():
            raise RuntimeError(f"hdc install 失败: {r.stdout[-500:]}")

    def start(self, bundle: str, ability: str = "EntryAbility") -> None:
        r = self._run(["shell", "aa", "start", "-a", ability, "-b", bundle])
        if r.returncode != 0:
            raise RuntimeError(f"aa start 失败: {r.stdout[-300:]}")

    def force_stop(self, bundle: str) -> None:
        self._run(["shell", "aa", "force-stop", bundle])

    def wake(self) -> None:
        # 已按 hdc 3.2.0f 实测校准：uiInput keyEvent Power
        for cmd in (["shell", "uitest", "uiInput", "keyEvent", "Power"],
                    ["shell", "power-shell", "wakeup"]):
            try:
                self._run(cmd, timeout_s=10)
                return
            except Exception:
                continue

    # ---------- 观测 ----------
    def screenshot(self, dst: str | Path) -> Path:
        """已按 hdc 3.2.0f 实测校准：uitest screenCap -p 远程路径 → hdc file recv。"""
        dst = Path(dst)
        remote = "/data/local/tmp/bench_s.png"
        r1 = self._run(["shell", "uitest", "screenCap", "-p", remote], timeout_s=30)
        if r1.returncode != 0 or "Fail" in r1.stdout:
            raise RuntimeError(f"截图失败: {r1.stdout[-200:]}")
        self._run(["file", "recv", remote, str(dst)], timeout_s=60)
        if not dst.exists() or dst.stat().st_size == 0:
            raise RuntimeError(f"截图失败：文件未回传（{r1.stdout[-200:]}）")
        return dst

    def dump_tree(self, bundle: str | None = None) -> dict:
        """UI 组件树。已按 hdc 3.2.0f 实测校准：
        uitest dumpLayout -p 落盘 → file recv；输出为多窗口 JSON 拼接体。
        bundle 非空时用 -b 只取目标应用窗口，避免冷启动期陈旧窗口串台。"""
        remote = "/data/local/tmp/bench_tree.json"
        local = "._bench_tree.json"
        args = ["shell", "uitest", "dumpLayout", "-p", remote]
        if bundle:
            args += ["-b", bundle]
        r = self._run(args, timeout_s=45)
        if r.returncode != 0 or "Fail" in r.stdout:
            raise RuntimeError(f"dumpLayout 失败: {r.stdout[-200:]}")
        self._run(["file", "recv", remote, str(local)], timeout_s=60)
        raw = Path(local).read_text(encoding="utf-8", errors="replace")
        nodes: list[dict] = []
        dec = json.JSONDecoder()
        idx, n = 0, len(raw)
        roots = []
        while idx < n:
            while idx < n and raw[idx] in " \t\r\n":
                idx += 1
            if idx >= n:
                break
            try:
                obj, end = dec.raw_decode(raw, idx)
            except json.JSONDecodeError:
                idx += 1
                continue
            roots.append(obj)
            idx = end
        for data in roots:
            flatten_nodes(data, nodes, 0, 40)
        # 简易去重：按 (type,text,bounds) 计数去重（多窗口重复节点）
        seen = set()
        uniq = []
        for nd in nodes:
            sig = (nd.get("type"), nd.get("text"), json.dumps(nd.get("bounds", {}), sort_keys=True))
            if sig in seen:
                continue
            seen.add(sig)
            uniq.append(nd)
        return {"raw": raw, "nodes": uniq}

    def text_snapshot(self, tree: dict, limit: int = 200) -> str:
        """把组件树渲染成适合塞进 prompt 的紧凑文本。"""
        lines = []
        for n in tree.get("nodes", [])[:limit]:
            tid = n.get("id") or ""
            text = (n.get("text") or "")[:60]
            bounds = n.get("bounds") or {}
            box = f"{bounds.get('l', 0)},{bounds.get('t', 0)}-{bounds.get('r', 0)},{bounds.get('b', 0)}"
            lines.append(f"[{n.get('type', '?')}] id={tid} text={text!r} @{box}")
        return "\n".join(lines)

    # ---------- 动作 ----------
    def click(self, x: int, y: int) -> None:
        r = self._run(["shell", "uitest", "uiInput", "click", str(int(x)), str(int(y))], timeout_s=20)
        if r.returncode != 0:
            raise RuntimeError(f"click 失败: {r.stdout[-200:]}")

    def click_node(self, node: dict) -> None:
        b = node.get("bounds", {})
        cx = (b.get("l", 0) + b.get("r", 0)) // 2
        cy = (b.get("t", 0) + b.get("b", 0)) // 2
        self.click(cx, cy)

    def input_text(self, text: str) -> None:
        # 已按 hdc 3.2.0f 实测校准：uiInput text 输入到已聚焦组件（先 click 聚焦）
        self._run(["shell", "uitest", "uiInput", "text", text], timeout_s=20)

    def long_press(self, x: int, y: int, ms: int = 800) -> None:
        self._run(["shell", "uitest", "uiInput", "longClick", str(int(x)), str(int(y))], timeout_s=20)

    def swipe_dir(self, direction: str = "up", dist: int = 600) -> None:
        # 屏幕居中竖滑；left/right 亦支持
        x = 540
        y0 = {"up": (1600, 900), "down": (900, 1600),
              "left": (900, 1200), "right": (300, 1200)}.get(direction, (1600, 900))
        self.swipe(x, y0[0], x, y0[1])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 300) -> None:
        # 已校准：uiInput swipe 无 velocity 时默认 600
        self._run(["shell", "uitest", "uiInput", "swipe",
                   str(x1), str(y1), str(x2), str(y2)], timeout_s=20)

    def key(self, name: str) -> None:
        if name == "back":
            self._run(["shell", "uitest", "uiInput", "keyEvent", "Back"], timeout_s=20)
        elif name == "home":
            self._run(["shell", "uitest", "uiInput", "keyEvent", "Home"], timeout_s=20)
        else:
            raise ValueError(f"unknown key: {name}")

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)


def _parse_bounds(b: str) -> dict:
    """'[l,t][r,b]' → {'l','t','r','b'} ints."""
    m = re.match(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]", b or "")
    if not m:
        return {}
    return {"l": int(m.group(1)), "t": int(m.group(2)), "r": int(m.group(3)), "b": int(m.group(4))}


def flatten_nodes(obj, acc: list | None = None, depth: int = 0, max_depth: int = 40) -> list[dict]:
    """dumpLayout 输出拍平（节点是 {attributes:{type,text,id,bounds,...}, children:[...]}）。"""
    if acc is None:
        acc = []
    if depth > max_depth or not isinstance(obj, (dict, list)):
        return acc
    if isinstance(obj, list):
        for item in obj:
            flatten_nodes(item, acc, depth + 1, max_depth)
        return acc
    attr = obj.get("attributes") or obj
    text = attr.get("text", "") or ""
    if not text:
        # 真实 UI：输入框占位符在 hint，文本可能在 originalText/description
        text = attr.get("hint", "") or attr.get("originalText", "") or attr.get("description", "")
    # 观测契约：**故意不提取 backgroundColor** 等纯视觉属性。颜色只应存在于像素层，
    # 否则 colorgate / pay-colorgate 这类视觉门控题对文本智能体就不再是门控
    # （dumpLayout 原始输出里确实带 backgroundColor，这里主动丢弃；sim 端同样剥离 color）。
    node = {
        "type": attr.get("type", "node"),
        "text": text,
        "id": attr.get("id", "") or (attr.get("key", "") or ""),
        "clickable": str(attr.get("clickable", "")).lower() in ("true", "1"),
        "focusable": str(attr.get("focused", "")).lower() in ("true", "1"),
        "checked": str(attr.get("checked", "")).lower() == "true",
        "enabled": str(attr.get("enabled", "")).lower() != "false",
        "bounds": _parse_bounds(attr.get("bounds", "")),
    }
    if attr.get("description"):
        node["description"] = attr["description"]
    acc.append(node)
    children = obj.get("children") or obj.get("childNodes") or []
    for child in children:
        flatten_nodes(child, acc, depth + 1, max_depth)
    return acc


def find_node_by_text(nodes: list[dict], text: str, exact: bool = False) -> dict | None:
    matches = [n for n in nodes
               if ((n.get("text") or "") == text if exact else text in (n.get("text") or ""))]
    for n in matches:  # 优先可点击组件（避免命中「密码登录」类标题）
        if n.get("clickable"):
            return n
    return matches[0] if matches else None


if os.environ.get("BENCH_ENV_SMOKE"):
    print("HOSDevice import OK; hdc=", _find_hdc() or "NOT FOUND")