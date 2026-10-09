#!/usr/bin/env python3
"""用 GIMBAL 对 dsh-desktop-bridge 暴露的回环 HTTP 接口做接口测试。

dsh-desktop-bridge 每次挂载都会重新随机端口和 token，并写进
``<DSH_HOME>/desktop-bridge.json``。GIMBAL 的 ``config.services`` 与 ``api.path``
在预处理阶段静态展开，所以这里在启动前完成三件事：

1. 读 descriptor，拿到 port / token；
2. 把 ``config.services.bridge`` 改写为 ``http://127.0.0.1:<port>``；
3. 确定被测会话 id（``--session-id``，否则取 ``GET /v1/sessions`` 的第一条），
   连同 token / port 写进渲染后场景的 ``config.vars``，再交给 ``gimbal run launch``。
   （当前 ``run launch`` 尚无 ``--var``；渲染件只落临时文件，跑完即删，token 不入库。）

默认只跑只读 + 负向用例；``--write`` 才会创建会话并发送消息——在真实桌面端上
这会启动一个以你的权限运行的 agent，请只对测试会话使用。

用法::

    python examples/dsh_desktop_bridge/run.py                       # 只读
    python examples/dsh_desktop_bridge/run.py --write --session-id session-…
    python examples/dsh_desktop_bridge/run.py -- -o json            # 透传 gimbal 参数
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCENARIOS = {
    "readonly": HERE / "scenario.readonly.json",
    "write": HERE / "scenario.write.json",
}


def default_descriptor() -> Path:
    home = os.environ.get("DSH_HOME") or str(Path.home() / ".dsh")
    return Path(home) / "desktop-bridge.json"


def load_descriptor(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"descriptor not found: {path}（插件未启用？或 DSH_HOME 不对）")
    if data.get("version") != 1:
        sys.exit(f"unsupported descriptor version: {data.get('version')!r}")
    return data


def first_session(base_url: str, token: str) -> str | None:
    req = urllib.request.Request(
        f"{base_url}/v1/sessions", headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        items = json.load(resp).get("items") or []
    for item in items:
        sid = item.get("sessionId") or item.get("id")
        if sid:
            return sid
    return None


def gimbal_cmd() -> list[str]:
    if os.environ.get("GIMBAL_BIN"):
        return [os.environ["GIMBAL_BIN"]]
    if shutil.which("gimbal"):
        return ["gimbal"]
    return [sys.executable, "-m", "gimbal"]


def launch(name: str, base_url: str, variables: dict[str, str], extra: list[str]) -> int:
    scenario = json.loads(SCENARIOS[name].read_text(encoding="utf-8"))
    scenario["config"]["services"]["bridge"] = base_url
    scenario["config"]["vars"].update(variables)
    with tempfile.NamedTemporaryFile(
        "w", suffix=f".{name}.json", delete=False, encoding="utf-8"
    ) as tmp:
        json.dump(scenario, tmp, ensure_ascii=False)
    try:
        cmd = [*gimbal_cmd(), "run", "launch", tmp.name, "-f", "json", *extra]
        print(f"\n=== {name}: {SCENARIOS[name].name} ===", flush=True)
        return subprocess.call(cmd)
    finally:
        os.unlink(tmp.name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--descriptor", type=Path, default=default_descriptor(),
                        help="desktop-bridge.json 路径（默认 $DSH_HOME/desktop-bridge.json）")
    parser.add_argument("--session-id", help="被测会话 id；缺省取列表第一条")
    parser.add_argument("--write", action="store_true",
                        help="额外运行写用例：创建会话 + 发送消息（会启动 agent）")
    parser.add_argument("--workdir", default=os.getcwd(),
                        help="--write 时新建会话的 cwd（必须是已存在目录，默认当前目录）")
    parser.add_argument("--message", default="gimbal bridge probe: please reply with OK.",
                        help="--write 时发送的消息文本")
    parser.add_argument("gimbal_args", nargs=argparse.REMAINDER,
                        help="'--' 之后的参数原样透传给 gimbal run launch")
    args = parser.parse_args()
    extra = args.gimbal_args[1:] if args.gimbal_args[:1] == ["--"] else args.gimbal_args

    desc = load_descriptor(args.descriptor)
    base_url = f"http://{desc['address']}:{desc['port']}"
    token = desc["token"]

    session_id = args.session_id or first_session(base_url, token)
    if not session_id:
        sys.exit("宿主里没有任何会话：先在桌面端开一个会话，或用 --session-id 指定")

    variables = {"token": token, "port": str(desc["port"]), "session_id": session_id}
    print(f"bridge={base_url} pid={desc.get('pid')} session={session_id}")

    rc = launch("readonly", base_url, variables, extra)
    if args.write:
        write_vars = {**variables, "workdir": str(Path(args.workdir).resolve()),
                      "message": args.message}
        rc = max(rc, launch("write", base_url, write_vars, extra))
    return rc


if __name__ == "__main__":
    sys.exit(main())
