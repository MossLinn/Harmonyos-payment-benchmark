# 支付 Benchmark 与 qwen 能力测试（round-2 更新：真机榜）

## 支付套件真机榜（DevEco 模拟器，8 任务）

| 任务 | 考点 | rules | glm-5.3-flash 文本 | qwen3.7-max 文本 | qwen3.8-max 视觉 |
|---|---|---|---|---|---|
| pay-normal-wechat | 微信渠道拉起+支付 | ✓ | ✓ 5步 | ✓ 5步 | ✓ 5步 |
| pay-normal-alipay | 支付宝渠道 | ✓ | ✓ 5步 | ✓ 5步 | — |
| pay-normal-bankcard | 银行卡渠道 | ✓ | ✓ 5步 | ✓ 5步 | — |
| pay-normal-huawei | 华为支付渠道 | ✓ | ✓ 20步 | ✓ 5步 | ✓ 5步 |
| pay-broken-wechat (B1) | 微信故障→换支付宝 | ✓ 7步 | ✓ 7步 | ✓ 7步 | ✓ 7步 |
| pay-dead-alipay (B2) | 死弹窗→Back→银行卡 | ✓ 7步 | ✗ 25步 | ✓ 7步 | ✓ 7步 |
| pay-blank-huawei (B3) | 空白页→Back→微信 | ✓ 5步 | ✗ 25步 | ✓ 7步 | — |
| pay-allbroken (B4) | 全故障→确认异常页 | ✗(冷启动树空) | ✓ 3步 | ✓ 2步 | ✓ 1步 |
| **SR** | | **7/8** | **6/8** | **8/8** | **7/8** |

## sim 参照（同套件，round-1）

| 任务 | rules | qwen3.8-max(视觉) | qwen3.7-max(文本) |
|---|---|---|---|
| pay-normal-wechat | ✓ | ✓ 7步 | ✓ 5步 |
| pay-normal-alipay | ✓ | ✓ 7步 | ✓ 6步 |
| pay-normal-bankcard | ✓ | ✓ 5步 | ✓ 5步 |
| pay-normal-huawei | ✓ | ✗ 20步耗尽 | ✓ 5步 |
| pay-broken-wechat (B1) | ✓ | ✗ 21步超时 | ✓ 7步 |
| pay-dead-alipay (B2) | ✓ | ✗ 25步耗尽 | ✓ 7步 |
| pay-blank-huawei (B3) | ✓ | ✗ 19步超时 | ✓ 7步 |
| pay-allbroken (B4) | ✓ | ✓ 1步 | ✓ 2步 |
| **SR** | **8/8** | **4/8** | **8/8** |

> 亮点（sim↔真机差异）：qwen3.8-max 视觉在 sim 上的 B1/B2/B3 三连败，在**真机上全胜**——
> 真实截图 + 真实返回键反而修正了它的恢复动作（sim 渲染信息不足是干扰源）。

## 二期形态（round-3）：B5 拉起后取消重选 / B6 风控二次确认

| 任务 | rules(sim) | qwen3.7-max 真机 | qwen3.8-max 真机 |
|---|---|---|---|
| pay-cancel-wechat (B5) | ✓ 5步 | ✓ 7步 | — |
| pay-twice-alipay (B6) | ✓ 6步 | ✓ 6步 | — |

## 二期形态（round-3/4：支付套件扩至 17 任务）

| 任务 | 考点 | rules(sim) | 真机 D2（旧模板 margin=220） |
|---|---|---|---|
| pay-cancel-wechat (B5) | 拉起后主动取消 → 换渠道完成 | ✓ 7步 | qwen3.7 ✓ 7步 |
| pay-twice-alipay (B6) | 风控二次确认弹窗 | ✓ 6步 | qwen3.7 ✓ 6步 |
| pay-amount-mismatch (B7) | 弹窗金额与订单不符 → 应取消而非支付 | ✓ 3步 | rules ✓3步 / qwen3.7 ✓3步 / qwen3.8 ✓2步 |
| pay-timeout-fast (B8a) | 45s 倒计时内完成支付 | ✓ 5步 | ❌ rules 18步耗尽、qwen3.7 触发 forbid（超时） |
| pay-timeout-late (B8b) | 逆向验证：故意放任超时 → 应到「订单已关闭」页 | ✓ 5步 | rules ✓4步 / qwen3.7 ✓3步 |
| pay-refund (B9) | 支付 + 二次确认 + 退款申请全链路 | ✓ 7步 | rules ✓7步 / ❌ qwen3.7 22步耗尽 |
| **pay-ime-clip (B10)** | 软键盘把确认按钮裁出树 → 应按返回键收起键盘 | ✓ 6步 | 🔄 D3 排队 |
| **pay-colorgate / 2 (P-VISUAL)** | 同文异色假冒支付入口（成对反序） | ✗ 按设计弃权 | 🔄 排队 |

**支付套件 rules 基线：15/17（sim）** —— 14 个功能题全过，2 个视觉门控题按设计诚实弃权。

### D2 三例失败已定位同一根因（非模型缺陷）

