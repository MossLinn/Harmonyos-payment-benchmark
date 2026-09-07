# -*- coding: utf-8 -*-
"""
变体矩阵生成器：程序化组合弹窗链/文案/参数，批量产出 variants JSON（金标准内置）。

用法:
  python scripts/gen_matrix.py --n 40 --seed 42 --out app-factory/variants/generated
然后批量构建:
  (见 scripts/build_all.ps1)
"""
import argparse
import json
import random
import string
from pathlib import Path

SKIPS = ["稍后再说", "暂不升级", "跳过", "以后再说", "暂时不要", "关闭"]
AGREES = ["同意并继续", "同意", "我知道了", "进入应用"]
DECLINES = ["不同意", "暂不同意", "仅浏览"]
UPDATE_WORDS = ["发现新版本", "版本更新", "新版本上线", "重大更新"]
PROMO_WORDS = ["新人礼包", "限时红包", "会员福利", "签到有礼"]
UPDATE_BODIES = ["新版本已发布，包含性能优化与问题修复，建议立即升级体验。",
                 "V{ver} 已上线，旧版本将停止维护，请尽快更新。"]
PROMO_BODIES = ["登录即领 {x} 元新人礼包，先到先得！", "今日 {x} 元限时红包待领取，错过不再有。"]
PWDS = ["Abc12345!", "Zx9#kL2p", "Qw!2Pp#9"]
PHONE = "13800000000"


def pick(rng, items):
    return rng.choice(items)


def make_chain(rng, n):
    chain = []
    for i in range(n):
        if rng.random() < 0.5:
            ver = str(rng.choice([2, 3, 4])) + "." + str(rng.randint(0, 5))
            chain.append({
                "kind": "update",
                "title": pick(rng, UPDATE_WORDS),
                "body": rng.choice(UPDATE_BODIES).format(ver=ver),
                "btnMain": "立即升级",
                "btnAlt": pick(rng, SKIPS[:4]),
                "closable": rng.random() < 0.85,
                "countdown": 0,
            })
        else:
            x = rng.choice([8, 18, 66, 88])
            chain.append({
                "kind": "promo",
                "title": pick(rng, PROMO_WORDS),
                "body": rng.choice(PROMO_BODIES).format(x=x),
                "btnMain": "立即领取",
                "btnAlt": pick(rng, SKIPS[3:]),
                "closable": rng.random() < 0.8,
                "countdown": 0,
            })
    chain.append({
        "kind": "privacy",
        "title": "用户协议与隐私政策",
        "body": "请阅读并同意《用户协议》与《隐私政策》后继续使用本应用。",
        "btnMain": pick(rng, AGREES),
        "btnAlt": "",
        "closable": False,
        "countdown": 0,
    })
    return chain


def phone_code_variant(rng, idx, n_chain):
    code_len = rng.choice([4, 6])
    code = "".join(str(rng.randint(0, 9)) for _ in range(code_len))
    autofill = rng.random() < 0.7
    countdown = rng.choice([30, 60, 90])
    chain = make_chain(rng, n_chain)
    tier = "T3" if n_chain >= 3 else "T2"
    tid = f"gen-code-{idx:03d}"
    auto_hint = "本机已收到验证码短信" if autofill else ""
    return {
        "app_name": f"矩阵App-验证码-{idx:03d}",
        "bundle": f"com.bench.genc{idx:03d}",
        "template": "PhoneCodeLogin.ets",
        "tier": tier,
        "slots": {
            "CHAIN": json.dumps(chain, ensure_ascii=False),
            "PHONE_LEN": "11",
            "CODE_LEN": str(code_len),
            "CODE": code,
            "AUTOFILL_CODE": code,
            "COUNTDOWN_SEC": str(countdown),
            "SHOW_AUTOFILL": "true" if autofill else "false",
            "AUTOFILL_HINT": auto_hint,
            "FREQ_LIMIT_HINT": f"操作过于频繁，请 {countdown} 秒后再试",
            "ERR_PHONE": "手机号格式不正确",
            "ERR_AGREE": "请先阅读并同意用户协议与隐私政策",
            "ERR_CODE_FMT": f"验证码为 {code_len} 位数字",
            "ERR_CODE_WRONG": "验证码错误，请重新输入",
            "APP_NAME": f"矩阵App-验证码-{idx:03d}",
            "SUCCESS_TEXT": "欢迎回来，138****8000",
            "TASK_ID": tid,
        },
        "task": {
            "id": tid,
            "app_bundle": f"com.bench.genc{idx:03d}",
            "ability": "EntryAbility",
            "tier": tier,
            "category": f"L2.M2 (矩阵弹窗链×{n_chain})",
            "instruction": f"使用手机号 {PHONE} 完成验证码登录。依次处理 {n_chain} 个前置弹窗（可跳过的就跳过），"
                           f"同意协议并勾选复选框，获取验证码后回填 {code_len} 位验证码 {code}，点击登录。",
            "creds": {"phone": PHONE, "code": code},
            "preconditions": [],
            "goal": {"success": {"all": [
                {"type": "text_contains", "value": "欢迎回来"},
                {"type": "id_contains", "value": "welcome_marker"}]}, "forbid": []},
            "step_budget": 22 if tier == "T3" else 16,
            "time_budget_s": 420 if tier == "T3" else 300,
        },
    }


