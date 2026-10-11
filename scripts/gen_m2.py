"""M2 生成脚本（M2 方案 v2.4 §9.4；开发计划 T1.3 / 步骤 2）。

子命令::

    gen    导出交换形态 → 入库 ``selfdescribe/m2.schema.json`` → 生成三份
           运行形态（执行器 ``gimbal/schema/_m2.py``、平台后端
           ``app/schemas/_m2.py``、前端 ``src/types/m2.ts``）→ 运行
           ``gimbal ext list --json`` 写 ``selfdescribe/executor_ext.json``
           → M2 信封对象写入构件池并提交构件分支（``plate/artifacts``，
           版本模型 v1.4 3.6 的第二个写入方；本地演练目录只写盘不提交）
    check  在临时目录重做 gen，与入库文件逐字节比对——任一不同即非零
           退出（CI 漂移守卫；envelope 提交不在 check 面）
    compat --base <git ref>
           取基线的 ``m2.schema.json`` 与当前比对：出现删除字段、收紧
           类型、新增必填项、枚举删值等不兼容变化而 ``M2_GENERATION``
           未递增时非零退出

生成参数（§4.2 G1–G7）固定写在脚本里，不依赖调用者传参（Q8：工具为
开发依赖，版本锁定在 ``pyproject.toml [dev]``）。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SELFDESCRIBE = REPO / "src" / "gimbal_plate" / "selfdescribe"
SCHEMA_JSON = SELFDESCRIBE / "m2.schema.json"
EXT_JSON = SELFDESCRIBE / "executor_ext.json"
EXECUTOR_M2 = REPO / "src" / "gimbal" / "schema" / "_m2.py"
PLATFORM_M2 = (REPO / "src" / "gimbal-platform" / "backend" / "app"
               / "schemas" / "_m2.py")
FRONTEND_TS = (REPO / "src" / "gimbal-platform" / "frontend" / "src"
               / "types" / "m2.ts")

ALL_TARGETS = ("schema", "envelope", "ext", "py", "ts")

# datamodel-code-generator 参数（附录 A 定稿；G7 手写 RunUnion 追加在生成物后）
_PY_GEN_ARGS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--collapse-root-models",               # G1 联合不包装
    "--strict-nullable",                    # G2 可空性严格
    "--use-subclass-enum",                  # G3 枚举基类 (str, Enum)
    "--output-datetime-class", "datetime",  # G4/M7
    "--set-default-enum-member",            # G5 缺省枚举成员
    # 目标版本钉死 3.12:0.28.5 不认识更新的解释器版本(本机 3.14 会
    # ValueError: '3.14' is not a valid PythonVersion),产物本就按
    # 3.12 语法生成,与运行解释器解耦。
    "--target-python-version", "3.12",
    # G6（E7 清单 → Literal）本版工具只有 all/one 语义且 all 会把全部
    # 枚举降为 Literal、丢成员名（E3 失效）——先保 E3，枚举一律 Enum 类；
    # 升级工具版本后再按 literal_fields 清单收紧。
    "--disable-timestamp",
]

G7_RUNION = '''

# G7（§4.2）：顶层判别联合——生成器会把它包成 RootModel，手写之。
RunUnion = Annotated[Union[Scenario, SuiteGraph], Field(discriminator="kind")]

# ── 手写导出面（Q19：导出名与被删除的子模块一致）─────────────────
ResourceUnion = Annotated[Union[Mock, File], Field(discriminator="kind")]
StrategyUnion = Annotated[Union[Extract, Assign, Assertion], Field(discriminator="kind")]
TimePolicyUnion = Annotated[Union[TimeoutPolicy, RecordPolicy], Field(discriminator="kind")]
RequestUnion = Request
StepUnion = Step
SetupUnion = Setup
TeardownUnion = Teardown
SubscribeSpec = list[SubscribeRule]


class Resource(BaseModel):
    """资源基类（生成器摊平了继承；此处保类型名，判别走 ResourceUnion）。"""
    name: str


class TimePolicy(BaseModel):
    """时间策略基类（同上，保类型名）。"""


class StrategyBase(BaseModel):
    """策略公共字段基类（类型注解用；判别与执行走 StrategyUnion）。"""
    name: Optional[str] = None
    phase: Optional[StrategyPhase] = None
    order: int = 0
    enabled: bool = True
    onFailure: FailurePolicy = FailurePolicy.ABORT
    timeout: Optional[float] = None
    tags: List[str] = []


# Step 便捷属性（执行器代码引用,Q19 导出面保持行为等价）
@property
def _step_call_protocol(self) -> str:
    return self.call.protocol

Step.call_protocol = _step_call_protocol


# ── 构建身份（M2 §5.1 代际门：这份生成物按哪份 M2 构建）─────────
M2_HASH = "{m2_hash}"
M2_GENERATION = {m2_generation}
'''

_CURRENT_EXPORT = None      # 进程级导出缓存（gen/check 同进程复用）


def _rel(p: Path) -> str:
    try:
        return str(p)
    except ValueError:
        return str(p)


def _die(msg: str) -> int:
    print(f"gen_m2: {msg}", file=sys.stderr)
    return 1


def _export():
    global _CURRENT_EXPORT
    if _CURRENT_EXPORT is None:
        from gimbal_plate.export.m2_schema import export_m2
        _CURRENT_EXPORT = export_m2()
    return _CURRENT_EXPORT


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", **kw)


def _dump_schema(path: Path, export) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(export.schema, ensure_ascii=False, indent=1,
                   sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    return path


def _run_ext_to(path: Path) -> Path:
    """运行 ``gimbal ext list --json`` 写 C 类快照（2.1）。"""
    r = _run([sys.executable, "-m", "gimbal", "ext", "list", "--json"])
    if r.returncode != 0:
        raise RuntimeError(f"gimbal ext list 失败: {r.stderr.strip()[:200]}")
    try:
        json.loads(r.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"ext list 输出非 JSON: {e}") from e
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        r.stdout if r.stdout.endswith("\n") else r.stdout + "\n",
        encoding="utf-8", newline="\n")
    return path


def _header(export) -> str:
    return (f'"""\nM2 运行形态（生成文件，禁止手改）。\n'
            f'来源: gimbal_plate/schema → m2.schema.json\n'
            f'm2_hash: {export.m2_hash}\n'
            f'm2_generation: {export.m2_generation}\n'
            f'生成: scripts/gen_m2.py gen\n"""\n')


