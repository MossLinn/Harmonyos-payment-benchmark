# 变体配置 Schema（variants/*.json）

一个 JSON 文件 = 一个可构建的鸿蒙 App + 一个基准任务。字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `app_name` | string | 应用显示名 |
| `bundle` | string | 包名（反向域名，小写字母/数字/点） |
| `template` | string | `templates/` 下的页面模板文件名 |
| `tier` | string | 难度层级 T1~T5（见 docs/spec.md） |
| `slots` | object | 模板槽位键值对；生成器把模板里每个 `{{KEY}}` 替换为 `slots[KEY]`（str 化）。任何未覆盖的槽位会报错 |
| `task` | object | 自动导出的任务描述：`id/instruction/creds/step_budget/time_budget/goal` |

## goal 谓词语法

```jsonc
"goal": {
  "success": { "all": [ {"type": "text_contains", "value": "欢迎回来"} ] },
  "forbid":  [ {"type": "id_contains", "value": "welcome_marker"} ]
}
```

- 谓词：`text_contains` / `id_contains` / `exists` / `type_count`（`type`,`op`,`n`）
- 组合：`all` / `any` / `not`
- 目标状态注解：模板页面里 `welcome_marker`（成功）、`browse_marker`（仅浏览）
  即为判定锚点；变体的 `SUCCESS_TEXT` / 目标页面文案由槽位控制。

## 弹窗链 `CHAIN` 槽（PhoneCodeLogin 模板）

字符串形式的 JSON 数组，元素：`kind`(privacy|update|promo)、`title`、`body`、
`btnMain`、`btnAlt`、`closable`（false=强制单按钮）、`countdown`（预留）。

## 当前变体清单

| 文件 | 模板 | 难度 | 考点 |
|---|---|---|---|
| privacy-full.json | PrivacyDialog | T1 | 单隐私弹窗同意 |
| privacy-mislead.json | PrivacyDialog | T3 | 诱导样式 + 假关闭 × + 正确路径是「暂不同意」 |
| privacy-seg.json | PrivacyDialog | T2 | 双条款分段勾选联动 |
| privacy-scroll.json | PrivacyDialog | T2 | 条款在正文底部，需滚动到位后才能勾选 |
| code-login.json | PhoneCodeLogin | T2 | 弹窗链(更新+营销+隐私) + 手机号 + 6 位验证码 + 倒计时 + 自动填充 |
| code-nofill.json | PhoneCodeLogin | T2 | 无自动填充，手动输验证码 + 频控提示 |
| code-trap.json | PhoneCodeLogin | T3 | 自动填充回填错码(1111)，需纠错重输 |
| pwd-captcha.json | PwdLogin | T2 | 密码 + 图形算式验证码 + 锁定风控 |
| pwd-lock.json | PwdLogin | T3 | 连续 2 次错密码锁定 45 秒 |
| colorgate.json | PrivacyDialog | **T4 视觉门控** | 同文案双按钮，只有颜色区分正确路径（位置按种子洗牌，文本智能体仅 50% 胜率） |
| captcha-colortext.json | PwdLogin | **T4 视觉门控** | Canvas 绘制的蓝色四位字符验证码，树内无文本，只能读图 |
| gen-t5-*.json (generated/) | **T5Captcha** | **T5** | 三形态：`slider` 滑块对齐缺口（无数字答案）/ `clickchars` 按成语顺序点被乱序的四字（错即重置）/ `hidden` 协议与登录按钮藏于「更多」之后 |

## 批量生成（矩阵扩量）

```powershell
python scripts/gen_matrix.py --n 70 --seed 2026 --offset 1000 --out app-factory/variants/generated
# 现总量：11 精选 + 110 生成 = 121 变体（含 8 个 T5）