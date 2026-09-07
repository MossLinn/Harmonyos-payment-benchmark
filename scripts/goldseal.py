# -*- coding: utf-8 -*-
"""
金标准密封（golden seal）：评测集完整性公证。

- seal：对 apps/*/task.json 与 apps/*/variant.json 计算 SHA256 → docs/goldseal.json
- verify：重算并比对，任何差异（内容改动/增删任务）都失败退出

目的：模型训练数据与评测集严格隔离的硬保障；榜单发布时附 goldseal 快照，
他人可复核「跑分所用任务集未被事后修改」。

用法:
  python scripts/goldseal.py seal
  python scripts/goldseal.py verify
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEAL = ROOT / "docs" / "goldseal.json"


def scan() -> dict:
    out = {}
    for p in sorted(ROOT.glob("apps/*/task.json")) + sorted(ROOT.glob("apps/*/variant.json")):
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def seal():
    SEAL.write_text(json.dumps({"version": 1, "entries": scan()}, indent=2), encoding="utf-8")
    print(f"[goldseal] 已密封 {len(scan())} 个文件 → {SEAL.name}")


def verify():
    if not SEAL.exists():
        print("[goldseal] 无快照，先 seal")
        return 2
    stored = json.loads(SEAL.read_text(encoding="utf-8"))["entries"]
    current = scan()
    issues = []
    for k in sorted(set(stored) | set(current)):
        if k not in stored:
            issues.append(f"新增: {k}")
        elif k not in current:
            issues.append(f"删除: {k}")
        elif stored[k] != current[k]:
            issues.append(f"改动: {k}")
    if issues:
        print("[goldseal] 校验失败：")
        for i in issues:
            print("  -", i)
        return 1
    print(f"[goldseal] 校验通过：{len(current)} 个文件一致")
    return 0


if __name__ == "__main__":
    sys.exit(verify() if len(sys.argv) > 1 and sys.argv[1] == "verify" else seal())