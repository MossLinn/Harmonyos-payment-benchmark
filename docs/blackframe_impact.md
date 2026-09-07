# 黑帧影响分层分析

黑帧判据：灰度均值 ≤8 或暗像素占比 ≥98%（`runner.is_black_frame`，真机标定）。

| run | agent | 任务 | 需输密码 | 截图数 | 黑帧数 | 结果 | 步数 |
|---|---|---|---|---|---|---|---|
| A_baseline | vlm | captcha-colortext | 否 | 13 | 8 | ✅ | 13 |
| A_baseline | vlm | code-login | 否 | 20 | 0 | ✅ | 20 |
| A_baseline | vlm | pay-normal-bankcard | 是 | 20 | 15 | ❌ steps_exhausted | 20 |
| D3_qwen38lowres_dev | vlm | pay-amount-mismatch | 否 | 2 | 0 | ✅ | 2 |
| D3_qwen38lowres_dev | vlm | pay-ime-clip | 是 | 6 | 2 | ✅ | 6 |
| D3_qwen38lowres_dev | vlm | pay-refund | 是 | 7 | 2 | ✅ | 7 |
| D3_qwen38lowres_dev | vlm | pay-timeout-fast | 是 | 5 | 2 | ✅ | 5 |
| D3_qwen38lowres_dev | vlm | pay-timeout-late | 否 | 3 | 0 | ✅ | 3 |

## 交叉汇总

| 分层 | 任务数 | 出现黑帧的任务 | 成功 | 成功率 |
|---|---|---|---|---|
| 需要输密码 | 4 | 4 | 3 | 75% |
| 不需要输密码 | 4 | 1 | 4 | 100% |
| 需要输密码 且 出现黑帧 | 4 | 4 | 3 | 75% |
| 需要输密码 且 无黑帧 | 0 | 0 | 0 | - |

## 按 agent 类型

| agent | 任务数 | 黑帧任务数 | 成功率 | 是否有组件树通道 |
|---|---|---|---|---|
| vlm | 8 | 5 | 88% | 是（树+图，黑帧自动降级） |