_FIELD_RE = re.compile(r"^(\s+)(\w+): (.+?) = Field\((.*?)\n\1\)",
                       re.S | re.M)


def _wrap_discriminated(ann: str, disc: str) -> str:
    """Union[...]（含 List/Optional/Dict 包装）→ Annotated 判别联合
    （每层包装只剥一对括号，递归处理内层）。"""
    ann = ann.strip()
    if ann.startswith("Union["):
        return f"Annotated[{ann}, Field(discriminator='{disc}')]"
    for prefix in ("Optional[List[", "List[", "Dict[str, ",
                   "Optional["):
        if ann.startswith(prefix) and ann.endswith("]"):
            inner = ann[len(prefix):-1]
            return f"{prefix}{_wrap_discriminated(inner, disc)}]"
    return f"Annotated[{ann}, Field(discriminator='{disc}')]"


def _fix_discriminators(text: str) -> str:
    """生成器怪癖修正：``Field(..., discriminator=...)`` → Annotated 形式
    （pydantic v2 只接受 Annotated[Union, Field(discriminator)]）。"""

    def repl(m: "re.Match[str]") -> str:
        indent, fname, ann, body = m.groups()
        dm = re.search(r",?\s*discriminator='(\w+)'", body)
        if not dm:
            return m.group(0)
        disc = dm.group(1)
        body2 = (body[:dm.start()] + body[dm.end():]).rstrip().rstrip(",")
        return (f"{indent}{fname}: {_wrap_discriminated(ann, disc)} "
                f"= Field({body2}\n{indent})")

    text = _FIELD_RE.sub(repl, text)
    if "Annotated[" in text and "from typing import" in text \
            and "Annotated" not in text.split("from typing import", 1)[1].split("\n", 1)[0]:
        text = text.replace("from typing import", "from typing import Annotated, ", 1)
    return text


