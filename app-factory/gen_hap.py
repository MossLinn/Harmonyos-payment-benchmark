#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
App 工厂生成器：variants/*.json → 完整鸿蒙 (HarmonyOS NEXT Stage 模型, API 12) 工程
→ hvigor 构建 HAP → (可选) hdc 安装并拉起。

用法:
  python gen_hap.py --variant variants/code-login.json --out apps/code_login
  python gen_hap.py --variant variants/pwd-captcha.json --out apps/pwd_captcha --build
  python gen_hap.py --variant variants/privacy-full.json --out apps/privacy_full --build --install

工程骨架按 HarmonyOS NEXT (API 12) Stage 模型生成。不同 DevEco Studio/SDK 小版本
可能要求微调 hvigor-config.json5 / build-profile.json5 / module.json5 字段 ——
已用 “TODO-verify” 注释标出需要对照你本机 DevEco 新工程模板校正的位置。
"""
import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 1x1 透明 PNG（系统图标占位，避免二进制资源缺失）
APP_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)

SLOT_RE = re.compile(r"\{\{(\w+)\}\}")

ENTRY_ABILITY_ETS = """import { AbilityConstant, UIAbility, Want } from '@kit.AbilityKit';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { window } from '@kit.ArkUI';

export default class EntryAbility extends UIAbility {
  onCreate(want: Want, launchParam: AbilityConstant.LaunchParam): void {
    hilog.info(0x0000, 'bench', 'EntryAbility onCreate');
  }

  onWindowStageCreate(windowStage: window.WindowStage): void {
    windowStage.loadContent('pages/Index', (err) => {
      if (err.code) {
        hilog.error(0x0000, 'bench', 'loadContent failed: %s', JSON.stringify(err));
        return;
      }
    });
  }

  onWindowStageDestroy(): void {}
  onForeground(): void {}
  onBackground(): void {}
  onDestroy(): void {}
}
"""

# {(relative path): content, ...}；占位符 {bundle} {app_name}
def scaffold(bundle: str, app_name: str, page_ets: str, app_icon_png: bytes) -> dict:
    return {
        "build-profile.json5": (
            "{\n"
            "  \"app\": {\n"
            "    \"signingConfigs\": [],\n"
            "    \"products\": [\n"
            "      {\n"
            "        \"name\": \"default\",\n"
            "        \"signingConfig\": \"default\",\n"
            '        "compatibleSdkVersion": "5.0.0(12)",\n'  # TODO-verify：对照本机 DevEco 模板
            '        "runtimeOS": "HarmonyOS"\n'
            "      }\n"
            "    ]\n"
            "  },\n"
            "  \"modules\": [\n"
            "    {\n"
            '      "name": "entry",\n'
            '      "srcPath": "./entry",\n'
            "      \"targets\": [\n"
            "        {\n"
            '          "name": "default",\n'
            '          "applyToProducts": ["default"]\n'
            "        }\n"
            "      ]\n"
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        "hvigorfile.ts": (
            "import { appTasks } from '@ohos/hvigor-ohos-plugin';\n"
            "export default {\n"
            "  system: appTasks,\n"
            "  plugins: []\n"
            "}\n"
        ),
        "hvigor/hvigor-config.json5": (
            '{\n  "modelVersion": "5.0.0",\n  "dependencies": {}\n}\n'  # 经 hvigor 6.x 实测：dependencies 为必填
        ),
        "oh-package.json5": (
            '{\n  "modelVersion": "5.0.0",\n  "description": "bench generated app",\n'
            '  "dependencies": {}\n}\n'
        ),
        "AppScope/app.json5": (
            "{\n"
            "  \"app\": {\n"
            f'    "bundleName": "{bundle}",\n'
            '    "vendor": "bench",\n'
            '    "versionCode": 1000000,\n'
            '    "versionName": "1.0.0",\n'
            '    "icon": "$media:app_icon",\n'
            '    "label": "$string:app_name"\n'
            "  }\n"
            "}\n"
        ),
        "AppScope/resources/base/element/string.json": (
            '{\n  "string": [\n    {\n      "name": "app_name",\n'
            f'      "value": "{app_name}"\n'
            "    }\n  ]\n}\n"
        ),
        "AppScope/resources/base/media/app_icon.png": app_icon_png,
        "entry/build-profile.json5": (
            "{\n"
            '  "apiType": "stageMode",\n'
            '  "buildOption": {},\n'  # TODO-verify
            "  \"targets\": [\n"
            "    {\n"
            '      "name": "default",\n'
            '      "runtimeOS": "HarmonyOS"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        "entry/hvigorfile.ts": (
            "import { hapTasks } from '@ohos/hvigor-ohos-plugin';\n"
            "export default {\n"
            "  system: hapTasks,\n"
            "  plugins: []\n"
            "}\n"
        ),
        "entry/oh-package.json5": (
            '{\n  "name": "entry",\n  "version": "1.0.0",\n  "description": "",\n'
            '  "main": "",\n  "author": "",\n  "license": "",\n  "dependencies": {}\n}\n'
        ),
        "entry/src/main/module.json5": (
            "{\n"
            "  \"module\": {\n"
            '    "name": "entry",\n'
            '    "type": "entry",\n'
            '    "description": "$string:module_desc",\n'
            '    "mainElement": "EntryAbility",\n'
            '    "deviceTypes": ["phone"],\n'
            '    "deliveryWithInstall": true,\n'
            '    "installationFree": false,\n'
            '    "pages": "$profile:main_pages",\n'
            "    \"abilities\": [\n"
            "      {\n"
            '        "name": "EntryAbility",\n'
            '        "srcEntry": "./ets/entryability/EntryAbility.ets",\n'
            '        "description": "$string:EntryAbility_desc",\n'
            '        "icon": "$media:app_icon",\n'
            '        "label": "$string:EntryAbility_label",\n'
            '        "startWindowIcon": "$media:app_icon",\n'
            '        "startWindowBackground": "$color:start_window_background",\n'
            '        "exported": true,\n'
            "        \"skills\": [\n"
            "          {\n"
            '            "entities": ["entity.system.home"],\n'
            '            "actions": ["action.system.home"]\n'
            "          }\n"
            "        ]\n"
            "      }\n"
            "    ]\n"
            "  }\n"
            "}\n"
        ),
        "entry/src/main/resources/base/element/string.json": (
            "{\n"
            "  \"string\": [\n"
            "    {\"name\": \"module_desc\", \"value\": \"bench module\"},\n"
            '    {\n      "name": "EntryAbility_desc",\n      "value": "bench ability"\n    },\n'
            "    {\n"
            '      "name": "EntryAbility_label",\n'
            f'      "value": "{app_name}"\n'
            "    }\n"
            "  ]\n"
            "}\n"
        ),
        "entry/src/main/resources/base/element/color.json": (
            '{\n  "color": [\n    {\n      "name": "start_window_background",\n'
            '      "value": "#FFFFFF"\n    }\n  ]\n}\n'
        ),
        "entry/src/main/resources/base/media/app_icon.png": app_icon_png,
        "entry/src/main/resources/base/profile/main_pages.json": '{\n  "src": ["pages/Index"]\n}\n',
        "entry/src/main/ets/entryability/EntryAbility.ets": ENTRY_ABILITY_ETS,
        "entry/src/main/ets/pages/Index.ets": page_ets,
    }


def _escape_ets(value: str) -> str:
    """把槽位值转义成可放进 ArkTS 单引号字符串字面量的形式（\n 保持转义序列，禁止原始换行）。"""
    return (value.replace("\\", "\\\\").replace("\r", "")
            .replace("\n", "\\n").replace("'", "\\'"))


def render_template(template_path: Path, slots: dict) -> str:
    text = template_path.read_text(encoding="utf-8")
    needed = {m.group(1) for m in SLOT_RE.finditer(text)}
    missing = needed - set(slots.keys())
    if missing:
        raise SystemExit(f"槽位缺失（模板 {template_path.name}）: {sorted(missing)}")
    for key in needed:
        text = text.replace("{{" + key + "}}", _escape_ets(str(slots[key])))
    leftover = SLOT_RE.findall(text)
    if leftover:
        raise SystemExit(f"模板替换后仍有未处理槽位: {leftover}")
    return text


def find_hvigorw() -> str | None:
    cands = []
    env = os.environ.get("DEVECO_SDK_HOME")
    if env:
        cands.append(Path(env).parent / "tools" / "hvigor" / "bin" / "hvigorw.bat")
    home = os.environ.get("DEVECO_HOME")
    if home:
        cands.append(Path(home) / "tools" / "hvigor" / "bin" / "hvigorw.bat")
    for pf in ["C:/Program Files/Huawei", "D:/Program Files/Huawei",
               "G:/360downloads/DevEco Studio", "C:/360downloads/DevEco Studio",
               "G:/DevEco Studio"]:
        root = Path(pf)
        if root.exists():
            cands.append(root / "tools" / "hvigor" / "bin" / "hvigorw.bat")
            cands.extend(root.glob("DevEco Studio*/tools/hvigor/bin/hvigorw.bat"))
    for c in cands:
        if c.exists():
            return str(c)
    return None


