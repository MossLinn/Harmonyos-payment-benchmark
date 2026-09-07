# MA-v3 真机横评结果（8 个多模态模型 × 新登录方式）

> 由 `scripts/mav3_board.py` 聚合；未列全 16 题的模型仍在跑。

| 模型 | SR | 步均 | tokens/题 | 状态 |
|---|---|---|---|---|
| 规则基线(真机) | 11/16 | 7.2 | 0 | 完成 |
| qwen38max | 2/16 | 9.4 | 126,949 | 完成 |
| qwen38flash | 10/16 | 7.5 | 68,786 | 完成 |
| qwen37plus | 8/16 | 7.1 | 47,584 | 完成 |
| minimax | 3/16 | 12.6 | 136,677 | 完成 |
| hy3 | 0/16 | 10.2 | 164,106 | 完成 |
| doubao | 7/16 | 5.3 | 71,390 | 完成 |
| glm53flash | 6/16 | 5.5 | 158,405 | 完成 |
| kimi | 1/16 | 6.1 | 205,670 | 完成 |

## 失败原因分布（按模型）

| 模型 | fail_reason | 计数 |
|---|---|---|
| qwen38max | mav3_error | 13 |
| minimax | steps_exhausted | 11 |
| hy3 | goal_not_reached | 8 |
| glm53flash | mav3_error | 8 |
| kimi | mav3_error | 8 |
| doubao | mav3_error | 7 |
| qwen38flash | steps_exhausted | 6 |
| kimi | steps_exhausted | 6 |
| qwen37plus | steps_exhausted | 5 |
| hy3 | steps_exhausted | 5 |
| hy3 | mav3_error | 3 |
| qwen37plus | mav3_error | 2 |
| glm53flash | goal_not_reached | 2 |
| qwen38max | goal_not_reached | 1 |
| qwen37plus | goal_not_reached | 1 |
| minimax | mav3_error | 1 |
| minimax | goal_not_reached | 1 |
| doubao | goal_not_reached | 1 |
| doubao | steps_exhausted | 1 |
| kimi | goal_not_reached | 1 |