# 0.28.5 的 PythonVersion 枚举只到 3.13,而包在 import 期按**运行解释器**
# 版本构造缺省值(model/__init__.py:17)—— 3.14+ 解释器上 import 即炸,
# 任何 CLI 参数都来不及传。前导把 version_info 封顶到 3.13 再进包,
# 产物版本仍由 --target-python-version 显式钉死(见 _PY_GEN_ARGS)。
_DMCG_PREAMBLE = (
    "import sys\n"
    "if sys.version_info[:2] > (3, 13):\n"
    # 原生类型不可实例化,用 tuple 子类保住 .major/.minor 属性访问
    "    class _VI(tuple):\n"
    "        major = property(lambda s: s[0])\n"
    "        minor = property(lambda s: s[1])\n"
    "        micro = property(lambda s: s[2])\n"
    "        releaselevel = property(lambda s: s[3])\n"
    "        serial = property(lambda s: s[4])\n"
    "    sys.version_info = _VI((3, 13, 0, 'final', 0))\n"
    "from datamodel_code_generator.__main__ import main\n"
    "sys.exit(main())\n"
)


def _gen_py(schema_path: Path, out_path: Path) -> None:
    r = _run([sys.executable, "-c", _DMCG_PREAMBLE,
              "--input", str(schema_path), "--output", str(out_path),
              *_PY_GEN_ARGS])
    if r.returncode != 0:
        raise RuntimeError(
            f"datamodel-code-generator 失败: {r.stderr.strip()[:400]}")
    export = _export()
    text = (_header(export) + _fix_discriminators(
        out_path.read_text(encoding="utf-8"))
        + G7_RUNION.format(m2_hash=export.m2_hash,
                           m2_generation=export.m2_generation))
    out_path.write_text(text, encoding="utf-8", newline="\n")


def _gen_ts(schema_path: Path, out_path: Path) -> None:
    import json as _json
    import shutil
    import subprocess as _sp
    import sys as _sys
    import tempfile as _tf

    # Any 字段(expected: Any)的空 schema 在 json-schema-to-typescript
    # 默认生成 {[k:string]:unknown};实际语义是"任意值"。
    # 方案:遍历 schema 副本的**全部** $defs,凡无类型约束(type 缺省
    # 且无 $ref/items/enum)的属性统一加 tsType:"unknown" hint——
    # 不硬编码某个模型,后续新增 Any 字段自动覆盖。
    # Dict[str,Any] 字段有 additionalProperties → 不受影响。
    # 只改生成用副本,入库的 m2.schema.json 不动(m2_hash 不变)。
    schema = _json.loads(schema_path.read_text(encoding="utf-8"))
    for defn in schema.get("$defs", {}).values():
        props = defn.get("properties") or {}
        for pname, pdef in props.items():
            if not isinstance(pdef, dict):
                continue
            has_type = ("type" in pdef or "$ref" in pdef
                        or "items" in pdef or "enum" in pdef
                        or "anyOf" in pdef or "oneOf" in pdef
                        or "allOf" in pdef or "tsType" in pdef)
            if not has_type and "additionalProperties" not in pdef:
                pdef["tsType"] = "unknown"

    # 临时副本放临时目录、文件名固定 m2.schema.json——schema 根没有
    # title,json2ts 用文件名当根类型名,随机命名(NamedTemporaryFile)
    # 会导致每次生成的根类型不同(M2Schema→Tmpxxx),CI 漂移守卫必红
    tmp_dir = _tf.mkdtemp(prefix="gen_m2_ts_")
    tmp_path = Path(tmp_dir) / "m2.schema.json"
    tmp_path.write_text(_json.dumps(schema, ensure_ascii=False),
                        encoding="utf-8")

    npx = shutil.which("npx") or "npx"
    r = _sp.run(
        [npx, "--yes", "json-schema-to-typescript",
         "--input", str(tmp_path), "--output", str(out_path)],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(REPO), shell=_sys.platform == "win32")
    import shutil as _shl
    _shl.rmtree(tmp_dir, ignore_errors=True)
    if r.returncode != 0:
        raise RuntimeError(
            "json-schema-to-typescript 失败(需 node/npx): "
            f"{r.stderr.strip()[:300]}")

    export = _export()
    out_path.write_text(
        f"/* M2 运行形态（生成文件，禁止手改）。"
        f"m2_hash: {export.m2_hash} "
        f"m2_generation: {export.m2_generation} */\n"
        + out_path.read_text(encoding="utf-8"),
        encoding="utf-8", newline="\n")


