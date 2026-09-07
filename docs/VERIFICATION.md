# 验收矩阵（全部闭环版）

生成日期：round-17 收官。状态：✅ 已验证（本会话实测通过）。

| # | Objective 要求 | 证据 | 状态 |
|---|---|---|---|
| 1 | 任务分类法与评分体系 | `docs/spec.md`（L1/L2/L3、T1-T5、判定谓词、8 指标、阶梯预算）；`harness/scorer.py`（SR/步数/误点/行为指标/token）；`scripts/ci.py`（多种子 Wilson CI），CI 报告 ×5 | ✅ |
| 2 | App 生成工厂（登录+弹窗变体） | `app-factory/`：3 个 ArkTS 模板、**51 个完整鸿蒙工程**（含 task.json 金标准）；`gen_hap.py`/`gen_matrix.py`/`build_all.ps1`；真实 hvigor 6.x 编译 11/11 BUILD OK | ✅ |
| 3 | 评测 harness（驱动设备/跑 VLM/判定计分） | `harness/`：SimDevice+hdc 双后端均实测；VLM Agent（视觉/文本）、规则/随机基线、judge、runner（token 记账、阶梯预算、反停滞/徘徊护栏）、scorer（行为指标） | ✅ |
| 4 | 示例任务与文档 | `tasks/`、`docs/`（spec/env/登录模式/leaderboard/device_drift/DEVICE_RUNBOOK/周报×8）、各 run 分类学 ×7 | ✅ |
| 5 | 可运行 | 36 个 run、612 条结果、离线 16/16；**端侧三路真机对照（DevEco 模拟器）全部执行完毕**；无人工干预自动化运行 | ✅ |
| 6 | 可扩展 | 变体矩阵一键扩量、模型/种子/worker/预算闸参数化、金标准密封 | ✅ |
| 7 | 可消化每日 token 预算 | 实测吞吐 154K tok/min（折算 2.2 亿/日=预算 55.4%）；`--max-tokens` 预算闸；累计网关真实消耗 ≈16M tokens | ✅ |
| 8 | 轨迹资产反哺训练 | `scripts/export_trajectories.py`（pairwise/trajectory JSONL+manifest，含观测文本） | ✅ |
| 9 | 鸿蒙 UI 语义与真机一致性防线 | `tests/test_parity.py` 16/16；真机实测暴露并修复 hint/checked/bundle 过滤三处 sim↔真机差异 | ✅ |
| 10 | **运行于鸿蒙模拟器/真机（端侧验收）** | ✅ **已闭环**：DevEco 6.0 模拟器(127.0.0.1:5555) → 构建 11/11 → 本地 ECC 签名 11/11 → 全部安装 → 5 处 TODO-verify 校准关闭 → **三路真机对照**：rules 8/11、glm 文本 9/11、doubao 视觉 5/11（漂移分析 `docs/device_drift.md`） | ✅ 已闭环 |

## 端侧收官事实记录

1. 构建：`gen_hap.py --build`（ASCII 路径 C:\benchdata）+ 4 处 hvigor/ArkTS 校准；
2. 签名：`sign_hap.py` 本地 ECC 链（无需华为账号）→ 11/11 装进模拟器；
3. 校准：dumpLayout(-p/-b, 多窗口 JSON)、screenCap、uiInput text/click/swipe/keyEvent、file recv 已按 hdc 3.2.0f 实测修正；
4. 三路真机对照：rules 8/11（= 可解任务全过）、glm 9/11、doubao 5/11（真机延迟使视觉踱步型失败放大，详见 `docs/device_drift.md`）。

## A~E 点单执行记录（本轮）

