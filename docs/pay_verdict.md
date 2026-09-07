# 支付功能健康判定书

生成时间：2026-09-06T13:05:04　判定口径：渠道拉起 milestone + 注入故障真值对比

## run: pay_qwen37_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：胜任（故障识别 100%，任务成功率 100%）**

| 渠道 | 拉起命中/应命中 |
|---|---|
| wechat | 2/2 |
| alipay | 2/2 |
| bankcard | 2/2 |
| huawei | 1/1 |

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

## run: pay_qwen38_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：胜任（故障识别 100%，任务成功率 100%）**

| 渠道 | 拉起命中/应命中 |
|---|---|
| wechat | 1/1 |
| alipay | 1/1 |
| bankcard | 1/1 |
| huawei | 1/1 |

- 注入故障总数：2　识别：2　识别率：100%
- 识别且恢复完成的任务：2

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-broken-wechat | P-DIAG | broken | broken:✓ | alipay | ✅ | 7 |
| pay-dead-alipay | P-DIAG | dead | dead:✓ | bankcard | ✅ | 7 |
| pay-normal-huawei | P-NORMAL | - | - | huawei | ✅ | 5 |
| pay-normal-wechat | P-NORMAL | - | - | wechat | ✅ | 5 |

## run: pay_glm_dev（agent=vlm）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：部分胜任（故障识别 100%，但恢复/完成率仅 75%）**

| 渠道 | 拉起命中/应命中 |
|---|---|
| wechat | 2/2 |
| alipay | 2/2 |
| bankcard | 2/2 |
| huawei | 1/1 |

- 注入故障总数：4　识别：4　识别率：100%
- 识别且恢复完成的任务：2

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-allbroken | P-DIAG | allbroken | allbroken:✓ | - | ✅ | 3 |
| pay-blank-huawei | P-DIAG | blank | blank:✓ | wechat | ❌ steps_exhausted | 25 |
| pay-broken-wechat | P-DIAG | broken | broken:✓ | alipay | ✅ | 7 |
| pay-dead-alipay | P-DIAG | dead | dead:✓ | bankcard | ❌ steps_exhausted | 25 |
| pay-normal-alipay | P-NORMAL | - | - | alipay | ✅ | 5 |
| pay-normal-bankcard | P-NORMAL | - | - | bankcard | ✅ | 5 |
| pay-normal-huawei | P-NORMAL | - | - | huawei | ✅ | 20 |
| pay-normal-wechat | P-NORMAL | - | - | wechat | ✅ | 5 |

## run: pay_rules_dev（agent=rules）

- **应用侧判定：NORMAL（四渠道均可拉起支付弹窗，正常支付流程全部走通）**
- **Agent 侧判定：不胜任（故障识别仅 50%，任务成功率 88%）**

| 渠道 | 拉起命中/应命中 |
|---|---|
| wechat | 2/2 |
| alipay | 2/2 |
| bankcard | 2/2 |
| huawei | 1/1 |

- 注入故障总数：4　识别：2　识别率：50%
- 识别且恢复完成的任务：2

| 任务 | 类型 | 注入故障 | 识别 | 拉起渠道 | 结果 | 步数 |
|---|---|---|---|---|---|---|
| pay-allbroken | P-DIAG | allbroken | allbroken:✗ | - | ❌ steps_exhausted | 20 |
| pay-blank-huawei | P-DIAG | blank | blank:✗ | wechat | ✅ | 5 |
| pay-broken-wechat | P-DIAG | broken | broken:✓ | alipay | ✅ | 7 |
| pay-dead-alipay | P-DIAG | dead | dead:✓ | bankcard | ✅ | 7 |
| pay-normal-alipay | P-NORMAL | - | - | alipay | ✅ | 5 |
| pay-normal-bankcard | P-NORMAL | - | - | bankcard | ✅ | 5 |
| pay-normal-huawei | P-NORMAL | - | - | huawei | ✅ | 5 |
| pay-normal-wechat | P-NORMAL | - | - | wechat | ✅ | 5 |
