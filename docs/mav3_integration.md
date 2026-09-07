# Harness 接入 Mobile-Agent-v3（官方 X-PLUG 实现）

按用户要求：**agent 换成 Mobile-Agent-v3**，本仓库只保留 benchmark 的职责
（任务集 / 判定 / 计分 / 记账 / 报表），不再自己当"解题者"。

## 为什么能直接接：MA-v3 官方就支持鸿蒙

`Mobile-Agent-v3/README_zh.md` 原文：「❗目前仅安卓和**鸿蒙**系统支持工具调试」，
并提供 `mobile_v3/utils/harmonyos_controller.py` + `--hdc_path` 入口；模型侧用的是
**标准 OpenAI SDK**（`api_key` / `base_url` / `model`），因此可直接指向火山网关。

- 仓库：`X-PLUG/MobileAgent`（含 v1 / v2 / **v3** / v3.5 / PC-Agent / UI-S1 / GUI-Critic-R1）
- 本机副本：`E:\迅雷下载\MobileAgent-src\MobileAgent-main\`
  （`github.com:443` 不通但 `codeload.github.com` 通 → 整包 zip 下载 371 MB，无需 git；
  本机未安装 git）
- 技术报告：arXiv:2508.15144《Mobile-Agent-v3: Foundamental Agents for GUI Automation》

## 架构（每个 step 四次模型调用）

```
Manager（规划：completed_subgoal + plan；plan=="Finished" 即结束）
  → Executor/Operator（输出动作 JSON：click/swipe/type/system_button/answer）
  → ActionReflector（对比动作前后两张截图 → outcome A/B/C + error_description）
  → Notetaker（可选，outcome==A 时记录 important_notes）