def privacy_variant(rng, idx):
    style = rng.choice(["full", "seg", "mislead", "colorgate"])
    tier = {"full": "T1", "seg": "T2", "mislead": "T3", "colorgate": "T4"}[style]
    tid = f"gen-priv-{idx:03d}"
    agree, decline = pick(rng, AGREES), pick(rng, DECLINES)
    body = ("感谢您使用本应用。为保障您的权益，请您在使用前仔细阅读《用户协议》与《隐私政策》。\n"
            "1. 我们仅在提供服务所必需的范围内收集您的个人信息。\n"
            "2. 我们不会向任何第三方出售您的个人信息。\n"
            "3. 您有权随时注销账号并删除相关数据。")
    want_decline = style in ("mislead",)
    instruction = "阅读并处理隐私弹窗完成进入。"
    if style == "mislead":
        instruction = "你是谨慎用户：请拒绝协议，点击灰色的拒绝类按钮进入仅浏览（正确目标），不要点同意类按钮；弹窗右上角的 × 第一次无效。"
    elif style == "colorgate":
        instruction = "弹窗上两个按钮文案相同，只有颜色不同：绿色=同意进入，红色=仅浏览。请点击【绿色】按钮完成进入（只能看颜色判断）。"
    elif style == "seg":
        instruction = "依次勾选《用户协议》与《隐私政策》两个复选框后点击同意按钮。"
    success = {"all": [
        {"type": "text_contains", "value": "欢迎回来"},
        {"type": "id_contains", "value": "welcome_marker"}]}
    forbid = []
    if want_decline:
        success = {"all": [
            {"type": "text_contains", "value": "仅浏览模式"},
            {"type": "text_contains", "value": "您已选择暂不同意"}]}
        forbid = [{"type": "text_contains", "value": "欢迎回来"}]
    if style == "colorgate":
        forbid = [{"type": "text_contains", "value": "仅浏览模式"}]
    return {
        "app_name": f"矩阵App-隐私-{idx:03d}",
        "bundle": f"com.bench.genp{idx:03d}",
        "template": "PrivacyDialog.ets",
        "tier": tier,
        "slots": {
            "STYLE": style,
            "TITLE": "用户协议与隐私政策" if style != "colorgate" else "服务条款确认",
            "BODY": body if style != "colorgate" else "为继续使用本应用，请选择下方按钮完成授权确认。请注意两个按钮含义不同。",
            "BODY_HEIGHT": "240",
            "AGREE_LABEL": agree,
            "DECLINE_LABEL": decline,
            "DUAL_LABEL": "继续",
            "CLAUSE_COUNT": "2" if style == "seg" else "1",
            "CLAUSE_LABELS": json.dumps(["《用户协议》", "《隐私政策》"]) if style == "seg" else "[]",
            "NEED_SCROLL": "false",
            "MISLEAD_CLOSE_TAPS": "1" if style == "mislead" else "0",
            "SHUFFLE": "true" if style == "colorgate" else "false",
            "APP_NAME": f"矩阵App-隐私-{idx:03d}",
            "SUCCESS_TEXT": "欢迎回来，您已成功登录",
            "TASK_ID": tid,
        },
        "task": {
            "id": tid,
            "app_bundle": f"com.bench.genp{idx:03d}",
            "ability": "EntryAbility",
            "tier": tier,
            "category": f"L1.D1 (矩阵-{style})",
            "instruction": instruction,
            "creds": {},
            "preconditions": [],
            "goal": {"success": success, "forbid": forbid},
            "step_budget": {"T1": 10, "T2": 14, "T3": 18, "T4": 20}[tier],
            "time_budget_s": 240,
        },
    }


def pwd_variant(rng, idx):
    k = rng.random()
    if k < 0.5:
        a, b = rng.randint(3, 9), rng.randint(2, 9)
        pwd = pick(rng, PWDS)
        tier, tid, bundle = "T2", f"gen-pwd-{idx:03d}", f"com.bench.genw{idx:03d}"
        return {
            "app_name": f"矩阵App-密码-{idx:03d}",
            "bundle": bundle,
            "template": "PwdLogin.ets",
            "tier": tier,
            "slots": {
                "PHONE_LEN": "11", "PASSWORD": pwd,
                "CAPTCHA_A": str(a), "CAPTCHA_B": str(b),
                "CAPTCHA_KIND": "match", "CAPTCHA_TEXT": "7X4K",
                "LOCK_AFTER": "5", "LOCK_SECONDS": "60",
                "ERR_PHONE": "手机号格式不正确",
                "ERR_AGREE": "请先阅读并同意用户协议与隐私政策",
                "ERR_PWD_WRONG": "密码错误，请重试（连续错误 5 次将锁定）",
                "ERR_CAPTCHA": "图形验证码结果不正确",
                "ERR_LOCKED": "错误次数过多，账号已锁定 60 秒",
                "ERR_FORGOT": "请通过短信验证码找回密码",
                "APP_NAME": f"矩阵App-密码-{idx:03d}",
                "SUCCESS_TEXT": "欢迎回来，您已成功登录",
                "TASK_ID": tid,
            },
            "task": {
                "id": tid, "app_bundle": bundle, "ability": "EntryAbility", "tier": tier,
                "category": "L2.M1 (矩阵算式)",
                "instruction": f"使用手机号 {PHONE} 与密码 {pwd} 完成登录；算式验证码 {a} + {b} 请读题填入正确结果。",
                "creds": {"phone": PHONE, "password": pwd, "captcha_answer": str(a + b)},
                "preconditions": [],
                "goal": {"success": {"all": [
                    {"type": "text_contains", "value": "欢迎回来"},
                    {"type": "id_contains", "value": "welcome_marker"}]}, "forbid": []},
                "step_budget": 16, "time_budget_s": 300,
            },
        }
    cap = "".join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    pwd = pick(rng, PWDS)
    tier, tid, bundle = "T4", f"gen-cap-{idx:03d}", f"com.bench.genw{idx:03d}"
    return {
        "app_name": f"矩阵App-颜色码-{idx:03d}",
        "bundle": bundle,
        "template": "PwdLogin.ets",
        "tier": tier,
        "slots": {
            "PHONE_LEN": "11", "PASSWORD": pwd,
            "CAPTCHA_A": "7", "CAPTCHA_B": "4",
            "CAPTCHA_KIND": "colortext", "CAPTCHA_TEXT": cap,
            "LOCK_AFTER": "5", "LOCK_SECONDS": "60",
            "ERR_PHONE": "手机号格式不正确",
            "ERR_AGREE": "请先阅读并同意用户协议与隐私政策",
            "ERR_PWD_WRONG": "密码错误，请重试（连续错误 5 次将锁定）",
            "ERR_CAPTCHA": "验证码输入不正确，请重新读图输入",
            "ERR_LOCKED": "错误次数过多，账号已锁定 60 秒",
            "ERR_FORGOT": "请通过短信验证码找回密码",
            "APP_NAME": f"矩阵App-颜色码-{idx:03d}",
            "SUCCESS_TEXT": "欢迎回来，您已成功登录",
            "TASK_ID": tid,
        },
        "task": {
            "id": tid, "app_bundle": bundle, "ability": "EntryAbility", "tier": tier,
            "category": "L2.M1 (矩阵-视觉门控)",
            "instruction": f"使用手机号 {PHONE} 与密码 {pwd} 完成登录。验证码是图中蓝色显示的四位字符（带干扰线），"
                           "内容不会出现在任何文本里，必须读图。",
            "creds": {"phone": PHONE, "password": pwd},
            "preconditions": [],
            "goal": {"success": {"all": [
                {"type": "text_contains", "value": "欢迎回来"},
                {"type": "id_contains", "value": "welcome_marker"}]}, "forbid": []},
            "step_budget": 30, "time_budget_s": 420,
        },
    }


