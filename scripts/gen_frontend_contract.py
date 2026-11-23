"""前端契约单源生成(B5 治本切片 1;登记册 B5)。

从后端契约快照(``gen_api_contract.py`` 的产物,单一事实源)生成前端
可直接消费的 TS 模块,替代 37 个 api 文件的手写镜像起步面:

* ``openapi.json`` → ``src/api/generated/openapi.ts``
  —— 219 个 schema 的 TS interface/type(属性级 ``anyOf+null`` =
  ``T | null``;enum → 字面量 union;additionalProperties →
  Record;``-`` 键名合法化)。
* ``error-codes.json`` → ``src/api/generated/errorCodes.ts``
  —— ``ERROR_CODES``(as const:字符串码 + 数值商务码)、
  ``ApiErrorCode``(字符串码 union)、``NumericApiErrorCode``。

生成幂等(重跑 diff 为零);``--check`` 模式与盘上文件比对,漂移
非零退出(ext_gates 守卫位)。api 文件以 facade 模式逐步切换
(re-export 生成类型,组件 import 面零改动)。

用法::

    python scripts/gen_frontend_contract.py            # 生成
    python scripts/gen_frontend_contract.py --check    # 守卫比对
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_BACKEND = _REPO / "src" / "gimbal-platform" / "backend"
_FRONTEND = _REPO / "src" / "gimbal-platform" / "frontend"

_OPENAPI = _BACKEND / "contract" / "openapi.json"
_ERROR_CODES = _BACKEND / "contract" / "error-codes.json"
_OUT_OPENAPI = _FRONTEND / "src" / "api" / "generated" / "openapi.ts"
_OUT_CODES = _FRONTEND / "src" / "api" / "generated" / "errorCodes.ts"


def _ts_name(name: str) -> str:
    """合法 TS 标识符(ScenarioDraft-Input → ScenarioDraft_Input)。"""
    return name.replace("-", "_")


def _type_of(prop: dict) -> str:
    """openapi 属性/schema → TS 类型(拍平名引用 $ref)。"""
    if "$ref" in prop:
        return _ts_name(prop["$ref"].rsplit("/", 1)[-1])
    if "anyOf" in prop:
        parts = [_type_of(p) for p in prop["anyOf"]]
        return " | ".join(dict.fromkeys(parts))
    if "oneOf" in prop:
        return " | ".join(dict.fromkeys(
            _type_of(p) for p in prop["oneOf"]))
    if "enum" in prop:
        return " | ".join(json.dumps(v) for v in prop["enum"])
    t = prop.get("type")
    if t == "array":
        inner = _type_of(prop.get("items") or {})
        return f"Array<{inner}>"
    if t == "object":
        ap = prop.get("additionalProperties")
        if isinstance(ap, dict):
            return f"Record<string, {_type_of(ap)}>"
        if ap is True:
            return "Record<string, unknown>"
        return "Record<string, unknown>"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "null":
        return "null"
    return "unknown"


def _gen_openapi(spec: dict) -> str:
    schemas = spec.get("components", {}).get("schemas", {})
    lines = [
        "// 由 scripts/gen_frontend_contract.py 从 backend/contract/openapi.json",
        "// 生成 —— 勿手改;单源事实在后端契约快照(gen_api_contract.py)。",
        "// 切换策略:api/*.ts facade re-export,组件 import 面零改动。",
        "",
    ]
    for name, s in sorted(schemas.items()):
        n = _ts_name(name)
        desc = (s.get("description") or "").strip().splitlines()
        for d in desc[:6]:
            lines.append(f"// {d}")
        if not s.get("properties"):
            # 根级 enum / 自由标量 / 空对象
            t = _type_of(s) if ("enum" in s or s.get("type")) else None
            lines.append(f"export type {n} = {t or 'Record<string, unknown>'}")
            lines.append("")
            continue
        lines.append(f"export interface {n} {{")
        required = set(s.get("required") or [])
        for pn, p in sorted(s.get("properties", {}).items()):
            key = pn if pn.isidentifier() else json.dumps(pn)
            opt = "" if pn in required else "?"
            lines.append(f"  {key}{opt}: {_type_of(p)}")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def _gen_codes(ec: dict) -> str:
    codes: dict = ec.get("codes", {})
    str_codes = {k: v for k, v in codes.items() if not k.isdigit()}
    num_codes = {k: v for k, v in codes.items() if k.isdigit()}
    lines = [
        "// 由 scripts/gen_frontend_contract.py 从 backend/contract/error-codes.json",
        "// 生成 —— 勿手改。字符串码 = detail.code 取值面(判等用",
        "// ApiErrorCode 获得编译期拼写检查);数值码 = 平台信封商务码。",
        "",
        "export const ERROR_CODES = {",
    ]
    for k in sorted(str_codes):
        lines.append(f"  {json.dumps(k)}: true,")
    lines.append("} as const")
    lines.append("")
    lines.append("export type ApiErrorCode = keyof typeof ERROR_CODES")
    lines.append("")
    lines.append("export const NUMERIC_ERROR_CODES = {")
    for k in sorted(num_codes, key=int):
        name = num_codes[k].get("name") or f"CODE_{k}"
        lines.append(f"  {k}: {json.dumps(name)},")
    lines.append("} as const")
    lines.append("")
    lines.append("export type NumericApiErrorCode = keyof typeof NUMERIC_ERROR_CODES")
    lines.append("")
    return "\n".join(lines)


def _write_if_changed(path: Path, content: str) -> bool:
    """落盘(内容相同不动 mtime);返回是否写入。"""
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def main(check: bool) -> int:
    spec = json.loads(_OPENAPI.read_text(encoding="utf-8"))
    ec = json.loads(_ERROR_CODES.read_text(encoding="utf-8"))
    targets = [
        (_OUT_OPENAPI, _gen_openapi(spec)),
        (_OUT_CODES, _gen_codes(ec)),
    ]
    if check:
        drift = [str(p) for p, c in targets
                 if not p.exists() or p.read_text(encoding="utf-8") != c]
        if drift:
            print("[gen-frontend-contract] FAIL: 生成物与契约快照漂移:")
            for d in drift:
                print(f"  {d}")
            print("重跑: python scripts/gen_frontend_contract.py")
            return 1
        print("[gen-frontend-contract] check: 生成物与契约快照一致")
        return 0
    for p, c in targets:
        wrote = _write_if_changed(p, c)
        print(f"{'gen' if wrote else 'noop'}: {p.relative_to(_REPO)}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="与盘上生成物比对,漂移非零退出(守卫位)")
    args = ap.parse_args()
    raise SystemExit(main(args.check))
