# MA-v3 真机横评：全部多模态模型 × 新登录方式数据集

## 目的

用 Mobile-Agent-v3 作为 agent，在**真实鸿蒙模拟器**上横评网关**全部多模态模型**，
在你刚扩展的「Top100 App 登录方式」数据集上，测出各模型的端到端登录完成率。

## 模型分类（逐个实测：发图探测 + 单帧坐标标定）

网关 13 个模型里，**5 个纯文本、8 个多模态**：

| 模型 | 多模态 | 坐标制式 | `--coor-type` / 图通道 |
|---|---|---|---|
| doubao-seed-2.1-pro | ✅ | 0-1000 相对（[500,327]，离真值 3px） | qwen-vl / 768 |
| qwen3.8-max | ✅ | 0-1000 相对（[500,324]，**0 误差**） | qwen-vl / 768 |
| qwen3.8-flash | ✅ | 0-1000 相对（[500,325]，1px） | qwen-vl / 768 |
| qwen3.7-plus | ✅ | 标定漂移（[540,650]，非干净 abs/rel） | qwen-vl / 768（猜测） |
| MiniMax-M3 | ✅ | 标定漂移（[195,543]） | qwen-vl / 768（猜测） |
| hy3 | ✅ | 定位弱（[0,0]） | qwen-vl / 768（猜测） |
| glm-5.3-flash | ✅ | **绝对像素**（[620,868]，离 36px） | **abs / 全分辨率** |
| kimi-k2.7-code | ✅ | **绝对像素**（[540,900]，离 92px） | **abs / 全分辨率** |
| deepseek-v4-pro / flash | ❌ 文本 | — | 不参评 |
| glm-5.2 / glm-5.3 | ❌ 文本 | — | 不参评 |
| qwen3.7-max | ❌ 文本 | — | 不参评 |

> 坐标制式正确性关键点：**绝对制模型的坐标 = 发送图空间**，发送前降采样会导致落点错位，
> 因此 abs 模型必须发全分辨率（`--image-max-side 0`）；相对制模型的坐标由 MA-v3
> 按磁盘原图尺寸换算，768 降采样提速约 7 倍且不损精度（A 消融已证）。

## 测试集（16 题代表集，覆盖 9 类新登录方式）

一键登录×2、第三方授权×2（含诱导拒绝）、语音验证码×2、邮箱×2、扫码×2、生物识别×2
（含失败降级）、组合链×3（密码→短信 / 图验→短信 / 滑块→密码）、T5 左向滑块×1。
对照：规则基线同集真机（可解上界）。

## 运行

```powershell
$env:VOLC_API_KEY = "..."
E:\迅雷下载\mav3env\Scripts\python.exe scripts/run_mav3.py \
  --tasks _mav3_eval --out runs/MAV3EVAL_qwen38max \
  --config harness/config_mav3_qwen38max.json --coor-type qwen-vl --image-max-side 768 --timeout 240
```

结果自动汇总到 `docs/mav3_eval_board.md`。

## 结果

见 `docs/mav3_eval_board.md`（跑完自动生成）。