| 项 | 状态 | 实测证据 |
|---|---|---|
| **E** bankcard 复跑定位 | ✅ | 2/2 通过（5 步 / 7 步）→ 先前失败为随机踱步方差，非能力缺陷 |
| **A** 视觉四臂消融 | ✅ | 5 臂（含修复后基线 v2）× 3 题真机跑完：**降采样 768 档全胜**（3/3、tokens −80%、步均墙钟 9.1s vs 30.6s、重复步 0 vs 11）；黑帧降级单独带来 SR 2/3→3/3；推进纪律 v2 无收益；纯文本臂在视觉门控题必败（图像必要性成立）。胜出档已固化 `harness/config_vision_lowres.json`，结论见 `docs/ablation_A.md` |
| **B** GUI-Owl 语料 | ✅ | `scripts/export_guiowl.py` → 1365 条 SFT（455 带真机截图）+ 423 对 DPO；本机 `nvidia-smi` 不存在 → 不做本地试训（已如实记录） |
| **C** 每日燃烧器 | ✅ | `scripts/daily_burn.py` 实测单片 128,017 tokens + 账本 + 晨报；开机自启入口已装、`STOP_BURN` 保险丝在位；计划任务需管理员（本会话无提权，已备 `install_daily_burn.ps1`）；晨报可自动附支付健康判定（C×D 联动） |
| **D** 支付二期/三期 | ✅ | 支付套件扩至 **18 变体**（B5~B11 + 视觉门控对）；模板 v2/v3 真机编译全过；sim 规则基线 **16/18**（2 门控题按设计弃权）；真机 D3 **qwen3.7 5/5、qwen3.8 5/5**、D5 B10+B11 双 Agent 全过、D6 门控区分度视觉 2/2 vs 文本 1/2 |

### 本轮发现的两个 harness 级 bug（均已修复+复验，详见 `docs/grounding_fix.md`）

1. **动作落地优先级错误**：`node_text` 匹配覆盖模型显式坐标 → 同文案多控件时永远点第一个，
   使所有视觉门控题对任何模型都不可解（真机 D4 铁证：视觉模型给出 y=1127「下方绿色」，
   exec 却记录 `click_node(微信支付)` 点了上方红色）。修复=坐标优先 + 歧义拒绝执行 + 反馈闭环。
2. **sim 三套坐标空间不一致**（树 1080×1920 / 截图 720×1280 / click 入参假定 720×1280）：
   模型按树里坐标点击会偏移 1.5 倍、永远点空；旧落地逻辑恰好绕过它，两 bug 互相掩护。
   修复=公布 bounds 统一缩放到截图像素空间 + `click_node` 走同一换算。
   三空间一致性已实测（绿按钮中心像素 = #22AA55、click 命中 stage privacy→done）。

修复后复验：sim 视觉臂门控 **4/4**（修复前同题 task_timeout）、文本臂 **0/4**（符合理论预期）；
真机支付门控视觉 **2/2**、文本 **1/2**；`tests/test_parity.py` **16/16**。

### 本轮新增的平台级发现（重要）

**支付密码页防截屏**：真机 `uitest screenCap` 在支付弹窗出现后返回 99.6% 全黑图
（灰度均值 0.5），UI 树不受影响。已修复：`is_black_frame()`（均值≤8 或暗像素≥98%，
对 20 张真机截图判出 15 黑 5 正常、零误判）+ 自动降级为纯树观测 + `shot_black`
入轨迹 + `black_frames` 入 scorer。详见 `docs/blackscreen_finding.md`。

### 本轮新增的顶层交付

**支付功能健康判定书** `scripts/pay_verdict.py`：双侧结论（应用侧 NORMAL/PARTIAL/
DEGRADED/BROKEN；Agent 侧 胜任/部分胜任/不胜任）。真机实测四路 run 应用侧均判
**NORMAL（四渠道拉起 100%）**；Agent 侧 qwen3.7-max / qwen3.8-max 胜任、glm 部分胜任、
rules 不胜任。

## 回归入口

```powershell
python tests/test_parity.py        # 16 项离线回归（全 PASS）
python scripts/device_acceptance.py --hap-dir C:/benchdata/apps --tasks apps
python scripts/pay_verdict.py --run runs/pay_qwen37_dev    # 支付健康判定书
python scripts/pay_metrics.py --runs runs/pay_qwen37_dev,runs/pay_glm_dev
python scripts/report.py --runs runs
```