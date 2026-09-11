# -*- coding: utf-8 -*-
from __future__ import annotations
"""
VLM Agent：OpenAI 兼容网关客户端 + 决策循环体。

- 支持带截图（vision）与纯 UI 树文本两种观测；
- 每次调用的 usage 记账（网关缺失 usage 时按字符估算，标注 estimated）；
- 输出解析：优先 ```json 代码块，其次首尾花括号，最后启发式文本。
- 模型网关即你的 Aiwanguan 火山网关（OpenAI 兼容 /v1），视觉任务建议
  doubao-seed-2.1-pro / glm-5.x；纯文本可换 deepseek-v4-pro/flash。
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request

ACTION_SCHEMA = """{
  "action": "click|input|swipe|key|wait|done",
  "x": <int, click 必填：目标控件 bounds 的几何中心>,
  "y": <int, click 必填>,
  "node_text": "<目标控件文本，仅作核对用；坐标优先级高于它>",
  "text": "<input 内容 | 可选>",
  "direction": "up|down|left|right",
  "key": "back|home",
  "seconds": <float>,
  "reason": "<一句话解释这一步>"
}"""

SYSTEM_PROMPT_TMPL = """你是一个运行在鸿蒙设备上的 UI 自动化 Agent，正在执行登录类任务。

任务：{instruction}
可用凭据：{creds}
你已达步数：{step}/{max_steps}

每次观测包含：【屏幕截图（如有）】与【UI 组件树】（含组件类型/id/文本/坐标）。
组件树坐标 (l,t-r,b) 为绝对像素，点击请用几何中心。文本输入前先点击输入框。

输出要求：只输出一个 JSON 动作对象（不要多余文字），JSON 形如：
{action_schema}

动作要领：
- 先处理遮挡的弹窗：更新弹窗点「稍后再说/暂不」，营销弹窗找关闭或「暂时不要」；
- 同意协议前先勾选协议复选框；未勾选时登录按钮通常不可用；
- 倒计时结束前不要重复点「获取验证码」；
- 严守任务约束：任务要求拒绝时绝不要点同意类按钮；
- 所有字段填写完毕并勾选协议后，及时点击登录按钮推进任务；已填过的输入框不要重复点击或重输；
- 只有屏幕/组件树中出现真实的可疑状态（如报错提示）时才修正该字段，否则推进下一步。
- 点击必须以 **x,y 坐标为准**（取目标控件 bounds 的几何中心）；node_text 只作核对，不用于定位。
  若组件树里存在**多个文案完全相同**的控件（例如同名按钮/入口），务必结合截图判断哪一个是目标
  （颜色、位置、上下文），并给出该目标的坐标——只写文案会被判为歧义且不执行；