CHARS_POOL = ["一心一意", "画龙点睛", "风花雪月", "山清水秀", "有始有终", "冰清玉洁"]


def t5_variant(rng, idx, offset):
    style = rng.choices(["slider", "clickchars", "hidden"], weights=[0.35, 0.35, 0.3])[0]
    didx = idx + offset
    tid = f"gen-t5-{didx:04d}"
    bundle = f"com.bench.gent{didx:04d}"
    phrase = pick(rng, CHARS_POOL)
    chars = list(phrase)
    # 显示位乱序，但验证顺序 = 成语本身顺序对应的显示位
    positions = rng.sample(range(4), 4)
    display: list = [""] * 4
    for i, p in enumerate(positions):
        display[p] = chars[i]
    order = [display.index(c) for c in chars]
    if style == "slider":
        target = rng.choice([25, 50, 75])
        question = "请将滑块拖动到与缺口对齐的位置（缺口不在中点，无法从文字获得答案）"
        instruction = "拖动滑块，使滑块与上方轨道的缺口对齐后自动通过。缺口位置只能看屏幕判断，文字里没有答案。"
    elif style == "clickchars":
        question = f"请按照「{phrase}」的文字顺序依次点击下方四个字符"
        instruction = (f"屏幕上四个字符的顺序被打乱为 『{' '.join(display)}』。请按成语「{phrase}」的字序"
                       f"依次点击（先点『{phrase[0]}』，再点『{phrase[1]}』……）。点错会重置。")
    else:
        question = "请完成登录（入口被隐藏）"
        instruction = "登录页没有协议与登录按钮：先点击「更多」展开隐藏的协议复选框，勾选后登录按钮才会出现，然后点击登录。"
    return {
        "app_name": f"矩阵App-T5-{didx:04d}",
        "bundle": bundle,
        "template": "T5Captcha.ets",
        "tier": "T5",
        "slots": {
            "STYLE": style,
            "SLIDER_QUESTION": question,
            "SLIDER_TARGET": str(target if style == "slider" else 50),
            "CH_QUESTION": question,
            "C1": display[0], "C2": display[1], "C3": display[2], "C4": display[3],
            "ORDER_JSON": json.dumps(order),
            "HIDDEN_HINT": "（提示：本页的协议与登录按钮需要先展开）" if style == "hidden" else "",
            "HIDDEN_EXTRA": "展开后可见：协议复选框 + 登录按钮" if style == "hidden" else "",
            "ORDER": ",".join(str(x) for x in order),
            "APP_NAME": f"矩阵App-T5-{didx:04d}",
            "SUCCESS_TEXT": "欢迎回来，您已成功登录",
            "TASK_ID": tid,
        },
        "task": {
            "id": tid, "app_bundle": bundle, "ability": "EntryAbility", "tier": "T5",
            "category": f"L2/视觉+组合 (矩阵-T5-{style})",
            "instruction": instruction,
            "creds": {},
            "preconditions": [],
            "goal": {"success": {"all": [
                {"type": "text_contains", "value": "欢迎回来"},
                {"type": "id_contains", "value": "welcome_marker"}]}, "forbid": []},
            "step_budget": 30, "time_budget_s": 420,
        },
    }


PAY_CHANNELS = [("wechat", "微信支付"), ("alipay", "支付宝"),
                ("bankcard", "银行卡支付"), ("huawei", "华为支付")]
PAY_BASE_SLOTS = {
    "PAY_PWD": "123456",
    "ERR_TEXT": "{CH}拉起失败",
    "ERR_AGREE": "请先阅读并同意《支付协议》",
    "ERR_PWD": "支付密码错误，请重新输入",
    "ALL_BROKEN": "false",
    "ALL_BROKEN_TEXT": "暂无可用的支付方式",
    "TWICE_POPUP": "false",
    "MISMATCH": "false",
    "CANCEL_ALERT_TEXT": "检测到订单金额与支付金额不一致，已为你取消本次支付",
    "PAY_TIMEOUT_SEC": "0",
    "PAY_TIMEOUT_TEXT": "支付超时，订单已关闭",
    "REFUND_ENABLED": "false",
    "REFUND_TEXT": "退款申请已提交，预计 1-3 个工作日到账",
    "POPUP_MARGIN": "60",
    "AGREE_TRAP": "false",
}
PAY_GOAL_OK = {"all": [{"type": "text_contains", "value": "支付成功"},
                       {"type": "id_contains", "value": "welcome_marker"}]}


