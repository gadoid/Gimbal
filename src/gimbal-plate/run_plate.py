"""Tiny launcher so we can run Plate via `python run_plate.py`.

X5(外部接口登记批):启动配置化 —— 环境变量 ``PLATE_HOST`` /
``PLATE_PORT`` / ``PLATE_LOG_LEVEL``,进程级环境变量优先;同级 ``.env``
(KEY=VALUE,``#`` 注释行忽略;**进程环境变量已存在的键不覆盖**)其次;
CLI 参数显式最优先。纯 launcher 局部解析,**不引 pydantic-settings
依赖**(gimbal_plate 包零新依赖面,设计 v1.0 §7)。
"""
import argparse
import os
import sys
from pathlib import Path

import uvicorn

# 2026-10-08 起 gimbal_plate 与 gimbal 同为 src/ 平级包(打包根因修复,
# 见 pyproject 注释);run_plate.py 仍在 src/gimbal-plate/ 下,脚本目录
# 不再包含包 —— 把 repo src/ 放进 sys.path,不依赖 editable 安装。
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load_dotenv(path: Path) -> None:
    """.env 的最小解析:KEY=VALUE 落 os.environ(已存在的键不动)。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default) or default


def main() -> None:
    # .env 在 src/gimbal-plate/ 下(restart-services.ps1 的工作目录);
    # 进程环境变量(如 PLATE_ARTIFACTS_PATH)优先级更高,不被覆盖。
    _load_dotenv(Path(__file__).resolve().parent / ".env")

    parser = argparse.ArgumentParser(description="Run the Plate HTTP service.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="watch gimbal_plate/ for code changes and restart on change",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="bind address (0.0.0.0 exposes the service on the LAN);"
             " default = $PLATE_HOST or 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"default = $PLATE_PORT or 8765",
    )
    args = parser.parse_args()

    # uvicorn reload requires an import string (it re-imports the module in a
    # fresh worker on restart); passing an app object would disable reload.
    kwargs: dict = {
        "factory": True,
        "host": args.host or _env("PLATE_HOST", "127.0.0.1"),
        "port": args.port or int(_env("PLATE_PORT", "8765")),
        "log_level": _env("PLATE_LOG_LEVEL", "info"),
    }
    if args.reload:
        # Pin the watch scope to the package dir so it works regardless of cwd;
        # run_plate.py itself stays outside (launcher changes need a manual restart).
        package_dir = _SRC / "gimbal_plate"
        kwargs["reload"] = True
        kwargs["reload_dirs"] = [str(package_dir)]

    uvicorn.run("gimbal_plate.http.app:create_app", **kwargs)


if __name__ == "__main__":
    main()
