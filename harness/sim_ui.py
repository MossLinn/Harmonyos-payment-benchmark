# -*- coding: utf-8 -*-
"""
离线模拟器：把三个 ArkTS 模板的状态机在 Python 里精确镜像，供 harness 在
**无鸿蒙设备**时端到端运行（Agent 决策 → 执行 → 判定 → 计分全链路），
也作为「合成 UI 评测」的快车道——烧 token 不依赖设备吞吐。

与真实设备的两条约定：
1. 组件树节点与 HOSDevice.dump_tree() 的节点同构（type/text/id/bounds/clickable），
   判定器与基线 Agent 无需感知差异；
2. 页面可按需渲染成 PNG（PIL 可用时绘制中文文本 UI），视觉模型路径同样可测。

动作语义（与真机等价）：
- click(x,y)/click(node) 命中节点后触发其 handler；
- input(text) 写入最近聚焦的输入框（click 输入框 = 聚焦）；
- key('back') 取消聚焦；wait(s) 推进倒计时/锁定冷却。
"""
import json
import random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False


def _font(size: int):
    for name in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _node(typ, text, key, y, h=110, x0=120, x1=960, clickable=True, nid="", color=None):
    n = {"type": typ, "text": text, "id": nid, "key": key, "clickable": clickable,
         "bounds": {"l": x0, "t": y, "r": x1, "b": y + h}}
    if color:
        n["color"] = color
    return n


class SimApp:
    """基类：三种模板共用的页面 node 组装与点击分发。"""

    def __init__(self, variant: dict):
        self.variant = variant
        self.slots = variant.get("slots", {})
        self.task = variant.get("task", {})
        self.focus: str | None = None

    # ---- 由子类实现 ----
    def nodes(self) -> list[dict]:
        raise NotImplementedError

    def on_key(self, key: str) -> None:
        raise NotImplementedError

    def on_input(self, text: str) -> None:
        raise NotImplementedError

    def on_wait(self, seconds: float) -> None:
        raise NotImplementedError

    def on_swipe(self, direction: str) -> None:
        pass  # 默认无滚动语义；子类按需覆盖

    # ---- 通用 ----
    def click(self, x: int, y: int) -> None:
        for n in self.nodes():
            b = n["bounds"]
            if b["l"] <= x <= b["r"] and b["t"] <= y <= b["b"] and n.get("clickable"):
                self.on_key(n["key"])
                return
        # 点击空白：无效果（与真实 UI 行为一致）

    def render_png(self, dst) -> bool:
        if not PIL_OK:
            return False
        W, H = 720, 1280
        img = Image.new("RGB", (W, H), "#F2F3F5")
        d = ImageDraw.Draw(img)
        f_title = _font(30)
        f_body = _font(24)
        f_small = _font(20)
        scale_x = W / 1080
        scale_y = H / 1920
        for n in self.nodes():
            b = n["bounds"]
            x0, y0 = int(b["l"] * scale_x), int(b["t"] * scale_y)
            x1, y1 = int(b["r"] * scale_x), int(b["b"] * scale_y)
            t = n.get("text") or ""
            if n["type"] == "Button":
                fill = n.get("color") or "#FFFFFF"
                d.rounded_rectangle([x0, y0, x1, y1], radius=10, fill=fill, outline="#CCCCCC")
                txt = "#FFFFFF" if n.get("color") else "#333333"
                d.text((x0 + 12, y0 + 8), t[:24], font=f_body, fill=txt)
            elif n["type"] == "TextInput":
                d.rounded_rectangle([x0, y0, x1, y1], radius=8, fill="#FFFFFF", outline="#999999")
                d.text((x0 + 12, y0 + 8), t[:24] or " ", font=f_body, fill="#888888")
            else:
                size = f_title if n.get("id") in ("welcome_marker", "browse_marker") else f_body
                d.text((x0, y0), t[:36], font=size, fill="#111111")
            if n.get("id"):
                d.text((x0, y0 - 26), "·marker:" + n["id"], font=f_small, fill="#FF3B30")
        for k, v in self.extra_hint().items():
            d.text((20, 20 + 40 * list(self.extra_hint()).index(k)), v, font=f_small, fill="#007DFF")
        self.draw_extra(d, scale_x, scale_y)
        img.save(dst)
        return True

    def extra_hint(self) -> dict:
        return {"step": self.__class__.__name__}

    def draw_extra(self, d, scale_x: float, scale_y: float) -> None:
        pass  # 子类可在渲染图上补画视觉专属内容（树里不存在）