- 输入文本前必须先点击对应输入框（前一拍），再在下一拍输出 input；
- 确认目标达成时输出 {{"action":"done"}}。""".format


def estimate_tokens(text: str, out: bool = False) -> int:
    return max(1, len(text) // (2 if out else 3))


class OpenAIClient:
    """最小 OpenAI 兼容客户端（stdlib，无三方依赖），带 usage 记账。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float = 0.2, max_tokens: int = 1024, timeout_s: int = 90):
        self.base_url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0, "estimated": 0}

    def chat(self, messages: list[dict], max_tokens: int | None = None) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        started = time.time()
        last_err = None
        for attempt in range(5):  # 429/5xx 指数退避（5/10/20/40s）+ 网络抖动重试
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")[:400]
                if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(5 * (2 ** attempt))
                    continue
                raise RuntimeError(f"模型网关 HTTP {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = e
                if attempt < 4:
                    time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"模型网关网络错误（重试 5 次后放弃）: {last_err}")
        content = ""
        try:
            content = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError):
            raise RuntimeError(f"网关响应缺少 choices: {json.dumps(body)[:300]}")
        usage = body.get("usage") or {}
        if usage:
            self.usage["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
            self.usage["completion_tokens"] += int(usage.get("completion_tokens", 0))
        else:
            self.usage["estimated"] += 1
        self.usage["calls"] += 1
        elapsed = time.time() - started
        return {"content": content, "usage": usage or None, "elapsed_s": elapsed}

    @staticmethod
    def png_data_uri(path: str, max_side: int = 0) -> str:
        """把截图转 data URI；max_side>0 时用 PIL 等比降采样（省 token、降延迟）。"""
        data = None
        if max_side and max_side > 0:
            try:
                from PIL import Image  # 延迟导入：无 PIL 时退回原图
                with Image.open(path) as im:
                    w, h = im.size
                    if max(w, h) > max_side:
                        scale = max_side / float(max(w, h))
                        im = im.convert("RGB").resize((max(1, int(w * scale)), max(1, int(h * scale))))
                        import io
                        buf = io.BytesIO()
                        im.save(buf, format="JPEG", quality=82)
                        data = buf.getvalue()
            except Exception:
                data = None
        if data is None:
            with open(path, "rb") as f:
                data = f.read()
            mime = "image/png"
        else:
            mime = "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"


def parse_action(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if not m:
        m = re.search(r"(\{.*\})", text, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 兜底一：中文/英文动作语句
    m = re.search(r'点(?:击|了)?["\u201c\u300c]?([^"\u201d\u300d，。;；,\n]{1,30})["\u201d\u300d]?', text)
    if m and ("点击" in text or "点" in text):
        return {"action": "click", "node_text": m.group(1).strip(), "reason": "fallback-cn-click"}
    m = re.search(r'输(?:入|了)?[\u201c"]?(.{1,30})[\u201d"]?', text)
    if m and "输入" in text:
        return {"action": "input", "text": m.group(1).strip('\u201d"'), "reason": "fallback-cn-input"}
    low = text.lower()
    if "done" in low or "完成" in text:
        return {"action": "done"}
    if "back" in low or "返回" in text:
        return {"action": "key", "key": "back"}
    return {"action": "wait", "seconds": 1.0, "reason": "unparseable", "raw": text[:200]}


class VLMAgent:
    def __init__(self, client: OpenAIClient, task: dict, agent_cfg: dict, vision: bool = True):
        self.client = client
        self.task = task
        self.cfg = agent_cfg
        self.vision = vision
        self.image_max_side = int(agent_cfg.get("image_max_side", 0) or 0)
        self.prompt_v2 = bool(agent_cfg.get("prompt_v2", False))
        self.history: list[dict] = []
        self.last_image_path: str | None = None

    def _system(self, step: int) -> dict:
        creds = json.dumps(self.task.get("creds", {}), ensure_ascii=False)
        base = SYSTEM_PROMPT_TMPL(
            instruction=self.task.get("instruction", ""),
            creds=creds,
            step=step,
            max_steps=self.cfg.get("max_steps", 30),
            action_schema=ACTION_SCHEMA,
        )
        if self.prompt_v2:
            base += (
                "\n\n【推进纪律 v2】\n"
                f"- 你只有 {self.cfg.get('max_steps', 30)} 步预算，第 {step} 步。请把每一步都用于「产生新状态」；\n"
                "- 禁止重复上一步的等价动作（同一按钮/同一输入框连点视为浪费）；\n"
                "- 若某控件点击后界面无变化，改换策略：换控件、按返回键、或滑动后再试；\n"
                "- 表单类任务的固定次序：勾选协议 → 填字段 → 点确认/登录；已填字段不再触碰；\n"
                "- 输出尽量短：reason 不超过 15 字，不要复述界面内容。"
            )
        return {"role": "system", "content": base}

    def act(self, tree_text: str, screenshot_path: str | None, step: int) -> dict:
        msgs = [self._system(step)]
        for h in self.history[-6:]:
            msgs.append(h)
        content = tree_text[: self.cfg.get("tree_max_text_len", 6000)]
        image_changed = (screenshot_path != self.last_image_path)
        if self.vision and screenshot_path and image_changed:
            uri = OpenAIClient.png_data_uri(screenshot_path, self.image_max_side)
            msgs.append({"role": "user", "content": [
                {"type": "text", "text": "观测（截图 + UI 树）：\n" + content},
                {"type": "image_url", "image_url": {"url": uri}},
            ]})
        else:
            msgs.append({"role": "user", "content": "观测（UI 树）：\n" + content})
        resp = self.client.chat(msgs)
        action = parse_action(resp["content"])
        action.setdefault("reason", "")
        self.history.append({"role": "user", "content": f"[第{step}步观测]\n" + content[:1500]})
        self.history.append({"role": "assistant", "content": resp["content"][:800]})
        self.last_image_path = screenshot_path
        return action