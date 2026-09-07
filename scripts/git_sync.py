# -*- coding: utf-8 -*-
"""每日 Git 同步：add → commit（若有改动）→ push（若配了远程）。

- 保险丝：存在 STOP_GIT 则直接退出（与 STOP_BURN 独立的开关）。
- 找不到 PATH 里的 git 时，回退到 winget 装的 MinGit 固定路径。
- 日志写到 runs/git_sync.log（该目录已 .gitignore，不会被推上去）。
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOP = ROOT / "STOP_GIT"
LOG = ROOT / "runs" / "git_sync.log"
MIN_GIT = r"C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages\Git.MinGit_Microsoft.Winget.Source_8wekyb3d8bbwe\cmd\git.exe"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def git() -> str:
    p = shutil.which("git")
    if p:
        return p
    if os.path.exists(MIN_GIT):
        return MIN_GIT
    raise SystemExit("找不到 git（PATH 与 MinGit 固定路径均无）")


def run(g, *args, cwd):
    return subprocess.run([g, *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=180)


def main() -> int:
    if STOP.exists():
        _log("STOP_GIT 保险丝存在，跳过")
        return 0
    g = git()
    try:
        r = run(g, "rev-parse", "--is-inside-work-tree", cwd=ROOT)
        if r.returncode != 0:
            _log("非 git 仓库，跳过（尚未 git init）")
            return 0

        run(g, "add", "-A", cwd=ROOT)
        st = run(g, "status", "--porcelain", cwd=ROOT)
        if not st.stdout.strip():
            _log("无改动，跳过 commit")
        else:
            n = len(st.stdout.strip().splitlines())
            msg = f"chore: 每日自动同步 {datetime.now().strftime('%Y-%m-%d %H:%M')} ({n} 文件)"
            run(g, "commit", "-m", msg, cwd=ROOT)
            _log(f"commit: {msg}")

        rem = run(g, "remote", "get-url", "origin", cwd=ROOT)
        if rem.returncode != 0 or not rem.stdout.strip():
            _log("未配置 origin 远程，跳过 push（等配置 remote 后自动生效）")
            return 0
        pr = run(g, "push", "origin", "HEAD", cwd=ROOT)
        if pr.returncode == 0:
            _log("push 成功")
        else:
            _log(f"push 失败: {pr.stderr.strip()[:300]}")
        return 0
    except Exception as e:
        _log(f"异常: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())