class PaymentApp(SimApp):
    """PaymentPage.ets 镜像：四渠道支付 + 故障形态（broken/dead/blank/allbroken）。"""

    LABEL = {"wechat": "微信支付", "alipay": "支付宝", "bankcard": "银行卡支付", "huawei": "华为支付"}

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.channels = json.loads(s.get("CHANNELS_JSON", "[]"))
        self.chan_map = {c.get("key"): c for c in self.channels}
        self.broken = json.loads(s.get("BROKEN_JSON", "[]"))
        self.dead = json.loads(s.get("DEAD_JSON", "[]"))
        self.blank_list = json.loads(s.get("BLANK_JSON", "[]"))
        self.all_broken = s.get("ALL_BROKEN", "false") == "true"
        self.twice = s.get("TWICE_POPUP", "false") == "true"
        self.mismatch = s.get("MISMATCH", "false") == "true"
        self.refund_on = s.get("REFUND_ENABLED", "false") == "true"
        self.timeout_sec = int(s.get("PAY_TIMEOUT_SEC", "0") or 0)
        self.popup_amount = s.get("POPUP_AMOUNT", s.get("AMOUNT", "9.90"))
        self.pwd_ok = s.get("PAY_PWD", "123456")
        self.agree = False
        self.chan = ""
        self.blank = False
        self.pwd = ""
        self.err = ""
        self.done = False
        self.cancel_alert = False
        self.refund = False
        self.left = 0
        self.ime_open = False
        self.agree_trap = s.get("AGREE_TRAP", "false") == "true"
        self.popup_margin = int(s.get("POPUP_MARGIN", "60") or 60)

    # 软键盘弹出且弹窗位置过低时，按钮被裁出组件树（真机实测阈值在 1411~1513px 之间）
    CLIP_MARGIN = 200

    @property
    def ime_clipped(self) -> bool:
        return bool(self.ime_open and self.popup_margin >= self.CLIP_MARGIN and self.chan
                    and not self.chan.endswith((":dead", ":twice")))

    def label(self, key):
        return self.LABEL.get(key, key)

    def nodes(self):
        s = self.slots
        if self.refund:
            return [
                _node("Text", s.get("REFUND_TEXT", "退款申请已提交"), None, 830, clickable=False, nid="refund_marker"),
                _node("Text", s["TASK_ID"], None, 950, clickable=False),
            ]
        if self.done:
            out = [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
            ]
            if self.refund_on:
                out.append(_node("Button", "申请退款", "btn:refund", 950, h=90, clickable=True))
            out.append(_node("Text", s["TASK_ID"], None, 1080, clickable=False))
            return out
        if self.cancel_alert:
            return [
                _node("Text", s.get("CANCEL_ALERT_TEXT", "已取消支付"), None, 760, h=110,
                      clickable=False, nid="cancel_alert_marker"),
                _node("Button", "我知道了", "btn:ack", 900, h=90, clickable=True),
            ]
        if self.chan == "timeout":
            return [
                _node("Text", s.get("PAY_TIMEOUT_TEXT", "支付超时，订单已关闭"), None, 760, h=110,
                      clickable=False, nid="timeout_marker"),
                _node("Text", s["TASK_ID"], None, 950, h=60, clickable=False),
            ]
        if self.blank:
            return [_node("Text", "（空白页面）", None, 900, h=60, clickable=False)]
        if self.chan == "fail":
            return [
                _node("Text", self.err, None, 700, h=110, clickable=False),
                _node("Button", "更换支付方式", "btn:switch", 840, h=90, clickable=True),
            ]
        if self.chan.endswith(":dead"):
            return [
                _node("Text", self.label(self.chan.split(":")[0]), None, 700, h=90, clickable=False),
                _node("Text", f"¥ {self.popup_amount}", None, 810, h=70, clickable=False),
                _node("Text", "（弹窗内容异常，无确认按钮）", None, 900, h=60, clickable=False),
            ]
        if self.chan.endswith(":twice"):
            out = [
                _node("Text", "再次确认支付", None, 620, h=100, clickable=False),
                _node("Text", f"订单金额：¥ {self.popup_amount}", None, 740, h=70, clickable=False),
            ]
            if self.timeout_sec > 0:
                out.append(_node("Text", f"剩余支付时间：{self.left}s", None, 820, h=60, clickable=False))
            out += [
                _node("Button", "确认支付", "btn:pay", 900, h=100, clickable=True),
                _node("Button", "返回修改", "btn:backmod", 1030, h=90, clickable=True),
            ]
            return out
        if self.chan == "none":
            return [
                _node("Text", s.get("ALL_BROKEN_TEXT", "暂无可用的支付方式"), None, 700, h=110, clickable=False),
                _node("Text", s["TASK_ID"], None, 950, h=60, clickable=False),
            ]
        if self.chan:
            out = [
                _node("Text", self.label(self.chan), None, 620, h=100, clickable=False, nid=f"pay_popup_{self.chan}"),
                _node("Text", f"订单金额：¥ {self.popup_amount}", None, 740, h=70, clickable=False),
            ]
            if self.timeout_sec > 0:
                out.append(_node("Text", f"剩余支付时间：{self.left}s", None, 820, h=60, clickable=False))
            # 真机一致性：输入后占位符被实际内容（掩码）取代，不能再靠占位符识别弹窗
            pwd_txt = ("*" * len(self.pwd)) if self.pwd else "请输入支付密码"
            out.append(_node("TextInput", pwd_txt, "in:pwd", 900, h=90, clickable=True))
            if self.ime_clipped:
                # B10：软键盘弹出后视口被压缩，弹窗位置过低 → 确认/取消按钮被裁出组件树
                out.append(_node("Text", "（软键盘已弹出）", None, 1020, h=60, clickable=False))
            else:
                out += [
                    _node("Button", "确认支付", "btn:pay", 1020, h=100, clickable=True),
                    _node("Button", "取消", "btn:cancel", 1150, h=90, clickable=True),
                ]
            if self.err:
                out.append(_node("Text", self.err, None, 1270, h=60, clickable=False))
            return out
        # 主支付页
        y = 400
        out = [
            _node("Text", "订单支付", None, 340, h=80, clickable=False),
            _node("Text", s.get("ORDER_TITLE", "订单"), None, 430, h=60, clickable=False),
            _node("Text", f"应付金额：¥ {s.get('AMOUNT', '9.90')}", None, 500, h=70, clickable=False),
        ]
        if self.agree_trap:
            # B11：只有小方块可点，文字标签不可点（还原真机热区缺陷）
            out += [
                _node("Checkbox", "✓" if self.agree else "〇", "chk:agree", 580, h=90, clickable=True),
                _node("Text", "我已阅读并同意《支付协议》", None, 580, h=90, x0=220, clickable=False),
            ]
        else:
            out.append(_node("Checkbox", ("✓" if self.agree else "〇") + " 我已阅读并同意《支付协议》",
                             "chk:agree", 580, h=90, clickable=True))
        out.append(_node("Text", "选择支付方式", None, 690, h=60, clickable=False))
        for c in self.channels:
            out.append(_node("Button", c["label"], f"ch:{c['key']}", y, h=100, clickable=True,
                             color=c.get("color") or None))
            y += 120
        if self.err:
            out.append(_node("Text", self.err, None, y, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, y + 80, h=60, clickable=False))
        return out

    def on_key(self, key: str) -> None:
        if key == "back":
            if self.ime_open:
                # 第一下返回键只收起软键盘，弹窗保持（真机行为待验证）
                self.ime_open = False
                self.focus = None
                return
            if self.chan or self.blank:
                self.chan = ""
                self.blank = False
                self.pwd = ""
                self.ime_open = False
            return
        if key == "chk:agree":
            self.agree = True
        elif key == "btn:switch":
            self.chan = ""
            self.err = ""
        elif key == "btn:cancel":
            self.chan = ""
            self.pwd = ""
            self.err = ""
            self.left = 0
            if self.mismatch:
                self.cancel_alert = True
        elif key == "btn:ack":
            self.cancel_alert = False
        elif key == "btn:refund":
            self.refund = True
        elif key == "in:pwd":
            self.focus = "pwd"
            self.ime_open = True
        elif key == "btn:pay":
            if not self.agree:
                self.err = self.slots.get("ERR_AGREE", "请先阅读并同意支付协议")
            elif self.pwd != self.pwd_ok:
                self.err = self.slots.get("ERR_PWD", "支付密码错误")
            elif self.twice and not self.chan.endswith(":twice"):
                self.chan = self.chan + ":twice"
            else:
                self.err = ""
                self.done = True
        elif key == "btn:backmod":
            self.chan = self.chan.split(":")[0]
            self.pwd = ""
        elif str(key).startswith("ch:"):
            k = key.split(":")[1]
            self.err = ""
            entry = self.chan_map.get(k, {})
            if entry.get("decoy") is True:
                # 视觉门控：假冒入口（文字与正规入口相同，仅颜色不同）
                self.err = "该入口不是正规支付通道，已为你拦截"
                self.chan = "fail"
            elif self.all_broken:
                self.err = self.slots.get("ALL_BROKEN_TEXT", "暂无可用的支付方式")
                self.chan = "none"
            elif k in self.broken:
                self.err = self.slots.get("ERR_TEXT", "{CH}拉起失败").replace("{CH}", self.label(k))
                self.chan = "fail"
            elif k in self.blank_list:
                self.blank = True
                self.chan = k
            elif k in self.dead:
                self.chan = k + ":dead"
            else:
                self.chan = k
                self.left = self.timeout_sec  # 弹窗拉起即开始倒计时（0=不限时）

    def on_input(self, text: str) -> None:
        if self.focus == "pwd":
            self.pwd = text[:6]

    def on_wait(self, seconds: float) -> None:
        # 支付超时语义：仅在「真弹窗/二次确认」状态下计时
        if self.timeout_sec <= 0 or not self.chan or self.chan in ("fail", "none", "timeout"):
            return
        if self.chan.endswith(":dead"):
            return
        self.left = max(0, self.left - int(seconds))
        if self.left <= 0:
            self.chan = "timeout"
            self.pwd = ""


