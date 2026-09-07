# 支付功能健康判定书

生成时间：2026-09-06T14:44:46　判定口径：渠道拉起 milestone + 注入故障真值对比

## run: D3_rules_dev（agent=rules）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：部分胜任（故障识别 100%，但恢复/完成率仅 80%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 2/2 | 0 |
| bankcard | 1/1 | 0 |
| huawei | 0/0 | 1 |

- 注入故障总数：5　识别：5　识别率：100%
- 识别且恢复完成的任务：4

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-amount-mismatch | P-DIAG | mismatch | mismatch:✓ | wechat | ✅ | 3 |
| pay-ime-clip | P-DIAG | - | - | alipay | ❌ steps_exhausted | 20 |
| pay-refund | P-NORMAL | twice,refund | twice:✓,refund:✓ | bankcard | ✅ | 7 |
| pay-timeout-fast | P-NORMAL | timeout | timeout:✓ | alipay | ✅ | 5 |
| pay-timeout-late | P-DIAG | timeout | timeout:✓ | wechat | ✅ | 4 |

## run: D3_qwen37_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：胜任（故障识别 100%，任务成功率 100%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 2/2 | 0 |
| bankcard | 0/0 | 1 |
| huawei | 1/1 | 0 |

- 注入故障总数：5　识别：5　识别率：100%
- 识别且恢复完成的任务：4

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-amount-mismatch | P-DIAG | mismatch | mismatch:✓ | wechat | ✅ | 3 |
| pay-ime-clip | P-DIAG | - | - | alipay | ✅ | 6 |
| pay-refund | P-NORMAL | twice,refund | twice:✓,refund:✓ | huawei | ✅ | 7 |
| pay-timeout-fast | P-NORMAL | timeout | timeout:✓ | alipay | ✅ | 5 |
| pay-timeout-late | P-DIAG | timeout | timeout:✓ | wechat | ✅ | 3 |

## run: D3_qwen38lowres_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：胜任（故障识别 100%，任务成功率 100%）**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 2/2 | 0 |
| alipay | 2/2 | 0 |
| bankcard | 0/0 | 1 |
| huawei | 1/1 | 0 |

- 注入故障总数：5　识别：5　识别率：100%
- 识别且恢复完成的任务：4

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-amount-mismatch | P-DIAG | mismatch | mismatch:✓ | wechat | ✅ | 2 |
| pay-ime-clip | P-DIAG | - | - | alipay | ✅ | 6 |
| pay-refund | P-NORMAL | twice,refund | twice:✓,refund:✓ | huawei | ✅ | 7 |
| pay-timeout-fast | P-NORMAL | timeout | timeout:✓ | alipay | ✅ | 5 |
| pay-timeout-late | P-DIAG | timeout | timeout:✓ | wechat | ✅ | 3 |

## run: D5_rules_dev（agent=rules）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：（本 run 无注入故障）任务成功率 100%**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 1/1 | 0 |
| alipay | 1/1 | 0 |
| bankcard | 0/0 | 0 |
| huawei | 0/0 | 0 |

- 本 run 无注入故障
- 识别且恢复完成的任务：0

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-agree-trap | P-DIAG | - | - | wechat | ✅ | 5 |
| pay-ime-clip | P-DIAG | - | - | alipay | ✅ | 6 |

## run: D5_qwen38lowres_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：（本 run 无注入故障）任务成功率 100%**

| 渠道 | 拉起命中/已尝试 | 未覆盖(弃权) |
|---|---|---|
| wechat | 1/1 | 0 |
| alipay | 1/1 | 0 |
| bankcard | 0/0 | 0 |
| huawei | 0/0 | 0 |

- 本 run 无注入故障
- 识别且恢复完成的任务：0

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-agree-trap | P-DIAG | - | - | wechat | ✅ | 5 |
| pay-ime-clip | P-DIAG | - | - | alipay | ✅ | 6 |