def _write_envelope(export) -> str | None:
    """M2 信封对象入构件池 + 提交构件分支（版本模型 3.6 / C1）。"""
    from gimbal_plate.release.release import (
        _commit_artifacts,
        _pool_write,
        resolve_artifacts_root,
    )

    root = resolve_artifacts_root()
    _pool_write(root, export.m2_hash, "m2", export.schema)
    return _commit_artifacts(root, f"m2@{export.m2_hash[:12]}")


def cmd_gen(targets: list[str]) -> int:
    export = _export()
    tmp = Path(tempfile.mkdtemp(prefix="gen_m2_"))
    try:
        if "schema" in targets:
            _dump_schema(SCHEMA_JSON, export)
            print(f"schema   → {_rel(SCHEMA_JSON)} "
                  f"(m2_hash={export.m2_hash[:12]}, "
                  f"gen={export.m2_generation})")
        if "ext" in targets:
            _run_ext_to(EXT_JSON)
            print(f"ext      → {_rel(EXT_JSON)}")
        if "py" in targets:
            schema_path = (SCHEMA_JSON if SCHEMA_JSON.exists()
                           else _dump_schema(tmp / "m2.schema.json", export))
            for out in (EXECUTOR_M2, PLATFORM_M2):
                out.parent.mkdir(parents=True, exist_ok=True)
                _gen_py(schema_path, out)
                print(f"py       → {_rel(out)}")
        if "ts" in targets:
            schema_path = (SCHEMA_JSON if SCHEMA_JSON.exists()
                           else _dump_schema(tmp / "m2.schema.json", export))
            FRONTEND_TS.parent.mkdir(parents=True, exist_ok=True)
            _gen_ts(schema_path, FRONTEND_TS)
            print(f"ts       → {_rel(FRONTEND_TS)}")
        if "envelope" in targets:
            commit = _write_envelope(export)
            where = (f"构件提交 {commit[:8]}" if commit
                     else "（演练目录，未提交构件分支）")
            print(f"envelope → objects/{export.m2_hash[:12]}… {where}")
    except RuntimeError as e:
        return _die(str(e))
    return 0


def cmd_check(targets: list[str]) -> int:
    """临时目录重做 gen → 与入库文件逐字节比对（漂移守卫）。"""
    check_targets = [t for t in targets if t != "envelope"]
    export = _export()
    tmp = Path(tempfile.mkdtemp(prefix="gen_m2_check_"))
    repo_files: dict[Path, Path] = {}     # 入库文件 ← 临时再生成文件
    try:
        if "schema" in check_targets:
            repo_files[SCHEMA_JSON] = _dump_schema(tmp / "m2.schema.json",
                                                   export)
        if "ext" in check_targets:
            repo_files[EXT_JSON] = _run_ext_to(tmp / "executor_ext.json")
        if "py" in check_targets:
            schema_path = _dump_schema(tmp / "py" / "m2.schema.json", export)
            for out in (EXECUTOR_M2, PLATFORM_M2):
                if not out.exists():
                    return _die(f"{_rel(out)} 不存在——先运行 gen")
                gen = tmp / "py" / out.name
                _gen_py(schema_path, gen)
                repo_files[out] = gen
        if "ts" in check_targets:
            schema_path = _dump_schema(tmp / "ts" / "m2.schema.json", export)
            gen = tmp / "ts" / "m2.ts"
            _gen_ts(schema_path, gen)
            repo_files[FRONTEND_TS] = gen
    except RuntimeError as e:
        return _die(str(e))
    drift = []
    for repo_file, regenerated in repo_files.items():
        if not repo_file.exists():
            drift.append(f"缺失: {_rel(repo_file)}")
        elif repo_file.read_bytes() != regenerated.read_bytes():
            drift.append(f"漂移: {_rel(repo_file)}")
    if drift:
        for d in drift:
            print(d, file=sys.stderr)
        return _die(f"{len(drift)} 个文件未重新生成（漂移守卫失败）")
    print(f"check 通过：{len(repo_files)} 个入库生成物与当前定义一致")
    return 0