def find_hdc() -> str | None:
    sh = shutil.which("hdc")
    if sh:
        return sh
    for pf in ["C:/Program Files/Huawei", "D:/Program Files/Huawei"]:
        root = Path(pf)
        if root.exists():
            hits = list(root.glob("DevEco Studio*/sdk/**/toolchains/hdc.exe"))
            if hits:
                return str(hits[0])
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="生成鸿蒙基准 App 工程（可选构建/安装）")
    ap.add_argument("--variant", required=True, help="variants/*.json 路径")
    ap.add_argument("--out", required=True, help="输出目录（将创建 <out>/<task_id>/）")
    ap.add_argument("--build", action="store_true", help="尝试调用 hvigor 构建 HAP")
    ap.add_argument("--install", action="store_true", help="构建后 hdc 安装并拉起首台设备")
    args = ap.parse_args()

    variant_path = Path(args.variant).resolve()
    variant = json.loads(variant_path.read_text(encoding="utf-8"))
    template_name = variant.get("template")
    template_path = HERE / "templates" / template_name
    if not template_path.exists():
        raise SystemExit(f"模板不存在: {template_path}")

    task = variant["task"]
    task_id = task["id"]
    project_dir = Path(args.out).resolve() / task_id
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True)

    slots = dict(variant.get("slots", {}))
    page_ets = render_template(template_path, slots)
    files = scaffold(variant["bundle"], variant["app_name"], page_ets, base64.b64decode(APP_ICON_B64))
    for rel, content in files.items():
        p = project_dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            p.write_bytes(content)
        else:
            p.write_text(content, encoding="utf-8", newline="\n")

    (project_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    (project_dir / "variant.json").write_text(json.dumps(variant, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[gen] 工程已生成: {project_dir}")
    print(f"[gen] 任务(id={task_id}, tier={task.get('tier')}, category={task.get('category')})")

    if not (args.build or args.install):
        print("[gen] 未构建。加 --build 尝试 hvigor 构建；或直接在 DevEco Studio 打开该目录构建。")
        return

    hvigor = find_hvigorw()
    if not hvigor:
        print("[build] 未找到 DevEco/hvigor。请安装 DevEco Studio 或在 DEVECO_SDK_HOME 环境变量指向 SDK 后重试；")
        print("[build] 或手动在 DevEco Studio 打开工程构建（自动签名）。")
        return
    print(f"[build] 使用 hvigor: {hvigor}")
    cmd = [hvigor, "assembleHap", "--mode", "module", "-p", "product=default", "assembleHap", "--no-daemon"]
    r = subprocess.run(cmd, cwd=str(project_dir), capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(r.stdout[-2000:] if r.stdout else "")
    print(r.stderr[-2000:] if r.stderr else "")
    if r.returncode != 0:
        raise SystemExit(f"[build] 构建失败 (exit {r.returncode})，按 TODO-verify 清单校正工程骨架字段。")

    if args.install:
        hdc = find_hdc()
        if not hdc:
            print("[install] 未找到 hdc，跳过安装。")
            return
        haps = sorted(project_dir.rglob("*.hap"))
        if not haps:
            print("[install] 未找到 HAP 产物。")
            return
        hap = str(haps[-1])
        subprocess.run([hdc, "install", hap], check=False)
        subprocess.run([hdc, "shell", "aa", "start", "-a", task["ability"], "-b", task["app_bundle"]], check=False)
        print(f"[install] 已安装并拉起 {task['app_bundle']} ({hap})")


if __name__ == "__main__":
    main()