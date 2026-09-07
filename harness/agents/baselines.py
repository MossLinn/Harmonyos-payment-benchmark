# -*- coding: utf-8 -*-
"""
基线 Agent：规则基线（校准用）与随机基线（下界）。

规则基线完全基于 UI 树文本 + 任务凭据动作，不拷 VLM。它体现「这个场景
死规则能做到什么程度」——VLM 超过它的部分才是模型能力的真实增量。
输入类字段走「聚焦(1) → 输入(2)」两拍状态机，倒计时/回填/锁定由页面状态推导。
"""
import random
import re


class RuleAgent:
    def __init__(self, task: dict, agent_cfg: dict):
        self.task = task
        self.cfg = agent_cfg
        self.field_steps: dict[str, int] = {}
        self.sent = False
        self.autofilled = False
        self.swipes = 0
        self.pay_chan = False
        self.last_pick = ""
        self.avoid: set = set()
        self.cancel_done = False
        self.ime_backs = 0
        self.social_cancel_done = False

    def _find(self, nodes, substr):
        for n in nodes:
            if substr in (n.get("text") or ""):
                return n
        return None

    def _find_exact(self, nodes, text):
        for n in nodes:
            if (n.get("text") or "") == text and n.get("clickable"):
                return n
        return None

    def _has(self, nodes, substr):
        return self._find(nodes, substr) is not None

    def _click(self, node, reason):
        return {"action": "click", "x": 0, "y": 0, "node": node, "reason": reason}

    def _type_field(self, nodes, box_text, value, field_key):
        """两拍输入：先聚焦输入框，再输值。拍满后返回 None 放行后续规则。"""
        n = self._find(nodes, box_text)
        if not n:
            return None
        st = self.field_steps.get(field_key, 0)
        self.field_steps[field_key] = st + 1
        if st == 0:
            return self._click(n, f"聚焦输入框[{field_key}]")
        if st == 1:
            return {"action": "input", "text": str(value), "reason": f"输入[{field_key}]"}
        return None

    def act(self, tree_text: str, screenshot_path: str | None, step: int, nodes: list[dict]) -> dict:
        joined = " | ".join(n.get("text") or "" for n in nodes)
        creds = self.task.get("creds", {})
        instruction = self.task.get("instruction", "")
        countdown_active = bool(re.search(r"\d+\s*s\s*后重发", joined))

        # 0) 视觉门控任务：规则基线无颜色/图形感知，诚实退避（等待=放弃，验证门控生效）
        if any(k in instruction for k in ["绿色", "蓝色"]) and ("点击" in instruction or "验证码" in instruction):
            return {"action": "wait", "seconds": 1.0, "reason": "视觉门控任务：规则基线无颜色/图形感知"}

        # 1) 弹窗链：更新/营销可跳过项
        if any(k in joined for k in ["升级", "新版本", "礼包", "有礼"]):
            for w in ["稍后再说", "暂时不要", "暂不", "跳过", "以后再说", "×", "关闭"]:
                n = self._find(nodes, w)
                if n:
                    return self._click(n, f"跳过弹窗:{w}")

        # 2) 任务要求拒绝（诱导款正确路径；容忍多种拒绝类按钮文案）
        want_decline = any(k in instruction for k in ["拒绝", "暂不同意", "仅浏览"])
        if want_decline:
            for w in ["暂不同意", "不同意", "仅浏览"]:
                n = self._find_exact(nodes, w)
                if n and n.get("clickable"):
                    return self._click(n, "任务要求拒绝")

        # 2.5) 支付任务专规（P-NORMAL/P-DIAG；mindset: 勾选 → 选渠道 → 密码 → 确认）
        pay_labels = ["微信支付", "支付宝", "银行卡支付", "华为支付"]
        if ("弹窗内容异常" in joined) or ("空白页面" in joined):
            if self.last_pick:
                self.avoid.add(self.last_pick)
            return {"action": "key", "key": "back", "reason": "退出故障弹窗/空白页"}
        if "更换支付方式" in joined:
            for w in pay_labels:
                if w in joined:
                    self.avoid.add(w)
            n = self._find_exact(nodes, "更换支付方式")
            if n:
                return self._click(n, "换渠道")
        # 勾选先行（真机 checked 属性 / 模拟器 〇 文本）
        for n in nodes:
            if n.get("type") == "Checkbox" and n.get("checked") is False:
                return self._click(n, "勾选(checked=false)")
        for n in nodes:
            t = n.get("text") or ""
            if "〇" in t and ("《" in t or "我已阅读" in t):
                return self._click(n, f"勾选:{t[:20]}")
        # B11 陷阱形态：标签与勾选框分离、只有小方块可点（sim 中 Checkbox 文本仅 〇/✓）
        for n in nodes:
            if n.get("type") == "Checkbox" and "〇" in (n.get("text") or ""):
                return self._click(n, "勾选Checkbox本体(〇)")
        if "选择支付方式" in joined and "确认支付" not in joined and not any(k in joined for k in ["请输入支付密码"]):
            for w in pay_labels:
                if w in self.avoid:
                    continue
                n = self._find_exact(nodes, w)
                if n and n.get("clickable"):
                    self.last_pick = w
                    return self._click(n, f"选渠道:{w}")
        # 二期形态：退款 / 主动取消 / 放任超时
        if "申请退款" in joined and "退款" in instruction:
            n = self._find_exact(nodes, "申请退款")
            if n and n.get("clickable"):
                return self._click(n, "申请退款")
        # 弹窗是否开着：不能依赖占位符（真机输入后占位符被掩码内容取代）
        popup_open = (("订单金额" in joined) or ("pay_popup_" in joined)
                      or ("请输入支付密码" in joined) or ("剩余支付时间" in joined))
        if popup_open and "超时" in instruction and "等待" in instruction:
            return {"action": "wait", "seconds": 3.0, "reason": "放任支付超时以验证超时逻辑"}
        if popup_open and "取消" in instruction and not self.cancel_done:
            n = self._find_exact(nodes, "取消")
            if n and n.get("clickable"):
                self.cancel_done = True
                if self.last_pick:
                    self.avoid.add(self.last_pick)   # 取消过的渠道不再选（B5：换渠道重试）
                return self._click(n, "主动取消支付")
        if "我知道了" in joined:
            n = self._find_exact(nodes, "我知道了")
            if n and n.get("clickable"):
                return self._click(n, "确认异常提示")
        if creds.get("pay_pwd") and "请输入支付密码" in joined:
            a = self._type_field(nodes, "请输入支付密码", creds["pay_pwd"], "paypwd")
            if a:
                return a
        # B10 恢复：密码已输入但确认按钮被软键盘裁出组件树 → 按返回键收起键盘
        # 触发条件必须是「状态式」的：真机上输入后占位符消失，靠文本判断会永不触发
        if (self.field_steps.get("paypwd", 0) >= 2 and popup_open
                and "确认支付" not in joined and self.ime_backs < 3):
            self.ime_backs += 1
            return {"action": "key", "key": "back",
                    "reason": f"确认支付不在树中，收起软键盘({self.ime_backs}/3)"}
        n = self._find_exact(nodes, "确认支付")
        if n and self.last_pick and self.field_steps.get("paypwd", 0) >= 2 and n.get("clickable"):
            return self._click(n, "确认支付")

        # 2.6) 六类新登录方式专规（Top100 App 扩展）
        # 生物识别：模拟指纹/人脸 → 直接识别；连续失败后降级密码解锁
        if "模拟" in joined and "识别" in joined:
            n = self._find(nodes, "模拟")
            if n and n.get("clickable"):
                return self._click(n, "模拟生物识别")
        if "请输入解锁密码" in joined:
            a = self._type_field(nodes, "请输入解锁密码", creds.get("password", ""), "biopwd")
            if a:
                return a
            n = self._find_exact(nodes, "解锁")
            if n and self.field_steps.get("biopwd", 0) >= 2:
                return self._click(n, "解锁登录")
        # 扫码登录
        if "模拟扫码成功" in joined:
            n = self._find_exact(nodes, "模拟扫码成功")
            if n:
                return self._click(n, "模拟扫码")
        if "点击刷新二维码" in joined:
            n = self._find_exact(nodes, "点击刷新二维码")
            if n:
                return self._click(n, "刷新二维码")
        for w in ["模拟手机端确认登录", "继续"]:
            n = self._find_exact(nodes, w)
            if n:
                return self._click(n, f"扫码后确认:{w}")
        # 一键登录（有未勾选的 〇 时先走下方勾选规则）
        if "一键登录" in joined and "〇" not in joined:
            n = self._find_exact(nodes, "一键登录")
            if n:
                return self._click(n, "一键登录")
        # 第三方授权
        for lab in ["微信账号", "支付宝账号", "QQ账号", "微博账号", "华为账号"]:
            n = self._find(nodes, "使用" + lab + "登录")
            if n and n.get("clickable"):
                return self._click(n, "选授权渠道:" + lab)
        if "授权登录" in joined and self._has(nodes, "同意授权"):
            if self._find_exact(nodes, "取消") and "取消" in instruction and not self.social_cancel_done:
                self.social_cancel_done = True
                return self._click(self._find_exact(nodes, "取消"), "先取消授权")
            n = self._find_exact(nodes, "同意授权")
            if n:
                return self._click(n, "同意授权")
        # 语音验证码：获取 → 从播报 banner 提取码 → 输入 → 登录
        if "获取语音验证码" in joined and "语音播报" not in joined:
            n = self._find_exact(nodes, "获取语音验证码")
            if n:
                return self._click(n, "获取语音验证码")
        m_voice = re.search(r"语音播报[：:]\s*(\d{4,6})", joined)
        if m_voice and self._has(nodes, "请输入语音验证码"):
            a = self._type_field(nodes, "请输入语音验证码", m_voice.group(1), "voice")
            if a:
                return a
        # 邮箱
        if creds.get("email") and self._has(nodes, "请输入邮箱地址"):
            a = self._type_field(nodes, "请输入邮箱地址", creds["email"], "email")
            if a:
                return a
        if self._has(nodes, "请输入邮箱验证码") and self._find_exact(nodes, "获取验证码") and not self.sent:
            self.sent = True
            return self._click(self._find_exact(nodes, "获取验证码"), "获取邮箱验证码")
        if creds.get("code") and self._has(nodes, "请输入邮箱验证码"):
            a = self._type_field(nodes, "请输入邮箱验证码", creds["code"], "emailcode")
            if a:
                return a
        if creds.get("password") and self._has(nodes, "请输入邮箱密码"):
            a = self._type_field(nodes, "请输入邮箱密码", creds["password"], "emailpwd")
            if a:
                return a
        # 双因子：密码 → 下一步 → 短信验证码
        if "请输入登录密码" in joined:
            a = self._type_field(nodes, "请输入登录密码", creds.get("password", ""), "tfpwd")
            if a:
                return a
            n = self._find_exact(nodes, "下一步")
            if n and self.field_steps.get("tfpwd", 0) >= 2:
                return self._click(n, "密码通过→下一步")
        if "请输入短信验证码" in joined and not self.sent and creds.get("code"):
            n = self._find_exact(nodes, "获取验证码")
            if n:
                self.sent = True
                return self._click(n, "获取短信验证码")
        if "请输入短信验证码" in joined and creds.get("code"):
            a = self._type_field(nodes, "请输入短信验证码", creds["code"], "tfcode")
            if a:
                return a
        # 图验→短信：算式答案在 creds.captcha_answer（通用 rule 5 已输），这里点「确认」放行
        if "请输入结果" in joined and creds.get("captcha_answer"):
            n = self._find_exact(nodes, "确认")
            if n and self.field_steps.get("ans", 0) >= 2:
                return self._click(n, "确认图形验证码")

        # 3) 协议/隐私勾选（兼容两种信号：真机 checked=false 属性 / 模拟器文本 〇）
        for n in nodes:
            if n.get("type") == "Checkbox" and n.get("checked") is False:
                return self._click(n, "勾选(checked=false)")
        for n in nodes:
            t = n.get("text") or ""
            if "〇" in t and ("《" in t or "我已阅读" in t):
                return self._click(n, f"勾选:{t[:20]}")

        # 3.5) 滚动阅读任务：条款在正文底部，先上滑再勾选
        need_swipe = any(k in instruction for k in ["滑动", "滚动", "底部"])
        if need_swipe and not any(("〇" in (n.get("text") or "")) or (n.get("type") == "Checkbox")
                                  for n in nodes) and self.swipes < 3:
            self.swipes += 1
            return {"action": "swipe", "direction": "up", "reason": f"上滑阅读协议底部({self.swipes}/3)"}

        # 4) 同意类按钮（精确或前缀匹配，且必须是可点击组件）
        if not want_decline:
            for w in ["同意并继续", "同意", "我知道了", "进入应用"]:
                for n in nodes:
                    t = n.get("text") or ""
                    hit = (t == w) or (w == "同意并继续" and t.startswith("同意并继续"))
                    if hit and n.get("clickable"):
                        return self._click(n, f"同意:{w}")

        # 5) 输入字段（两拍状态机；先手机号，再密码/验证码答案/验证码）
        if creds.get("phone"):
            a = self._type_field(nodes, "请输入手机号", creds["phone"], "phone")
            if a:
                return a
        if creds.get("password"):
            a = self._type_field(nodes, "请输入密码", creds["password"], "pwd")
            if a:
                return a
        if "请输入结果" in joined and creds.get("captcha_answer"):
            a = self._type_field(nodes, "请输入结果", creds["captcha_answer"], "ans")
            if a:
                return a
        if creds.get("code") and (self.sent or self.autofilled) and not self.autofilled:
            a = self._type_field(nodes, "请输入验证码", creds["code"], "code")
            if a:
                return a

        # 6) 验证码：先自动填充（仅一次），其次获取验证码
        if creds.get("code") and not self.autofilled:
            n = self._find(nodes, "模拟短信自动填充")
            if n:
                self.autofilled = True
                return self._click(n, "自动填充验证码")
            n = self._find(nodes, "获取验证码")
            if n and not countdown_active and not self.sent:
                self.sent = True
                return self._click(n, "获取验证码")

        # 6.5) 自动填充陷阱恢复：错码导致验证码错误 → 重新聚焦并手输正确验证码
        if self.autofilled and any("验证码" in (n.get("text") or "") for n in nodes) and creds.get("code"):
            a = self._type_field(nodes, "请输入验证码", creds["code"], "retry")
            if a:
                return a

        # 7) 登录按钮（exact 匹配，避开「密码登录」等标题；勾选/验证码齐备才点）
        n = self._find_exact(nodes, "登录")
        if n:
            if self._has(nodes, "〇"):
                return None  # 还有未勾选项，回规则 3
            if creds.get("code") and not (self.sent or self.autofilled):
                return None  # 还没取验证码
            return self._click(n, "点击登录")

        # 8) 兜底
        clickable = [x for x in nodes if x.get("type") == "Button" or x.get("clickable")]
        if clickable:
            return self._click(random.choice(clickable), "兜底点击")
        return {"action": "wait", "seconds": 1.0, "reason": "无可用动作"}


class RandomAgent:
    def __init__(self, task: dict, agent_cfg: dict, seed: int = 0):
        self.rng = random.Random(seed)

    def act(self, tree_text: str, screenshot_path: str | None, step: int, nodes: list[dict]) -> dict:
        interact = [n for n in nodes if (n.get("type") in ("Button", "TextInput", "Checkbox")
                                         or n.get("clickable"))]
        r = self.rng.random()
        if nodes and r < 0.75 and interact:
            n = self.rng.choice(interact)
            return {"action": "click", "x": 0, "y": 0, "node": n, "reason": "随机点击"}
        if r < 0.85:
            return {"action": "swipe", "direction": self.rng.choice(["up", "down"]), "reason": "随机滑动"}
        return {"action": "wait", "seconds": 1.0, "reason": "随机等待"}