class T5App(SimApp):
    """T5Captcha.ets 镜像：slider / clickchars / hidden 三种高难形态。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.style = s["STYLE"]
        self.slider_value = 0
        self.slider_done = False
        self.clicked: list = []
        self.order = json.loads(s.get("ORDER_JSON", "[0,1,2,3]"))
        self.chars = [s[k] for k in ("C1", "C2", "C3", "C4")]
        self.err = ""
        self.show_more = False
        self.agree = False
        self.done = False
        self.target = int(s.get("SLIDER_TARGET", "50"))
        self.slider_value = int(s.get("SLIDER_START", "0") or 0)

    def nodes(self):
        s = self.slots
        if self.done:
            return [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                _node("Text", s["TASK_ID"], None, 950, clickable=False),
            ]
        if self.style == "slider":
            return [
                _node("Text", s["SLIDER_QUESTION"], None, 520, h=80, clickable=False),
                _node("Text", "将滑块拖到与上方缺口对齐的位置", None, 620, h=60, clickable=False),
                _node("Slider", f"滑块(缺口中)位置无数字答案", "sld", 780, h=90, clickable=True),
                _node("Text", s["TASK_ID"], None, 950, h=60, clickable=False),
            ]
        if self.style == "clickchars":
            out = [_node("Text", s["CH_QUESTION"], None, 520, h=80, clickable=False)]
            for i in range(4):
                c = self.chars[i]
                col = i % 4
                out.append(_node("Text", c, f"ch:{i}", 700, h=120,
                                 x0=120 + col * 210, x1=300 + col * 210, clickable=True))
            if self.err:
                out.append(_node("Text", self.err, None, 1100, h=60, clickable=False))
            out.append(_node("Text", s["TASK_ID"], None, 1250, h=60, clickable=False))
            return out
        # hidden
        out = [_node("Text", "登录", None, 500, h=80, clickable=False),
               _node("Text", s["HIDDEN_HINT"], None, 600, h=60, clickable=False)]
        if not self.show_more:
            out.append(_node("Button", "更多", "more", 700, h=90, clickable=True))
        else:
            mark = "✓" if self.agree else "〇"
            out.append(_node("Checkbox", f"{mark} 我已阅读并同意《用户协议》与《隐私政策》",
                             "chk:agree", 700, h=90, clickable=True))
            out.append(_node("Text", s["HIDDEN_EXTRA"], None, 810, h=60, clickable=False))
            if self.agree:
                out.append(_node("Button", "登录", "btn:login", 900, h=90, clickable=True))
        out.append(_node("Text", s["TASK_ID"], None, 1050, h=60, clickable=False))
        return out

    def on_key(self, key: str) -> None:
        if key == "sld":
            return  # 滑块靠 on_swipe 驱动
        if str(key).startswith("ch:"):
            i = int(key.split(":")[1])
            ok = (i == self.order[len(self.clicked)]) if len(self.clicked) < len(self.order) else False
            if ok:
                self.clicked.append(i)
                self.err = ""
                if len(self.clicked) == len(self.order):
                    self.done = True
            else:
                self.clicked = []
                self.err = "顺序错误，请按题面从头点击"
        elif key == "more":
            self.show_more = True
        elif key == "chk:agree":
            self.agree = True
        elif key == "btn:login":
            self.done = True

    def on_swipe(self, direction: str) -> None:
        if self.style == "slider" and direction in ("right", "left"):
            delta = 25 if direction == "right" else -25
            self.slider_value = max(0, min(100, self.slider_value + delta))
            if abs(self.slider_value - self.target) <= 2:
                self.done = True

    def on_input(self, text: str) -> None:
        pass

    def on_wait(self, seconds: float) -> None:
        pass


class PrivacyApp(SimApp):
    """PrivacyDialog.ets 的镜像：full / seg / mislead 三种样式。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.style = s["STYLE"]
        self.n_clauses = int(s.get("CLAUSE_COUNT", "1"))
        self.close_taps = 0
        self.mislead_close_taps = int(s.get("MISLEAD_CLOSE_TAPS", "0"))
        self.clause_checked = [False] * self.n_clauses
        self.need_scroll = s.get("NEED_SCROLL", "false") == "true"
        self.scroll_pos = 0
        self.stage = "privacy"
        # 视觉门控公平性：同文异色按钮的左右位置按种子洗牌（文本智能体只能猜 50%）
        shuffle = s.get("SHUFFLE", "false") == "true"
        if self.style == "colorgate" and shuffle:
            self.green_left = random.Random(variant.get("_seed", 0) + 7).random() < 0.5
        else:
            self.green_left = True

    def on_swipe(self, direction: str) -> None:
        # 滚动语义：勾选项位于协议正文底部，需先上滑
        if self.style == "seg" and self.need_scroll:
            if direction == "up":
                self.scroll_pos = 1
            elif direction == "down":
                self.scroll_pos = 0

    def all_checked(self):
        return all(self.clause_checked)

    def nodes(self):
        s = self.slots
        if self.stage == "done":
            return [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                _node("Text", s["TASK_ID"], None, 950, clickable=False),
            ]
        if self.stage == "browse":
            return [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", "您已选择暂不同意", None, 830, clickable=False, nid="browse_marker"),
                _node("Text", "仅浏览模式：部分功能不可用", None, 950, clickable=False),
                _node("Text", s["TASK_ID"], None, 1070, clickable=False),
            ]
        out = [_node("Text", s["TITLE"], None, 400, h=80, clickable=False)]
        if self.style == "mislead":
            out.append(_node("Button", "×", "btn:close", 520, h=80, x0=800, x1=900, clickable=True))
        body_h = int(s.get("BODY_HEIGHT", "260"))
        out.append(_node("Text", s["BODY"][:120] + "…", None, 620, h=min(body_h, 260), clickable=False))
        y = 900
        if self.style == "seg":
            visible = (not self.need_scroll) or self.scroll_pos > 0
            if visible:
                labels = json.loads(s.get("CLAUSE_LABELS", "[]"))
                for i in range(self.n_clauses):
                    label = labels[i] if i < len(labels) else f"条款 {i+1}"
                    mark = "✓" if self.clause_checked[i] else "〇"
                    out.append(_node("Checkbox", f"{mark} {label}", f"chk:{i}", y, h=90))
                    y += 100
            else:
                out.append(_node("Text", "（继续向上滑动，查看正文底部的条款勾选）", None, 900, h=60, clickable=False))
                return out
        if self.style == "colorgate":
            if self.green_left:
                out.append(_node("Button", s["DUAL_LABEL"], "btn:agree", y, h=96, x0=120, x1=520, color="#22AA55"))
                out.append(_node("Button", s["DUAL_LABEL"], "btn:red", y, h=96, x0=540, x1=960, color="#EE4444"))
            else:
                out.append(_node("Button", s["DUAL_LABEL"], "btn:red", y, h=96, x0=120, x1=520, color="#EE4444"))
                out.append(_node("Button", s["DUAL_LABEL"], "btn:agree", y, h=96, x0=540, x1=960, color="#22AA55"))
        elif self.style == "mislead":
            out.append(_node("Button", s["DECLINE_LABEL"], "btn:decline", y, h=76, x0=120, x1=460))
            out.append(_node("Button", s["AGREE_LABEL"], "btn:agree", y, h=96, x0=480, x1=960))
        else:
            out.append(_node("Button", s["AGREE_LABEL"], "btn:agree", y, h=90, x0=120, x1=520))
            out.append(_node("Button", s["DECLINE_LABEL"], "btn:decline", y, h=90, x0=540, x1=960))
        return out

    def decline(self):
        if self.style in ("mislead", "colorgate"):
            self.stage = "browse"
        return

    def on_key(self, key: str) -> None:
        if key == "btn:agree":
            if self.style == "seg" and not self.all_checked():
                return  # 勾选未齐：按钮不可用
            self.stage = "done"
        elif key == "btn:decline":
            self.decline()
        elif key == "btn:red":
            self.decline()  # colorgate：红色按钮 = 错误路径（同文案不同色）
        elif key == "btn:close":
            self.close_taps += 1  # 假关闭：状态不变
        elif str(key).startswith("chk:"):
            i = int(key.split(":")[1])
            self.clause_checked[i] = not self.clause_checked[i]

    def on_input(self, text: str) -> None:
        pass

    def on_wait(self, seconds: float) -> None:
        pass


