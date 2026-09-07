# 示例任务（手写）

工厂生成的每个 App 都会自带 `task.json`；本目录放**手写任务**作为 schema 参考与扩展位。
任务 schema 与工厂变体 `task` 字段一致（见 `app-factory/variants/README.md`）。
把新任务 JSON 放进这里，配合 `--tasks` 目录批量运行。

## 推荐的工作流

1. 先设计变体（`app-factory/variants/*.json`），用 `gen_hap.py` 生成 App（自动带任务）；
2. 需要「同一 App 上的多任务」（普通任务/拒绝任务/超时任务…）时，
   在 `tasks/extras/<bundle>/task-*.json` 手写补充，与工厂任务一起跑；
3. 跑分用 `runner.py --tasks <含 task.json 的目录>`。