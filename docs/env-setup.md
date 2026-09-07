# 环境搭建：模拟器 / 真机 / DevEco / hdc

本 Benchmark 的**执行层**有两种后端：
- **`--backend sim`（离线模拟器）**：在 `harness/sim_ui.py` 里用 Python 精确镜像全部
  模板页面状态机，无需任何鸿蒙设备即可端到端跑通，适合 prompt 消融、模型横向对比与
  大规模烧 token（瓶颈只在网关 QPS，不在设备吞吐）。首次跑视觉模式需 `pip install pillow`。
- **`--backend hdc`（真实设备）**：走 DevEco 工具链。当前研发机（外网 Windows）未装
  DevEco，以下安装步骤 + 「TODO-verify」清单用于首次接设备时校正。

## 1. 软件要求

| 组件 | 版本 | 用途 |
|---|---|---|
| DevEco Studio | 5.x（含 HarmonyOS NEXT SDK） | 构建 HAP、模拟器 |
| HarmonyOS NEXT SDK | API 12+ | 编译目标（工厂模板按 API 12 编写） |
| hdc | SDK toolchains 自带 | 设备驱动（list/install/uitest/snapshot） |
| Python | 3.10+ | 工厂生成 + Harness |
| 模拟器 | DevEco Emulator（Phone 模板，建议 1080×2340） | 执行环境 A |
| 真机 | 华为手机（HarmonyOS NEXT，开发者模式 + 签名） | 执行环境 B |

## 2. 安装步骤（Windows，已按本机 DevEco 6.0 实测校准）

| 校准点 | 事实 |
|---|---|
| 本机安装 | `G:\360downloads\DevEco Studio`（hdc 在 `sdk\default\openharmony\toolchains\hdc.exe`，hvigor 在 `tools\hvigor\bin\hvigorw.bat`） |
| hvigor-config.json5 | **必须含 `dependencies: {}`**（缺了直接 schema 校验失败） |
| 构建路径 | **必须纯 ASCII**（hvigor 拒绝中文路径，如 `E:\迅雷下载` 会报 00306003） |
| CLI 构建 | `gen_hap.py --build` 产出 `entry-default-unsigned.hap`（无签名）；安装到模拟器可能需要 IDE 自动签名或本地调试证书 |
| ArkTS 严格 N 条 | build() 内禁 `let`；TextInput 无 `.text()`；字面量常量比较（如 `'false'==='true'`）被判"无重叠"编译错；字符串内禁原始换行——**以上均已由生成器/模板消化** |

1. 安装 DevEco Studio（LTS 版本），首次启动下载 HarmonyOS NEXT SDK；
2. 把 `hdc` 加进 PATH：
   `DevEco Studio 安装目录\sdk\default\openharmony\toolchains\hdc.exe`
   （不同版本路径略有差异，`Get-Command hdc` 找不到时按实际 SDK 目录搜索）；
3. 模拟器：DevEco → Tools → Device Manager → 新建模拟器（Phone，HarmonyOS NEXT）；
4. 真机：设置 → 关于手机连点版本号开开发者模式 → 开启 USB 调试；运行签名 App
   需要华为开发者账号 + 调试证书（DevEco 自动签名）。

## 3. hdc 常用命令（执行层全部基于这些）

```powershell
hdc list targets                     # 模拟器为 127.0.0.1:5555
hdc -t <sn> install <hap>            # 路径须反斜杠（正斜杠会被拼进 CWD）；模拟器 unsigned/signed 均可装
hdc -t <sn> shell aa start -a EntryAbility -b com.bench.xxx
hdc -t <sn> shell uitest dumpLayout -p /data/local/tmp/t.json [-b <bundle>]   # 输出落盘不打印 stdout；多窗口 JSON 拼接体
hdc -t <sn> file recv /data/local/tmp/t.json .\_x.json
hdc -t <sn> shell uitest screenCap -p /data/local/tmp/s.png                   # 截图（无 snapshot_display）
hdc -t <sn> shell uitest uiInput click <x> <y>
hdc -t <sn> shell uitest uiInput text <text>       # 输入到已聚焦组件（先 click 聚焦）
hdc -t <sn> shell uitest uiInput swipe x1 y1 x2 y2
hdc -t <sn> shell uitest uiInput keyEvent Back/Home/Power
```

> ✅ TODO-verify 已全部按 hdc 3.2.0f 实测关闭：栏位语义 = attributes.{text→hint→
> originalText/description, type, id/key, bounds:"[l,t][r,b]", clickable/checked/enabled:bool 字符串}；
> 勾选状态在 checked 属性；冷启动设置 settle 5s + dumpLayout -b 过滤目标 bundle。

## 4. 并发与吞吐（token 消化能力的关键）

| 资源 | 单模拟器 | 建议配置 |
|---|---|---|
| 模拟器（本机） | 取决于内存，8G/台 起 | 外网机器（A100/4090 不影响模拟器，吃 CPU/内存）可起 4~8 台 |
| 云真机/内部真机群 | 1 台 = 1 任务流 | 目标 20 台 → 日吞吐 ~1200~2000 任务 |
| 单任务墙钟 | 30~90s（30 步 × VLM 1.5~3s） | 20 并发 ≈ 日 1.5万 步任务 |

策略：**设备只做执行与截图，VLM 决策全部走外网网关**；设备不足时用
「UI 树文本模式」离线回放录制数据补 token（Harness 支持 no-device 回放模式，M2 实现）。

## 5. 常见坑（提前打钩）

- [ ] 模拟器锁屏/熄屏 → 先 `keyEvent` 唤醒；建议模拟器设「不熄屏」；
- [ ] 首次弹窗（隐私/更新）会阻碍 `aa start` 后的自动流 → 由任务本身处理即可，属于考题；
- [ ] 真机需要关闭「清理后台」对被测 App 的干扰；建议飞行模式 + 固定测试码；
- [ ] `dumpLayout` 返回树极大（几万节点）→ Harness 已内置截断/关键字裁剪（见 judge.py）。