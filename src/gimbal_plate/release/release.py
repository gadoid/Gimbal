"""release 冻结与发版（版本模型 v1.4 3.1–3.6；开发计划 T1.6 主体）。

与 S1 版（YYYY.MM.N、只收 reviewed、零 finding 才能发版）的差异全部按
版本模型 v1.4 落地：

- **冻结范围（3.1）**：通过机械校验的**全部**块（含草稿）逐对象记录
  评审状态；``gimbal:system``（服务声明）随修订冻结，``gimbal:defaults``
  不冻结。成熟度由评审状态计算，不由签发人选择。
- **发布闸门分级（3.2，D-4）**：F0 / F3 / F5 等树级与唯一性检查一律
  阻塞；其余 finding（含 C 类一致性）按 ``[line, end_line]`` 区间映射到
  块——只落在草稿块内降为告警（写入 manifest ``warnings``），涉及任一
  已评审对象即阻塞。
- **引用闭包（3.2）**：已评审对象只能引用已评审对象；草稿之间可互引
  （草稿引用的 common 词条随冻结，但不作闸门）。
- **修订沿 git 祖先关系前进（3.3）**：脏树拒绝（``systems/``、``types/``
  无未提交变更），``source_commit`` = 执行时 HEAD，上一修订的
  ``source_commit`` 必须是 HEAD 的祖先；新版本线首修订要求
  ``predecessor_line`` 已有修订（首条除外）。
- **编号（3.4）**：``<line>#<n>``，布局 ``<系统>/lines/<line>/<n>/``。
- **manifest（3.5）**：``line_scheme`` / ``line_service`` 入 manifest
  （plate 服务只见构件，``/lines`` 承诺返回 scheme）；``corrections``
  = 与上一修订相比 ``shape_hash`` 变化的接口；对象文件统一信封
  ``{"type", "data"}``（F1 修复），call 投影入对象池（manifest 记 hash）。
- **构件分支（3.6，R18/B1–B4）**：构件根唯一来源 = ``PLATE_ARTIFACTS_PATH``
  （指向构件分支检出；未配置即报错，无推导无缺省）；发版产生的唯一
  提交是构件分支上的构件提交（提交信息 ``<系统>@<line>#<n>``），
  artifacts 根若非 git 工作树（本地演练目录）则只写盘不提交。

``m2_hash`` / ``m2_generation``（用例侧，只作溯源）随 M2 方案步骤 2
（``gen_m2.py`` / ``export_m2``）接线后写入，此处暂缺。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gimbal_plate.dialect import (
    EndpointSpec,
    Statement,
    Term,
    object_hash,
    shape_hash,
)
from gimbal_plate.dialect.validation import (
    Finding,
    ValidationReport,
    collect_system_tree,
    load_types,
    validate_system_tree,
)

DIALECT_VERSION = "1"   # 方言版本(manifest 记录,修订四)
M2_VERSION = "2"        # 知识侧 M2 代际(水合门;用例侧 m2_hash 随 T1.3 接线)

# 树级检查:不论评审状态一律阻塞(3.2 分级规则)。F0=方言错误、F3=唯一性、
# F5=版本线声明(入口 frontmatter,不属于任何块)。
_TREE_LEVEL_RULES = {"F0", "F3", "F5"}


class ReleaseResult:
    def __init__(self, *, success: bool, line: str | None = None,
                 revision: str | None = None, message: str = "",
                 manifest: dict[str, Any] | None = None,
                 report: ValidationReport | None = None) -> None:
        self.success = success
        self.line = line
        self.revision = revision          # "<line>#<n>"
        self.message = message
        self.manifest = manifest
        self.report = report

    def __repr__(self) -> str:  # pragma: no cover - 调试便利
        return (f"ReleaseResult(success={self.success}, "
                f"revision={self.revision!r}, message={self.message!r})")


def resolve_artifacts_root(explicit: Path | None = None) -> Path:
    """构件根唯一来源(3.6/B2):显式参数 > ``PLATE_ARTIFACTS_PATH`` > 报错。

    无推导、无写死缺省——未配置即 fail-fast 指路配置(与
    ``PLATE_REPO_ROOT`` 同型)。现状 CLI 的写死与 ``repo_root`` 推导随
    本函数落地删除。
    """
    if explicit is not None:
        return explicit
    env = os.environ.get("PLATE_ARTIFACTS_PATH", "").strip()
    if not env:
        raise RuntimeError(
            "构件根未配置:设置 PLATE_ARTIFACTS_PATH 指向构件分支"
            "(plate/artifacts)的检出(版本模型 3.6/B2;本地演练可指向任意目录)"
        )
    return Path(env)


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, encoding="utf-8",
    )


def _call_projection(ep: EndpointSpec) -> dict[str, Any]:
    """binding → call 投影（6.2 export 映射;timeout_seconds → timeout）。"""
    b = ep.binding
    out: dict[str, Any] = {
        "protocol": b.protocol,
        "service": ep.service,
        "timeout": b.timeout_seconds,
    }
    for attr in ("method", "path", "headers"):
        if hasattr(b, attr):
            out[attr] = getattr(b, attr)
    # G1(集成 P2/Y1):binding.auth → call.auth 透传(四标准值;custom
    # 另带 auth_signer,binding 级声明优先)。none/缺省不写键 —— 存量
    # call 形状不变,重投影/比对零扰动。
    b_auth = getattr(b, "auth", None)
    if b_auth and b_auth != "none":
        out["auth"] = b_auth
        b_signer = getattr(b, "auth_signer", None)
        if b_auth == "custom" and b_signer:
            out["auth_signer"] = b_signer
    return out


def _dict_hash(data: dict[str, Any]) -> str:
    """普通 dict 的规范 hash（call 投影入池用；键序不携带语义）。"""
    return hashlib.sha256(
        json.dumps(data, ensure_ascii=False, separators=(",", ":"),
                   sort_keys=True).encode("utf-8")
    ).hexdigest()


def _pool_write(artifacts_root: Path, h: str, type_: str,
                data: dict[str, Any]) -> None:
    """信封 ``{"type","data"}`` 落全局池，文件名 = 内容寻址 hash（幂等）。"""
    objects_dir = artifacts_root / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)
    path = objects_dir / f"{h}.json"
    content = json.dumps({"type": type_, "data": data},
                         ensure_ascii=False, indent=1,
                         sort_keys=True).encode("utf-8")
    if not (path.exists() and path.read_bytes() == content):
        fd, tmp = tempfile.mkstemp(dir=objects_dir, suffix=".tmp")
        try:
            os.write(fd, content)
        finally:
            os.close(fd)
        os.replace(tmp, path)   # 原子:截断文件不会被「已存在」掩护


def _grade(report: ValidationReport, tree: Any,
           ) -> tuple[list[Finding], list[Finding]]:
    """D-4 分级：返回 (阻塞, 告警)。

    树级规则一律阻塞；其余 finding（含 C 类）按行号区间映射到块——只
    落在草稿块内降为告警，落在已评审块内或映射不到块（frontmatter 等
    文件级问题）保持阻塞。
    """
    ranges: dict[str, list[tuple[int, int, bool]]] = {}
    for d in tree.deliverables:
        ranges[d.source] = sorted(
            (b.line, b.end_line, b.review == "reviewed") for b in d.blocks()
        )
    blocking: list[Finding] = []
    warns: list[Finding] = []
    for f in report.findings:
        if f.severity not in ("blocking", "correction"):
            continue
        if f.rule in _TREE_LEVEL_RULES:
            blocking.append(f)
            continue
        hits = [r for r in ranges.get(f.source or "", [])
                if r[0] <= (f.line or 0) <= r[1]]
        if hits and all(not reviewed for _, _, reviewed in hits):
            warns.append(f)
        else:
            blocking.append(f)
    return blocking, warns


def _lines_dir(artifacts_root: Path, system: str) -> Path:
    return artifacts_root / system / "lines"


def latest_revision_manifest(artifacts_root: Path, system: str, line: str,
                             ) -> tuple[int, dict[str, Any]] | None:
    """该版本线最新修订 (n, manifest)；无修订返回 None。"""
    line_dir = _lines_dir(artifacts_root, system) / line
    if not line_dir.is_dir():
        return None
    # 只认 manifest 已落盘的修订目录(整体评审 2026-10-15 #7):编号目录
    # 由 mkdir 抢占先于 manifest 写入 —— 发版进行中/中途崩溃留下的空目录
    # 不是修订,不得被当作「最新」读出 FileNotFoundError。
    nums = sorted(
        int(p.name) for p in line_dir.iterdir()
        if p.is_dir() and p.name.isdigit() and (p / "manifest.json").is_file()
    )
    if not nums:
        return None
    n = nums[-1]
    m = line_dir / str(n) / "manifest.json"
    return n, json.loads(m.read_text(encoding="utf-8"))


def _commit_artifacts(artifacts_root: Path, message: str) -> str | None:
    """构件分支提交(3.6):artifacts 根为 git 工作树时 add+commit。

    非工作树(本地演练目录)只写盘不提交——发版本的演练路径。探测按
    ``rev-parse --show-toplevel`` 且要求 toplevel == artifacts 根:A-5
    收口(2026-10-12)前用 ``--is-inside-work-tree``,根本身不是仓库时
    git 会向上发现祖先仓库(如用户主目录的杂散 .git),把整个祖先当
    工作树 add/commit——既可能污染他人仓库也必然失败。
    幂等:add 后无暂存变更(对象已在分支上)直接返回当前 HEAD,不造
    空提交也不报错——plate 启动侧的 ensure_m2_pooled 每次启动都会
    走到这里,重复启动必须无感。
    """
    probe = _git(["rev-parse", "--show-toplevel"], artifacts_root)
    if probe.returncode != 0:
        return None
    try:
        if Path(probe.stdout.strip()).resolve() != artifacts_root.resolve():
            return None
    except OSError:
        return None
    ident = ["-c", "user.name=plate-release", "-c", "user.email=release@plate"]
    # 发版锁与原子写临时文件不入构件分支(整体评审 2026-10-15 #7:锁在
    # 提交期间仍持有,add -A 会把它一并提交)
    _git(ident + ["add", "-A", "--", ".",
                  ":(exclude,glob)**/.release.lock",
                  ":(exclude,glob)**/*.tmp"], artifacts_root)
    if _git(["diff", "--cached", "--quiet"], artifacts_root).returncode == 0:
        return _git(["rev-parse", "HEAD"], artifacts_root).stdout.strip()
    r = _git(ident + ["commit", "-m", message], artifacts_root)
    if r.returncode != 0:
        raise RuntimeError(f"构件分支提交失败: {r.stderr.strip()}")
    return _git(["rev-parse", "HEAD"], artifacts_root).stdout.strip()


_M2_POOL_SKIPS = 0    # 构件根未配置的启动跳过计数(A-5;healthz 暴露)


def ensure_m2_pooled() -> dict[str, Any]:
    """plate 启动把当前 M2 信封写进构件池(A-5,版本模型 3.6)。

    工作代码的 ``m2_hash`` 若不在池里,后续 freeze 引用该身份时读取面
    (routes_grammar 的 /api/m2、release.read 的 load_snapshot)会
    404 / RELEASE_CORRUPT——启动即写入,保证「运行中的身份必然可回读」。

    * 构件根未配置 → 计数 + 静默跳过(发版路径仍走 resolve_artifacts_root
      的 fail-fast,不受影响);启动不因未配置而炸。
    * 已配置 → 幂等写对象(内容寻址,同 hash 不重写);根即工作树时提交
      构件分支,演练目录只写盘。
    * 写入/提交失败 → error 状态返回,不阻断启动——working 面服务不
      依赖池,池的缺口只影响发版回读。
    """
    global _M2_POOL_SKIPS
    try:
        root = resolve_artifacts_root()
    except RuntimeError:
        _M2_POOL_SKIPS += 1
        return {"status": "unconfigured", "skips": _M2_POOL_SKIPS}
    try:
        from ..export.m2_schema import export_m2
        export = export_m2()
        _pool_write(root, export.m2_hash, "m2", export.schema)
        commit = _commit_artifacts(root, f"m2@{export.m2_hash[:12]} (startup)")
        return {"status": "pooled", "hash": export.m2_hash, "commit": commit}
    except Exception as e:  # noqa: BLE001 — 启动韧性:池失败不炸服务
        return {"status": "error", "message": f"{type(e).__name__}: {e}"[:200]}


def _atomic_write_text(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


RELEASE_LOCK_TIMEOUT_S = 120.0
RELEASE_LOCK_STALE_S = 30 * 60.0


class _SystemReleaseLock:
    """按系统的发版互斥锁(整体评审 2026-10-15 #7):跨平台 O_EXCL 锁文件。

    锁内完成「读上一修订 → 祖先校验 → 分配编号 → 写 manifest」,并发
    发版不再基于同一个陈旧的上一修订计算 ``previous_revision`` /
    corrections。持锁进程崩溃留下的锁文件超过 ``RELEASE_LOCK_STALE_S``
    视为陈旧并清除;等待超过 ``RELEASE_LOCK_TIMEOUT_S`` 放弃。
    """

    def __init__(self, artifacts_root: Path, system: str) -> None:
        self.path = artifacts_root / system / ".release.lock"
        self._held = False

    def acquire(self, timeout: float | None = None) -> bool:
        import time
        if timeout is None:
            timeout = RELEASE_LOCK_TIMEOUT_S   # 调用期读取(可配置/可测)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue            # 持有者刚释放,立即重试
                if age > RELEASE_LOCK_STALE_S:
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.2)
                continue
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(f"pid={os.getpid()} at={datetime.now(timezone.utc).isoformat()}\n")
            self._held = True
            return True

    def release(self) -> None:
        if self._held:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass
            self._held = False


def release_system(
    system_root: Path,
    *,
    artifacts_root: Path | None = None,
    signed_by: str = "",
    checklist: dict[str, int] | None = None,
) -> ReleaseResult:
    """冻结一个系统(版本模型 v1.4 的修订签发);按系统串行(发版锁)。"""
    resolved = resolve_artifacts_root(artifacts_root)
    lock = _SystemReleaseLock(resolved, system_root.name)
    if not lock.acquire():
        return ReleaseResult(
            success=False,
            message=(f"{system_root.name} 另有发版进行中(锁 {lock.path} "
                     f"超过 {int(RELEASE_LOCK_TIMEOUT_S)}s 未释放)——稍后重试"))
    try:
        return _release_system_locked(
            system_root, artifacts_root=resolved, signed_by=signed_by,
            checklist=checklist)
    finally:
        lock.release()


def _release_system_locked(
    system_root: Path,
    *,
    artifacts_root: Path | None = None,
    signed_by: str = "",
    checklist: dict[str, int] | None = None,
) -> ReleaseResult:
    """冻结一个系统（版本模型 v1.4 的修订签发）。

    ``checklist``：交付件清单阈值（F4；按已评审对象计算，3.2）。
    """
    artifacts_root = resolve_artifacts_root(artifacts_root)
    if not system_root.is_dir():
        return ReleaseResult(success=False,
                             message=f"系统目录不存在: {system_root}")
    if system_root.name == "common":
        return ReleaseResult(
            success=False,
            message="common 不单独发版(N3):被引用的 common 对象随引用系统的 manifest 冻结")
    if not signed_by or not signed_by.strip():
        return ReleaseResult(success=False, message="签发人(signed_by)不可为空")

    # ── git 前置(3.3/3.6,B1):发版需要 git 工作树 + 干净的源树 ──
    repo_root = system_root.parent.parent
    probe = _git(["rev-parse", "--show-toplevel"], repo_root)
    if probe.returncode != 0:
        return ReleaseResult(
            success=False,
            message="发版需要在 git 工作树中执行(版本模型 3.6;3.3 需要 git)")
    status = _git(["status", "--porcelain", "--", "systems/", "types/"],
                  repo_root)
    if status.stdout.strip():
        return ReleaseResult(
            success=False,
            message=("发版前置失败:源树有未提交变更(systems/ 或 types/)——"
                     "先经评审入库再发版(版本模型 3.6/B1);首条: "
                     + status.stdout.strip().splitlines()[0]))
    head = _git(["rev-parse", "HEAD"], repo_root).stdout.strip()

    # ── 装载 + 机械检查(与 check 同一引擎,J1)──
    from gimbal_plate.dialect.parser import DialectError

    types = load_types(repo_root / "types" / "types.yaml")
    try:
        tree = collect_system_tree(system_root)
    except DialectError as e:
        report = ValidationReport()
        report.add(Finding("F0", "blocking", str(e),
                           source=e.source, line=e.line))
        return ReleaseResult(success=False, message=f"方言错误: {e}",
                             report=report)
    report = validate_system_tree(system_root, types=types, tree=tree)

    # ── 版本线声明(2.1):发版要求 system.md 声明 line ──
    fm = tree.system_frontmatter
    if fm is None or not fm.line:
        return ReleaseResult(
            success=False,
            message="system.md 未声明版本线 line(版本模型 2.1)——发版前先声明",
            report=report)

    # ── 祖先校验(3.3)──
    latest = latest_revision_manifest(
        artifacts_root, system_root.name, fm.line)
    if latest is not None:
        prev_n, prev = latest
        prev_commit = str(prev.get("source_commit") or "")
        if prev_commit:
            anc = _git(["merge-base", "--is-ancestor", prev_commit, head],
                       repo_root)
            if anc.returncode != 0:
                return ReleaseResult(
                    success=False,
                    message=(f"修订必须沿 git 祖先关系前进(3.3):"
                             f"{fm.line}#{prev_n} 的 source_commit "
                             f"{prev_commit[:8]} 不是当前 HEAD 的后代——"
                             "旧版本线的修订须在其维护分支上发"),
                    report=report)
    else:
        prev_n, prev = None, None
        if fm.predecessor_line:
            pred = latest_revision_manifest(
                artifacts_root, system_root.name, fm.predecessor_line)
            if pred is None:
                return ReleaseResult(
                    success=False,
                    message=(f"predecessor_line {fm.predecessor_line!r} "
                             "尚未发出任何修订(3.3)"),
                    report=report)

    # ── F4:交付件清单阈值(按已评审对象计算)──
    from gimbal_plate.dialect.gaps import gap_items
    items = gap_items(tree.endpoints, tree.statements,
                      tree.terms, tree.common_terms)
    for key, minimum in (checklist or {}).items():
        actual = items.get(key)
        if actual is not None and actual < minimum:
            report.add(Finding(
                "F4", "blocking",
                f"交付件清单: {key} = {actual} < 阈值 {minimum}",
            ))

    # ── 收集冻结对象(3.1:全部块,逐对象记录评审状态)──
    # D-3:gimbal:system(服务声明)随修订冻结——服务是接口坐标的一部分;
    # gimbal:defaults 不冻结(偏环境属性,平台读 working)。
    all_objects: list[tuple[str, Any, bool]] = []   # (kind, model, reviewed)
    from gimbal_plate.schema.service_definition import ServiceDefinition
    for d in tree.deliverables:
        for b in d.blocks():
            if b.type == "system":
                items = (b.payload if isinstance(b.payload, list)
                         else [b.payload])
                for item in items:
                    if not isinstance(item, dict) or not item.get("name"):
                        continue
                    try:
                        ServiceDefinition.model_validate(item)
                    except Exception as e:  # noqa: BLE001
                        return ReleaseResult(
                            success=False,
                            message=f"服务声明非法(3.1/D-3): {e}",
                            report=report)
                    all_objects.append(("service", item,
                                        b.review == "reviewed"))
                continue
            for m in b.models():
                if isinstance(m, EndpointSpec):
                    all_objects.append(("endpoint", m,
                                        b.review == "reviewed"))
                elif isinstance(m, Statement):
                    all_objects.append(("statement", m,
                                        b.review == "reviewed"))
                elif isinstance(m, Term):
                    all_objects.append(("term", m,
                                        b.review == "reviewed"))
    if not all_objects:
        return ReleaseResult(
            success=False,
            message="无可冻结对象(树中没有任何块)——空修订拒绝发出",
            report=report)

    # ── 引用闭包(3.2):已评审只引用已评审;草稿引用只决定 common 冻结面 ──
    from gimbal_plate.dialect.validation import _parent_of

    def _term_edges(tid: str) -> list[str]:
        t_ = tree.terms.get(tid) or tree.common_terms.get(tid)
        if t_ is None:
            return []
        out: list[str] = []
        if t_.refers:
            out.append(t_.refers)
        if t_.replaced_by:
            out.append(t_.replaced_by)
        parent = _parent_of(tid)
        if parent:
            out.append(parent)
        return out

    def _refs_of(kind: str, m: Any) -> list[str]:
        if kind == "endpoint":
            return [r for r in (m.capability, *m.consumes, *m.produces) if r]
        if kind == "statement":
            out: list[str] = []
            for v in m.slots.values():
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend(x for x in v if isinstance(x, str))
            return out
        if kind == "term":
            return _term_edges(m.id)
        return []

    closure: list[tuple[str, str]] = []
    common_frozen: set[str] = set()
    visited: set[str] = set()
    queue: list[tuple[str, str]] = []
    for kind, m, reviewed in all_objects:
        for r in _refs_of(kind, m):
            if reviewed:
                queue.append((getattr(m, "id", "?"), r))
            elif r in tree.common_terms:
                # 草稿对象的引用不作闸门,但其指向的 common 词条随冻结
                common_frozen.add(r)
    while queue:
        owner, tid = queue.pop()
        if tid in visited:
            continue
        visited.add(tid)   # 边始终展开:种子(reviewed)也不例外——传递引用仍要查
        if tid not in tree.terms and tid not in tree.common_terms:
            closure.append((owner, tid))   # 不存在(S2 已报,双保险)
            continue
        if not tree.term_block_review.get(tid, False):
            closure.append((owner, tid))   # 草稿词条被已评审内容引用
            continue
        if tid in tree.common_terms:
            common_frozen.add(tid)
        queue.extend((owner, e) for e in _term_edges(tid))
    if closure:
        return ReleaseResult(
            success=False,
            message=(f"引用闭包未闭合: {len(closure)} 处已评审内容引用"
                     f"未评审词条(首条: {closure[0][0]} → {closure[0][1]})"),
            report=report)

    # ── 闸门分级(D-4)──
    blocking, warns = _grade(report, tree)
    if blocking:
        return ReleaseResult(
            success=False,
            message=(f"发布闸门未过: {len(blocking)} 条阻塞"
                     f"(首条: {blocking[0].rule} {blocking[0].message})"),
            report=report)

    # ── 冻结(3.1 全部对象;信封 3.5;hash=对象 hash,池文件按 hash 命名)──
    review_of = {id(m): reviewed for _, m, reviewed in all_objects}
    freeze_list: list[tuple[str, Any]] = [(k, m) for k, m, _ in all_objects]
    freeze_list += [("term", tree.common_terms[mid])
                    for mid in sorted(common_frozen)]

    def _entry(kind: str, m: Any) -> dict[str, Any]:
        if kind == "service":
            h = _dict_hash(m)
            _pool_write(artifacts_root, h, "service", m)
            return {"id": m.get("name", ""), "type": "service",
                    "hash": h,
                    "review": "reviewed" if review_of.get(id(m)) else "draft"}
        h = object_hash(m)
        _pool_write(artifacts_root, h, kind, m.model_dump(mode="json"))
        e: dict[str, Any] = {
            "id": getattr(m, "id", ""),
            "type": kind,
            "hash": h,
            "review": "reviewed" if review_of.get(id(m)) else "draft",
        }
        if kind == "endpoint":
            e["shape_hash"] = shape_hash(m)
        return e

    object_entries = [_entry(kind, m) for kind, m in freeze_list]
    call_projections: dict[str, str] = {}
    for kind, m, _ in all_objects:
        if kind == "endpoint":
            proj = _call_projection(m)
            ph = _dict_hash(proj)
            _pool_write(artifacts_root, ph, "call", proj)
            call_projections[m.id] = ph

    # ── 编号(3.4)──
    line_dir = _lines_dir(artifacts_root, system_root.name) / fm.line
    n = (prev_n or 0) + 1
    manifest_dir = line_dir / str(n)
    for _attempt in range(8):
        try:
            manifest_dir.mkdir(parents=True)
            break
        except FileExistsError:
            n += 1
            manifest_dir = line_dir / str(n)
    else:
        return ReleaseResult(success=False, message="修订号竞争重试耗尽")

    # ── corrections(3.5):与上一修订相比 shape_hash 变化的接口 ──
    corrections: list[str] = []
    if prev is not None:
        prev_shapes = {e["id"]: e.get("shape_hash")
                       for e in prev.get("objects", [])
                       if e.get("type") == "endpoint"}
        cur_shapes = {e["id"]: e.get("shape_hash") for e in object_entries
                      if e["type"] == "endpoint"}
        corrections = sorted(
            eid for eid in (prev_shapes.keys() & cur_shapes.keys())
            if prev_shapes[eid] != cur_shapes[eid]
        )

    manifest = {
        "system": system_root.name,
        "line": fm.line,
        "revision": n,
        "line_scheme": fm.line_scheme or "free",
        "line_service": fm.line_service,
        "predecessor_line": fm.predecessor_line,
        "previous_revision": prev_n,
        "source_commit": head,
        "released_at": datetime.now(timezone.utc).isoformat(),
        "signed_by": signed_by,
        "dialect_version": DIALECT_VERSION,
        "m2_version": M2_VERSION,
        "types_version": 1,
        "checklist_applied": checklist or {},
        "objects": object_entries,
        "call_projections": call_projections,
        "corrections": corrections,
        "warnings": [
            {"rule": f.rule, "severity": f.severity, "message": f.message,
             "source": f.source, "line": f.line}
            for f in warns
        ],
        "summary": {
            "endpoints": sum(1 for k, _ in freeze_list if k == "endpoint"),
            "statements": sum(1 for k, _ in freeze_list if k == "statement"),
            "terms": sum(1 for k, _ in freeze_list if k == "term"),
            "services": sum(1 for k, _ in freeze_list if k == "service"),
            "common_terms_frozen": len(common_frozen),
            "draft_objects": sum(1 for _, m in freeze_list
                                 if not review_of.get(id(m))),
        },
    }
    # 原子落盘(整体评审 2026-10-15 #7):tmp + os.replace,与对象池同口径
    # —— 中途崩溃不会留下半截 manifest(读侧只认完整文件)。
    _atomic_write_text(
        manifest_dir / "manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=1))

    revision = f"{fm.line}#{n}"
    commit = _commit_artifacts(
        artifacts_root, f"{system_root.name}@{revision}")
    return ReleaseResult(
        success=True, line=fm.line, revision=revision, manifest=manifest,
        report=report,
        message=(f"冻结 {manifest['summary']['endpoints']} 接口 / "
                 f"{manifest['summary']['statements']} 片段 / "
                 f"{manifest['summary']['terms']} 词条"
                 + (f"（{len(warns)} 条草稿告警入 warnings）" if warns else "")
                 + (f"；构件提交 {commit[:8]}" if commit
                    else "（演练目录，未提交构件分支）")),
    )


__all__ = [
    "DIALECT_VERSION", "M2_VERSION", "ReleaseResult",
    "latest_revision_manifest", "release_system", "resolve_artifacts_root",
]