class PhoneCodeApp(SimApp):
    """PhoneCodeLogin.ets 的镜像：弹窗链 → 验证码登录 → done。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.chain = json.loads(s.get("CHAIN", "[]"))
        self.chain_idx = 0
        self.phone = ""
        self.code = ""
        self.agree = False
        self.sent = False
        self.countdown = 0
        self.err = ""
        self.freq = ""
        self.phone_len = int(s.get("PHONE_LEN", "11"))
        self.code_len = int(s.get("CODE_LEN", "6"))
        self.correct = s["CODE"]
        self.autofill_code = s.get("AUTOFILL_CODE", s["CODE"])
        self.autofill_on = s.get("SHOW_AUTOFILL", "false") == "true"
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                _node("Text", s["TASK_ID"], None, 950, clickable=False),
            ]
        if self.chain_idx < len(self.chain):
            item = self.chain[self.chain_idx]
            out = [
                _node("Text", item["title"], None, 560, h=90, clickable=False),
                _node("Text", item["body"], None, 680, h=160, clickable=False),
                _node("Button", item["btnMain"], "chain:main", 900, h=100),
            ]
            if item.get("closable"):
                out.append(_node("Button", item["btnAlt"], "chain:alt", 1040, h=100))
            return out
        y = 300
        out = [_node("Text", "登录", None, 260, h=90, clickable=False),
               _node("TextInput", "请输入手机号" + (f"（{self.phone}）" if self.phone else ""), "in:phone", y, h=90)]
        y += 120
        out.append(_node("TextInput", "请输入验证码" + (f"（{self.code}）" if self.code else ""), "in:code", y, h=90, x0=120, x1=640))
        send_label = f"{self.countdown}s 后重发" if self.countdown > 0 else "获取验证码"
        out.append(_node("Button", send_label, "btn:send", y, h=90, x0=660, x1=960,
                         clickable=len(self.phone) == self.phone_len))
        y += 120
        if self.autofill_on:
            out.append(_node("Text", s["AUTOFILL_HINT"], None, y, h=60, clickable=False))
            out.append(_node("Button", "模拟短信自动填充", "btn:autofill", y + 40, h=90))
            y += 160
        mark = "✓" if self.agree else "〇"
        out.append(_node("Checkbox", f"{mark} 我已阅读并同意《用户协议》与《隐私政策》", "chk:agree", y, h=90))
        y += 120
        out.append(_node("Button", "登录", "btn:login", y, h=100, clickable=self.agree))
        y += 130
        if self.err:
            out.append(_node("Text", self.err, None, y, h=60, clickable=False))
            y += 70
        if self.freq:
            out.append(_node("Text", self.freq, None, y, h=60, clickable=False))
            y += 70
        out.append(_node("Text", s["TASK_ID"], None, y + 60, h=60, clickable=False))
        return out

    def on_key(self, key: str) -> None:
        if key == "chain:main":
            self.chain_idx += 1
        elif key == "chain:alt":
            self.chain_idx += 1
        elif key == "in:phone":
            self.focus = "phone"
        elif key == "in:code":
            self.focus = "code"
        elif key == "btn:send":
            if self.countdown > 0:
                self.freq = self.slots["FREQ_LIMIT_HINT"]
                return
            if len(self.phone) != self.phone_len:
                self.err = self.slots["ERR_PHONE"]
                return
            self.err = ""
            self.freq = ""
            self.sent = True
            self.countdown = int(self.slots["COUNTDOWN_SEC"])
        elif key == "btn:autofill":
            self.code = self.autofill_code
            self.err = ""
        elif key == "chk:agree":
            self.agree = not self.agree
        elif key == "btn:login":
            if not self.agree:
                self.err = self.slots["ERR_AGREE"]
            elif len(self.code) != self.code_len:
                self.err = self.slots["ERR_CODE_FMT"]
            elif self.code != self.correct:
                self.err = self.slots["ERR_CODE_WRONG"]
            else:
                self.err = ""
                self.done = True

    def on_input(self, text: str) -> None:
        if self.focus == "phone":
            self.phone = text[: self.phone_len]
        elif self.focus == "code":
            self.code = text[: self.code_len]

    def on_wait(self, seconds: float) -> None:
        if self.countdown > 0:
            self.countdown = max(0, self.countdown - int(seconds))


class PwdApp(SimApp):
    """PwdLogin.ets 的镜像：密码 + 算式验证码 + 锁定风控。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.phone = ""
        self.pwd = ""
        self.ans = ""
        self.agree = False
        self.show_pwd = False
        self.err = ""
        self.wrong = 0
        self.locked = False
        self.lock_left = 0
        self.phone_len = int(s.get("PHONE_LEN", "11"))
        self.a = int(s["CAPTCHA_A"]) if "CAPTCHA_A" in s else 0
        self.b = int(s["CAPTCHA_B"]) if "CAPTCHA_B" in s else 0
        self.captcha_kind = s.get("CAPTCHA_KIND", "match")
        self.captcha_text = s.get("CAPTCHA_TEXT", "")
        self.lock_after = int(s.get("LOCK_AFTER", "5"))
        self.lock_seconds = int(s.get("LOCK_SECONDS", "60"))
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [
                _node("Text", s["APP_NAME"], None, 700, clickable=False),
                _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                _node("Text", s["TASK_ID"], None, 950, clickable=False),
            ]
        y = 300
        out = [_node("Text", "密码登录", None, 260, h=90, clickable=False),
               _node("TextInput", "请输入手机号" + (f"（{self.phone}）" if self.phone else ""), "in:phone", y, h=90)]
        y += 130
        masked = "*" * len(self.pwd) if not self.show_pwd else self.pwd
        out.append(_node("TextInput", "请输入密码" + (f"（{masked}）" if masked else ""), "in:pwd", y, h=90, x0=120, x1=640))
        out.append(_node("Button", "隐藏" if self.show_pwd else "显示", "btn:toggle", y, h=90, x0=660, x1=960))
        y += 130
        if self.captcha_kind == "colortext":
            # 视觉门控：验证码内容只画在像素上，树里无文本
            out.append(_node("Canvas", " ", "cap", y, h=90, x0=120, x1=320, clickable=False))
            out.append(_node("Text", "输入图中蓝色字符", None, y, h=60, x0=340, x1=470, clickable=False))
        else:
            out.append(_node("Text", f"图形验证码：{self.a} + {self.b} = ?", None, y, h=90, clickable=False))
        out.append(_node("TextInput", "请输入结果" + (f"（{self.ans}）" if self.ans else ""), "in:ans", y, h=90, x0=480, x1=960))
        y += 130
        mark = "✓" if self.agree else "〇"
        out.append(_node("Checkbox", f"{mark} 我已阅读并同意《用户协议》与《隐私政策》", "chk:agree", y, h=90))
        y += 130
        btn_label = f"锁定中 {self.lock_left}s" if self.locked else "登录"
        out.append(_node("Button", btn_label, "btn:login", y, h=100, clickable=self.agree and not self.locked))
        y += 130
        if self.err:
            out.append(_node("Text", self.err, None, y, h=60, clickable=False))
            y += 70
        out.append(_node("Button", "忘记密码？", "btn:forgot", y, h=70))
        out.append(_node("Text", s["TASK_ID"], None, y + 110, h=60, clickable=False))
        return out

    def on_key(self, key: str) -> None:
        if key == "in:phone":
            self.focus = "phone"
        elif key == "in:pwd":
            self.focus = "pwd"
        elif key == "in:ans":
            self.focus = "ans"
        elif key == "btn:toggle":
            self.show_pwd = not self.show_pwd
        elif key == "btn:forgot":
            self.err = self.slots["ERR_FORGOT"]
        elif key == "chk:agree":
            self.agree = not self.agree
        elif key == "btn:login":
            self._login()

    def _login(self):
        if not self.agree:
            self.err = self.slots["ERR_AGREE"]
            return
        if len(self.phone) != self.phone_len:
            self.err = self.slots["ERR_PHONE"]
            return
        if self.captcha_kind == "colortext":
            if self.ans != self.captcha_text:
                self.err = self.slots["ERR_CAPTCHA"]
                return
        elif self.ans != str(self.a + self.b):
            self.err = self.slots["ERR_CAPTCHA"]
            return
        if self.pwd != self.slots["PASSWORD"]:
            self.wrong += 1
            if self.wrong >= self.lock_after:
                self.locked = True
                self.lock_left = self.lock_seconds
                self.err = self.slots["ERR_LOCKED"]
            else:
                self.err = self.slots["ERR_PWD_WRONG"]
            return
        self.err = ""
        self.done = True

    def on_input(self, text: str) -> None:
        if self.focus == "phone":
            self.phone = text[: self.phone_len]
        elif self.focus == "pwd":
            self.pwd = text[:32]
        elif self.focus == "ans":
            self.ans = text[:4]

    def on_wait(self, seconds: float) -> None:
        if self.locked:
            self.lock_left = max(0, self.lock_left - int(seconds))
            if self.lock_left <= 0:
                self.locked = False
                self.wrong = 0
                self.err = ""

    def draw_extra(self, d, scale_x: float, scale_y: float) -> None:
        # 视觉门控：把树里不存在的验证码文字画到「Canvas」区域
        if self.captcha_kind == "colortext":
            for n in self.nodes():
                if n.get("type") == "Canvas":
                    b0 = n["bounds"]
                    x0 = int(b0["l"] * scale_x)
                    y0 = int(b0["t"] * scale_y)
                    for i in range(6):
                        d.line([(x0 + i * 12, y0), (x0 + i * 12 + 26, y0 + 40)], fill="#BBBBBB", width=2)
                    d.text((x0 + 6, y0 + 14), self.captcha_text, font=_font(34), fill="#1E6FFF")
                    return


