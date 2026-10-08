"""Tiny launcher so we can run Plate via `python run_plate.py`."""
import argparse
import sys
from pathlib import Path

import uvicorn

# 2026-10-08 起 gimbal_plate 与 gimbal 同为 src/ 平级包(打包根因修复,
# 见 pyproject 注释);run_plate.py 仍在 src/gimbal-plate/ 下,脚本目录
# 不再包含包 —— 把 repo src/ 放进 sys.path,不依赖 editable 安装。
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Plate HTTP service.")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="watch gimbal_plate/ for file changes and restart on change",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address (0.0.0.0 exposes the service on the LAN)",
    )
    args = parser.parse_args()

    # uvicorn reload requires an import string (it re-imports the module in a
    # fresh worker on restart); passing an app object would disable reload.
    kwargs: dict = {
        "factory": True,
        "host": args.host,
        "port": 8765,
        "log_level": "info",
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