```

MA-v3 是**纯视觉 agent**：全程只用截图，不读组件树。判定仍由本仓库的 Judge
基于 UI 树 + milestone 完成，两者互不干扰。

## 环境（本机实测）

| 项 | 处理 |
|---|---|
| Python 依赖 | 独立 venv：`E:\迅雷下载\mav3env`（openai 3.8.0 / qwen_vl_utils 0.0.14 / numpy 2.5.2 / pillow / pydantic / av） |
| 系统 Python 装不上 | `pip install` 写 `C:\python312\Scripts\*.exe` 反复 `WinError 2`（f2py.exe / normalizer.exe，疑似杀软拦截）→ 改用 venv 绕开 |
| torch | `qwen_vl_utils` 导入即 `import torch`，但 MA-v3 只用它一个 `smart_resize`；本机无 GPU，故用 `harness/mav3_shim.py` **按 0.0.14 源码逐字照抄**该函数并注册为同名模块，省下数百 MB torch/torchvision |
| `qwen_agent` | 仅 `function_call_mobile_answer.py` 需要，真机路径不 import → 不装 |

## 接入方式：不改官方代码，两处运行时注入

`scripts/run_mav3.py` 在导入 MA-v3 之前替换两个类：

1. **`GUIOwlWrapper` 子类**
   - 官方 `OpenAI(timeout=30)`，而本网关视觉调用实测 20~60s → 放宽为 `--timeout`（默认 180s）；
   - 官方不把 token 用量返回给调用方 → 从 `predict_mm` 返回的 completion 对象里取 `.usage`，
     逐次记账（实测可取：如单题 `prompt=15023, completion=2497, calls=4`）。
2. **`HarmonyOSController` 子类**
   - 在 `tap / slide / type / back / home` 每个动作之后：拉取 UI 树 → 用本仓库 `Judge`
     增量判定 `success / forbid / milestones` → 写出与 `runner.py` **同构的 `trace.jsonl`**；
   - `get_screenshot` 顺带把 MA-v3 自己截的图归档到本 run 的 `shots/`。

产物目录与 `runner.py` 一致（`result.json` + `trace.jsonl` + `results.json`），
因此 `scorer.py` / `pay_verdict.py` / `pay_metrics.py` / `report.py` **全部可直接复用**。

## 两项必须校准的事实（实测得出）

### ① 坐标制式：qwen3.8-max 用 0-1000 相对坐标 → 必须 `--coor_type qwen-vl`

同一帧截图（1256×2760）交叉验证：

| 来源 | 值 |
|---|---|
| 组件树里「银行卡支付」按钮真实中心 | (628, 896) |
| 归一化到 1000 制 | (500, 325) |
| **模型输出** | **(500, 324)** |
| 反算绝对像素 | (628, 894) |

误差 2px。若误用默认 `abs`，所有点击会系统性落到左上角区域（500,324 被当成绝对像素）。

### ② 官方 HarmonyOSController × 本机 hdc 3.2.0f：逐原语全通

| 原语 | 命令 | 实测 |
|---|---|---|
| `get_screenshot` | `shell uitest screenCap -p` + `file recv` | ✅ 1256×2760、138 KB |
| `tap` | `shell uitest uiInput click x y` | ✅ Checkbox `checked: False→True` |
| `type` | 逐字符 `shell uitest uiInput inputText 1 1 <char>` | ✅ 密码框显示 `******`（本以为这种写法在 3.2.0f 上不通，实测可用） |
| `slide` | `shell uitest uiInput swipe x1 y1 x2 y2 500` | ✅（同族命令已校准） |
| `back` / `home` | `shell uitest uiInput keyEvent Back/Home` | ✅ 弹窗关闭（13→11 节点） |

设备目标通过字符串拼接注入：`--hdc_path '"G:\...\hdc.exe" -t 127.0.0.1:5555'`
（官方实现是 `hdc_path + " shell ..."` 且 `shell=True`，因此可行）。

## 图像通道：官方全分辨率 vs 768 降采样（同题同模型同设备实测）

MA-v3 官方 `image_to_base64` 用 `smart_resize(MAX_PIXELS=10035200)`，本机 1256×2760
（3.47M 像素）**不会被缩小**，反而被对齐放大到 1260×2772 后以 PNG 发送（108 KB/帧）。
实测代价（`pay-broken-wechat` 前 6 步 vs `pay-agree-trap` 前 3 步）：

| 指标 | 官方全分辨率 | `--image-max-side 768` |
|---|---|---|
| Manager 调用 | 39s | **11s** |
| Executor 调用 | **187s** | **6s** |
| Reflector 调用 | 19s | **16s** |
| 单步合计 | ~4 分钟 | **~33 秒（≈7×）** |
| 发送图尺寸/体积 | 1260×2772 PNG，108 KB | 336×756 JPEG q82，**13 KB（11.9%）** |
| 每步日志体积 | manager 156 KB / reflector 310 KB | **18 KB / 31 KB（≈1/9）** |
| 长尾风险 | Executor >180s 触发官方"sleep 20s × 最多 10 次"重试风暴，重复烧 token | 未观察到 |

**为什么降采样不损精度**：qwen3.8-max 输出 0-1000 **相对坐标**，且 MA-v3 的坐标换算读取的是
**磁盘上的原图尺寸**（`width, height = Image.open(local_image_dir).size`），
发送前缩放只影响模型看到的像素密度，不改变落点换算：
相对 (500,324) → 绝对 (628,894)，与原图路径完全一致（交叉验证误差 2px）。

因此 `--image-max-side 768` 是**默认推荐档**（与本仓库 A 消融结论一致：SR 不降、tokens −80%）；
`--image-max-side 0` 保留为"完全官方行为"对照档。两者的实际设置都写进 `result.json` 的
`image_mode` 字段以便审计。

## 运行

```powershell
$env:VOLC_API_KEY = "<网关 key>"
# 单题打通
E:\迅雷下载\mav3env\Scripts\python.exe scripts/run_mav3.py `
  --tasks _mav3_smoke --out runs/MAV3_smoke --config harness/config_mav3.json --max-step 8

# 支付全套件（18 题）
E:\迅雷下载\mav3env\Scripts\python.exe scripts/run_mav3.py `
  --tasks _pay18 --out runs/MAV3_pay --config harness/config_mav3.json

# 出判定书 / 指标（与既有工具完全通用）
python scripts/pay_verdict.py  --run runs/MAV3_pay --out docs/pay_verdict_mav3.md
python scripts/pay_metrics.py  --runs runs/MAV3_pay
python harness/scorer.py       --run runs/MAV3_pay --config harness/config_mav3.json
```

常用参数：`--coor-type {qwen-vl,abs}`、`--max-step N`（默认取任务 `step_budget`）、
`--notetaker`（开启 Notetaker 记忆体）、`--only id1,id2`、`--timeout`、`--settle`。

## 已验证的首个结果

| 任务 | 结果 | 步数 | 墙钟 | tokens（4 次调用） |
|---|---|---|---|---|
| privacy-full（单隐私弹窗） | ✅ success | 1 | 76.9s | 17,520（prompt 15,023 / completion 2,497） |

MA-v3 自身日志（Manager/Executor/Reflector 的完整 prompt 与响应）保存在
`runs/<out>/<task_id>/mav3_logs/<时间戳>_<指令前10字>/step_N/*.json`，可逐步审计。