class OneTapApp(SimApp):
    """OneTapLogin.ets 镜像：本机号码一键登录。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.need_agree = s.get("NEED_AGREE", "false") == "true"
        self.alt_hidden = s.get("ALT_HIDDEN", "false") == "true"
        self.mismatch = s.get("MISMATCH", "false") == "true"
        self.agree = False
        self.alt_shown = False
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        y = 320
        out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
               _node("Text", "本机号码一键登录", None, 430, h=60, clickable=False),
               _node("Text", s.get("CARRIER", "中国移动"), None, 510, h=50, clickable=False),
               _node("Text", s.get("MASKED_PHONE", "138****8000"), None, 570, h=70, clickable=False, nid="masked_phone"),
               _node("Button", "一键登录", "btn:onetap", 680, h=90, clickable=True)]
        if self.err:
            out.append(_node("Text", self.err, None, 790, h=60, clickable=False))
        if self.need_agree:
            out.append(_node("Checkbox", ("✓" if self.agree else "〇") + " 我已阅读并同意《用户协议》与《隐私政策》",
                             "chk:agree", 860, h=80, clickable=True))
        y = 960
        if self.alt_hidden:
            out.append(_node("Button", "短信验证码登录" if self.alt_shown else "更多登录方式 ▾",
                             "btn:more", y, h=80, clickable=True))
        else:
            out.append(_node("Button", "短信验证码登录", "btn:sms", y, h=80, clickable=True))
            out.append(_node("Button", "账号密码登录", "btn:pwd", y + 110, h=80, clickable=True))
        out.append(_node("Text", s["TASK_ID"], None, y + 220, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "chk:agree":
            self.agree = True
        elif key == "btn:onetap":
            self.err = ""
            if self.need_agree and not self.agree:
                self.err = "请先阅读并同意《用户协议》与《隐私政策》"
            elif self.mismatch:
                self.err = "当前展示号码与您的预期不符，请选择「其他登录方式」换号登录"
            else:
                self.done = True
        elif key in ("btn:sms", "btn:pwd"):
            self.err = "请使用本机号码一键登录"
        elif key == "btn:more":
            if self.alt_shown:
                self.err = "请使用本机号码一键登录"
            else:
                self.alt_shown = True

    def on_input(self, text):
        pass

    def on_wait(self, seconds):
        pass


class SocialApp(SimApp):
    """SocialLogin.ets 镜像：第三方授权登录。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.providers = json.loads(s.get("PROVIDERS_JSON", "[]"))
        self.induce = s.get("INDUCE_DECLINE", "false") == "true"
        self.cancel_req = s.get("CANCEL_REQUIRED", "false") == "true"
        self.stage = "login"
        self.auth_provider = ""
        self.cancelled = False
        self.err = ""

    def label(self, key):
        return {"wechat": "微信账号", "alipay": "支付宝账号", "qq": "QQ账号",
                "weibo": "微博账号", "huawei": "华为账号"}.get(key, key)

    def nodes(self):
        s = self.slots
        if self.stage == "done":
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        if self.stage == "auth":
            out = [_node("Text", "授权登录", None, 560, h=90, clickable=False),
                   _node("Text", self.label(self.auth_provider), None, 660, h=60, clickable=False),
                   _node("Text", "即将获得以下权限：获取你的昵称、头像", None, 740, h=60, clickable=False)]
            if self.induce:
                out.append(_node("Button", "暂不同意", "btn:decline", 820, h=110, clickable=True))
                out.append(_node("Button", "同意授权", "btn:agree", 960, h=80, clickable=True))
            else:
                out.append(_node("Button", "同意授权", "btn:agree", 820, h=100, clickable=True))
                out.append(_node("Button", "取消", "btn:cancel", 950, h=80, clickable=True))
            if self.err:
                out.append(_node("Text", self.err, None, 1060, h=60, clickable=False))
            return out
        y = 360
        out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
               _node("Text", "选择登录方式", None, 440, h=60, clickable=False)]
        for p in self.providers:
            out.append(_node("Button", "使用" + self.label(p["key"]) + "登录", f"ch:{p['key']}", y, h=100, clickable=True))
            y += 120
        if self.err:
            out.append(_node("Text", self.err, None, y, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, y + 80, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "chk:agree":
            pass
        elif str(key).startswith("ch:"):
            self.auth_provider = key.split(":")[1]
            self.stage = "auth"
            self.err = ""
        elif key == "btn:agree":
            if self.cancel_req and not self.cancelled:
                self.err = "请先取消本次授权，再重新进入授权页同意"
                self.stage = "login"
            else:
                self.stage = "done"
        elif key == "btn:cancel":
            self.cancelled = True
            self.stage = "login"
        elif key == "btn:decline":
            self.err = "已拒绝授权（这不是正确路径，任务失败）"
            self.stage = "login"

    def on_input(self, text):
        pass

    def on_wait(self, seconds):
        pass


class VoiceApp(SimApp):
    """VoiceCode.ets 镜像：语音验证码登录（含倒计时与过期）。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.delay = int(s.get("DELAY_SEC", "0") or 0)
        self.expire = int(s.get("EXPIRE_SEC", "0") or 0)
        self.got = False
        self.code = ""
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
               _node("Text", "手机号 " + s.get("MASKED_PHONE", "138****8000"), None, 440, h=60, clickable=False),
               _node("Button", "已获取（" + s.get("COOLDOWN_TEXT", "27s") + "）" if self.delay > 0 else "获取语音验证码",
                     "btn:get", 560, h=100, clickable=True)]
        if self.got:
            out.append(_node("Text", "验证码已通过语音播报：" + s.get("VOICE_CODE", "1234") + "（语音播报 mock）",
                             None, 700, h=80, clickable=False))
            if self.expire > 0:
                out.append(_node("Text", "剩余有效时间：" + str(self.delay) + "s", None, 790, h=60, clickable=False))
        out.append(_node("TextInput", "请输入语音验证码", "in:code", 880, h=90, clickable=True))
        out.append(_node("Button", "登录", "btn:login", 990, h=100, clickable=True))
        if self.err:
            out.append(_node("Text", self.err, None, 1100, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1180, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:get":
            self.err = ""
            if self.delay > 0:
                self.err = "语音验证码尚未就绪，请等待 " + self.slots.get("COOLDOWN_TEXT", "27s")
            else:
                self.got = True
                if self.expire > 0:
                    self.delay = self.expire
        elif key == "btn:login":
            if self.code != self.slots.get("VOICE_CODE", "1234"):
                self.err = "验证码错误，请重新输入"
            else:
                self.done = True
        elif key == "in:code":
            self.focus = "code"

    def on_input(self, text):
        if self.focus == "code":
            self.code = text[:6]

    def on_wait(self, seconds):
        if self.got and self.expire > 0:
            self.delay = max(0, self.delay - int(seconds))
            if self.delay <= 0:
                self.got = False
                self.err = "验证码已过期，请重新获取"


class EmailApp(SimApp):
    """EmailCode.ets 镜像：邮箱验证码 / 邮箱密码登录。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.need_email = s.get("NEED_EMAIL", "false") == "true"
        self.pwd_only = s.get("EMAIL_PWD", "") != ""
        self.email = ""
        self.sent = False
        self.code = ""
        self.pwd = ""
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
               _node("Text", "邮箱登录", None, 440, h=60, clickable=False)]
        if self.need_email:
            out.append(_node("TextInput", "请输入邮箱地址", "in:email", 560, h=90, clickable=True))
        else:
            out.append(_node("Text", "邮箱：" + s.get("PREFILL_EMAIL", "user@example.com"), None, 570, h=60, clickable=False))
        if self.pwd_only:
            out.append(_node("TextInput", "请输入邮箱密码", "in:pwd", 700, h=90, clickable=True))
        else:
            out.append(_node("TextInput", "请输入邮箱验证码", "in:code", 700, h=90, clickable=True))
            out.append(_node("Button", "获取验证码", "btn:send", 820, h=90, clickable=True))
        out.append(_node("Button", "登录", "btn:login", 940, h=100, clickable=True))
        if self.err:
            out.append(_node("Text", self.err, None, 1050, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1120, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:send":
            self.err = ""
            if self.need_email and ("@" not in self.email or "." not in self.email):
                self.err = "请输入正确的邮箱地址"
            else:
                self.sent = True
        elif key == "btn:login":
            self.err = ""
            if self.pwd_only:
                if self.pwd != self.slots.get("EMAIL_PWD"):
                    self.err = "邮箱密码错误，请重新输入"
                else:
                    self.done = True
            else:
                if self.code != self.slots.get("CODE", "123456"):
                    self.err = "邮箱验证码错误，请重新输入"
                else:
                    self.done = True
        elif key in ("in:email", "in:code", "in:pwd"):
            self.focus = key.split(":")[1]

    def on_input(self, text):
        if self.focus == "email":
            self.email = text[:64]
        elif self.focus == "code":
            self.code = text[:6]
        elif self.focus == "pwd":
            self.pwd = text[:32]

    def on_wait(self, seconds):
        pass


class QRApp(SimApp):
    """QRLogin.ets 镜像：扫码登录（含过期刷新 / 手机端确认）。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.expire = int(s.get("EXPIRE_SEC", "0") or 0)
        self.need_confirm = s.get("NEED_CONFIRM", "false") == "true"
        self.stage = "qr"
        self.left = self.expire

    def nodes(self):
        s = self.slots
        if self.stage == "done":
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        if self.stage == "expired":
            return [_node("Text", "二维码已过期", None, 800, h=80, clickable=False),
                    _node("Button", "点击刷新二维码", "btn:refresh", 900, h=100, clickable=True)]
        if self.stage == "scanned":
            out = [_node("Text", "已扫码", None, 700, h=80, clickable=False),
                   _node("Text", "请在手机上确认登录", None, 790, h=60, clickable=False)]
            out.append(_node("Button", "模拟手机端确认登录", "btn:confirm", 900, h=100, clickable=True)
                       if self.need_confirm else
                       _node("Button", "继续", "btn:go", 900, h=100, clickable=True))
            return out
        out = [_node("Text", "扫码登录", None, 340, h=80, clickable=False),
               _node("Text", "▣", None, 560, h=160, clickable=False),
               _node("Text", "请使用手机 App 扫描二维码", None, 740, h=60, clickable=False)]
        if self.expire > 0:
            out.append(_node("Text", "二维码剩余有效时间：" + str(self.left) + "s", None, 820, h=60, clickable=False))
        out.append(_node("Button", "模拟扫码成功", "btn:scan", 920, h=100, clickable=True))
        out.append(_node("Text", s["TASK_ID"], None, 1040, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:scan":
            self.stage = "scanned"
        elif key == "btn:confirm" or key == "btn:go":
            self.stage = "done"
        elif key == "btn:refresh":
            self.stage = "qr"
            self.left = self.expire

    def on_input(self, text):
        pass

    def on_wait(self, seconds):
        if self.stage == "qr" and self.expire > 0:
            self.left = max(0, self.left - int(seconds))
            if self.left <= 0:
                self.stage = "expired"


class BioApp(SimApp):
    """Biometric.ets 镜像：指纹/人脸 mock + 失败降级密码。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.fail_limit = int(s.get("FAIL_LIMIT", "0") or 0)
        self.face = s.get("BIO_TYPE", "fingerprint") == "face"
        self.fails = 0
        self.err = ""
        self.pwd = ""
        self.stage = "bio"

    def nodes(self):
        s = self.slots
        if self.stage == "done":
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        if self.stage == "pwd":
            out = [_node("Text", s.get("BIO_LABEL", "生物识别") + "不可用", None, 700, h=80, clickable=False),
                   _node("Text", "请使用解锁密码", None, 790, h=60, clickable=False),
                   _node("TextInput", "请输入解锁密码", "in:pwd", 880, h=90, clickable=True),
                   _node("Button", "解锁", "btn:unlock", 990, h=100, clickable=True)]
            if self.err:
                out.append(_node("Text", self.err, None, 1100, h=60, clickable=False))
            return out
        out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
               _node("Text", "🤖" if self.face else "👆", None, 460, h=120, clickable=False),
               _node("Text", s.get("BIO_LABEL", "请验证指纹"), None, 620, h=70, clickable=False),
               _node("Text", "请验证身份以继续登录", None, 700, h=50, clickable=False),
               _node("Button", "模拟" + ("人脸" if self.face else "指纹") + "识别", "btn:bio", 790, h=100, clickable=True),
               _node("Text", "使用密码登录", "btn:usefallback", 930, h=80, clickable=True)]
        if self.err:
            out.append(_node("Text", self.err, None, 1030, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1120, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:bio":
            self.err = ""
            if self.fail_limit > 0 and self.fails < self.fail_limit:
                self.fails += 1
                if self.fails >= self.fail_limit:
                    self.err = "生物识别连续失败 " + str(self.fail_limit) + " 次，请使用密码登录解锁"
                    self.stage = "pwd"
                else:
                    self.err = "识别失败，请重试（剩余 " + str(self.fail_limit - self.fails) + " 次）"
            else:
                self.stage = "done"
        elif key == "btn:usefallback":
            self.stage = "pwd"
            self.err = ""
        elif key == "btn:unlock":
            if self.pwd != self.slots.get("FALLBACK_PWD", "123456"):
                self.err = "解锁密码错误，请重新输入"
            else:
                self.stage = "done"
        elif key == "in:pwd":
            self.focus = "pwd"

    def on_input(self, text):
        if self.focus == "pwd":
            self.pwd = text[:32]

    def on_wait(self, seconds):
        pass


class TwoFactorApp(SimApp):
    """TwoFactorLogin.ets 镜像：密码 + 短信验证码双因子。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.stage = 1            # 1=密码，2=短信码
        self.pwd = ""
        self.code = ""
        self.sent = False
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        if self.stage == 1:
            out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
                   _node("Text", "账号 " + s.get("PHONE", "138****8000"), None, 440, h=60, clickable=False),
                   _node("TextInput", "请输入登录密码", "in:pwd", 560, h=90, clickable=True),
                   _node("Button", "下一步", "btn:next", 680, h=100, clickable=True)]
            if self.err:
                out.append(_node("Text", self.err, None, 800, h=60, clickable=False))
            out.append(_node("Text", s["TASK_ID"], None, 900, h=50, clickable=False))
            return out
        out = [_node("Text", "二次验证", None, 340, h=80, clickable=False),
               _node("Text", "已向 " + s.get("PHONE", "138****8000") + " 发送短信验证码", None, 440, h=60, clickable=False),
               _node("TextInput", "请输入短信验证码", "in:code", 560, h=90, clickable=True),
               _node("Button", "获取验证码", "btn:send", 680, h=90, clickable=True),
               _node("Button", "登录", "btn:login", 800, h=100, clickable=True)]
        if self.err:
            out.append(_node("Text", self.err, None, 920, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1000, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:next":
            self.err = ""
            if self.pwd != self.slots.get("PWD", "123456"):
                self.err = "登录密码错误，请重新输入"
            else:
                self.stage = 2
        elif key == "btn:send":
            self.sent = True
            self.err = ""
        elif key == "btn:login":
            self.err = ""
            if self.code != self.slots.get("SMS_CODE", "123456"):
                self.err = "短信验证码错误，请重新输入"
            else:
                self.done = True
        elif key in ("in:pwd", "in:code"):
            self.focus = key.split(":")[1]

    def on_input(self, text):
        if self.focus == "pwd":
            self.pwd = text[:32]
        elif self.focus == "code":
            self.code = text[:6]

    def on_wait(self, seconds):
        pass


class CaptchaSmsApp(SimApp):
    """CaptchaSmsLogin.ets 镜像：图形验证码 → 短信验证码 双闸门。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.stage = 1
        self.ans = ""
        self.code = ""
        self.sent = False
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        if self.stage == 1:
            out = [_node("Text", s["APP_NAME"], None, 340, h=80, clickable=False),
                   _node("Text", "请先完成图形验证码", None, 440, h=60, clickable=False),
                   _node("Text", "验证码题目：" + s.get("CAPTCHA_QUESTION", "7+4=?"), None, 520, h=60, clickable=False),
                   _node("TextInput", "请输入结果", "in:ans", 620, h=90, clickable=True),
                   _node("Button", "确认", "btn:ok", 740, h=100, clickable=True)]
            if self.err:
                out.append(_node("Text", self.err, None, 860, h=60, clickable=False))
            out.append(_node("Text", s["TASK_ID"], None, 950, h=50, clickable=False))
            return out
        out = [_node("Text", "二次验证", None, 340, h=80, clickable=False),
               _node("Text", "已向 " + s.get("PHONE", "138****8000") + " 发送短信验证码", None, 440, h=60, clickable=False),
               _node("TextInput", "请输入短信验证码", "in:code", 560, h=90, clickable=True),
               _node("Button", "获取验证码", "btn:send", 680, h=90, clickable=True),
               _node("Button", "登录", "btn:login", 800, h=100, clickable=True)]
        if self.err:
            out.append(_node("Text", self.err, None, 920, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1000, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:ok":
            self.err = ""
            if self.ans != self.slots.get("CAPTCHA_ANSWER", ""):
                self.err = "图形验证码错误，请重新输入"
            else:
                self.stage = 2
        elif key == "btn:send":
            self.sent = True
            self.err = ""
        elif key == "btn:login":
            self.err = ""
            if self.code != self.slots.get("SMS_CODE", ""):
                self.err = "短信验证码错误，请重新输入"
            else:
                self.done = True
        elif key in ("in:ans", "in:code"):
            self.focus = key.split(":")[1]

    def on_input(self, text):
        if self.focus == "ans":
            self.ans = text[:6]
        elif self.focus == "code":
            self.code = text[:6]

    def on_wait(self, seconds):
        pass


class SliderPwdApp(SimApp):
    """SliderPwdLogin.ets 镜像：风控滑块 → 密码 双闸门。"""

    def __init__(self, variant):
        super().__init__(variant)
        s = self.slots
        self.val = 0
        self.target = int(s.get("SLIDER_TARGET", "50"))
        self.unlocked = False
        self.pwd = ""
        self.err = ""
        self.done = False

    def nodes(self):
        s = self.slots
        if self.done:
            return [_node("Text", s["APP_NAME"], None, 700),
                    _node("Text", s["SUCCESS_TEXT"], None, 830, clickable=False, nid="welcome_marker"),
                    _node("Text", s["TASK_ID"], None, 950, clickable=False)]
        out = [_node("Text", s["APP_NAME"], None, 320, h=80, clickable=False),
               _node("Text", "安全验证", None, 420, h=60, clickable=False),
               _node("Text", "拖动滑块到缺口位置以完成验证", None, 500, h=60, clickable=False),
               _node("Slider", f"滑块位置 {self.val}(缺口无数字答案)", "sld", 580, h=90, clickable=True),
               _node("Text", "✓ 验证通过" if self.unlocked else "未通过验证", None, 700, h=60, clickable=False)]
        if self.unlocked:
            out.append(_node("TextInput", "请输入登录密码", "in:pwd", 800, h=90, clickable=True))
            out.append(_node("Button", "登录", "btn:login", 920, h=100, clickable=True))
        if self.err:
            out.append(_node("Text", self.err, None, 1040, h=60, clickable=False))
        out.append(_node("Text", s["TASK_ID"], None, 1120, h=50, clickable=False))
        return out

    def on_key(self, key):
        if key == "btn:login":
            self.err = ""
            if self.pwd != self.slots.get("PWD", ""):
                self.err = "登录密码错误，请重新输入"
            else:
                self.done = True
        elif key == "in:pwd":
            self.focus = "pwd"

    def on_input(self, text):
        if self.focus == "pwd":
            self.pwd = text[:32]

    def on_wait(self, seconds):
        pass

    def on_swipe(self, direction: str) -> None:
        if direction == "right":
            self.val = min(100, self.val + 25)
        elif direction == "left":
            self.val = max(0, self.val - 25)
        if abs(self.val - self.target) <= 2:
            self.unlocked = True


def build_sim(variant: dict, seed: int = 0) -> SimApp:
    variant = dict(variant)
    variant["_seed"] = seed
    template = variant.get("template", "")
    if template == "PrivacyDialog.ets":
        return PrivacyApp(variant)
    if template == "PhoneCodeLogin.ets":
        return PhoneCodeApp(variant)
    if template == "PwdLogin.ets":
        return PwdApp(variant)
    if template == "T5Captcha.ets":
        return T5App(variant)
    if template == "PaymentPage.ets":
        return PaymentApp(variant)
    if template == "OneTapLogin.ets":
        return OneTapApp(variant)
    if template == "SocialLogin.ets":
        return SocialApp(variant)
    if template == "VoiceCode.ets":
        return VoiceApp(variant)
    if template == "EmailCode.ets":
        return EmailApp(variant)
    if template == "QRLogin.ets":
        return QRApp(variant)
    if template == "Biometric.ets":
        return BioApp(variant)
    if template == "TwoFactorLogin.ets":
        return TwoFactorApp(variant)
    if template == "CaptchaSmsLogin.ets":
        return CaptchaSmsApp(variant)
    if template == "SliderPwdLogin.ets":
        return SliderPwdApp(variant)
    raise ValueError(f"暂无该模板的模拟器镜像: {template}")


def load_variant_from_task_dir(task_dir: Path) -> dict:
    for name in ("variant.json",):
        p = Path(task_dir) / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"未找到 variant.json（task 目录: {task_dir}）")


if __name__ == "__main__":
    # 独立冒烟：跑一遍隐私弹窗的完整点击序列
    d = Path(__file__).resolve().parent.parent
    v = load_variant_from_task_dir(d / "apps" / "privacy-mislead")
    app = build_sim(v)
    for ln in [n["text"] for n in app.nodes()]:
        print("node:", ln)
    app.click(850, 560)   # 点 ×（假关闭）
    app.click(290, 940)   # 点「暂不同意」区域
    print("stage after decline:", app.stage)
    ok = app.render_png(d / "apps" / "_sim_preview.png")
    print("PIL render:", ok, "| PIL_OK:", PIL_OK)