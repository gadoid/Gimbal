"""RS0 测试共享 fixture：git 仓库 + 构件分支 worktree（版本模型 3.6/B3）。

发版需要 git（3.3 祖先校验、B1 脏树前置），发版相关测试都在临时 git
仓库里跑；构件分支按 3.6 以孤儿分支创建（空树提交，不含源码历史）。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"  # git 空树常量
IDENT = ("-c", "user.name=tester", "-c", "user.email=t@t")

SYSTEM_MD = """---
type: system
system: fin
line: '{line}'{extra}
---

# fin

```gimbal:system
review: reviewed
name: fin-service
title: fin-service
version: 1.0.0
```
"""

ENDPOINT_MD = """---
id: fin.a.{name}
type: endpoints
system: fin
---

# {name}

```gimbal:endpoint
{review}id: fin.a.{name}
system: fin
service: fin-service
name: {name}{extra}
binding:
  protocol: http
  method: GET
  path: {path}
responses:
  '200': {{}}
```
"""


def git(cwd: Path, *args: str) -> str:
    r = subprocess.run(["git", "-C", str(cwd), *IDENT, *args],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, f"git {args} 失败: {r.stderr}"
    return r.stdout.strip()


def commit(cwd: Path, msg: str) -> str:
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", msg)
    return git(cwd, "rev-parse", "HEAD")


def init_artifacts_branch(repo: Path, worktree: Path) -> Path:
    """孤儿构件分支（plate/artifacts）+ worktree 检出（3.6/B3）。"""
    r = subprocess.run(
        ["git", "-C", str(repo), "commit-tree", EMPTY_TREE,
         "-m", "init: plate/artifacts"],
        capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    git(repo, "branch", "plate/artifacts", r.stdout.strip())
    git(repo, "worktree", "add", str(worktree), "plate/artifacts")
    return worktree


def write_system_md(fin: Path, line: str, extra: str = "") -> None:
    fin.joinpath("system.md").write_text(
        SYSTEM_MD.format(line=line, extra=extra),
        encoding="utf-8", newline="\n")


def write_endpoint(fin: Path, name: str, *, reviewed: bool = True,
                   path: str = "/a", extra: str = "") -> None:
    fin.joinpath("endpoints", f"fin.a.{name}.md").write_text(
        ENDPOINT_MD.format(
            name=name, path=path, extra=extra,
            review="review: reviewed\n" if reviewed else ""),
        encoding="utf-8", newline="\n")


def make_repo(tmp_path: Path, *, line: str = "1.0", extra: str = "",
              copy_types: bool = True) -> tuple[Path, Path, Path]:
    """临时 git 仓库 + 构件分支检出。返回 (repo, systems/fin, artifacts)。"""
    repo = tmp_path / "repo"
    fin = repo / "systems" / "fin"
    fin.joinpath("endpoints").mkdir(parents=True)
    if copy_types:
        shutil.copytree(REPO_ROOT / "types", repo / "types")
    write_system_md(fin, line, extra)
    write_endpoint(fin, "a", reviewed=True, path="/a")
    git(repo, "init", "-q")
    commit(repo, "init")
    art = init_artifacts_branch(repo, tmp_path / "artifacts")
    return repo, fin, art