真机实测发现：`TextInput` 获焦 → 软键盘弹出 → 页面视口被压缩 →
**低于新视口底的控件被裁出 `dumpLayout` 节点列表**。带倒计时行的弹窗比不带的低 102px，
确认按钮 y 从 1411（存活）变 1513（被裁），于是 rules/qwen3.7 在输完密码后永远点不到确认。
证据链与阈值见 `docs/ime_clip_finding.md`。

处置：① 全部非 B10 变体的 `POPUP_MARGIN` 改为 60vp（键盘安全），已真机重编译 5 个 App；
② 把该缺陷固化为**故意注入的 B10 故障类**（`POPUP_MARGIN=320vp`），正确解法是按返回键收起键盘；
③ 规则基线加了恢复规则（密码框在树里但确认按钮不在 → 按 Back，最多 3 次），sim 6 步通过；
④ sim 侧同步建模（`ime_open` + `CLIP_MARGIN=200`），保持双后端语义同构。
修复后的真机复验为 `runs/D3_*`（已排队自动执行）。

## 三期：布局缺陷修复后的真机复验（D2 → D3，决定性对照）

D2 的失败经逐帧取证定位为**两处被测应用布局缺陷**（非模型能力问题）：
① 弹窗 `margin=220vp` + 输入法压缩视口 → 确认按钮被裁出组件树（`docs/ime_clip_finding.md`）；
② 协议行只有小方块可点、文字标签不可点 → 视觉模型反复点标签、勾选永不生效
（`docs/agree_hotzone_finding.md`）。修复：`POPUP_MARGIN=60vp` + 协议整行可点（幂等置真）。

| Agent | D2（旧模板，4 题） | D3（修复后，5 题含 B10 陷阱） |
|---|---|---|
| 规则基线 | 3/4 | 4/5（B10 失败：该轮跑在旧规则代码上，未触发返回键恢复） |
| qwen3.7-max 文本 | 2/4 | **5/5** |
| qwen3.8-max 视觉（768 降采样档） | 2/4 | **5/5** |

**B10（输入法裁剪）在真机上确证可解**：两个模型各自独立走出同一条最优 6 步路径
（输密码 → 视口 2760→1489、按钮消失 → 按返回键 → 视口恢复 2760、按钮回树 → 点确认）。
由此得到一条可复用的自动化信号：**root 视口高度 2760↔1489 即输入法开合状态**。

## 四期：支付视觉门控真机区分度（D6，落地层修复后）

成对反序变体 `pay-colorgate`（红假冒在前）/ `pay-colorgate2`（绿正规在前），
两个按钮文案完全相同、**只有颜色能区分**，点错即 forbid 判负。

| 臂 | pay-colorgate | pay-colorgate2 | 门控对成绩 | 对照题 pay-normal-wechat |
|---|---|---|---|---|
| **视觉 qwen3.8-max（768 降采样）** | ✅ 5 步 | ✅ 5 步 | **2/2 = 100%** | ✅ 5 步 |
| 文本 qwen3.7-max | ❌ 2 步 forbid（点红被拦截） | ✅ 5 步（绿在前，蒙对） | **1/2 = 50%** | ✅ 5 步 |

→ 与设计预测完全吻合：**视觉模型 100%、纯靠位置猜的文本模型 50%**，对照题两臂全过（无回归）。
这条区分度只有在修掉 harness 的两个落地层 bug 之后才成立，详见 `docs/grounding_fix.md`
（① `node_text` 匹配覆盖模型坐标；② sim 三套坐标空间不一致）。

## 渠道拉起成功率聚合（`docs/pay_metrics.md`，milestone 口径）

**全部 run 的四渠道拉起成功率均为 100%**（微信 2/2、支付宝 2/2、银行卡 2/2、华为 1/1）；
差异集中在「判异常准确率」：qwen3.7-max 4/4 = glm文本 2/4 = 诊断能力分水岭。

## 参照题（同批 12 题里的登录/门控）

| 任务 | qwen3.8-max(视觉) | qwen3.7-max(文本) |
|---|---|---|
| colorgate（同文异色） | ✓ 6步 | ✓ 1步(顺序蒙对) |
| captcha-colortext（OCR 门控） | ✓ 8步（**读图成功**） | ✗ 25步（文本不可解,符合预期） |
| privacy-mislead | ✓ 1步 | ✓ 1步 |
| code-trap | ✓ 14步 | ✓ 8步 |

## 结论

1. **qwen3.7-max 经网关不支持图片**（`Unexpected item type in content`），文本模式却极强：
   11/12、4 分钟 149K tokens、支付套 8/8——**支付链路首选便宜解**；
2. qwen3.8-max 视觉可用（OCR 门控 8 步过、colorgate 6 步过），但**诊断类（需要 Back/换渠的
   恢复性操作）4 连败**，且单步慢（30-50s）——与 doubao 的“慢+踱步”属同类弱点，但更集中在
   “状态恢复”动作上；华为渠道正常流也失败（20 步），值得单题复跑定位；
3. 支付 Benchmark 环境自检通过（rules 8/8 = 可解上界），**故障形态判定在 sim 上完全可判**；
   下一步：支付套件 × qwen/glm/doubao 上真机横评 + 拉起成功率分渠道指标汇总。

## 数据

- `runs/qwen38max_test`（vision 12 题）、`runs/qwen37max_text`（文本 12 题）、`runs/pay_rules_sim5`
- 设计文档 `docs/payment_spec.md`