def _load_base_schema(ref: str) -> dict | None:
    r = _run(["git", "show",
              f"{ref}:src/gimbal_plate/selfdescribe/m2.schema.json"],
             cwd=REPO)
    if r.returncode != 0:
        if "exists on disk, but not in" in r.stderr:
            return None      # 基线还没有 M2 Schema(首次引入)→ 跳过 compat
        raise RuntimeError(
            f"取基线 m2.schema.json 失败({ref}): {r.stderr.strip()[:150]}")
    return json.loads(r.stdout)


def _base_generation(ref: str) -> int:
    """基线代际：从 git 历史读 ``_next.__init__`` 的 M2_GENERATION。"""
    r = _run(["git", "show",
              f"{ref}:src/gimbal_plate/schema/__init__.py"], cwd=REPO)
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if line.startswith("M2_GENERATION"):
                try:
                    return int(line.split("=", 1)[1].strip())
                except ValueError:
                    break
    return 1


def _find_incompatibilities(base: dict, cur: dict) -> list[str]:
    """P8 口径：删除字段 / 收紧类型 / 新增必填 / 枚举删值 = 不兼容。"""
    problems: list[str] = []
    base_defs = base.get("$defs", {})
    cur_defs = cur.get("$defs", {})
    for name, b in base_defs.items():
        c = cur_defs.get(name)
        if c is None:
            problems.append(f"$defs.{name} 整体消失")
            continue
        b_props = b.get("properties", {})
        c_props = c.get("properties", {})
        for p in b_props:
            if p not in c_props:
                problems.append(f"$defs.{name}.{p} 被删除")
        for req in c.get("required", []):
            if req not in b.get("required", []) and req in b_props:
                problems.append(f"$defs.{name}.{req} 变为必填")
        for p, bspec in b_props.items():
            cspec = c_props.get(p)
            if cspec is None:
                continue
            b_enum, c_enum = bspec.get("enum"), cspec.get("enum")
            if b_enum and c_enum:
                removed = [v for v in b_enum if v not in c_enum]
                if removed:
                    problems.append(f"$defs.{name}.{p} 枚举删值 {removed}")
            b_type, c_type = bspec.get("type"), cspec.get("type")
            if b_type and c_type and b_type != c_type:
                problems.append(f"$defs.{name}.{p} 类型 {b_type}→{c_type}")
    return problems


def cmd_compat(base_ref: str) -> int:
    export = _export()
    try:
        base = _load_base_schema(base_ref)
    except RuntimeError as e:
        return _die(str(e))
    if base is None:
        print(f"compat 跳过：基线 {base_ref} 尚无 m2.schema.json(首次引入)")
        return 0
    problems = _find_incompatibilities(base, export.schema)
    if not problems:
        print(f"compat 通过：对 {base_ref} 无不兼容变化")
        return 0
    if export.m2_generation <= _base_generation(base_ref):
        for p in problems:
            print(p, file=sys.stderr)
        return _die(
            f"出现 {len(problems)} 处不兼容变化而 M2_GENERATION 未递增"
            f"（当前 {export.m2_generation}）——递增 _next.M2_GENERATION "
            "并提供迁移函数（M2 §5.2）")
    # §5.2:代际递增时迁移函数必须存在且对语料跑通
    base_gen = _base_generation(base_ref)
    if export.m2_generation > base_gen + 1:
        return _die(
            f"M2_GENERATION 从 {base_gen} 直接跳到 "
            f"{export.m2_generation}——须逐代递增,每代各带迁移函数")
    from gimbal_plate.schema.migrate import _migrate_map
    if base_gen not in _migrate_map:
        return _die(
            f"代际 {base_gen} → {base_gen + 1} 的迁移函数未注册"
            "（schema/migrate.py 的 @register_migrate({base_gen})）")
    print(f"compat 通过：{len(problems)} 处不兼容变化已随代际 "
          f"{export.m2_generation} 递增（迁移函数 gen{base_gen} 已注册）")
    return 0