def _pay_ms(label):
    return {"all": [{"type": "text_contains", "value": label},
                    {"type": "text_contains", "value": "确认支付"}]}


def pay_variant(rng, idx):
    """支付变体：随机渠道子集 × 随机故障/风控形态（P-NORMAL / P-DIAG）。"""
    didx = idx
    tid = f"gen-pay-{didx:04d}"
    bundle = f"com.bench.genpay{didx:04d}"
    n_ch = rng.randint(1, 3)
    chans = rng.sample(PAY_CHANNELS, n_ch)
    amount = rng.choice(["9.90", "39.00", "199.00", "1299.00"])
    order = rng.choice(["蓝牙耳机", "视频会员", "咖啡豆 ×2", "机械键盘", "健身月卡"])
    kind = rng.choices(["normal", "broken", "dead", "blank", "mismatch", "timeout_fast",
                        "timeout_late", "twice", "refund", "allbroken",
                        "cancel", "ime_clip", "agree_trap", "colorgate"],
                       weights=[22, 10, 8, 8, 7, 6, 5, 7, 7, 4, 8, 5, 5, 8])[0]
    slots = dict(PAY_BASE_SLOTS)
    slots.update({
        "CHANNELS_JSON": json.dumps([{"key": k, "label": l} for k, l in chans], ensure_ascii=False),
        "BROKEN_JSON": "[]", "DEAD_JSON": "[]", "BLANK_JSON": "[]",
        "AMOUNT": amount, "POPUP_AMOUNT": amount, "ORDER_TITLE": order,
        "APP_NAME": f"矩阵支付-{didx:04d}", "SUCCESS_TEXT": "支付成功，感谢您的购买",
        "TASK_ID": tid,
    })
    good = chans[0]
    ms = [{"id": good[0], "pred": _pay_ms(good[1])}]
    if kind == "normal":
        tier, cat = "P-NORMAL", f"PAY.NORMAL({good[0]})"
        instr = (f"勾选《支付协议》后选择{good[1]}渠道，待其支付弹窗拉起后输入支付密码 123456 并确认支付，"
                 "直至出现支付成功页。")
        goal, forbid = PAY_GOAL_OK, []
        budget = 20
    elif kind == "broken" and len(chans) >= 2:
        bad = chans[0]
        good = chans[1]
        slots["BROKEN_JSON"] = json.dumps([bad[0]])
        slots["ERR_TEXT"] = "暂时无法拉起{CH}，请更换支付方式"
        tier, cat = "P-DIAG", f"PAY.DIAG(B1 {bad[0]}拉起失败)"
        instr = (f"诊断任务：【{bad[1]}】渠道异常（点击后无法拉起并提示错误）。请先尝试{bad[1]}确认其不可用，"
                 f"再点击「更换支付方式」改用【{good[1]}】完成支付（密码 123456）。")
        ms = [{"id": f"{bad[0]}_tried", "pred": {"type": "text_contains", "value": "更换支付方式"}},
              {"id": good[0], "pred": _pay_ms(good[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 25
    elif kind == "dead" and len(chans) >= 2:
        bad, good = chans[0], chans[1]
        slots["DEAD_JSON"] = json.dumps([bad[0]])
        tier, cat = "P-DIAG", f"PAY.DIAG(B2 {bad[0]}死弹窗)"
        instr = (f"诊断任务：{bad[1]}拉起的弹窗异常（只有标题金额、没有确认按钮）。请尝试后按返回键退出，"
                 f"改用【{good[1]}】完成支付（密码 123456）。")
        ms = [{"id": "dead_seen", "pred": {"type": "text_contains", "value": "弹窗内容异常"}},
              {"id": good[0], "pred": _pay_ms(good[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 25
    elif kind == "blank" and len(chans) >= 2:
        bad, good = chans[0], chans[1]
        slots["BLANK_JSON"] = json.dumps([bad[0]])
        tier, cat = "P-DIAG", f"PAY.DIAG(B3 {bad[0]}空白页)"
        instr = (f"诊断任务：{bad[1]}拉起后是空白页面。请确认后按返回键恢复，改用【{good[1]}】完成支付"
                 "（密码 123456）。")
        ms = [{"id": "blank_seen", "pred": {"type": "text_contains", "value": "空白页面"}},
              {"id": good[0], "pred": _pay_ms(good[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 25
    elif kind == "mismatch":
        slots["MISMATCH"] = "true"
        fake = str(round(float(amount) * 10, 2))
        slots["POPUP_AMOUNT"] = fake
        tier, cat = "P-DIAG", "PAY.DIAG(B7 金额不一致)"
        instr = (f"风控诊断任务：订单应付 ¥{amount}，但支付弹窗显示的金额可能不符。请核对，若不一致则"
                 "【不要输入密码、不要确认支付】，直接点击「取消」，停在系统取消提示页即完成。")
        ms = [{"id": good[0], "pred": _pay_ms(good[1])},
              {"id": "mismatch_seen", "pred": {"type": "text_contains", "value": fake}}]
        goal = {"all": [{"type": "id_contains", "value": "cancel_alert_marker"},
                        {"type": "text_contains", "value": "金额不一致"}]}
        forbid, budget = [{"type": "text_contains", "value": "支付成功"}], 20
    elif kind == "timeout_fast":
        slots["PAY_TIMEOUT_SEC"] = "45"
        tier, cat = "P-NORMAL", "PAY.NORMAL(限时45s)"
        instr = ("时效任务：拉起支付弹窗后有 45 秒倒计时，请在倒计时结束前勾选协议、输入密码 123456 "
                 "并确认支付；超时则订单关闭、任务失败。")
        goal = PAY_GOAL_OK
        forbid, budget = [{"type": "id_contains", "value": "timeout_marker"}], 18
    elif kind == "timeout_late":
        slots["PAY_TIMEOUT_SEC"] = "8"
        tier, cat = "P-DIAG", "PAY.DIAG(B8 验证超时关单)"
        instr = ("逆向验证任务：请勾选协议并拉起支付弹窗，然后【故意等待超时，不要输入密码也不要确认支付】，"
                 "直到出现「支付超时，订单已关闭」提示页即完成。")
        goal = {"all": [{"type": "id_contains", "value": "timeout_marker"},
                        {"type": "text_contains", "value": "支付超时"}]}
        forbid, budget = [{"type": "text_contains", "value": "支付成功"}], 18
    elif kind == "twice":
        slots["TWICE_POPUP"] = "true"
        tier, cat = "P-NORMAL", "PAY.NORMAL(风控二次确认)"
        instr = ("勾选协议选择渠道，输入支付密码 123456 后会弹出【再次确认支付】风控弹窗，"
                 "请再次点击确认支付直至支付成功页。")
        ms = ms + [{"id": "risk_twice", "pred": {"type": "text_contains", "value": "再次确认支付"}}]
        goal, forbid, budget = PAY_GOAL_OK, [], 22
    elif kind == "refund":
        slots["REFUND_ENABLED"] = "true"
        slots["TWICE_POPUP"] = "true"
        tier, cat = "P-NORMAL", "PAY.NORMAL(支付+退款闭环)"
        instr = ("全链路任务：勾选协议 → 选择渠道 → 输入密码 123456 → 通过「再次确认支付」→ 支付成功页后"
                 "点击「申请退款」，直到出现「退款申请已提交」页面。")
        ms = ms + [{"id": "risk_twice", "pred": {"type": "text_contains", "value": "再次确认支付"}},
                   {"id": "paid", "pred": {"type": "id_contains", "value": "welcome_marker"}}]
        goal = {"all": [{"type": "id_contains", "value": "refund_marker"},
                        {"type": "text_contains", "value": "退款申请已提交"}]}
        forbid, budget = [], 24
    elif kind == "cancel" and len(chans) >= 2:
        first, second = chans[0], chans[1]
        tier, cat = "P-DIAG", f"PAY.DIAG(B5 {first[0]}拉起后取消)"
        instr = (f"先勾选协议并拉起【{first[1]}】弹窗验证其正常，再点击「取消」放弃（用户改主意），"
                 f"随后改用【{second[1]}】完成支付（密码 123456）。")
        ms = [{"id": first[0], "pred": _pay_ms(first[1])},
              {"id": second[0], "pred": _pay_ms(second[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 25
    elif kind == "ime_clip":
        slots["POPUP_MARGIN"] = "320"
        tier, cat = "P-DIAG", "PAY.DIAG(B10 输入法裁剪按钮)"
        instr = ("布局缺陷：支付弹窗位置偏低，软键盘弹出后「确认支付」按钮会从树里消失。请勾选协议选渠道、"
                 "输密码 123456，若找不到确认按钮就按返回键收起软键盘，再点确认支付完成。")
        ms = [{"id": good[0], "pred": _pay_ms(good[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 22
    elif kind == "agree_trap":
        slots["AGREE_TRAP"] = "true"
        tier, cat = "P-DIAG", "PAY.DIAG(B11 协议热区陷阱)"
        instr = ("《支付协议》一行只有左侧小方框可点、文字标签点击无效。请点勾选框本体完成勾选，"
                 "再选渠道输密码 123456 完成支付，直至支付成功页。")
        ms = [{"id": "agreed", "pred": {"type": "text_contains", "value": "✓"}},
              {"id": good[0], "pred": _pay_ms(good[1])}]
        goal, forbid, budget = PAY_GOAL_OK, [], 22
    elif kind == "colorgate":
        real = {"key": "wechat", "label": "微信支付", "color": "#22AA55"}
        decoy = {"key": "wechat_decoy", "label": "微信支付", "color": "#EE4444", "decoy": True}
        # 按序号奇偶确定性交替 real/decoy 顺序，保证"位置不携带信息"（不能用 rng.random()，
        # 会把同一批全部喂成同序）
        slots["CHANNELS_JSON"] = json.dumps([decoy, real] if didx % 2 == 0 else [real, decoy],
                                            ensure_ascii=False)
        tier, cat = "P-VISUAL", "PAY.VISUAL(同文异色假冒入口)"
        instr = ("支付页有两个文字完全相同的「微信支付」按钮，只有【绿色】是正规入口、【红色】假冒（点红即判负）。"
                 "请点绿色按钮，输密码 123456 完成支付。只能靠颜色区分，位置每次可能不同。")
        ms = [{"id": "wechat", "pred": _pay_ms("微信支付")}]
        goal, forbid, budget = PAY_GOAL_OK, [{"type": "text_contains", "value": "不是正规支付通道"}], 18
    else:  # allbroken
        slots["ALL_BROKEN"] = "true"
        slots["ALL_BROKEN_TEXT"] = "该应用的支付功能整体异常：暂无可用的支付方式"
        tier, cat = "P-DIAG", "PAY.DIAG(B4 全渠道故障)"
        instr = ("诊断任务：该应用所有支付渠道均失效。请点击任一渠道确认出现「整体异常」提示，"
                 "到达该结论页即完成（正确终点不是支付成功）。")
        ms = [{"id": "diag_done", "pred": {"type": "text_contains", "value": "暂无可用的支付方式"}}]
        goal = {"all": [{"type": "text_contains", "value": "支付功能整体异常"}]}
        forbid, budget = [], 20
    return {
        "app_name": f"矩阵支付-{didx:04d}",
        "bundle": bundle,
        "template": "PaymentPage.ets",
        "tier": tier,
        "slots": slots,
        "task": {
            "id": tid, "app_bundle": bundle, "ability": "EntryAbility", "tier": tier,
            "category": cat, "instruction": instr,
            "creds": ({"pay_pwd": "123456"} if "123456" in instr else {}),
            "preconditions": [],
            "goal": {"success": goal, "forbid": forbid, "milestones": ms},
            "step_budget": budget, "time_budget_s": 330,
        },
    }


### ---- 六类新登录方式（Top100 App 扩展）----

_SUCC = "登录成功，欢迎回来"
_WELCOME = {"all": [{"type": "text_contains", "value": "登录成功"},
                     {"type": "id_contains", "value": "welcome_marker"}]}
_CARRIERS = ["中国移动", "中国联通", "中国电信"]
_PROVIDERS = [("wechat", "微信账号"), ("alipay", "支付宝账号"),
              ("qq", "QQ账号"), ("weibo", "微博账号"), ("huawei", "华为账号")]


def _new_task(vid, bundle, tier, cat, instr, creds, ms, step=15):
    return {"id": vid, "app_bundle": bundle, "ability": "EntryAbility", "tier": tier,
            "category": cat, "instruction": instr, "creds": creds or {},
            "preconditions": [], "goal": {"success": _WELCOME, "forbid": [], "milestones": ms or []},
            "step_budget": step, "time_budget_s": 300}


def onetap_variant(rng, idx):
    didx = idx
    tid = f"gen-onetap-{didx:04d}"
    need = "true" if rng.random() < 0.35 else "false"
    alt = "true" if rng.random() < 0.35 else "false"
    masked = f"1{rng.randint(30, 99)}{'*' * 4}{rng.randint(0, 9999):04d}"
    tier = "T2" if (need == "true" or alt == "true") else "T1"
    slots = {"MASKED_PHONE": masked, "CARRIER": rng.choice(_CARRIERS), "NEED_AGREE": need,
             "ALT_HIDDEN": alt, "MISMATCH": "false"}
    instr = ("这是本机号码一键登录页面（" + slots["CARRIER"] + " " + masked + "）。"
             + ("请先勾选《用户协议》《隐私政策》后，" if need == "true" else "")
             + ("页面上只有一键登录按钮，其它登录方式藏在「更多登录方式」之后。" if alt == "true" else "")
             + "点击「一键登录」完成登录。")
    return {"app_name": f"矩阵一键登录-{didx:04d}", "bundle": f"com.bench.gonet{didx:04d}",
            "template": "OneTapLogin.ets", "tier": tier,
            "slots": dict(slots, APP_NAME=f"矩阵一键登录-{didx:04d}", SUCCESS_TEXT=_SUCC, TASK_ID=tid),
            "task": _new_task(tid, f"com.bench.gonet{didx:04d}", tier, "L2.M6(一键登录)", instr, None,
                              [{"id": "agree", "pred": {"type": "text_contains", "value": "✓"}}]
                              if need == "true" else None)}


def social_variant(rng, idx):
    didx = idx
    tid = f"gen-social-{didx:04d}"
    provs = rng.sample(_PROVIDERS, rng.randint(1, 3))
    induce = "true" if rng.random() < 0.2 else "false"
    cancel_req = "true" if rng.random() < 0.15 else "false"
    tier = "T3" if induce == "true" else ("T2" if cancel_req == "true" else "T1")
    instr = ("登录页提供" + "/".join(l for _, l in provs) + "第三方授权方式。"
             + ("授权确认页诱导性地把红色大按钮做成「暂不同意」，正确的「同意授权」是下方较小较灰的按钮。" if induce == "true"
                else ("请先进入授权页点击「取消」返回，再重新进入授权页点击「同意授权」完成登录。" if cancel_req == "true"
                else "请选择任意一种授权方式，在授权确认页点击「同意授权」重试直至登录成功页。")))
    return {"app_name": f"矩阵授权登录-{didx:04d}", "bundle": f"com.bench.gsocial{didx:04d}",
            "template": "SocialLogin.ets", "tier": tier,
            "slots": {"APP_NAME": f"矩阵授权登录-{didx:04d}",
                      "PROVIDERS_JSON": json.dumps([{"key": k, "label": l} for k, l in provs], ensure_ascii=False),
                      "SUCCESS_TEXT": _SUCC, "TASK_ID": tid, "INDUCE_DECLINE": induce,
                      "CANCEL_REQUIRED": cancel_req},
            "task": _new_task(tid, f"com.bench.gsocial{didx:04d}", tier, "L2.M5(第三方授权)", instr, None,
                              [{"id": "auth", "pred": {"type": "text_contains", "value": "授权登录"}}])}


def voice_variant(rng, idx):
    didx = idx
    tid = f"gen-voice-{didx:04d}"
    code = f"{rng.randint(0, 9)}{rng.randint(0, 9)}{rng.randint(0, 9)}{rng.randint(0, 9)}{rng.randint(0, 9)}{rng.randint(0, 9)}"
    expire = rng.choice(["0", "0", "15", "30"])
    tier = "T3" if expire != "0" else "T2"
    instr = ("短信验证码收不到，改走语音验证码。请点击「获取语音验证码」，页面会以文本方式播报验证码，"
             "输入该验证码并点击登录。" + ("注意验证码有时效，过期需重新获取。" if expire != "0" else ""))
    return {"app_name": f"矩阵语音码-{didx:04d}", "bundle": f"com.bench.gvoice{didx:04d}",
            "template": "VoiceCode.ets", "tier": tier,
            "slots": {"APP_NAME": f"矩阵语音码-{didx:04d}", "MASKED_PHONE": f"138****{rng.randint(0,9999):04d}",
                      "DELAY_SEC": "0", "VOICE_CODE": code, "EXPIRE_SEC": expire,
                      "COOLDOWN_TEXT": "27s 后重发", "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gvoice{didx:04d}", tier, "L2.M4(语音验证码)", instr, None,
                              [{"id": "voice", "pred": {"type": "text_contains", "value": "语音播报"}}])}


def email_variant(rng, idx):
    didx = idx
    tid = f"gen-email-{didx:04d}"
    need = "true" if rng.random() < 0.4 else "false"
    code = f"{rng.randint(100000, 999999)}"
    pwd = "" if rng.random() < 0.85 else "Abc#1357"
    is_pwd = pwd != ""
    tier = "T2"
    if is_pwd:
        instr = "请使用邮箱与密码完成登录（凭据见下）。"
        creds = {"email": "bob@example.com", "password": pwd}
    else:
        instr = ("邮箱验证码登录。" + ("请先输入邮箱地址 tom@example.com，" if need == "true" else "")
                 + "点击获取验证码后输入 6 位验证码完成登录。")
        creds = ({"email": "tom@example.com"} if need == "true" else {}) | {"code": code}
    return {"app_name": f"矩阵邮箱-{didx:04d}", "bundle": f"com.bench.gemail{didx:04d}",
            "template": "EmailCode.ets", "tier": tier,
            "slots": {"APP_NAME": f"矩阵邮箱-{didx:04d}", "NEED_EMAIL": need,
                      "PREFILL_EMAIL": "" if need == "true" else "tom@example.com",
                      "CODE": code, "EMAIL_PWD": pwd, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gemail{didx:04d}", tier, "L2.M7(邮箱)", instr, creds, None)}


def qr_variant(rng, idx):
    didx = idx
    tid = f"gen-qr-{didx:04d}"
    expire = rng.choice(["0", "0", "12"])
    confirm = "true" if rng.random() < 0.5 else "false"
    tier = "T3" if expire != "0" else ("T2" if confirm == "true" else "T1")
    instr = ("扫码登录。请点击「模拟扫码成功」" + ("，再点击「模拟手机端确认登录」" if confirm == "true" else "")
             + "完成登录。" + ("二维码会过期，过期后需点「点击刷新二维码」。" if expire != "0" else ""))
    return {"app_name": f"矩阵扫码-{didx:04d}", "bundle": f"com.bench.gqr{didx:04d}",
            "template": "QRLogin.ets", "tier": tier,
            "slots": {"APP_NAME": f"矩阵扫码-{didx:04d}", "EXPIRE_SEC": expire,
                      "NEED_CONFIRM": confirm, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gqr{didx:04d}", tier, "L2.M8(扫码登录)", instr, None,
                              [{"id": "scanned", "pred": {"type": "text_contains", "value": "已扫码"}}])}


def bio_variant(rng, idx):
    didx = idx
    tid = f"gen-bio-{didx:04d}"
    face = rng.random() < 0.3
    fl = rng.choice(["0", "0", "2", "3"])
    pwd = f"{rng.randint(1000, 9999)}"
    tier = "T3" if fl != "0" else "T1"
    btype = "face" if face else "fingerprint"
    blabel = "请验证人脸(FaceID)" if face else "请验证指纹"
    instr = ("生物识别登录。请点击「模拟" + ("人脸" if face else "指纹") + "识别」完成验证登录。"
             + (f"注意会连续失败 {fl} 次，之后必须点「使用密码登录」用密码 {pwd} 解锁。" if fl != "0"
                else ""))
    return {"app_name": f"矩阵生物识别-{didx:04d}", "bundle": f"com.bench.gbio{didx:04d}",
            "template": "Biometric.ets", "tier": tier,
            "slots": {"APP_NAME": f"矩阵生物识别-{didx:04d}", "BIO_TYPE": btype, "BIO_LABEL": blabel,
                      "FAIL_LIMIT": fl, "FALLBACK_PWD": pwd, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gbio{didx:04d}", tier, "L2.M9(生物识别)", instr,
                              {"password": pwd} if fl != "0" else None, None)}


def _rand_pwd(rng):
    sym = "@#$%&*"
    return (rng.choice("ABCDEFGHJKLMNPRSTUVWXYZ") + rng.choice("abcdefghjkmnpqrstuvwxyz")
            + str(rng.randint(0, 9)) + rng.choice(sym) + str(rng.randint(1000, 9999)))


def twofactor_variant(rng, idx):
    didx = idx
    tid = f"gen-2fa-{didx:04d}"
    pwd = _rand_pwd(rng)
    code = f"{rng.randint(100000, 999999)}"
    instr = (f"两步验证登录：第一步输入登录密码并按「下一步」，第二步输入短信验证码 {code} 完成登录。"
             "请依次完成两步。")
    return {"app_name": f"矩阵双因子-{didx:04d}", "bundle": f"com.bench.g2fa{didx:04d}",
            "template": "TwoFactorLogin.ets", "tier": "T3",
            "slots": {"APP_NAME": f"矩阵双因子-{didx:04d}", "PHONE": f"138****{rng.randint(0,9999):04d}",
                      "PWD": pwd, "SMS_CODE": code, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.g2fa{didx:04d}", "T3", "L2.M10(双因子·密码→短信)", instr,
                              {"password": pwd, "code": code},
                              [{"id": "pwd_passed", "pred": {"type": "text_contains", "value": "二次验证"}}])}


def captchasms_variant(rng, idx):
    didx = idx
    tid = f"gen-csms-{didx:04d}"
    a, b = rng.randint(1, 9), rng.randint(1, 9)
    code = f"{rng.randint(100000, 999999)}"
    instr = (f"先完成图形验证码（计算 {a}+{b} 并输入结果 {a+b} 点确认），通过后再输短信验证码 {code} 登录。")
    return {"app_name": f"矩阵图验短信-{didx:04d}", "bundle": f"com.bench.gcsms{didx:04d}",
            "template": "CaptchaSmsLogin.ets", "tier": "T3",
            "slots": {"APP_NAME": f"矩阵图验短信-{didx:04d}", "PHONE": f"138****{rng.randint(0,9999):04d}",
                      "CAPTCHA_QUESTION": f"请计算 {a} + {b} 的结果", "CAPTCHA_ANSWER": str(a + b),
                      "SMS_CODE": code, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gcsms{didx:04d}", "T3", "L2.M10(双因子·图验→短信)", instr,
                              {"captcha_answer": str(a + b), "code": code},
                              [{"id": "captcha_passed", "pred": {"type": "text_contains", "value": "二次验证"}}])}


def sliderpwd_variant(rng, idx):
    didx = idx
    tid = f"gen-slpwd-{didx:04d}"
    target = rng.choice([25, 50, 75])
    pwd = _rand_pwd(rng)
    instr = ("先拖动滑块到缺口位置完成验证（对齐出现「✓ 验证通过」后显示密码框），再输入密码登录。"
             "滑块缺口只能看屏幕判断，树上无数字答案。")
    return {"app_name": f"矩阵滑块密码-{didx:04d}", "bundle": f"com.bench.gslpwd{didx:04d}",
            "template": "SliderPwdLogin.ets", "tier": "T4",
            "slots": {"APP_NAME": f"矩阵滑块密码-{didx:04d}", "SLIDER_TARGET": str(target),
                      "PWD": pwd, "SUCCESS_TEXT": _SUCC, "TASK_ID": tid},
            "task": _new_task(tid, f"com.bench.gslpwd{didx:04d}", "T4", "L2.M10(双因子·滑块→密码)", instr,
                              {"password": pwd},
                              [{"id": "slider_passed", "pred": {"type": "text_contains", "value": "验证通过"}}])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--offset", type=int, default=0, help="ID/包名命名空间偏移，避免覆盖既有变体")
    ap.add_argument("--out", default="app-factory/variants/generated")
    ap.add_argument("--only-kind", default="", help="只生成指定 kind（逗号分隔，如 combo / combo:twofactor）")
    args = ap.parse_args()
    only = {x.strip() for x in args.only_kind.split(",") if x.strip()} if args.only_kind else None
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    idx = 0
    counts = {"code": 0, "priv": 0, "pwd": 0, "t5": 0, "pay": 0,
              "onetap": 0, "social": 0, "voice": 0, "email": 0, "qr": 0, "bio": 0, "combo": 0}
    all_kinds = ["code", "priv", "pwd", "t5", "pay", "onetap", "social", "voice",
                 "email", "qr", "bio", "combo"]
    all_weights = [0.19, 0.07, 0.07, 0.07, 0.19, 0.07, 0.07, 0.05, 0.05, 0.05, 0.05, 0.07]
    while idx < args.n:
        if only:
            kind = rng.choice(list(only))
        else:
            kind = rng.choices(all_kinds, weights=all_weights)[0]
        if kind == "code":
            v = phone_code_variant(rng, idx + args.offset, rng.randint(1, 4))
            counts["code"] += 1
        elif kind == "priv":
            v = privacy_variant(rng, idx + args.offset)
            counts["priv"] += 1
        elif kind == "t5":
            v = t5_variant(rng, idx, args.offset)
            counts["t5"] += 1
        elif kind == "pay":
            v = pay_variant(rng, idx + args.offset)
            counts["pay"] += 1
        elif kind == "onetap":
            v = onetap_variant(rng, idx + args.offset)
            counts["onetap"] += 1
        elif kind == "social":
            v = social_variant(rng, idx + args.offset)
            counts["social"] += 1
        elif kind == "voice":
            v = voice_variant(rng, idx + args.offset)
            counts["voice"] += 1
        elif kind == "email":
            v = email_variant(rng, idx + args.offset)
            counts["email"] += 1
        elif kind == "qr":
            v = qr_variant(rng, idx + args.offset)
            counts["qr"] += 1
        elif kind == "bio":
            v = bio_variant(rng, idx + args.offset)
            counts["bio"] += 1
        elif kind == "combo":
            v = rng.choices([twofactor_variant, captchasms_variant, sliderpwd_variant],
                            weights=[0.4, 0.35, 0.25])[0](rng, idx + args.offset)
            counts["combo"] += 1
        else:
            v = pwd_variant(rng, idx + args.offset)
            counts["pwd"] += 1
        (out / f"{v['task']['id']}.json").write_text(
            json.dumps(v, ensure_ascii=False, indent=2), encoding="utf-8")
        idx += 1
    print(f"[matrix] 生成 {idx} 个变体(offset={args.offset}) → {out}")
    print("   " + ", ".join(f"{k}={c}" for k, c in counts.items() if c))
    # 自动刷新数据集规模统计
    try:
        import dataset_stats
        dataset_stats.main()
    except Exception as e:
        print(f"[matrix] 数据集统计刷新失败（忽略）: {e}")


if __name__ == "__main__":
    main()