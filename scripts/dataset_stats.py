# -*- coding: utf-8 -*-
"""
数据集规模统计：自动生成 docs/dataset_stats.md。

用法：
  python scripts/dataset_stats.py          # 手动刷新
  # gen_matrix.py 每次生成矩阵后会自动调用本脚本刷新

统计口径：
  - 支付 = PaymentPage.ets；登录 = 其余全部模板；
  - 精选 = app-factory/variants/*.json；矩阵 = app-factory/variants/generated/*.json。
"""
import collections
import glob
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUR = ROOT / "app-factory" / "variants"
GEN = CUR / "generated"

TEMPLATE_LABEL = {
    "PhoneCodeLogin.ets": "短信验证码登录",
    "PwdLogin.ets": "密码登录（含图形/OCR 验证码）",
    "PrivacyDialog.ets": "隐私/协议弹窗",
    "T5Captcha.ets": "滑块/点选汉字/隐藏入口",
    "OneTapLogin.ets": "本机号码一键登录",
    "SocialLogin.ets": "第三方授权登录",
    "VoiceCode.ets": "语音验证码",
    "EmailCode.ets": "邮箱验证码/邮箱密码",
    "QRLogin.ets": "扫码登录",
    "Biometric.ets": "生物识别（指纹/人脸）",
    "TwoFactorLogin.ets": "双因子（密码→短信）",
    "CaptchaSmsLogin.ets": "双闸门（图验→短信）",
    "SliderPwdLogin.ets": "双闸门（风控滑块→密码）",
    "PaymentPage.ets": "支付（四渠道+故障/风控）",
}


def collect():
    curated = sorted(CUR.glob("*.json"))
    generated = sorted(GEN.glob("*.json"))
    files = curated + generated
    login_tmpl = collections.Counter()
    pay = 0
    login = 0
    tiers = collections.Counter()
    is_cur = 0
    for f in files:
        try:
            v = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        t = v.get("template", "?")
        tier = v.get("tier", "?")
        tiers[tier] += 1
        if f.parent == CUR:
            is_cur += 1
        if t == "PaymentPage.ets":
            pay += 1
        else:
            login += 1
            login_tmpl[t] += 1
    return {
        "total": len(files), "login": login, "pay": pay,
        "curated": is_cur, "matrix": len(files) - is_cur,
        "login_tmpl": login_tmpl, "tiers": tiers,
        "captcha_code": sum(login_tmpl[t] for t in
                            ("PhoneCodeLogin.ets", "VoiceCode.ets", "T5Captcha.ets", "EmailCode.ets")),
    }


def render(s) -> str:
    L = ["# 数据集规模统计（自动生成）", "",
         f"> 生成时间：{datetime.now().isoformat(timespec='seconds')}；刷新：`python scripts/dataset_stats.py`（gen_matrix 每次生成后自动刷新）", "",
         f"- **总样本：{s['total']}**（精选 {s['curated']} + 矩阵 {s['matrix']}）",
         f"- **登录场景：{s['login']}** ｜ **支付场景：{s['pay']}**",
         f"- 验证码/动态口令类（短信+语音+滑块点选+邮箱码）：{s['captcha_code']}", "",
         "## 登录模板分布", "",
         "| 模板 | 样本 |", "|---|---|"]
    for t, c in s["login_tmpl"].most_common():
        L.append(f"| {TEMPLATE_LABEL.get(t, t)} | {c} |")
    L += ["", "## 支付模板", "", "| 模板 | 样本 |", "|---|---|",
          f"| {TEMPLATE_LABEL['PaymentPage.ets']} | {s['pay']} |", "",
          "## 难度层分布", "", "| tier | 样本 |", "|---|---|"]
    for t, c in sorted(s["tiers"].items()):
        L.append(f"| {t} | {c} |")
    return "\n".join(L) + "\n"


def main(out: str = "docs/dataset_stats.md"):
    s = collect()
    (ROOT / out).write_text(render(s), encoding="utf-8")
    print(render(s))
    print(f"[dataset_stats] 已写出 {ROOT / out}")


if __name__ == "__main__":
    main()