def migrate_definition(defn: dict) -> dict:
    """已定迁移项（M2 §8 / 步骤 0 清单）：``api`` → ``call``、
    ``view_hints.endpoint_id`` → ``step.endpoint``、剥平台扩展字段
    （field_states / steps[].id / meta.scenarioId / meta.updateTime）。
    其余保持原样（M6 的 Meta 默认值与 UserCredential 兼容面由模型吸收）。"""
    import copy

    d = copy.deepcopy(defn)
    meta = d.get("meta") or {}
    meta.pop("scenarioId", None)
    meta.pop("updateTime", None)
    d["meta"] = meta
    steps = []
    for st in d.get("steps") or []:
        if not isinstance(st, dict):
            steps.append(st)
            continue
        call = st.get("call")
        if call is None:
            call = st.get("api") or {}          # 旧形态（api 键）
        st.pop("api", None)                     # 混合形态的遗留键
        if isinstance(call, dict):
            if call.get("kind") == "api":       # 旧形态 kind 同步改写
                call["kind"] = "call"
            call.setdefault("protocol", "http")  # 存量缺 protocol（必填化前）
            vh = call.pop("view_hints", None) or {}
            eid = vh.get("endpoint_id") if isinstance(vh, dict) else None
            if eid:
                st["endpoint"] = str(eid)
        st.pop("field_states", None)
        st.pop("id", None)
        st["call"] = call
        steps.append(st)
    d["steps"] = steps
    return d


def cmd_roundtrip(corpus_dir: Path) -> int:
    """步骤 2 验收门：步骤 0 语料「迁移 → _m2 校验 → dump → 再校验 →
    对象级一致」。逐份报告，失败列出首个校验错误（= 新的迁移规则线索）。"""
    src = str(REPO / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import gimbal.schema._m2 as m2
    files = sorted(corpus_dir.glob("*.json"))
    if not files:
        return _die(f"语料目录为空: {corpus_dir}")
    ok = fail = 0
    for f in files:
        payload = json.loads(f.read_text(encoding="utf-8"))
        defn = payload.get("definition") or payload
        try:
            migrated = migrate_definition(defn)
            obj = m2.Scenario.model_validate(migrated)
            redumped = obj.model_dump(mode="json")
            again = m2.Scenario.model_validate(redumped)
            if again != obj:
                raise ValueError("再校验对象不一致")
            ok += 1
        except Exception as e:  # noqa: BLE001 — 报告即产出
            fail += 1
            print(f"FAIL {f.name}: {str(e)[:160]}", file=sys.stderr)
    print(f"roundtrip: {ok} 一致 / {fail} 失败（共 {len(files)} 份）")
    return 0 if fail == 0 else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("gen", help="导出+生成+快照+信封提交")
    p_gen.add_argument("--targets", default=",".join(ALL_TARGETS),
                       help="逗号分隔：schema,envelope,ext,py,ts")
    p_check = sub.add_parser("check", help="漂移守卫（临时重做 gen 比对）")
    p_check.add_argument("--targets", default="schema,ext,py",
                         help="默认不含 envelope（提交不在 check 面）"
                              "/ts（需 node，CI 显式开启）")
    p_compat = sub.add_parser("compat", help="不兼容变更守卫")
    p_compat.add_argument("--base", required=True)
    p_rt = sub.add_parser("roundtrip", help="步骤 0 语料往返验收")
    p_rt.add_argument("--corpus", required=True, help="语料目录(*.json)")
    args = ap.parse_args(argv)
    if args.cmd == "compat":
        return cmd_compat(args.base)
    if args.cmd == "roundtrip":
        return cmd_roundtrip(Path(args.corpus))
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in ALL_TARGETS]
    if bad:
        return _die(f"未知 targets: {bad}")
    if args.cmd == "gen":
        return cmd_gen(targets)
    return cmd_check(targets)


if __name__ == "__main__":
    raise SystemExit(main())
