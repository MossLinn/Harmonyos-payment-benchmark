# 支付功能健康判定书

生成时间：2026-09-06T14:29:21　判定口径：渠道拉起 milestone + 注入故障真值对比

## run: D2_rules_dev（agent=rules）

- **应用侧判定：PARTIAL（渠道均可拉起，但 1/2 个正常支付流程未走完）**
- **Agent 侧判定：部分胜任（故障识别 80%，但恢复/完成率仅 75%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 1/1 | 0 |
| bankcard | 1/1 | 0 |
| huawei | 0/0 | 1 |

- 注入故障总数：5　识别：4　识别率：80%
- 识别且恢复完成的任务：3

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-amount-mismatch | P-DIAG | mismatch | mismatch:✓ | wechat | ✅ | 3 |
| pay-refund | P-NORMAL | twice,refund | twice:✓,refund:✓ | bankcard | ✅ | 7 |
| pay-timeout-fast | P-NORMAL | timeout | timeout:✗ | alipay | ❌ steps_exhausted | 18 |
| pay-timeout-late | P-DIAG | timeout | timeout:✓ | wechat | ✅ | 4 |

## run: D2_qwen37_dev（agent=vlm）

- **应用侧判定：PARTIAL（渠道均可拉起，但 2/2 个正常支付流程未走完）**
- **Agent 侧判定：不胜任（故障识别仅 40%，任务成功率 50%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 1/1 | 0 |
| bankcard | 0/0 | 1 |
| huawei | 1/1 | 0 |

- 注入故障总数：5　识别：2　识别率：40%
- 识别且恢复完成的任务：2

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-amount-mismatch | P-DIAG | mismatch | mismatch:✓ | wechat | ✅ | 3 |
| pay-refund | P-NORMAL | twice,refund | twice:✗,refund:✗ | huawei | ❌ steps_exhausted | 22 |
| pay-timeout-fast | P-NORMAL | timeout | timeout:✗ | alipay | ❌ forbid_misclick | 17 |
| pay-timeout-late | P-DIAG | timeout | timeout:✓ | wechat | ✅ | 3 |

## run: pay_qwen37_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：胜任（故障识别 100%，任务成功率 100%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 2/2 | 0 |
| bankcard | 2/2 | 0 |
| huawei | 1/1 | 0 |

- 注入故障总数：4　识别：4　识别率：100%
- 识别且恢复完成的任务：4

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-allbroken | P-DIAG | allbroken | allbroken:✓ | - | ✅ | 2 |
| pay-blank-huawei | P-DIAG | blank | blank:✓ | wechat | ✅ | 7 |
| pay-broken-wechat | P-DIAG | broken | broken:✓ | alipay | ✅ | 7 |
| pay-dead-alipay | P-DIAG | dead | dead:✓ | bankcard | ✅ | 7 |
| pay-normal-alipay | P-NORMAL | - | - | alipay | ✅ | 5 |
| pay-normal-bankcard | P-NORMAL | - | - | bankcard | ✅ | 5 |
| pay-normal-huawei | P-NORMAL | - | - | huawei | ✅ | 5 |
| pay-normal-wechat | P-NORMAL | - | - | wechat | ✅ | 5 |
