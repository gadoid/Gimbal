"""gimbal asset —— 资产仓库的 CLI 入口（仿 Docker）。

子命令树：

    gimbal asset push      NAMESPACE/NAME:TAG  -f FILE  上传资产
    gimbal asset pull      NAMESPACE/NAME[:TAG] 下载资产
    gimbal asset list      [NAMESPACE]          列出资产
    gimbal asset inspect   NAMESPACE/NAME[:TAG] 查看元数据
    gimbal asset remove    NAMESPACE/NAME[:TAG] 删除 tag
    gimbal asset tag       SRC  DST              给已有 digest 添加新 tag
    gimbal asset gc                              清理孤儿 blob

所有子命令共享：
    --registry PATH    本地注册表根目录（默认 ~/.gimbal/registry）

设计哲学：CLI 走"快路径"——每个子命令直接构造 LocalFsContentStore，
不经过 bootstrap（asset 操作不需要 ContextManager / Plugins / Hooks）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Annotated, Any, Optional

import typer

from gimbal.cli.exit_codes import EXIT_ASSET_NOT_FOUND, EXIT_OK, EXIT_USAGE_ERROR
from gimbal.exceptions import (
    AssetAlreadyExists,
    AssetDigestMismatch,
    AssetNotFound,
    InvalidAssetRef,
)
from gimbal.log import get_logger
from gimbal.repository import (
    AssetRef,
    AssetStore,
    LocalFsContentStore,
    compute_digest,
)

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# Typer 子应用
# ════════════════════════════════════════════════════════════════════════════


asset_app = typer.Typer(
    name="asset",
    help=(
        "资产仓库管理（仿 Docker Registry）。\n\n"
        "支持的子命令：\n"
        "  push      上传资产到本地仓库\n"
        "  pull      下载资产\n"
        "  list      列出资产（按 namespace）\n"
        "  inspect   查看资产元数据（不下载内容）\n"
        "  remove    删除资产的某个 tag\n"
        "  tag       给已有 digest 加新 tag\n"
        "  gc        清理孤儿 blob"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)


# ── 共享选项 ──


DEFAULT_REGISTRY = Path("~/.gimbal/registry")


def _opt_registry() -> Any:
    return typer.Option(
        "--registry", "-r",
        help=f"本地注册表根目录。默认 {DEFAULT_REGISTRY}。",
        rich_help_panel="仓库选项",
    )


def _resolve_registry(registry: Optional[Path]) -> Path:
    """解析 --registry 选项，未提供时用默认。"""
    p = (registry or DEFAULT_REGISTRY).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _build_store(registry: Optional[Path]) -> AssetStore:
    backend = LocalFsContentStore(root=_resolve_registry(registry))
    return AssetStore(backend=backend)


# ════════════════════════════════════════════════════════════════════════════
# 子命令：push
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("push")
def push(
    ctx: typer.Context,
    ref_str: Annotated[
        str,
        typer.Argument(help="目标 ref，如 `customs/declare:v1.0`。", metavar="REF"),
    ],
    file: Annotated[
        Optional[Path],
        typer.Option(
            "-f", "--file",
            help="从文件读取内容；不指定则从 stdin 读。",
            rich_help_panel="输入",
        ),
    ] = None,
    kind: Annotated[
        str,
        typer.Option(
            "--kind", "-k",
            help="资产类型：suite / scenario / data / blob。",
            rich_help_panel="元数据",
        ),
    ] = "blob",
    media_type: Annotated[
        str,
        typer.Option(
            "--media-type", "-m",
            help="MIME 类型。",
            rich_help_panel="元数据",
        ),
    ] = "application/octet-stream",
    metadata: Annotated[
        Optional[list[str]],
        typer.Option(
            "--meta",
            help="附加元数据，KEY=VALUE 形式，可重复。",
            rich_help_panel="元数据",
        ),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help="目标 tag 已存在时是否覆盖。默认不覆盖。",
        ),
    ] = False,
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """上传资产到本地仓库。"""
    try:
        ref = AssetRef.parse(ref_str)
    except InvalidAssetRef as e:
        typer.secho(f"Error: invalid ref {ref_str!r}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    # 读数据
    if file is not None:
        if not file.exists():
            typer.secho(f"Error: file not found: {file}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=EXIT_USAGE_ERROR)
        data = file.read_bytes()
    else:
        if sys.stdin.isatty():
            typer.secho("Reading from stdin... (Ctrl-D to end)", fg=typer.colors.YELLOW)
        data = sys.stdin.buffer.read()

    # 解析 metadata
    meta_dict: dict[str, str] = {}
    for item in metadata or []:
        if "=" not in item:
            typer.secho(f"Error: invalid --meta {item!r}, expected KEY=VALUE", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=EXIT_USAGE_ERROR)
        k, v = item.split("=", 1)
        meta_dict[k.strip()] = v

    store = _build_store(registry)
    try:
        record = store.push(
            ref=ref,
            data=data,
            kind=kind,                              # type: ignore[arg-type]
            media_type=media_type,
            metadata=meta_dict,
            overwrite=overwrite,
        )
    except AssetAlreadyExists as e:
        typer.secho(
            f"Error: ref already exists: {ref} (use --overwrite to replace)",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=EXIT_USAGE_ERROR)
    except AssetDigestMismatch as e:
        typer.secho(
            f"Error: digest mismatch — declared={e.context.get('declared')} actual={e.context.get('actual')}",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    typer.secho(
        f"Pushed: {ref}  digest={record.digest}  size={record.size}B",
        fg=typer.colors.GREEN,
    )


# ════════════════════════════════════════════════════════════════════════════
# 子命令：pull
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("pull")
def pull(
    ctx: typer.Context,
    ref_str: Annotated[
        str,
        typer.Argument(help="资产 ref，如 `customs/declare:v1.0` 或 `@digest`。", metavar="REF"),
    ],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "-o", "--output",
            help="写入文件；不指定则写到 stdout（适合 binary）。",
            rich_help_panel="输出",
        ),
    ] = None,
    raw: Annotated[
        bool,
        typer.Option(
            "--raw/--no-raw",
            help="--raw: 只写 raw bytes；默认会自动 JSON 解析（仅 stdout 模式生效）。",
        ),
    ] = False,
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """下载资产。"""
    try:
        ref = AssetRef.parse(ref_str)
    except InvalidAssetRef as e:
        typer.secho(f"Error: invalid ref {ref_str!r}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    store = _build_store(registry)
    try:
        content = store.pull(ref, parse_json=not raw)
    except AssetNotFound as e:
        typer.secho(f"Error: asset not found: {ref}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ASSET_NOT_FOUND)

    if output is not None:
        output.write_bytes(content.raw)
        typer.secho(
            f"Pulled: {ref}  → {output}  size={content.size}B",
            fg=typer.colors.GREEN,
        )
    else:
        if raw or content.parsed is None:
            # binary 写到 stdout buffer
            sys.stdout.buffer.write(content.raw)
            sys.stdout.flush()
        else:
            typer.echo(json.dumps(content.parsed, ensure_ascii=False, indent=2))


# ════════════════════════════════════════════════════════════════════════════
# 子命令：list
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("list")
def list_(
    ctx: typer.Context,
    namespace: Annotated[
        Optional[str],
        typer.Argument(help="限定 namespace；不传则全库。", metavar="[NAMESPACE]"),
    ] = None,
    output: Annotated[
        str,
        typer.Option(
            "--output", "-o",
            help="输出格式：table / json。",
            case_sensitive=False,
        ),
    ] = "table",
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """列出资产。"""
    store = _build_store(registry)
    records = store.list_assets(namespace=namespace)

    if output == "json":
        # 输出 record 列表的 JSON
        out = [
            {
                "ref": str(r.ref),
                "digest": r.digest,
                "size": r.size,
                "kind": r.kind,
                "media_type": r.media_type,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in records
        ]
        typer.echo(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # table 格式
    if not records:
        typer.secho("(empty)", fg=typer.colors.YELLOW)
        return

    # 按 (namespace, name, tag) 排序
    records.sort(key=lambda r: (r.ref.namespace, r.ref.name, r.ref.tag))

    from rich.table import Table
    from rich.console import Console
    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("REF", style="cyan")
    table.add_column("DIGEST", style="dim", no_wrap=True)
    table.add_column("SIZE", justify="right")
    table.add_column("KIND")
    table.add_column("UPDATED")
    for r in records:
        table.add_row(
            str(r.ref),
            r.digest[:19] + "…",
            _human_size(r.size),
            r.kind,
            r.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
    console.print(table)
    typer.echo(f"Total: {len(records)} record(s)")


# ════════════════════════════════════════════════════════════════════════════
# 子命令：inspect
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("inspect")
def inspect(
    ctx: typer.Context,
    ref_str: Annotated[str, typer.Argument(help="资产 ref。", metavar="REF")],
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """查看资产元数据（不下载内容）。"""
    try:
        ref = AssetRef.parse(ref_str)
    except InvalidAssetRef as e:
        typer.secho(f"Error: invalid ref {ref_str!r}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    store = _build_store(registry)
    try:
        rec = store.inspect(ref)
    except AssetNotFound:
        typer.secho(f"Error: asset not found: {ref}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ASSET_NOT_FOUND)

    out = {
        "ref": str(rec.ref),
        "namespace": rec.ref.namespace,
        "name": rec.ref.name,
        "tag": rec.ref.tag,
        "digest": rec.digest,
        "size": rec.size,
        "kind": rec.kind,
        "media_type": rec.media_type,
        "created_at": rec.created_at.isoformat(),
        "updated_at": rec.updated_at.isoformat(),
        "metadata": rec.metadata,
    }
    typer.echo(json.dumps(out, ensure_ascii=False, indent=2))


# ════════════════════════════════════════════════════════════════════════════
# 子命令：remove
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("remove")
def remove(
    ctx: typer.Context,
    ref_str: Annotated[str, typer.Argument(help="资产 ref。", metavar="REF")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="跳过确认。"),
    ] = False,
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """删除资产的某个 tag（blob 在无引用时自动清理——gc 时）。"""
    try:
        ref = AssetRef.parse(ref_str)
    except InvalidAssetRef as e:
        typer.secho(f"Error: invalid ref {ref_str!r}: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    store = _build_store(registry)
    if not yes and sys.stdin.isatty():
        if not typer.confirm(f"Remove {ref}?", default=False):
            typer.echo("Aborted.")
            raise typer.Exit(code=EXIT_OK)
    try:
        store.remove(ref)
    except AssetNotFound:
        typer.secho(f"Error: asset not found: {ref}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ASSET_NOT_FOUND)
    typer.secho(f"Removed: {ref}", fg=typer.colors.GREEN)


# ════════════════════════════════════════════════════════════════════════════
# 子命令：tag
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("tag")
def tag(
    ctx: typer.Context,
    src_ref: Annotated[str, typer.Argument(help="源 ref（必须已存在）。", metavar="SRC")],
    dst_ref: Annotated[str, typer.Argument(help="目标 ref（要打的 tag）。", metavar="DST")],
    overwrite: Annotated[
        bool,
        typer.Option(
            "--overwrite/--no-overwrite",
            help="目标 ref 已存在时是否覆盖。",
        ),
    ] = False,
    registry: Annotated[Optional[Path], _opt_registry()] = None,
) -> None:
    """给已有 digest 添加新 tag。"""
    try:
        src = AssetRef.parse(src_ref)
        dst = AssetRef.parse(dst_ref)
    except InvalidAssetRef as e:
        typer.secho(f"Error: invalid ref: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_USAGE_ERROR)

    store = _build_store(registry)
    try:
        rec = store.tag(src, dst, overwrite=overwrite)
    except AssetNotFound as e:
        typer.secho(f"Error: source not found: {src}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=EXIT_ASSET_NOT_FOUND)
    except AssetAlreadyExists:
        typer.secho(
            f"Error: target already exists: {dst} (use --overwrite)",
            fg=typer.colors.RED, err=True,
        )
        raise typer.Exit(code=EXIT_USAGE_ERROR)
    typer.secho(
        f"Tagged: {src} → {dst}  digest={rec.digest}",
        fg=typer.colors.GREEN,
    )


# ════════════════════════════════════════════════════════════════════════════
# 子命令：gc
# ════════════════════════════════════════════════════════════════════════════


@asset_app.command("gc")
def gc(
    ctx: typer.Context,
    registry: Annotated[Optional[Path], _opt_registry()] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="跳过确认直接清理。"),
    ] = False,
) -> None:
    """清理孤儿 blob（无任何 tag 引用的内容）。"""
    backend = LocalFsContentStore(root=_resolve_registry(registry))
    stats_before = backend.stats()

    if not yes and sys.stdin.isatty():
        typer.echo(f"Current: {stats_before['n_blobs']} blob(s), {stats_before['n_manifests']} manifest(s).")
        if not typer.confirm("Proceed with GC?", default=False):
            typer.echo("Aborted.")
            raise typer.Exit(code=EXIT_OK)

    removed = backend.gc()
    stats_after = backend.stats()
    typer.secho(
        f"GC done: removed={removed}, remaining_blobs={stats_after['n_blobs']}",
        fg=typer.colors.GREEN,
    )


# ════════════════════════════════════════════════════════════════════════════
# 工具
# ════════════════════════════════════════════════════════════════════════════


def _human_size(n: int) -> str:
    """字节数 → 人类可读。"""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.1f}TB"
