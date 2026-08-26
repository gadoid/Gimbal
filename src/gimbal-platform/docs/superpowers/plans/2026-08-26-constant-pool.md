# 常量池(编排页常驻 Panel + 管理页 + plate generator dim)Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 内网测试平台新增"常量池":plate 把引擎 9 个生成器 spec 镜像成 `generators` 语法 dim → platform 代理目录 + per-user 常量条目 CRUD → 前端编排四页右栏常驻 Panel(复制/插入/播种 config.vars)+ 独立管理页(目录文档 + 条目维护)。

**Architecture:** 三层。① gimbal-plate:新增 `schema/generator.py`(引擎 spec 手工镜像)+ `http/generator_dim.py`(JSON-Schema 内省出 kind 参数描述符),注册为第 9 个 dim —— 走既有通用 dim 路由,**零新路由代码**;② platform 后端:`constant_entries` 表(owner 隔离 CRUD,409 冲突字典 detail)+ `generator-catalog` 代理(克隆 strategy_catalog);③ 前端:Pinia store 共享条目/目录(独立降级),`ConstantPoolPanel` 双挂载(步骤 0-2 右栏 rail / 步骤 3 Canvas col-info 之下),`useInsertTarget` DOM 焦点跟踪插入 + 快照播种 `config.vars[name] ??= spec`,管理页 `/constants`。引擎 `src/gimbal` 与 RunDialog **零改动**。

**Tech Stack:** FastAPI + SQLAlchemy async + Pydantic v2(plate 与 platform backend);Vue 3 + Element Plus + Pinia + @vue/test-utils/vitest(jsdom);pytest(fastapi TestClient / httpx ASGITransport + MockTransport)。

**Spec:** `src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md`(本计划从 spec 取证;执行者应同时读 spec 对应章节)

> **实现进度(2026-08-27 更新):已全部完成并合并。**
>
> - T1-T10 全部落地,合并入 `strbody_avaliable` 并推送远端(origin/strbody_avaliable)。
> - 验证:plate 436 例 / backend 268 例 / frontend 304 例全绿,`vue-tsc --noEmit` 0 错。
> - 后续 UI 微调(超出本计划范围,同一分支追加合并):分支 `constant-pool-ui-polish`
>   614c321 → e93f741 → f4c8d61 — 面板升级白卡外壳(`.c-card` 配方 + 分隔线卡头),
>   Canvas col-info 拆分为三张独立卡(step 信息 / 变量注册表 / 常量池;VRP 改常驻,
>   新增 F12b 钉住拆分),①-③ 页 rail 与主卡间隔收敛为精确 16px
>   (`with-rail` 限宽 1596px 居中,消除 c-page 居中产生的 ~54px 死白),
>   `/constants` 管理页参数表改发丝线 + kind-chip 靛蓝选中态。

## Global Constraints

- 平台**绝不求值、不造新模板语法**:插入产物仅三种引擎原生形态 —— 字面值文本 / `${var.x}` 引用 / config.vars 内的 spec 声明;求值唯一发生在引擎 preprocess(PLATFORM_REQUIREMENTS L242:平台只写配置阶段内容)。
- 生成器播种**快照语义**:`config.vars[name] ??= spec` — 已存在不覆盖(提示后仅插引用);播种后池子改动不回灌(同凭证池导入先例)。
- plate 新模块依赖方向 **http → schema**(不触碰 no-reverse-import 锁,`tests/plate/test_v3_no_reverse_import.py` 必须保持绿);引擎 `src/gimbal/generator/specs.py` 是执行权威源,plate 镜像手工同步 + 引擎对照测试防漂移。
- 常量条目 **per-user owner 隔离**:跨 owner 一律 404;`UniqueConstraint(owner_id, name)`;name 正则 `^[A-Za-z0-9_]{1,64}$`;literal 的 `value` 仅 str/int/float/bool,generator 的 `spec` 必须含非空字符串 `kind`;value/spec 互斥;`entry_kind` 创建后不可变。
- 后端**不校验 generator 参数合法性**(目录描述符驱动前端表单校验,引擎 preprocess 兜底)。
- 前端遵循既有惯例:api 层 interface + `http.get<T>(...).then(r => r.data)`、store 用 `useSetStatus`、panel 纯 props(VariableRegistryPanel 先例)、CSS 变量 `--c-*` 系列、`--font-mono`。
- 回归底线:plate / backend / vitest 现有套件**只增不减全绿**;`npx vue-tsc --noEmit` 绿。
- 测试命令(相对仓库根 `d:\Gimbal\Gimbal`):
  - plate: `python -m pytest tests/plate/test_generator_dim.py -v`(PYTHONPATH 由 tests/plate/conftest.py 注入)
  - plate 全量回归: `python -m pytest tests/plate -q`
  - backend: `cd src/gimbal-platform/backend && python -m pytest tests/test_constants_api.py tests/test_generator_catalog_proxy.py -v`
  - backend 全量回归: `cd src/gimbal-platform/backend && python -m pytest tests -q`
  - frontend 单测: `cd src/gimbal-platform/frontend && npx vitest run src/<路径>`
  - frontend 全量回归: `cd src/gimbal-platform/frontend && npx vitest run`
  - 类型检查: `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit`
- 每任务一个 commit;commit message 前缀 `feat(...)`/`test(...)`/`refactor(...)`,末尾加 Co-Authored-By: Claude <noreply@anthropic.com>。
- 所有新文件用 LF、UTF-8,Python 文件带 `from __future__ import annotations`。

## File Structure(全部新建/修改文件一览)

| 层 | 文件 | 职责 | 任务 |
|---|---|---|---|
| plate | `src/gimbal-plate/gimbal_plate/schema/generator.py` **(建)** | 引擎 9 个生成器 spec 的 1:1 镜像(字段/约束/默认值) | T1 |
| plate | `src/gimbal-plate/gimbal_plate/http/generator_dim.py` **(建)** | `GeneratorIndex`(BaseIndex)+ kind 元数据 + JSON-Schema 内省 → 参数描述符 | T1 |
| plate | `src/gimbal-plate/gimbal_plate/http/views.py` **(改,文件末尾追加)** | `GeneratorParamDesc` / `GeneratorKindView` / `GeneratorKindDetailView` | T1 |
| plate | `src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py` **(改,strategy 注册块之后)** | 注册第 9 个 dim `"generators"` | T1 |
| plate | `tests/plate/test_generator_dim.py` **(建)** | P1-P7(含引擎对照防漂移) | T1 |
| backend | `backend/app/models/constant_entry.py` **(建)** | `ConstantEntry` ORM 模型 | T2 |
| backend | `backend/app/models/__init__.py` **(改)** | 注册 `ConstantEntry` | T2 |
| backend | `backend/app/schemas/constants.py` **(建)** | Out/Create/Patch Pydantic schemas + 校验 | T2 |
| backend | `backend/app/routers/constants.py` **(建)** | per-user CRUD(409 字典 detail) | T2 |
| backend | `backend/app/main.py` **(改,include_router 区)** | 挂载 constants(T2)/ generator_catalog(T3) | T2/T3 |
| backend | `backend/tests/test_constants_api.py` **(建)** | B1-B9 | T2 |
| backend | `backend/app/routers/generator_catalog.py` **(建)** | plate `/api/generators*` 代理 | T3 |
| backend | `backend/tests/test_generator_catalog_proxy.py` **(建)** | B10-B11(代理三态) | T3 |
| frontend | `src/utils/clipboard.ts` **(建)** | `copyText` 双通道剪贴板 | T4 |
| frontend | `src/stores/scenario-draft.ts` **(改,copyJson)** | copyJson 改用 copyText | T4 |
| frontend | `src/utils/__tests__/clipboard.test.ts` **(建)** | 双通道用例 | T4 |
| frontend | `src/composables/useInsertTarget.ts` **(建)** | 焦点跟踪 + appendValue + provide/inject | T5 |
| frontend | `src/composables/__tests__/useInsertTarget.test.ts` **(建)** | F1-F3 | T5 |
| frontend | `src/types/constants.ts` **(建)** | ConstantEntry / GeneratorKindView / Detail | T6 |
| frontend | `src/api/constants.ts` **(建)** | `/api/constants` CRUD 包装 | T6 |
| frontend | `src/api/generator_catalog.ts` **(建)** | `/api/generator-catalog` 目录包装 | T6 |
| frontend | `src/stores/constants.ts` **(建)** | 条目 + 目录共享 store(独立降级) | T6 |
| frontend | `src/stores/__tests__/constants.test.ts` **(建)** | F19(去重/乐观更新) | T6 |
| frontend | `src/components/composer/ConstantPoolPanel.vue` **(建)** | 只读面板(双载荷行) | T7 |
| frontend | `src/components/composer/__tests__/ConstantPoolPanel.test.ts` **(建)** | F4-F8 | T7 |
| frontend | `src/utils/pool-var.ts` **(建)** | `seedPoolVarIntoDefinition` 纯函数(`??=`) | T8 |
| frontend | `src/utils/__tests__/pool-var.test.ts` **(建)** | F10(快照语义) | T8 |
| frontend | `src/views/CaseComposer.vue` **(改)** | body-split rail + provideInsertTarget + seedPoolVar | T8 |
| frontend | `src/components/composer/CaseComposerCanvas.vue` **(改)** | col-info 常驻挂载 + seedVar 转发 | T8 |
| frontend | `src/components/composer/__tests__/CaseComposerCanvas.test.ts` **(改,追加)** | F12-F13 | T8 |
| frontend | `src/views/__tests__/CaseComposer.poolrail.test.ts` **(建)** | F9/F11 | T8 |
| frontend | `src/views/ConstantsPool.vue` **(建)** | 管理页(目录卡片 + CRUD 弹框) | T9 |
| frontend | `src/views/__tests__/ConstantsPool.test.ts` **(建)** | F14-F18 | T9 |
| frontend | `src/router/index.ts` **(改)** | `/constants` 路由 | T10 |
| frontend | `src/components/TopNav.vue` **(改)** | 常量池入口 | T10 |
| frontend | `src/components/__tests__/TopNav.pool.test.ts` **(建)** | F20 | T10 |

依赖顺序:T1 → T3(代理依赖 plate dim 存在才有真实信封;测试用 MockTransport 不依赖 T1 运行时,但语义上 T1 先行);T2 独立;T4-T6 相互独立(前端基建);T7 依赖 T4/T5/T6;T8 依赖 T6/T7;T9 依赖 T6;T10 依赖 T9。**推荐按编号顺序执行。**

---

### Task 1: plate `generators` 语法 dim(镜像 schema + 内省 + 注册)

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/schema/generator.py`
- Create: `src/gimbal-plate/gimbal_plate/http/generator_dim.py`
- Modify: `src/gimbal-plate/gimbal_plate/http/views.py`(文件末尾追加,策略视图之后)
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py`(strategy 注册块之后)
- Test: `tests/plate/test_generator_dim.py`

**Interfaces:**
- Consumes: 既有 `BaseIndex` 契约(`gimbal_plate/http/grammar.py`:`list_global/list_for_system/get/to_view`)、`DimSpec(name/index/view_factory/full_view_factory/actions)`、通用 dim 路由(`GET /api/{dim}` → `{ok,dim,data:{items,total}}`;`GET /api/{dim}/{id}/full` → `{ok,dim,data:{item}}`;404 code=`dim_item_not_found`)、`register_fin_dims` 唯一装配入口(`tests/plate/conftest.py` 的 `fresh_registry`/`http_client` fixture 已覆盖)。
- Produces(Task 3 代理与 Task 6 前端类型依赖的精确形状):
  - `GET /api/generators` → `data.items: [{kind: str, summary: str}]`(light view 仅两键),`total=9`
  - `GET /api/generators/{kind}/full` → `data.item: {kind, summary, description, params: [{name, type, required, default, enum, min, max, description}], example}`(`exclude_none` 后无 None 键)
  - `gimbal_plate.http.generator_dim.GeneratorIndex`、`_KIND_MODELS`、`_descriptor_for`

**引擎事实锚点**(源:`src/gimbal/generator/specs.py`,`build_default_registry()` 注册 9 kind):全部 spec `extra="forbid"`、全部字段有默认值(⇒ 参数 required 恒 false)、`sequence` 是 `seq` 的历史别名(SeqSpec 内 validator 规范化,目录只列规范名)。9 kind 字段:
- `uuid`:无参数
- `random_str`:`length int=8 (1≤x≤1024)`、`charset Literal[alpha,digit,alnum]=alnum`
- `random_int`:`min int=0`、`max int=100`
- `random_decimal`:`min float=0.0`、`max float=100.0`、`places int=2 (0≤x≤10)`
- `timestamp`:`format str=iso`、`offset_seconds int=0`、`base str|None=None`、`base_format str|None=None`
- `now`:`format Literal[epoch,iso,compact]=iso`
- `seq`:`prefix str=""`、`width int=6 (1≤x≤20)`、`start int=1`
- `random_decorated`:`length int=8 (1≤x≤1024)`、`charset Literal[alpha,digit,alnum]=alnum`、`head str=""`、`tail str=""`、`separator str=""`
- `time_offset`:`unit Literal[milliseconds,seconds,minutes,hours,days,weeks,months,years]=seconds`、`value int=0`、`direction Literal[future,past]=future`、`base str|None=None`、`base_format str|None=None`

- [x] **Step 1.1: 写失败测试(全文)**

创建 `tests/plate/test_generator_dim.py`:

```python
"""generators dim HTTP 面单测 —— M6 通用路由上的第 9 个(语法级)dim。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §plate
全部走既有通用 handler(list/full),零新路由代码;钉死 9 个规范 kind
清单(P1)与"描述符由镜像 schema 内省派生"(P6);P7 直接 import 引擎
specs 对照,防 plate 镜像与引擎漂移(双权威手工同步的失效触发器)。
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from gimbal_plate.http.generator_dim import _KIND_MODELS, _descriptor_for

GENERATOR_KINDS = [
    "uuid", "random_str", "random_int", "random_decimal",
    "timestamp", "now", "seq", "random_decorated", "time_offset",
]


def _ok(body: dict) -> None:
    assert body["ok"] is True
    assert body["dim"] == "generators"


def test_p1_list_returns_nine_canonical_kinds(http_client: TestClient) -> None:
    """P1: light list 恰好 9 个规范 kind;light view 仅 kind/summary 两键。"""
    resp = http_client.get("/api/generators")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    items = body["data"]["items"]
    assert body["data"]["total"] == 9
    kinds = {it["kind"] for it in items}
    assert kinds == set(GENERATOR_KINDS)  # sequence 别名不单列
    for it in items:
        assert set(it.keys()) == {"kind", "summary"}


def test_p2_full_random_str_param_descriptors(http_client: TestClient) -> None:
    """P2: random_str/full 参数描述符含 type/default/min/max/enum。"""
    resp = http_client.get("/api/generators/random_str/full")
    assert resp.status_code == 200
    body = resp.json()
    _ok(body)
    item = body["data"]["item"]
    assert item["kind"] == "random_str"
    assert item["example"]["kind"] == "random_str"
    params = {p["name"]: p for p in item["params"]}
    assert params["length"]["type"] == "integer"
    assert params["length"]["default"] == 8
    assert params["length"]["min"] == 1
    assert params["length"]["max"] == 1024
    assert params["charset"]["enum"] == ["alpha", "digit", "alnum"]
    assert params["charset"]["default"] == "alnum"


def test_p3_full_time_offset_unit_enum(http_client: TestClient) -> None:
    """P3: Literal 八值枚举 + Optional(str|None)字段的 anyOf 处理。"""
    resp = http_client.get("/api/generators/time_offset/full")
    assert resp.status_code == 200
    params = {p["name"]: p for p in resp.json()["data"]["item"]["params"]}
    assert params["unit"]["enum"] == [
        "milliseconds", "seconds", "minutes", "hours",
        "days", "weeks", "months", "years",
    ]
    assert params["unit"]["default"] == "seconds"
    assert params["direction"]["enum"] == ["future", "past"]
    assert params["value"]["type"] == "integer"
    # base 是 str|None —— anyOf 取非 null 分支 → string
    assert params["base"]["type"] == "string"


def test_p4_uuid_has_no_params(http_client: TestClient) -> None:
    """P4: uuid 无参数(kind 之外零字段)。"""
    resp = http_client.get("/api/generators/uuid/full")
    assert resp.status_code == 200
    item = resp.json()["data"]["item"]
    assert item["params"] == []
    assert item["description"]


def test_p5_unknown_kind_404(http_client: TestClient) -> None:
    """P5: 未知 kind(含别名 sequence)404 dim_item_not_found。"""
    for bad in ("nope", "sequence"):
        resp = http_client.get(f"/api/generators/{bad}/full")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "dim_item_not_found"


def test_p6_descriptors_match_mirror_schema() -> None:
    """P6: 描述符由镜像 schema 内省派生 —— 每个镜像字段都有参数且默认值一致。"""
    for kind, model in _KIND_MODELS.items():
        d = _descriptor_for(kind)
        assert d is not None
        params = {p["name"]: p for p in d.params}
        for fname, finfo in model.model_fields.items():
            if fname == "kind":
                continue
            assert fname in params, f"{kind}.{fname} 丢失参数描述符"
            assert params[fname]["default"] == finfo.default


def test_p7_mirror_matches_engine_specs() -> None:
    """P7: 引擎对照防漂移 —— kind 清单/字段集/默认值与引擎 specs 一致。"""
    engine_root = Path(__file__).resolve().parents[2] / "src" / "gimbal"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    from gimbal.generator.registry import build_default_registry  # noqa: PLC0415

    reg = build_default_registry()
    engine_kinds = sorted(reg.generators.keys()) if hasattr(reg, "generators") else None
    # registry 无公开 kind 表时退化到 specs 模块符号表
    if engine_kinds is None:
        import gimbal.generator.specs as engine_specs  # noqa: PLC0415

        engine_kinds = sorted(
            n[:-4].lower() for n in dir(engine_specs) if n.endswith("Spec")
        )
    assert engine_kinds == sorted(GENERATOR_KINDS)

    import gimbal.generator.specs as engine_specs  # noqa: PLC0415

    for kind, mirror_model in _KIND_MODELS.items():
        engine_model = getattr(engine_specs, f"{type(mirror_model).__name__}")
        assert engine_model is not None
        mirror_fields = {
            n: f.default for n, f in mirror_model.model_fields.items() if n != "kind"
        }
        engine_fields = {
            n: f.default for n, f in engine_model.model_fields.items() if n != "kind"
        }
        assert mirror_fields == engine_fields, f"{kind} 镜像默认值与引擎漂移"
```

注意 P7 中 `reg.generators` 属性名以 `src/gimbal/generator/registry.py` 实际实现为准 —— 执行此 Step 前先打开该文件确认 registry 暴露 kind 集合的属性;若两者都不适用,保留符号表退化分支即可(它已能钉死清单)。

- [x] **Step 1.2: 跑测试确认失败**

Run: `python -m pytest tests/plate/test_generator_dim.py -v`
Expected: 全部 7 例 FAIL/ERROR,首因为 `ModuleNotFoundError: No module named 'gimbal_plate.http.generator_dim'`

- [x] **Step 1.3: 写镜像 schema**

创建 `src/gimbal-plate/gimbal_plate/schema/generator.py`:

```python
"""plate 侧生成器 spec 镜像 —— 常量池目录的内省源(2026-08-26)。

权威源约定(双权威手工同步,同 strategy):
引擎 ``src/gimbal/generator/specs.py`` 是执行权威源;本文件是其字段/
约束/默认值的 1:1 镜像,仅供 ``http/generator_dim.py`` 内省出 kind
参数描述符 —— plate 永不执行生成器,生成器实例照旧存在 scenario 的
``config.vars`` 里。引擎变更时手工同步本文件;
``tests/plate/test_generator_dim.py::test_p7_mirror_matches_engine_specs``
是失效触发器。

镜像规则:
- 只镜像字段/类型/约束/默认值,不镜像 validator(SeqSpec 的
  ``sequence`` 别名规范化属引擎行为,目录只列规范 kind);
- ``extra="forbid"`` 与引擎一致(未知参数引擎侧报错,目录如实反映);
- 描述文案是 plate 侧说明,不追求与引擎 docstring 逐字一致。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UuidSpec(BaseModel):
    """uuid — 32 位十六进制 UUID 字符串(无参数)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["uuid"]


class RandomStrSpec(BaseModel):
    """random_str — 定长随机字符串(charset: alpha/digit/alnum)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_str"]
    length: int = Field(default=8, ge=1, le=1024, description="随机串长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(
        default="alnum", description="字符集"
    )


class RandomIntSpec(BaseModel):
    """random_int — [min, max] 闭区间随机整数。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_int"]
    min: int = Field(default=0, description="下界(含)")
    max: int = Field(default=100, description="上界(含)")


class RandomDecimalSpec(BaseModel):
    """random_decimal — [min, max] 闭区间随机小数。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_decimal"]
    min: float = Field(default=0.0, description="下界(含)")
    max: float = Field(default=100.0, description="上界(含)")
    places: int = Field(default=2, ge=0, le=10, description="小数位数")


class TimestampSpec(BaseModel):
    """timestamp — 格式化时间戳(可偏移/可锚定基准)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["timestamp"]
    format: str = Field(default="iso", description="输出格式,iso=ISO-8601")
    offset_seconds: int = Field(default=0, description="相对当前时间的偏移秒数")
    base: str | None = Field(default=None, description="自定义基准时间")
    base_format: str | None = Field(default=None, description="基准时间的解析格式")


class NowSpec(BaseModel):
    """now — 当前时间(epoch 秒 / iso / compact)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["now"]
    format: Literal["epoch", "iso", "compact"] = Field(
        default="iso", description="输出格式"
    )


class SeqSpec(BaseModel):
    """seq — 执行内自增序号(引擎历史别名 sequence 规范化为 seq)。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["seq"]
    prefix: str = Field(default="", description="序号前缀")
    width: int = Field(default=6, ge=1, le=20, description="零填充宽度")
    start: int = Field(default=1, description="起始值")


class RandomDecoratedSpec(BaseModel):
    """random_decorated — head + 随机串 + tail,段间 separator 连接。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["random_decorated"]
    length: int = Field(default=8, ge=1, le=1024, description="随机段长度")
    charset: Literal["alpha", "digit", "alnum"] = Field(
        default="alnum", description="随机段字符集"
    )
    head: str = Field(default="", description="头部装饰段")
    tail: str = Field(default="", description="尾部装饰段")
    separator: str = Field(default="", description="段间连接符")


class TimeOffsetSpec(BaseModel):
    """time_offset — 以 unit 粒度向 direction 偏移 value 步的时间戳。"""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["time_offset"]
    unit: Literal[
        "milliseconds", "seconds", "minutes", "hours",
        "days", "weeks", "months", "years",
    ] = Field(default="seconds", description="偏移单位")
    value: int = Field(default=0, description="偏移量")
    direction: Literal["future", "past"] = Field(
        default="future", description="偏移方向"
    )
    base: str | None = Field(default=None, description="自定义基准时间")
    base_format: str | None = Field(default=None, description="基准时间的解析格式")
```

- [x] **Step 1.4: 写 dim 模块**

创建 `src/gimbal-plate/gimbal_plate/http/generator_dim.py`:

```python
"""generators dim —— 生成器语法的服务化(第 9 个 dim,语法级)。

对齐 strategy_dim 先例(2026-08-17):items 不是数据实例,而是从
plate 镜像 spec(``schema/generator.py``)内省出的 kind 描述符 ——
回答"生成器有哪些 kind、每个 kind 有哪些参数"。生成器实例照旧存在
scenario 的 ``config.vars`` 里,归平台/用户管;plate 只暴露语法
(结构权威源),永不执行。

权威源约定(双权威,同 strategy):引擎 ``src/gimbal/generator/specs.py``
是执行权威源;镜像手工同步,
``tests/plate/test_generator_dim.py::test_p7_mirror_matches_engine_specs``
防漂移。

依赖方向: http → schema(只读内省),不触碰 no-reverse-import 锁。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gimbal_plate.schema.generator import (
    NowSpec,
    RandomDecoratedSpec,
    RandomDecimalSpec,
    RandomIntSpec,
    RandomStrSpec,
    SeqSpec,
    TimeOffsetSpec,
    TimestampSpec,
    UuidSpec,
)

# kind 清单: 引擎 build_default_registry() 注册的 9 个规范 kind。
# ``sequence`` 是引擎侧历史别名(SeqSpec 内规范化为 seq),目录只列规范名。
_KIND_MODELS: dict[str, type] = {
    "uuid": UuidSpec,
    "random_str": RandomStrSpec,
    "random_int": RandomIntSpec,
    "random_decimal": RandomDecimalSpec,
    "timestamp": TimestampSpec,
    "now": NowSpec,
    "seq": SeqSpec,
    "random_decorated": RandomDecoratedSpec,
    "time_offset": TimeOffsetSpec,
}

# kind 元数据: (中文 summary, 说明, 示例 spec)。schema 不编码这三者,
# 在此单一维护 —— 与 strategy_dim._KIND_LABELS 同一拍板。
_KIND_META: dict[str, tuple[str, str, dict[str, Any]]] = {
    "uuid": (
        "UUID",
        "生成 32 位十六进制 UUID 字符串。无参数,声明 {\"kind\": \"uuid\"} 即可。",
        {"kind": "uuid"},
    ),
    "random_str": (
        "随机字符串",
        "按字符集生成定长随机字符串。charset: alpha=纯字母 / digit=纯数字 / alnum=字母数字。",
        {"kind": "random_str", "length": 8, "charset": "alnum"},
    ),
    "random_int": (
        "闭区间随机整数",
        "生成 [min, max] 闭区间内的随机整数。",
        {"kind": "random_int", "min": 0, "max": 100},
    ),
    "random_decimal": (
        "闭区间随机小数",
        "生成 [min, max] 闭区间内的随机小数;places 控制小数位数(0-10)。",
        {"kind": "random_decimal", "min": 0.0, "max": 100.0, "places": 2},
    ),
    "timestamp": (
        "格式化时间戳",
        "按 format 输出时间(默认 iso=ISO-8601);offset_seconds 相对当前时间偏移;"
        "base/base_format 可锚定自定义基准时间。",
        {"kind": "timestamp", "format": "iso", "offset_seconds": 0},
    ),
    "now": (
        "当前时间",
        "按 format 输出当前时间:epoch=Unix 秒 / iso=ISO-8601 / compact=紧凑数字串。"
        "比 timestamp 更轻,无偏移与基准参数。",
        {"kind": "now", "format": "iso"},
    ),
    "seq": (
        "自增序号",
        "执行内自增序号:prefix 前缀 + width 位零填充,从 start 起。"
        "引擎历史别名 sequence 会规范化为 seq,目录只列规范名。",
        {"kind": "seq", "prefix": "BL", "width": 6, "start": 1},
    ),
    "random_decorated": (
        "装饰随机串",
        "head + 随机串 + tail,段间以 separator 连接 —— 适合业务单号"
        "(如 GIMBAL728-XXXXXX)。",
        {
            "kind": "random_decorated", "length": 6, "charset": "alnum",
            "head": "GIMBAL728", "tail": "", "separator": "-",
        },
    ),
    "time_offset": (
        "偏移时间戳",
        "以 unit 粒度把基准时间(默认当前)向 direction 偏移 value 步,生成对应时间戳;"
        "单位覆盖 milliseconds 到 years 八种。",
        {"kind": "time_offset", "unit": "days", "value": 30, "direction": "future"},
    ),
}


def _prop_type(prop: dict[str, Any]) -> str:
    """JSON Schema 属性 → 参数类型字符串。

    Literal 字段内联 ``enum`` + ``type``;``str | None`` 可选字段产出
    ``anyOf: [{type: string}, {type: null}]`` —— 取非 null 分支。
    """
    if "enum" in prop:
        return "string"
    t = prop.get("type")
    if isinstance(t, str):
        return t
    for sub in prop.get("anyOf", []):
        st = sub.get("type")
        if isinstance(st, str) and st != "null":
            return st
    return "string"


def _params_from_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """从镜像 spec 的 JSON Schema 派生参数描述符(剔除 kind 判别字段)。

    ge/le → minimum/maximum → min/max;全部字段有默认值 ⇒ required 恒 False
    (如实暴露,管理页表单按默认值渲染)。
    """
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    out: list[dict[str, Any]] = []
    for name, prop in props.items():
        if name == "kind" or not isinstance(prop, dict):
            continue
        out.append(
            {
                "name": name,
                "type": _prop_type(prop),
                "required": name in required,
                "default": prop.get("default"),
                "enum": prop["enum"] if "enum" in prop else None,
                "min": prop.get("minimum"),
                "max": prop.get("maximum"),
                "description": str(prop.get("description") or ""),
            }
        )
    return out


@dataclass(frozen=True)
class _KindDescriptor:
    kind: str
    summary: str
    description: str
    params: list[dict[str, Any]]
    example: dict[str, Any]


def _descriptor_for(kind: str) -> _KindDescriptor | None:
    model = _KIND_MODELS.get(kind)
    if model is None:
        return None
    summary, description, example = _KIND_META[kind]
    return _KindDescriptor(
        kind=kind,
        summary=summary,
        description=description,
        params=_params_from_schema(model.model_json_schema()),
        example=example,
    )


class GeneratorIndex:
    """BaseIndex 实现 —— items 是 kind 描述符(语法级 dim,非数据)。

    ``list_for_system`` 无视 system 参数返回全量: 生成器语法是全局的
    (同 strategy 先例)。``registry`` 形参仅为对齐 BaseIndex 构造约定,
    内省不依赖它。
    """

    def __init__(self, registry: Any = None) -> None:  # noqa: ARG002
        self._descriptors: dict[str, _KindDescriptor] = {
            k: d for k in _KIND_MODELS if (d := _descriptor_for(k)) is not None
        }

    def list_global(self, *, filters: dict[str, Any] | None = None) -> list[_KindDescriptor]:
        return list(self._descriptors.values())

    def list_for_system(
        self, system: str, *, filters: dict[str, Any] | None = None
    ) -> list[_KindDescriptor]:
        return list(self._descriptors.values())

    def get(self, item_id: str) -> _KindDescriptor | None:
        return self._descriptors.get(item_id)

    def to_view(self, item: _KindDescriptor) -> dict[str, Any]:
        return {"kind": item.kind, "summary": item.summary}
```

- [x] **Step 1.5: views.py 追加三个视图模型**

在 `src/gimbal-plate/gimbal_plate/http/views.py` 文件末尾(strategy 视图之后)追加。先确认文件头部已有 `Any`、`Literal` 导入与 `BaseModel`/`ConfigDict`/`Field`(StrategyFieldDesc 同族在用;缺哪个补哪个):

```python
# ─── generators 语法 dim 视图(常量池目录,2026-08-26)──────────────


class GeneratorParamDesc(BaseModel):
    """生成器 kind 的一个参数描述符。

    与 StrategyFieldDesc 的差异: 管理页动态表单需要 min/max(InputNumber
    约束)与显式 JSON-Schema 风格 type,而非 ui_kind;生成器参数无
    path 概念(name 即键)。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    type: Literal["string", "integer", "number", "boolean"]
    required: bool = False
    default: Any | None = None
    enum: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    description: str = ""


class GeneratorKindView(BaseModel):
    """generators dim 的 light view —— 给 kind 下拉用(kind/summary)。"""

    model_config = ConfigDict(extra="forbid")

    kind: str
    summary: str

    @classmethod
    def from_descriptor(cls, d: Any) -> "GeneratorKindView":
        return cls(kind=d.kind, summary=d.summary)


class GeneratorKindDetailView(BaseModel):
    """generators dim 的 full view —— 管理页文档卡片与动态表单渲染契约。"""

    model_config = ConfigDict(extra="forbid")

    kind: str
    summary: str
    description: str
    params: list[GeneratorParamDesc] = Field(default_factory=list)
    example: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_descriptor(cls, d: Any) -> "GeneratorKindDetailView":
        return cls(
            kind=d.kind,
            summary=d.summary,
            description=d.description,
            params=[GeneratorParamDesc.model_validate(p) for p in d.params],
            example=dict(d.example),
        )
```

- [x] **Step 1.6: dimensions.py 注册 dim**

在 `src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py` 的 `register_fin_dims` 内 strategy 注册块之后追加(imports 区补:
`from gimbal_plate.http.generator_dim import GeneratorIndex`;views 导入行补 `GeneratorKindDetailView`、`GeneratorKindView`):

```python
    # generators: 语法级 dim(第 9 个),生成器 spec 描述符 —— 注册在 fin
    # 装配点的理由同 strategy(生产/测试共用唯一 dim 装配入口,防 drift)。
    # 引擎 src/gimbal/generator/specs.py 是执行权威源;plate 镜像
    # schema/generator.py 手工同步,tests/plate/test_generator_dim.py
    # P7 防漂移。语法全局,任意 system 作用域返回全量。
    reg.register_dim(
        "generators",
        DimSpec(
            name="generators",
            index=GeneratorIndex(registry=reg),
            view_factory=GeneratorKindView.from_descriptor,
            full_view_factory=GeneratorKindDetailView.from_descriptor,
            actions={},
        ),
    )
```

- [x] **Step 1.7: 跑测试确认通过**

Run: `python -m pytest tests/plate/test_generator_dim.py -v`
Expected: 7 passed。若 P7 因 registry 属性名不符而 FAIL,按 registry.py 实际暴露的 kind 集合修正测试的取数分支(保持断言不变)。

- [x] **Step 1.8: plate 全量回归 + no-reverse-import 锁**

Run: `python -m pytest tests/plate -q`
Expected: 全绿(新增 7 例,既有不减)。特别确认 `test_v3_no_reverse_import.py` 通过。

- [x] **Step 1.9: Commit**

```bash
git add src/gimbal-plate/gimbal_plate/schema/generator.py src/gimbal-plate/gimbal_plate/http/generator_dim.py src/gimbal-plate/gimbal_plate/http/views.py src/gimbal-plate/gimbal_plate/systems/fin/dimensions.py tests/plate/test_generator_dim.py
git commit -m "feat(plate): generators 语法 dim — 引擎 9 生成器 spec 镜像 + JSON-Schema 内省描述符

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: platform 后端 `constant_entries` CRUD

**Files:**
- Create: `src/gimbal-platform/backend/app/models/constant_entry.py`
- Modify: `src/gimbal-platform/backend/app/models/__init__.py`
- Create: `src/gimbal-platform/backend/app/schemas/constants.py`
- Create: `src/gimbal-platform/backend/app/routers/constants.py`
- Modify: `src/gimbal-platform/backend/app/main.py`(include_router 区,L108-124 附近,scenarios 之前)
- Test: `src/gimbal-platform/backend/tests/test_constants_api.py`

**Interfaces:**
- Consumes: `from ..core.db import get_db` / `from ..core.deps import CurrentUser` / `from ..models import ...`(与 `auth_sessions.py` router 同源);测试用 `backend/tests/conftest.py` 的 `client` fixture(ASGITransport)+ `backend/tests/helpers.py` 的 `register_and_login(client, username, password)` → Bearer headers。
- Produces(Task 6 前端 api 层依赖的精确形状):
  - `GET /api/constants` → `ConstantEntryOut[]`(按 name 升序)
  - `POST /api/constants` → 201 `ConstantEntryOut`;同名 → 409 `detail={"code": "constant_name_exists", ...}`(字典 detail,异于 auth_sessions 纯字符串)
  - `PATCH /api/constants/{id}` → 200 `ConstantEntryOut`(description/value/spec 按 None 判断缺席;entry_kind 不可变)
  - `DELETE /api/constants/{id}` → 204
  - `ConstantEntryOut = {id, name, description, entry_kind: "literal"|"generator", value, spec, created_at, updated_at}`(literal 行 spec=null,generator 行 value=null)

- [x] **Step 2.1: 写失败测试(全文)**

创建 `src/gimbal-platform/backend/tests/test_constants_api.py`:

```python
"""Constants-pool API 面单测 —— per-user 常量条目 CRUD。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §后端
覆盖: owner 隔离(B1/B2)、互斥校验(B3/B4)、name 规则(B5)、
409 字典 detail(B6)、PATCH 不可变 entry_kind/按行校验(B7)、
删除(B8)、字面量四类型往返(B9)。
"""
from __future__ import annotations

from httpx import AsyncClient
from tests.helpers import register_and_login


async def _auth(client: AsyncClient, username: str = "alice") -> dict[str, str]:
    return await register_and_login(client, username, "secret-123")


async def test_b1_create_and_list_owned_entries(client: AsyncClient) -> None:
    headers = await _auth(client)
    lit = {
        "name": "bank_id",
        "description": "联行号",
        "entry_kind": "literal",
        "value": "319666690256273408",
    }
    gen = {
        "name": "bl_no",
        "description": "业务单号",
        "entry_kind": "generator",
        "spec": {"kind": "random_decorated", "length": 6, "head": "GIMBAL728"},
    }
    for payload in (lit, gen):
        r = await client.post("/api/constants", json=payload, headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["name"] == payload["name"]
        assert body["id"] > 0
    assert body["value"] is None  # generator 行 value=null

    r = await client.get("/api/constants", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert [it["name"] for it in items] == ["bank_id", "bl_no"]  # name 升序


async def test_b2_owner_isolation_404(client: AsyncClient) -> None:
    alice = await _auth(client, "alice")
    r = await client.post(
        "/api/constants",
        json={"name": "x", "entry_kind": "literal", "value": "1"},
        headers=alice,
    )
    entry_id = r.json()["id"]

    bob = await _auth(client, "bob")
    for method, path in (
        ("get", f"/api/constants/{entry_id}"),
        ("patch", f"/api/constants/{entry_id}"),
        ("delete", f"/api/constants/{entry_id}"),
    ):
        r = await client.request(method, path, headers=bob, json={})
        assert r.status_code == 404, (method, r.text)
    # bob 看不到 alice 的条目
    r = await client.get("/api/constants", headers=bob)
    assert r.json() == []


async def test_b3_literal_requires_primitive_value(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "bad", "entry_kind": "literal", "value": {"a": 1}},
        headers=headers,
    )
    assert r.status_code == 422
    # literal 携带 spec 也拒
    r = await client.post(
        "/api/constants",
        json={
            "name": "bad2", "entry_kind": "literal", "value": "ok",
            "spec": {"kind": "uuid"},
        },
        headers=headers,
    )
    assert r.status_code == 422


async def test_b4_generator_requires_spec_with_kind(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "bad", "entry_kind": "generator", "spec": {"length": 6}},
        headers=headers,
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/constants",
        json={"name": "bad2", "entry_kind": "generator", "value": "x"},
        headers=headers,
    )
    assert r.status_code == 422


async def test_b5_name_pattern(client: AsyncClient) -> None:
    headers = await _auth(client)
    for bad in ("with space", "中文", "a" * 65, "x-y", ""):
        r = await client.post(
            "/api/constants",
            json={"name": bad, "entry_kind": "literal", "value": "1"},
            headers=headers,
        )
        assert r.status_code == 422, bad


async def test_b6_duplicate_name_409_dict_detail(client: AsyncClient) -> None:
    headers = await _auth(client)
    payload = {"name": "dup", "entry_kind": "literal", "value": "1"}
    r = await client.post("/api/constants", json=payload, headers=headers)
    assert r.status_code == 201
    r = await client.post("/api/constants", json=payload, headers=headers)
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert isinstance(detail, dict)
    assert detail["code"] == "constant_name_exists"


async def test_b7_patch_rules(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "g1", "entry_kind": "generator", "spec": {"kind": "seq"}},
        headers=headers,
    )
    gid = r.json()["id"]
    r = await client.post(
        "/api/constants",
        json={"name": "l1", "entry_kind": "literal", "value": "v"},
        headers=headers,
    )
    lid = r.json()["id"]

    # generator 行不接受 value;literal 行不接受 spec
    r = await client.patch(
        f"/api/constants/{gid}", json={"value": "x"}, headers=headers
    )
    assert r.status_code == 422
    r = await client.patch(
        f"/api/constants/{lid}", json={"spec": {"kind": "uuid"}}, headers=headers
    )
    assert r.status_code == 422
    # spec 必须含 kind
    r = await client.patch(
        f"/api/constants/{gid}", json={"spec": {"length": 6}}, headers=headers
    )
    assert r.status_code == 422
    # 正常 patch: generator 换 spec + 描述
    r = await client.patch(
        f"/api/constants/{gid}",
        json={"description": "序号", "spec": {"kind": "seq", "width": 8}},
        headers=headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["description"] == "序号"
    assert body["spec"] == {"kind": "seq", "width": 8}
    # 正常 patch: literal 换 int 值
    r = await client.patch(
        f"/api/constants/{lid}", json={"value": 42}, headers=headers
    )
    assert r.status_code == 200
    assert r.json()["value"] == 42


async def test_b8_delete(client: AsyncClient) -> None:
    headers = await _auth(client)
    r = await client.post(
        "/api/constants",
        json={"name": "gone", "entry_kind": "literal", "value": "1"},
        headers=headers,
    )
    eid = r.json()["id"]
    r = await client.delete(f"/api/constants/{eid}", headers=headers)
    assert r.status_code == 204
    r = await client.get("/api/constants", headers=headers)
    assert r.json() == []


async def test_b9_literal_primitive_roundtrip(client: AsyncClient) -> None:
    headers = await _auth(client)
    cases = [
        ("s_val", "文本"),
        ("i_val", 42),
        ("f_val", 3.14),
        ("b_val", True),
    ]
    for name, value in cases:
        r = await client.post(
            "/api/constants",
            json={"name": name, "entry_kind": "literal", "value": value},
            headers=headers,
        )
        assert r.status_code == 201, name
        assert r.json()["value"] == value
```

- [x] **Step 2.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_constants_api.py -v`
Expected: 全部 FAIL(404 Not Found,路由未挂)

- [x] **Step 2.3: 写 ORM 模型**

创建 `src/gimbal-platform/backend/app/models/constant_entry.py`(列定义惯例照抄 `auth_session.py`:`from ..core.db import Base`、`server_default=func.now()`、`onupdate=func.now()`):

```python
"""ConstantEntry model — per-user 常量池条目(常量池设计 2026-08-26)。

两类条目互斥:
* literal — ``value`` 存 str/int/float/bool 字面值(JSON 列);
* generator — ``spec`` 存引擎生成器声明(dict,必须含字符串 ``kind``)。

平台只存配置阶段内容、绝不求值;引擎 preprocess 是唯一求值点。
owner 隔离: 跨 owner 一律 404;同名约束在 DB(owner_id, name)。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.db import Base


class ConstantEntry(Base):
    __tablename__ = "constant_entries"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_constant_owner_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(256), default="")
    # "literal" | "generator" —— 创建后不可变(PATCH 拒改)
    entry_kind: Mapped[str] = mapped_column(String(16))
    value: Mapped[Any] = mapped_column(JSON, nullable=True, default=None)
    spec: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
```

修改 `src/gimbal-platform/backend/app/models/__init__.py`:在既有模型导入/导出列表(`AuthSession` 所在块)按字母序补:

```python
from .constant_entry import ConstantEntry
```

并在 `__all__`(如有)中补 `"ConstantEntry"`。

- [x] **Step 2.4: 写 Pydantic schemas**

创建 `src/gimbal-platform/backend/app/schemas/constants.py`:

```python
"""Pydantic schemas for the constants-pool API(常量池条目)。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

NAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,64}$")


def is_literal_primitive(v: Any) -> bool:
    """literal 条目 value 仅接受 str/int/float/bool(bool 是 int 子类,先排除)。"""
    if isinstance(v, bool):
        return True
    return isinstance(v, (str, int, float))


class ConstantEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    entry_kind: Literal["literal", "generator"]
    value: Any = None
    spec: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class ConstantEntryCreateIn(BaseModel):
    name: str
    description: str = Field(default="", max_length=256)
    entry_kind: Literal["literal", "generator"]
    value: Any = None
    spec: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_payload(self) -> "ConstantEntryCreateIn":
        if not NAME_PATTERN.match(self.name):
            raise ValueError("name 须匹配 ^[A-Za-z0-9_]{1,64}$")
        if self.entry_kind == "literal":
            if not is_literal_primitive(self.value):
                raise ValueError("literal 条目的 value 必须是 str/int/float/bool")
            if self.spec is not None:
                raise ValueError("literal 条目不能携带 spec(value/spec 互斥)")
        else:
            if self.value is not None:
                raise ValueError("generator 条目不能携带 value(value/spec 互斥)")
            if not (
                isinstance(self.spec, dict)
                and isinstance(self.spec.get("kind"), str)
                and self.spec["kind"]
            ):
                raise ValueError("generator 条目的 spec 必须含非空字符串 kind")
        return self


class ConstantEntryPatchIn(BaseModel):
    """PATCH 语义: None = 不改(与 auth_sessions 一致);校验依赖行的 entry_kind,在 router 层做。"""

    description: str | None = Field(default=None, max_length=256)
    value: Any = None
    spec: dict[str, Any] | None = None
```

- [x] **Step 2.5: 写 router**

创建 `src/gimbal-platform/backend/app/routers/constants.py`:

```python
"""Constants-pool API —— per-user 常量池条目 CRUD(常量池设计 2026-08-26)。

条目两型互斥: literal(value 字面值)/ generator(spec 含 kind)。后端不
校验 generator 参数合法性 —— 目录描述符驱动前端表单校验,引擎 preprocess
fail-fast 兜底。409 用字典 detail(与 auth_sessions 纯字符串不同):
前端按 ``detail.code == "constant_name_exists"`` 提示。
"""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.db import get_db
from ..core.deps import CurrentUser
from ..models import ConstantEntry
from ..schemas.constants import (
    ConstantEntryCreateIn,
    ConstantEntryOut,
    ConstantEntryPatchIn,
    is_literal_primitive,
)

router = APIRouter(prefix="/constants", tags=["constants"])

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def _get_owned(
    session: AsyncSession, entry_id: int, owner_id: int
) -> ConstantEntry:
    entry = await session.get(ConstantEntry, entry_id)
    if entry is None or entry.owner_id != owner_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"constant not found: {entry_id}",
        )
    return entry


def _validate_patch(entry: ConstantEntry, payload: ConstantEntryPatchIn) -> None:
    """PATCH 载荷按行的 entry_kind 校验(依赖 DB 行,schema 层做不了)。"""
    if payload.value is not None:
        if entry.entry_kind != "literal":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="generator 条目不接受 value",
            )
        if not is_literal_primitive(payload.value):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="value 必须是 str/int/float/bool",
            )
    if payload.spec is not None:
        if entry.entry_kind != "generator":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="literal 条目不接受 spec",
            )
        if not (
            isinstance(payload.spec.get("kind"), str) and payload.spec["kind"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="spec 必须含非空字符串 kind",
            )


@router.get("", response_model=list[ConstantEntryOut])
async def list_constants(
    user: CurrentUser, session: DbSession
) -> list[ConstantEntry]:
    rows = await session.scalars(
        select(ConstantEntry)
        .where(ConstantEntry.owner_id == user.id)
        .order_by(ConstantEntry.name.asc())
    )
    return list(rows)


@router.post("", response_model=ConstantEntryOut, status_code=status.HTTP_201_CREATED)
async def create_constant(
    payload: ConstantEntryCreateIn, user: CurrentUser, session: DbSession
) -> ConstantEntry:
    entry = ConstantEntry(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        entry_kind=payload.entry_kind,
        value=payload.value,
        spec=payload.spec,
    )
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "constant_name_exists",
                "message": f"常量名 '{payload.name}' 已存在",
            },
        ) from e
    await session.refresh(entry)
    return entry


@router.patch("/{entry_id}", response_model=ConstantEntryOut)
async def patch_constant(
    entry_id: int,
    payload: ConstantEntryPatchIn,
    user: CurrentUser,
    session: DbSession,
) -> ConstantEntry:
    entry = await _get_owned(session, entry_id, user.id)
    _validate_patch(entry, payload)
    if payload.description is not None:
        entry.description = payload.description
    if payload.value is not None:
        entry.value = payload.value
    if payload.spec is not None:
        entry.spec = payload.spec
    await session.commit()
    await session.refresh(entry)
    return entry


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_constant(
    entry_id: int, user: CurrentUser, session: DbSession
) -> None:
    entry = await _get_owned(session, entry_id, user.id)
    await session.delete(entry)
    await session.commit()
```

- [x] **Step 2.6: main.py 挂载**

在 `src/gimbal-platform/backend/app/main.py` 的 include_router 注册区(`strategy_catalog` 之后、`scenarios` 之前)补 import 与注册:

```python
from .routers import constants  # noqa: F401  (import 区,与既有 router import 并列)
```

```python
app.include_router(constants.router, prefix="/api")
```

- [x] **Step 2.7: 跑测试确认通过**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_constants_api.py -v`
Expected: 9 passed

- [x] **Step 2.8: backend 回归**

Run: `cd src/gimbal-platform/backend && python -m pytest tests -q`
Expected: 全绿(既有套件不减)

- [x] **Step 2.9: Commit**

```bash
git add src/gimbal-platform/backend/app/models/constant_entry.py src/gimbal-platform/backend/app/models/__init__.py src/gimbal-platform/backend/app/schemas/constants.py src/gimbal-platform/backend/app/routers/constants.py src/gimbal-platform/backend/app/main.py src/gimbal-platform/backend/tests/test_constants_api.py
git commit -m "feat(backend): constant_entries per-user CRUD — 常量池条目(两型互斥/409 字典 detail)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: platform 后端 generator-catalog 代理

**Files:**
- Create: `src/gimbal-platform/backend/app/routers/generator_catalog.py`
- Modify: `src/gimbal-platform/backend/app/main.py`(T2 已动过的注册区再补一行)
- Test: `src/gimbal-platform/backend/tests/test_generator_catalog_proxy.py`

**Interfaces:**
- Consumes: `..services.plate_client.get_client()`(进程级 AsyncClient 单例,MockTransport 测试替换随之生效 —— 与 strategy_catalog 同构);plate 侧 `GET /api/generators`、`GET /api/generators/{kind}/full`(Task 1 Produces 的信封形状)。
- Produces(Task 6 前端依赖):
  - `GET /api/generator-catalog` → `[{kind, summary}]`(解 `data.items`)
  - `GET /api/generator-catalog/{kind}/full` → `{kind, summary, description, params, example}`(解 `data.item`)
  - 错误:plate 5xx/连不上 → 502 `detail={"code": "plate_unavailable", ...}`;plate 404 → 404 `detail={"code": "generator_kind_not_found", ...}`;信封残缺 → 502 `plate_invalid_envelope`

- [x] **Step 3.1: 写失败测试(全文)**

创建 `src/gimbal-platform/backend/tests/test_generator_catalog_proxy.py`(克隆 `tests/test_strategy_catalog.py` 的 MockTransport 三态模式):

```python
"""Generator-catalog proxy 面单测 —— plate generators dim 代理三态。

设计: src/gimbal-platform/docs/superpowers/specs/2026-08-26-constant-pool-design.md §后端代理
与 test_strategy_catalog.py 同构: plate ok / plate 404 / plate 5xx /
连不上,验证信封解包与错误码映射(502 plate_unavailable、404
generator_kind_not_found)。
"""
from __future__ import annotations

import httpx
import pytest
from httpx import AsyncClient

from tests.helpers import register_and_login

_LIST_ENVELOPE = {
    "ok": True,
    "dim": "generators",
    "data": {
        "items": [
            {"kind": "uuid", "summary": "UUID"},
            {"kind": "seq", "summary": "自增序号"},
        ],
        "total": 2,
    },
}

_FULL_ENVELOPE = {
    "ok": True,
    "dim": "generators",
    "data": {
        "item": {
            "kind": "seq",
            "summary": "自增序号",
            "description": "执行内自增序号。",
            "params": [
                {"name": "prefix", "type": "string", "required": False,
                 "default": "", "description": "序号前缀"},
            ],
            "example": {"kind": "seq", "prefix": "BL", "width": 6, "start": 1},
        }
    },
}


class GeneratorPlateMock(httpx.MockTransport):
    """behaviour: ok | not_found | server_error | unavailable"""

    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour
        super().__init__(self.handler)

    def handler(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
        if self.behaviour == "unavailable":
            raise httpx.ConnectError("plate down")
        if self.behaviour == "server_error":
            return httpx.Response(500, text="boom")
        if self.behaviour == "not_found":
            return httpx.Response(
                404, json={"ok": False, "error": {"code": "dim_item_not_found"}}
            )
        if request.url.path.endswith("/full"):
            return httpx.Response(200, json=_FULL_ENVELOPE)
        return httpx.Response(200, json=_LIST_ENVELOPE)


async def _auth(client: AsyncClient) -> dict[str, str]:
    return await register_and_login(client, "alice", "secret-123")


@pytest.mark.parametrize("behaviour", ["ok", "server_error", "unavailable"])
async def test_b10_list_proxy_states(
    client: AsyncClient, plate, behaviour: str
) -> None:
    plate.set_client_for_tests(GeneratorPlateMock(behaviour))
    headers = await _auth(client)
    r = await client.get("/api/generator-catalog", headers=headers)
    if behaviour == "ok":
        assert r.status_code == 200
        assert r.json() == _LIST_ENVELOPE["data"]["items"]
    else:
        assert r.status_code == 502
        assert r.json()["detail"]["code"] == "plate_unavailable"


async def test_b11_full_proxy_states(
    client: AsyncClient, plate
) -> None:
    headers = await _auth(client)

    plate.set_client_for_tests(GeneratorPlateMock("ok"))
    r = await client.get("/api/generator-catalog/seq/full", headers=headers)
    assert r.status_code == 200
    assert r.json()["kind"] == "seq"
    assert r.json()["example"]["kind"] == "seq"

    plate.set_client_for_tests(GeneratorPlateMock("not_found"))
    r = await client.get("/api/generator-catalog/nope/full", headers=headers)
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "generator_kind_not_found"
```

注意: fixture 名 `plate`/`client` 与 `set_client_for_tests` 以 `backend/tests/conftest.py` 现有实现为准(`test_strategy_catalog.py` 用的就是这套);若名字不同,以 strategy 测试的实际用法为准照抄。

- [x] **Step 3.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_generator_catalog_proxy.py -v`
Expected: FAIL(404,路由未挂)

- [x] **Step 3.3: 写代理(全文,克隆 strategy_catalog.py)**

创建 `src/gimbal-platform/backend/app/routers/generator_catalog.py`:

```python
"""Generator catalog proxy — Platform → Plate (generators 语法 dim, 2026-08-26).

常量池管理页需要 plate 内省出的生成器 kind 描述符(哪些 kind、每个
kind 哪些参数)。权威源在 plate(``GET /api/generators`` 与
``GET /api/generators/{kind}/full``,见 gimbal_plate/http/generator_dim.py);
本模块代理这两条,让前端只打 Platform 一个 API 面。

与 strategy_catalog.py 同构(502 plate_unavailable / 404 / 信封透传),
差异: plate 路径、404 code(generator_kind_not_found)、
list 路由解 ``data.items`` 返回数组、full 解 ``data.item``。
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, status

from ..core.deps import CurrentUser
from ..services.plate_client import get_client

router = APIRouter(prefix="/generator-catalog", tags=["generator-catalog"])


def proxy_error(
    resp: httpx.Response,
    *,
    context: str,
    not_found_code: str = "generator_kind_not_found",
    not_found_msg: str = "generator kind not found",
) -> HTTPException:
    """Map a plate non-2xx response onto the platform error model."""
    if resp.status_code >= 500:
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "plate_unavailable", "message": resp.text[:200]},
        )
    if resp.status_code == 404:
        return HTTPException(
            status_code=404,
            detail={
                "code": not_found_code,
                "message": f"{not_found_msg}: {context}",
            },
        )
    try:
        env = resp.json()
    except Exception:  # noqa: BLE001
        env = {"ok": False, "error": {"message": resp.text[:200]}}
    return HTTPException(
        status_code=resp.status_code,
        detail=env.get("error") or {"code": "plate_error", "message": resp.text[:200]},
    )


def unavailable(e: Exception) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": "plate_unavailable", "message": str(e)},
    )


@router.get("")
async def list_generator_kinds(user: CurrentUser) -> list[dict]:
    """Proxy ``GET {plate}/api/generators`` and unwrap ``data.items``."""
    client = get_client()
    try:
        resp = await client.get("/api/generators")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context="list")
    items = (resp.json().get("data") or {}).get("items")
    if not isinstance(items, list):
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no items in response"},
        )
    return items


@router.get("/{kind}/full")
async def get_generator_kind_full(user: CurrentUser, kind: str) -> dict:
    """Proxy ``GET {plate}/api/generators/{kind}/full`` and unwrap ``data.item``."""
    client = get_client()
    try:
        resp = await client.get(f"/api/generators/{kind}/full")
    except httpx.HTTPError as e:
        raise unavailable(e) from e
    if resp.status_code != 200:
        raise proxy_error(resp, context=kind)
    item = (resp.json().get("data") or {}).get("item")
    if not item:
        raise HTTPException(
            status_code=502,
            detail={"code": "plate_invalid_envelope", "message": "no item in response"},
        )
    return item
```

main.py 在 T2 注册块后补:

```python
app.include_router(generator_catalog.router, prefix="/api")
```

(import 区补 `from .routers import generator_catalog` —— 若 T2 已把 import 写成多模块一行,合并即可)

- [x] **Step 3.4: 跑测试确认通过 + backend 回归**

Run: `cd src/gimbal-platform/backend && python -m pytest tests/test_generator_catalog_proxy.py -v && python -m pytest tests -q`
Expected: 新增 4 passed;全量回归绿

- [x] **Step 3.5: Commit**

```bash
git add src/gimbal-platform/backend/app/routers/generator_catalog.py src/gimbal-platform/backend/app/main.py src/gimbal-platform/backend/tests/test_generator_catalog_proxy.py
git commit -m "feat(backend): generator-catalog 代理 — plate generators dim 目录透传(502/404 映射)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: 前端 `utils/clipboard.ts` 抽取(copyJson 双通道复用)

**Files:**
- Create: `src/gimbal-platform/frontend/src/utils/clipboard.ts`
- Modify: `src/gimbal-platform/frontend/src/stores/scenario-draft.ts`(仅 copyJson 函数体)
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/clipboard.test.ts`

**Interfaces:**
- Consumes: `stores/scenario-draft.ts` 现有 `copyJson`(L95-110 附近,clipboard API 主 + execCommand 回退的内联实现)。
- Produces: `copyText(text: string): Promise<boolean>`(T7 panel / T9 管理页复制按钮复用)。

- [x] **Step 4.1: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/utils/__tests__/clipboard.test.ts`:

```ts
/**
 * clipboard.ts — 双通道剪贴板(clipboard API 主 + execCommand 回退)。
 * F 用例: 主通道成功;主通道缺失/抛错时回退 execCommand;回退后 DOM 清理。
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { copyText } from '@/utils/clipboard'

describe('copyText', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    document.body.innerHTML = ''
  })

  it('主通道: navigator.clipboard.writeText 成功 → true 且传参正确', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.assign(navigator, { clipboard: { writeText } })
    await expect(copyText('${var.bl_no}')).resolves.toBe(true)
    expect(writeText).toHaveBeenCalledWith('${var.bl_no}')
  })

  it('回退通道: clipboard 缺失 → execCommand(copy),textarea 用后即删', async () => {
    const orig = navigator.clipboard
    Object.defineProperty(navigator, 'clipboard', { value: undefined, configurable: true })
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand
    await expect(copyText('abc')).resolves.toBe(true)
    expect(exec).toHaveBeenCalledWith('copy')
    expect(document.querySelector('textarea')).toBeNull() // DOM 已清理
    Object.defineProperty(navigator, 'clipboard', { value: orig, configurable: true })
  })

  it('主通道抛错 → 落到回退通道', async () => {
    const writeText = vi.fn().mockRejectedValue(new Error('denied'))
    Object.assign(navigator, { clipboard: { writeText } })
    const exec = vi.fn(() => true)
    document.execCommand = exec as unknown as typeof document.execCommand
    await expect(copyText('x')).resolves.toBe(true)
    expect(exec).toHaveBeenCalled()
  })
})
```

- [x] **Step 4.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/clipboard.test.ts`
Expected: FAIL(`Failed to resolve import "@/utils/clipboard"`)

- [x] **Step 4.3: 写实现**

创建 `src/gimbal-platform/frontend/src/utils/clipboard.ts`:

```ts
/**
 * clipboard.ts — 剪贴板双通道(clipboard API 主 + execCommand 回退)。
 * 从 stores/scenario-draft.ts copyJson 抽出(常量池 Panel/管理页复用)。
 * jsdom 与非安全上下文(内网 http)下 navigator.clipboard 可能缺失/被拒 —
 * 回退保命。
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      /* 落到 execCommand 回退 */
    }
  }
  const ta = document.createElement('textarea')
  ta.value = text
  document.body.appendChild(ta)
  ta.select()
  let ok = false
  try {
    ok = document.execCommand('copy')
  } catch {
    ok = false
  }
  document.body.removeChild(ta)
  return ok
}
```

- [x] **Step 4.4: 重构 scenario-draft copyJson**

在 `src/gimbal-platform/frontend/src/stores/scenario-draft.ts`:删除 copyJson 内联的 clipboard/execCommand 分支(保留其 fetchConverted 逻辑与 ElMessage 提示),改为:

```ts
import { copyText } from '@/utils/clipboard'
```

```ts
  async function copyJson(): Promise<void> {
    const converted = await fetchConverted()
    const ok = await copyText(JSON.stringify(converted, null, 2))
    if (ok) ElMessage.success('plate 转换后的 JSON 已复制到剪贴板')
    else ElMessage.error('复制失败 — 请手动复制')
  }
```

(提示文案若与现状有出入,保留现状文案,仅替换通道部分)

- [x] **Step 4.5: 跑测试 + 相关回归**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/clipboard.test.ts src/stores/__tests__ 2>/dev/null || npx vitest run src/utils/__tests__/clipboard.test.ts`
Expected: 3 passed;若 stores 下有 scenario-draft 相关测试也保持绿

- [x] **Step 4.6: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/clipboard.ts src/gimbal-platform/frontend/src/utils/__tests__/clipboard.test.ts src/gimbal-platform/frontend/src/stores/scenario-draft.ts
git commit -m "refactor(frontend): copyText 抽取到 utils/clipboard — copyJson 双通道复用

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 前端 `composables/useInsertTarget.ts`(焦点跟踪插入)

**Files:**
- Create: `src/gimbal-platform/frontend/src/composables/useInsertTarget.ts`
- Test: `src/gimbal-platform/frontend/src/composables/__tests__/useInsertTarget.test.ts`

**Interfaces:**
- Consumes: 无(纯 Vue API:`ref`/`provide`/`inject`/`InjectionKey`)。
- Produces(T7 panel / T8 CaseComposer 依赖):
  - `useInsertTarget(): InsertTargetApi`,`InsertTargetApi = { lastTarget: Ref<HTMLElement | null>, start(root: HTMLElement): void, stop(): void, appendValue(text: string): boolean }`
  - `INSERT_TARGET_KEY: InjectionKey<InsertTargetApi>`
  - `provideInsertTarget(api: InsertTargetApi): void`
  - `useSharedInsertTarget(): InsertTargetApi`(inject;未 provide 时 throw)
  - `appendValue` 语义:目标断连返回 false 并清空;input/textarea 值尾追加后派发原生 `input` 事件(bubbles),contenteditable 追加文本节点。

- [x] **Step 5.1: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/composables/__tests__/useInsertTarget.test.ts`:

```ts
/**
 * useInsertTarget — DOM 焦点跟踪插入目标。
 * F1: 跟踪 text/textarea,忽略 number/checkbox/radio/file/select;
 * F2: 断连目标 appendValue 返回 false 并清引用;
 * F3: appendValue 值尾追加 + 派发原生 input 事件。
 */
import { describe, it, expect } from 'vitest'
import { useInsertTarget } from '@/composables/useInsertTarget'

function focus(el: Element): void {
  el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
}

describe('useInsertTarget', () => {
  it('F1: 跟踪文本可编辑元素,忽略 number/checkbox/radio/file/select', () => {
    document.body.innerHTML = `
      <div id="root">
        <input id="t1" type="text" />
        <input id="n1" type="number" />
        <input id="c1" type="checkbox" />
        <input id="r1" type="radio" />
        <input id="f1" type="file" />
        <select id="s1"><option>a</option></select>
        <textarea id="ta1"></textarea>
      </div>`
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)

    focus(document.getElementById('t1')!)
    expect(api.lastTarget.value?.id).toBe('t1')
    for (const id of ['n1', 'c1', 'r1', 'f1', 's1']) {
      focus(document.getElementById(id)!)
      expect(api.lastTarget.value?.id).toBe('t1') // 非文本目标不更新
    }
    focus(document.getElementById('ta1')!)
    expect(api.lastTarget.value?.id).toBe('ta1')
    api.stop()
    document.body.innerHTML = ''
  })

  it('F2: 目标已断连 — appendValue 返回 false 并清空引用', () => {
    document.body.innerHTML =
      '<div id="root"><input id="gone" type="text" value="x" /></div>'
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)
    focus(document.getElementById('gone')!)
    document.getElementById('gone')!.remove()
    expect(api.appendValue('Y')).toBe(false)
    expect(api.lastTarget.value).toBeNull()
    api.stop()
    document.body.innerHTML = ''
  })

  it('F3: appendValue 值尾追加 + 派发原生 input 事件', () => {
    document.body.innerHTML =
      '<div id="root"><input id="t" type="text" value="abc" /></div>'
    const api = useInsertTarget()
    api.start(document.getElementById('root')!)
    const input = document.getElementById('t') as HTMLInputElement
    focus(input)
    const spy = vi.fn()
    input.addEventListener('input', spy)
    expect(api.appendValue('-tail')).toBe(true)
    expect(input.value).toBe('abc-tail')
    expect(spy).toHaveBeenCalledTimes(1)
    api.stop()
    document.body.innerHTML = ''
  })
})
```

(文件顶部 import 行补 `vi`:`import { describe, it, expect, vi } from 'vitest'`)

- [x] **Step 5.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/composables/__tests__/useInsertTarget.test.ts`
Expected: FAIL(无法解析 `@/composables/useInsertTarget`)

- [x] **Step 5.3: 写实现(全文)**

创建 `src/gimbal-platform/frontend/src/composables/useInsertTarget.ts`:

```ts
/**
 * useInsertTarget — DOM 焦点跟踪的"插入目标"(常量池 Panel 插入到字段)。
 *
 * focusin 捕获挂在 composer 根,记录最后获焦的文本可编辑元素;插入 =
 * 值尾追加 + 派发原生 input 事件,兼容 FieldForm 原生 @input→setValue
 * (JSONPath)、el-input v-model、原生 textarea 三链。跳过
 * number/checkbox/radio/file/select —— 这些控件追加文本无意义。
 *
 * 通过 provide/inject 共享: CaseComposer 根 provideInsertTarget(),
 * rail Panel(步骤 0-2)与 Canvas col-info Panel(步骤 3)inject 同一实例。
 */
import { inject, provide, ref, type InjectionKey, type Ref } from 'vue'

const TEXT_SELECTOR =
  'input[type="text"], input:not([type]), input[type="search"], textarea, [contenteditable="true"]'

export interface InsertTargetApi {
  lastTarget: Ref<HTMLElement | null>
  start: (root: HTMLElement) => void
  stop: () => void
  /** 值尾追加 text 并派发原生 input;无有效目标返回 false。 */
  appendValue: (text: string) => boolean
}

export function useInsertTarget(): InsertTargetApi {
  const lastTarget = ref<HTMLElement | null>(null)
  let boundRoot: HTMLElement | null = null

  function isTextEditable(el: EventTarget | null): el is HTMLElement {
    if (!(el instanceof HTMLElement)) return false
    if (el.hasAttribute('disabled') || el.hasAttribute('readonly')) return false
    return el.matches(TEXT_SELECTOR)
  }

  function onFocusIn(e: FocusEvent): void {
    if (isTextEditable(e.target)) lastTarget.value = e.target
  }

  function start(root: HTMLElement): void {
    stop()
    boundRoot = root
    root.addEventListener('focusin', onFocusIn, true)
  }

  function stop(): void {
    if (boundRoot) boundRoot.removeEventListener('focusin', onFocusIn, true)
    boundRoot = null
    lastTarget.value = null
  }

  function appendValue(text: string): boolean {
    const el = lastTarget.value
    if (!el || !el.isConnected) {
      lastTarget.value = null
      return false
    }
    if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) {
      el.value = el.value + text
      el.dispatchEvent(new Event('input', { bubbles: true }))
    } else {
      el.appendChild(document.createTextNode(text))
      el.dispatchEvent(new InputEvent('input', { bubbles: true }))
    }
    return true
  }

  return { lastTarget, start, stop, appendValue }
}

export const INSERT_TARGET_KEY: InjectionKey<InsertTargetApi> = Symbol('insert-target')

export function provideInsertTarget(api: InsertTargetApi): void {
  provide(INSERT_TARGET_KEY, api)
}

/** Panel 侧取共享实例;CaseComposer 根提供。 */
export function useSharedInsertTarget(): InsertTargetApi {
  const api = inject(INSERT_TARGET_KEY)
  if (!api) {
    throw new Error(
      'useSharedInsertTarget: 未 provide INSERT_TARGET_KEY(应由 CaseComposer 根提供)',
    )
  }
  return api
}
```

- [x] **Step 5.4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/composables/__tests__/useInsertTarget.test.ts`
Expected: 3 passed

- [x] **Step 5.5: Commit**

```bash
git add src/gimbal-platform/frontend/src/composables/useInsertTarget.ts src/gimbal-platform/frontend/src/composables/__tests__/useInsertTarget.test.ts
git commit -m "feat(frontend): useInsertTarget 焦点跟踪插入目标 — capture focusin + 值尾追加原生 input

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: 前端类型 + api 层 + constants store

**Files:**
- Create: `src/gimbal-platform/frontend/src/types/constants.ts`
- Create: `src/gimbal-platform/frontend/src/api/constants.ts`
- Create: `src/gimbal-platform/frontend/src/api/generator_catalog.ts`
- Create: `src/gimbal-platform/frontend/src/stores/constants.ts`
- Test: `src/gimbal-platform/frontend/src/stores/__tests__/constants.test.ts`

**Interfaces:**
- Consumes: `@/api/http`(既有 axios 实例,`.get<T>()` 泛型 + `r.data` 模式,见 `api/auth_sessions.ts`);`@/utils/useSetStatus`(FetchStatus)。
- Produces(T7/T8/T9 依赖):
  - 类型 `ConstantEntry = { id: number; name: string; description: string; entry_kind: 'literal' | 'generator'; value: unknown; spec: Record<string, unknown> | null; created_at: string; updated_at: string }`
  - `GeneratorKindView = { kind: string; summary: string }`;`GeneratorParamDesc = { name: string; type: 'string' | 'integer' | 'number' | 'boolean'; required: boolean; default: unknown; enum: unknown[] | null; min: number | null; max: number | null; description: string }`;`GeneratorKindDetailView = { kind; summary; description; params: GeneratorParamDesc[]; example: Record<string, unknown> }`
  - api: `list()/create()/patch()/remove()`、`listGeneratorKinds()/getGeneratorKindFull(kind)`
  - store `useConstantsStore`:`entries` / `catalog` / `catalogError` / `fetchStatus` / `lastError` / `ensureEntries()`(in-flight 去重)/ `ensureCatalog()`(不抛错,失败落 `catalogError`)/ `createEntry` / `patchEntry` / `removeEntry`

- [x] **Step 6.1: 写类型 + api 层(纯声明,随测试一并验证)**

创建 `src/gimbal-platform/frontend/src/types/constants.ts`:

```ts
/**
 * constants.ts — 常量池前端类型(条目 + plate generators dim 目录)。
 * plate 输出 dict,前端在此建模(边界原则同 plate.ts)。
 */

/** 常量池条目(后端 ConstantEntryOut 镜像)。literal 行 value 有值/spec=null;generator 行相反。 */
export interface ConstantEntry {
  id: number
  name: string
  description: string
  entry_kind: 'literal' | 'generator'
  value: unknown
  spec: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface ConstantEntryCreateIn {
  name: string
  description?: string
  entry_kind: 'literal' | 'generator'
  value?: unknown
  spec?: Record<string, unknown> | null
}

export interface ConstantEntryPatchIn {
  description?: string
  value?: unknown
  spec?: Record<string, unknown> | null
}

/** generators dim light view(kind 下拉用)。 */
export interface GeneratorKindView {
  kind: string
  summary: string
}

/** generators dim full view 的参数描述符(动态表单驱动)。 */
export interface GeneratorParamDesc {
  name: string
  type: 'string' | 'integer' | 'number' | 'boolean'
  required: boolean
  default: unknown
  enum: unknown[] | null
  min: number | null
  max: number | null
  description: string
}

/** generators dim full view(文档卡片 + 动态表单契约)。 */
export interface GeneratorKindDetailView {
  kind: string
  summary: string
  description: string
  params: GeneratorParamDesc[]
  example: Record<string, unknown>
}
```

创建 `src/gimbal-platform/frontend/src/api/constants.ts`:

```ts
/** constants.ts — /api/constants 常量池 CRUD 包装。 */
import http from './http'
import type {
  ConstantEntry,
  ConstantEntryCreateIn,
  ConstantEntryPatchIn,
} from '@/types/constants'

export function list() {
  return http.get<ConstantEntry[]>('/constants').then((r) => r.data)
}

export function create(payload: ConstantEntryCreateIn) {
  return http.post<ConstantEntry>('/constants', payload).then((r) => r.data)
}

export function patch(id: number, payload: ConstantEntryPatchIn) {
  return http.patch<ConstantEntry>(`/constants/${id}`, payload).then((r) => r.data)
}

export function remove(id: number) {
  return http.delete(`/constants/${id}`).then(() => undefined)
}
```

创建 `src/gimbal-platform/frontend/src/api/generator_catalog.ts`:

```ts
/** generator_catalog.ts — /api/generator-catalog(plate generators dim 代理,只读)。 */
import http from './http'
import type { GeneratorKindDetailView, GeneratorKindView } from '@/types/constants'

export function listGeneratorKinds() {
  return http.get<GeneratorKindView[]>('/generator-catalog').then((r) => r.data)
}

export function getGeneratorKindFull(kind: string) {
  return http
    .get<GeneratorKindDetailView>(`/generator-catalog/${kind}/full`)
    .then((r) => r.data)
}
```

- [x] **Step 6.2: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/stores/__tests__/constants.test.ts`:

```ts
/**
 * stores/constants — F19: ensureEntries in-flight 去重 + 已有数据短路;
 * 目录独立降级(catalogError 不抛);CRUD 乐观更新。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useConstantsStore } from '@/stores/constants'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'
import type { ConstantEntry } from '@/types/constants'

vi.mock('@/api/constants', () => ({
  list: vi.fn(),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/generator_catalog', () => ({
  listGeneratorKinds: vi.fn(),
  getGeneratorKindFull: vi.fn(),
}))

function entry(partial: Partial<ConstantEntry>): ConstantEntry {
  return {
    id: 1, name: 'x', description: '', entry_kind: 'literal',
    value: 'v', spec: null, created_at: '', updated_at: '',
    ...partial,
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})

describe('useConstantsStore', () => {
  it('F19a: ensureEntries 并发去重 — 双调用仅一次 list', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([
      entry({ id: 1, name: 'a' }),
    ])
    const s = useConstantsStore()
    await Promise.all([s.ensureEntries(), s.ensureEntries()])
    expect(constantsApi.list).toHaveBeenCalledTimes(1)
    expect(s.entries).toHaveLength(1)
  })

  it('F19b: 已有数据时 ensureEntries 短路(不再请求)', async () => {
    const s = useConstantsStore()
    s.entries = [entry({ id: 1 })]
    await s.ensureEntries()
    expect(constantsApi.list).not.toHaveBeenCalled()
  })

  it('F19c: 目录失败不抛 — catalogError 落地,条目链路不受影响', async () => {
    vi.mocked(catalogApi.listGeneratorKinds).mockRejectedValue(
      new Error('plate down'),
    )
    const s = useConstantsStore()
    await expect(s.ensureCatalog()).resolves.toEqual([])
    expect(s.catalogError).toBe('plate down')
    expect(s.fetchStatus).toBe('idle') // 目录失败不污染条目状态(pinia 自动解包 ref)
  })

  it('F19d: create/patch/remove 乐观更新(本地数组立即反映)', async () => {
    const s = useConstantsStore()
    const a = entry({ id: 1, name: 'a' })
    const b = entry({ id: 2, name: 'b', entry_kind: 'generator', value: null, spec: { kind: 'seq' } })
    vi.mocked(constantsApi.create)
      .mockResolvedValueOnce(a)
      .mockResolvedValueOnce(b)
    await s.createEntry({ name: 'a', entry_kind: 'literal', value: 'v' })
    await s.createEntry({ name: 'b', entry_kind: 'generator', spec: { kind: 'seq' } })
    expect(s.entries.map((e) => e.name)).toEqual(['a', 'b']) // name 升序

    vi.mocked(constantsApi.patch).mockResolvedValue(
      entry({ id: 1, name: 'a', description: '改' }),
    )
    await s.patchEntry(1, { description: '改' })
    expect(s.entries[0].description).toBe('改')

    vi.mocked(constantsApi.remove).mockResolvedValue(undefined)
    await s.removeEntry(2)
    expect(s.entries.map((e) => e.id)).toEqual([1])
  })
})
```

注意: `fetchStatus` 是否带 `.value` 取决于 `useSetStatus` 的实现(若 store 展开 return 的是 ref 则带 `.value`,若 `useSetStatus` 返回 reactive 则直接 `.fetchStatus`)——写测试前打开 `src/utils/useSetStatus.ts` 核对,以实际形态断言(auth_sessions store 是先例)。

- [x] **Step 6.3: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/stores/__tests__/constants.test.ts`
Expected: FAIL(`Failed to resolve import "@/stores/constants"`)

- [x] **Step 6.4: 写 store(全文)**

创建 `src/gimbal-platform/frontend/src/stores/constants.ts`:

```ts
/**
 * stores/constants.ts — 常量池(条目 + 生成器目录)共享 store。
 *
 * 两个消费方: 编排页 ConstantPoolPanel(条目)/ 管理页 ConstantsPool
 * (条目 CRUD + 目录文档)。条目与目录相互独立拉取、独立降级 ——
 * 目录(plate 代理)挂了不影响字面量 CRUD 与 Panel。
 * ensureEntries/ensureCatalog in-flight 去重: 双挂载点(CaseComposer
 * rail 与 Canvas)同时触发也只发一次请求。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'
import type {
  ConstantEntry,
  ConstantEntryCreateIn,
  ConstantEntryPatchIn,
  GeneratorKindView,
} from '@/types/constants'
import { useSetStatus } from '@/utils/useSetStatus'

const byName = (a: ConstantEntry, b: ConstantEntry) => a.name.localeCompare(b.name)

export const useConstantsStore = defineStore('constants', () => {
  const entries = ref<ConstantEntry[]>([])
  const catalog = ref<GeneratorKindView[]>([])
  const catalogError = ref('')
  const { fetchStatus, lastError, setStatus } = useSetStatus()

  let entriesInFlight: Promise<ConstantEntry[]> | null = null
  let catalogInFlight: Promise<GeneratorKindView[]> | null = null

  async function fetchEntries(): Promise<ConstantEntry[]> {
    setStatus('loading')
    try {
      entries.value = await constantsApi.list()
      setStatus('idle')
      return entries.value
    } catch (e) {
      setStatus('error', e instanceof Error ? e.message : 'fetch failed')
      throw e
    }
  }

  /** 幂等拉取(已有数据/已在途时短路)— 挂载点可直接 void 调用。 */
  function ensureEntries(): Promise<ConstantEntry[]> {
    if (entriesInFlight) return entriesInFlight
    if (entries.value.length) return Promise.resolve(entries.value)
    entriesInFlight = fetchEntries().finally(() => {
      entriesInFlight = null
    })
    return entriesInFlight
  }

  /** 目录拉取不 throw — 失败落 catalogError,消费方渲染降级条。 */
  function ensureCatalog(): Promise<GeneratorKindView[]> {
    if (catalogInFlight) return catalogInFlight
    if (catalog.value.length || catalogError.value) return Promise.resolve(catalog.value)
    catalogInFlight = catalogApi
      .listGeneratorKinds()
      .then((items) => {
        catalog.value = items
        catalogError.value = ''
        return items
      })
      .catch((e: unknown) => {
        catalogError.value = e instanceof Error ? e.message : '生成器目录不可用'
        return []
      })
      .finally(() => {
        catalogInFlight = null
      })
    return catalogInFlight
  }

  async function createEntry(payload: ConstantEntryCreateIn): Promise<ConstantEntry> {
    const en = await constantsApi.create(payload)
    entries.value = [...entries.value, en].sort(byName)
    return en
  }

  async function patchEntry(id: number, payload: ConstantEntryPatchIn): Promise<ConstantEntry> {
    const en = await constantsApi.patch(id, payload)
    const idx = entries.value.findIndex((x) => x.id === id)
    if (idx >= 0) entries.value[idx] = en
    return en
  }

  async function removeEntry(id: number): Promise<void> {
    await constantsApi.remove(id)
    entries.value = entries.value.filter((x) => x.id !== id)
  }

  return {
    entries,
    catalog,
    catalogError,
    fetchStatus,
    lastError,
    ensureEntries,
    ensureCatalog,
    createEntry,
    patchEntry,
    removeEntry,
  }
})
```

- [x] **Step 6.5: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/stores/__tests__/constants.test.ts`
Expected: 4 passed(若 F19c 的 fetchStatus 形态断言与 useSetStatus 实现不符,按 Step 6.2 注释核对后修正断言写法,语义不变:目录失败不污染条目状态)

- [x] **Step 6.6: Commit**

```bash
git add src/gimbal-platform/frontend/src/types/constants.ts src/gimbal-platform/frontend/src/api/constants.ts src/gimbal-platform/frontend/src/api/generator_catalog.ts src/gimbal-platform/frontend/src/stores/constants.ts src/gimbal-platform/frontend/src/stores/__tests__/constants.test.ts
git commit -m "feat(frontend): 常量池类型/api/store — ensureEntries 去重 + 目录独立降级

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: 前端 `ConstantPoolPanel.vue`(双载荷只读面板)

**Files:**
- Create: `src/gimbal-platform/frontend/src/components/composer/ConstantPoolPanel.vue`
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/ConstantPoolPanel.test.ts`

**Interfaces:**
- Consumes: `copyText`(T4)、`useSharedInsertTarget`(T5)、`ConstantEntry`(T6)。
- Produces(T8 依赖):
  - props:`{ entries: ConstantEntry[] }`(纯展示,拉取是挂载点职责)
  - emits:`seedVar: [name: string, spec: Record<string, unknown>]`(仅生成器 key 插入成功时发)
  - 行内按钮类名契约(测试/回归选择器):`.act-copy-key` / `.act-insert-key` / `.act-copy-value` / `.act-insert-value`;条目根 `[data-entry="<name>"]`;根类 `.cp-panel`
  - 复制/插入载荷:字面量 → 值文本(`String(value)`);生成器 key → `` `${var.<name>}` ``;生成器 value → `JSON.stringify(spec)` 紧凑文本

- [x] **Step 7.1: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/components/composer/__tests__/ConstantPoolPanel.test.ts`:

```ts
/**
 * ConstantPoolPanel — F4-F8:
 * F4 渲染(空态/条目/徽标/双载荷行);
 * F5 复制载荷(字面量值文本、生成器 key、生成器 spec JSON);
 * F6 生成器 key 插入成功 → 追加引用 + emit seedVar;
 * F7 value 插入纯文本(生成器 spec JSON / 字面量值)不 emit seedVar;
 * F8 无插入目标 → ElMessage.info 且不 emit。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ConstantPoolPanel from '@/components/composer/ConstantPoolPanel.vue'
import { INSERT_TARGET_KEY, useInsertTarget } from '@/composables/useInsertTarget'
import { copyText } from '@/utils/clipboard'
import { ElMessage } from 'element-plus'
import type { ConstantEntry } from '@/types/constants'

vi.mock('element-plus', () => ({
  ElMessage: { success: vi.fn(), info: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))
vi.mock('@/utils/clipboard', () => ({ copyText: vi.fn().mockResolvedValue(true) }))

const GEN: ConstantEntry = {
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', charset: 'alnum', length: 6, head: 'GIMBAL728', separator: '-' },
  created_at: '',
  updated_at: '',
}
const LIT: ConstantEntry = {
  id: 2,
  name: 'bank_id',
  description: '',
  entry_kind: 'literal',
  value: '319666690256273408',
  spec: null,
  created_at: '',
  updated_at: '',
}
const GEN_SPEC_JSON = JSON.stringify(GEN.spec)

function mountPanel(entries: ConstantEntry[]) {
  const inserter = useInsertTarget()
  const root = document.createElement('div')
  document.body.appendChild(root)
  inserter.start(root)
  const w = mount(ConstantPoolPanel, {
    props: { entries },
    global: { provide: { [INSERT_TARGET_KEY as symbol]: inserter } },
    attachTo: root,
  })
  return { w, inserter, root }
}

function focus(el: Element): void {
  el.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
}

beforeEach(() => {
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ConstantPoolPanel', () => {
  it('F4: 渲染条目/徽标/双载荷行;空态提示', () => {
    const { w } = mountPanel([GEN, LIT])
    expect(w.find('.cp-panel').exists()).toBe(true)
    const gen = w.find('[data-entry="bl_no"]')
    expect(gen.exists()).toBe(true)
    expect(gen.find('.cp-badge.generator').text()).toBe('生成器')
    expect(gen.find('.act-copy-key').exists()).toBe(true) // key 载荷行
    expect(gen.find('.act-copy-value').exists()).toBe(true) // value 载荷行
    const lit = w.find('[data-entry="bank_id"]')
    expect(lit.find('.cp-badge.literal').text()).toBe('常量')
    expect(lit.find('.act-copy-key').exists()).toBe(false) // 字面量无 key 行
    w.unmount()

    const empty = mountPanel([])
    expect(empty.w.text()).toContain('常量池为空')
    empty.w.unmount()
  })

  it('F5: 复制载荷 — 字面量值文本 / 生成器 key / 生成器 spec JSON', async () => {
    const { w } = mountPanel([GEN, LIT])
    await w.find('[data-entry="bank_id"] .act-copy-value').trigger('click')
    expect(copyText).toHaveBeenCalledWith('319666690256273408')

    await w.find('[data-entry="bl_no"] .act-copy-key').trigger('click')
    expect(copyText).toHaveBeenCalledWith('${var.bl_no}')

    await w.find('[data-entry="bl_no"] .act-copy-value').trigger('click')
    expect(copyText).toHaveBeenCalledWith(GEN_SPEC_JSON)
    w.unmount()
  })

  it('F6: 生成器 key 插入 → 追加引用 + emit seedVar(含 spec 快照)', async () => {
    const { w, root } = mountPanel([GEN])
    const input = document.createElement('input')
    input.type = 'text'
    input.value = 'prefix-'
    root.appendChild(input)
    focus(input)

    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    expect(input.value).toBe('prefix-${var.bl_no}')
    expect(w.emitted('seedVar')).toBeTruthy()
    const [[name, spec]] = w.emitted('seedVar')!
    expect(name).toBe('bl_no')
    expect(spec).toEqual(GEN.spec)
    w.unmount()
  })

  it('F7: value 插入纯文本(生成器 spec JSON / 字面量值)不 emit seedVar', async () => {
    const { w, root } = mountPanel([GEN, LIT])
    const input = document.createElement('input')
    input.type = 'text'
    root.appendChild(input)
    focus(input)

    await w.find('[data-entry="bl_no"] .act-insert-value').trigger('click')
    expect(input.value).toBe(GEN_SPEC_JSON)
    expect(w.emitted('seedVar')).toBeFalsy()

    await w.find('[data-entry="bank_id"] .act-insert-value').trigger('click')
    expect(input.value).toBe(`${GEN_SPEC_JSON}319666690256273408`)
    expect(w.emitted('seedVar')).toBeFalsy()
    w.unmount()
  })

  it('F8: 无插入目标 → ElMessage.info 且不 emit、不复制', async () => {
    const { w } = mountPanel([GEN])
    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    expect(ElMessage.info).toHaveBeenCalledWith(
      expect.stringContaining('请先点击'),
    )
    expect(w.emitted('seedVar')).toBeFalsy()
    expect(copyText).not.toHaveBeenCalled()
    w.unmount()
  })
})
```

- [x] **Step 7.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/ConstantPoolPanel.test.ts`
Expected: FAIL(`Failed to resolve import .../ConstantPoolPanel.vue`)

- [x] **Step 7.3: 写组件(全文)**

创建 `src/gimbal-platform/frontend/src/components/composer/ConstantPoolPanel.vue`:

```vue
<!--
  ConstantPoolPanel.vue — 常量池只读面板(编排四页常驻,两处挂载同一组件)

  挂载: ① CaseComposer 右栏 rail(步骤 0-2)② Canvas col-info(步骤 3,
  VariableRegistryPanel 之下)。数据由挂载点从 store 传入(纯 props),
  拉取(ensureEntries)是挂载点的职责 —— panel 保持 presentational。

  行结构(生成器双载荷,spec §复制/插入交互):
  - 字面量: value 复制/插入(插入=纯文本追加,无播种)
  - 生成器: key ${var.name} 与 value spec JSON 均可复制/插入;
    key 插入成功时 emit seedVar(由 CaseComposer 播种 config.vars 快照),
    value 插入=纯文本追加(它本身就是声明,无播种)。

  插入走 useSharedInsertTarget(composer 根 provide);无目标时
  ElMessage.info 提示且不播种。
-->
<template>
  <div class="cp-panel">
    <div class="cp-head">
      <span class="cp-title">常量池 <span class="cp-count">{{ entries.length }}</span></span>
      <router-link class="cp-manage" to="/constants" title="管理常量池">管理</router-link>
    </div>

    <div v-if="!entries.length" class="cp-empty">
      常量池为空 — 到「常量池」管理页添加常用值或生成器声明
    </div>

    <div v-for="e in entries" :key="e.id" class="cp-entry" :data-entry="e.name">
      <div class="cp-row cp-name-row">
        <span class="cp-name" :title="e.description || e.name">{{ e.name }}</span>
        <span class="cp-badge" :class="e.entry_kind">
          {{ e.entry_kind === 'generator' ? '生成器' : '常量' }}
        </span>
      </div>

      <!-- 生成器 key 载荷(字面量无此行) -->
      <div v-if="e.entry_kind === 'generator'" class="cp-row">
        <code class="cp-key" :title="keyText(e)">key&nbsp;&nbsp;{{ keyText(e) }}</code>
        <span class="cp-actions">
          <button class="cp-btn act-copy-key" title="复制引用" @click="copyKey(e)">复制</button>
          <button class="cp-btn act-insert-key" title="插入引用并播种 config.vars" @click="insertKey(e)">插入</button>
        </span>
      </div>

      <!-- value 载荷(字面量=值;生成器=spec JSON) -->
      <div class="cp-row">
        <code class="cp-value" :title="valueText(e)">value {{ displayValue(e) }}</code>
        <span class="cp-actions">
          <button class="cp-btn act-copy-value" title="复制内容" @click="copyValue(e)">复制</button>
          <button class="cp-btn act-insert-value" title="插入到字段" @click="insertValue(e)">插入</button>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { copyText } from '@/utils/clipboard'
import { useSharedInsertTarget } from '@/composables/useInsertTarget'
import type { ConstantEntry } from '@/types/constants'

const props = defineProps<{ entries: ConstantEntry[] }>()
const emit = defineEmits<{
  seedVar: [name: string, spec: Record<string, unknown>]
}>()

const inserter = useSharedInsertTarget()

const keyText = (e: ConstantEntry): string => `\${var.${e.name}}`
/** 复制/插入均为完整紧凑 JSON 文本;行内显示截断。 */
const valueText = (e: ConstantEntry): string =>
  e.entry_kind === 'generator' ? JSON.stringify(e.spec) : String(e.value)

const displayValue = (e: ConstantEntry): string => {
  const t = valueText(e)
  return t.length > 42 ? `${t.slice(0, 42)}…` : t
}

const NO_TARGET_MSG = '请先点击要插入的输入框'

function copyKey(e: ConstantEntry): void {
  void copyText(keyText(e)).then((ok) => {
    if (ok) ElMessage.success('已复制引用')
    else ElMessage.error('复制失败 — 请手动复制')
  })
}

function copyValue(e: ConstantEntry): void {
  void copyText(valueText(e)).then((ok) => {
    if (ok) ElMessage.success('已复制')
    else ElMessage.error('复制失败 — 请手动复制')
  })
}

/** key 插入: 追加引用文本;成功才 emit seedVar(快照播种,写入点在 CaseComposer)。 */
function insertKey(e: ConstantEntry): void {
  if (!inserter.appendValue(keyText(e))) {
    ElMessage.info(NO_TARGET_MSG)
    return
  }
  emit('seedVar', e.name, (e.spec ?? {}) as Record<string, unknown>)
}

/** value 插入: 纯文本追加 — 字面量=值文本,生成器=spec JSON(本身即声明,无播种)。 */
function insertValue(e: ConstantEntry): void {
  if (!inserter.appendValue(valueText(e))) {
    ElMessage.info(NO_TARGET_MSG)
  }
}
</script>

<style scoped>
/* 视觉对齐 VariableRegistryPanel(col-info 240-300px 适配) */
.cp-panel {
  padding: 10px 12px;
  background: var(--c-bg-secondary);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.cp-head { display: flex; align-items: center; justify-content: space-between; }
.cp-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.cp-count {
  font-family: var(--font-mono);
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 0 6px;
  margin-left: 4px;
  font-size: 10px;
}
.cp-manage { color: var(--c-text-tertiary); text-decoration: none; font-size: 11px; }
.cp-manage:hover { color: var(--c-text-primary, #0f172a); }
.cp-empty { font-size: 11px; color: var(--c-text-tertiary); line-height: 1.6; }
.cp-entry {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 4px 6px;
  border-radius: 5px;
  background: var(--c-surface);
}
.cp-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}
.cp-name {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: 11.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cp-badge {
  padding: 1px 5px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  flex-shrink: 0;
}
.cp-badge.generator { background: #f3e8ff; color: #6b21a8; }
.cp-badge.literal { background: #f1f5f9; color: #334155; }
.cp-key,
.cp-value {
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--c-text-secondary, #64748b);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.cp-actions { display: inline-flex; gap: 3px; flex-shrink: 0; }
.cp-btn {
  border: 1px solid var(--c-border);
  background: transparent;
  color: var(--c-text-tertiary);
  border-radius: 4px;
  font-size: 10px;
  padding: 0 5px;
  cursor: pointer;
}
.cp-btn:hover { background: var(--c-bg-secondary); color: var(--c-text-primary, #0f172a); }
</style>
```

- [x] **Step 7.4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/composer/__tests__/ConstantPoolPanel.test.ts`
Expected: 5 passed

- [x] **Step 7.5: Commit**

```bash
git add src/gimbal-platform/frontend/src/components/composer/ConstantPoolPanel.vue src/gimbal-platform/frontend/src/components/composer/__tests__/ConstantPoolPanel.test.ts
git commit -m "feat(frontend): ConstantPoolPanel — 双载荷行(引用/spec)复制/插入 + seedVar 事件

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: 播种纯函数 + CaseComposer rail + Canvas col-info 挂载

**Files:**
- Create: `src/gimbal-platform/frontend/src/utils/pool-var.ts`
- Test: `src/gimbal-platform/frontend/src/utils/__tests__/pool-var.test.ts`
- Modify: `src/gimbal-platform/frontend/src/views/CaseComposer.vue`(template root/L123-157 body/imports/onMounted/onUnmounted/onVarPromote 旁/CSS)
- Modify: `src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue`(col-info 末尾/emits/onMounted)
- Test: `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`(追加 describe)
- Test: `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.poolrail.test.ts`(新建)

**Interfaces:**
- Consumes: T6 store、T7 panel(`seedVar` 事件)、T5 `useInsertTarget`/`provideInsertTarget`。
- Produces: `seedPoolVarIntoDefinition<T>(definition, name, spec) → { definition: T; seeded: boolean }`(快照 `??=` 语义);CaseComposer 对 panel 的 `@seed-var` 处理 `seedPoolVar(name, spec)`;Canvas emits 追加 `'seedVar': [name: string, spec: Record<string, unknown>]`。

**既有锚点(2026-08-26 实测)**:CaseComposer 模板根 `<div class="composer-shell">`(L18);body 为 `<main class="body">`(L123)内单个 `<transition>`(L124-156)切 4 子视图,链条件 `stepIdx === 0/1/2/v-else`,`stepIdx = ref(0)`(L252)、`canRun = !!scenario && steps.length > 0`(L310)、query.step 1-based(L365-366);imports L217 `import { computed, onMounted, onUnmounted, ref, watch } from 'vue'`、L219 `ElMessage` 已有;RunDialog L200-212(v-if Teleport);顶栏运行按钮 L80-83。Canvas col-info 为 `<aside class="col col-info">`,`v-if="currentStep"` info-body 内 VariableRegistryPanel + `v-else` 空态;emits 含 `varPromote`;Canvas 已直接使用 draftStore 且导入了 onMounted。

- [x] **Step 8.1: 写播种纯函数失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/utils/__tests__/pool-var.test.ts`:

```ts
/**
 * pool-var — F10: seedPoolVarIntoDefinition 快照播种语义。
 * ??= 语义: 同名已存在不覆盖且 seeded=false;不存在则快照拷贝 spec 且不回灌。
 */
import { describe, it, expect } from 'vitest'
import { seedPoolVarIntoDefinition } from '@/utils/pool-var'

const SPEC = { kind: 'random_decorated', length: 6, head: 'GIMBAL728' }

describe('seedPoolVarIntoDefinition', () => {
  it('F10a: config/vars 缺失时创建并播种', () => {
    const def = { meta: { name: 'x' } } as { meta: unknown }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.seeded).toBe(true)
    expect((r.definition as { config?: { vars?: Record<string, unknown> } }).config?.vars)
      .toEqual({ bl_no: SPEC })
  })

  it('F10b: 同名已存在 → 不覆盖,seeded=false,原值保留', () => {
    const def = {
      config: { vars: { bl_no: { kind: 'seq', width: 8 } } },
    }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.seeded).toBe(false)
    expect(r.definition.config?.vars?.['bl_no']).toEqual({ kind: 'seq', width: 8 })
  })

  it('F10c: 播种后改动源 spec 对象不回灌(快照仅引用当次对象,原 def 不变异)', () => {
    const def = { config: { vars: {} } }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.definition).not.toBe(def) // 不可变更新
    expect(def.config?.vars).toEqual({}) // 原 def 未被改动
  })

  it('F10d: 其他变量共存,新增变量追加而非替换整表', () => {
    const def = { config: { vars: { keep: 'x' } } }
    const r = seedPoolVarIntoDefinition(def, 'bl_no', SPEC)
    expect(r.definition.config?.vars).toEqual({ keep: 'x', bl_no: SPEC })
  })
})
```

- [x] **Step 8.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/pool-var.test.ts`
Expected: FAIL(无法解析 `@/utils/pool-var`)

- [x] **Step 8.3: 写纯函数**

创建 `src/gimbal-platform/frontend/src/utils/pool-var.ts`:

```ts
/**
 * pool-var.ts — 常量池播种 config.vars 的纯函数(快照语义)。
 *
 * 引擎事实: config.vars 在 preprocess Phase 1.5 求值生成器、Phase 3
 * 展开 ${var.x};因此生成器 key 的"插入"除插引用文本外,还要把 spec
 * 快照播种进 config.vars(name 已存在则不覆盖 —— ??= 语义,提示走调用方)。
 * 纯函数与组件解耦,便于单测快照语义。
 */

export interface SeedVarResult<T> {
  definition: T
  /** false = 同名已存在,未播种(调用方提示"使用现有值")。 */
  seeded: boolean
}

export function seedPoolVarIntoDefinition<
  T extends { config?: { vars?: Record<string, unknown> } | null },
>(definition: T, name: string, spec: Record<string, unknown>): SeedVarResult<T> {
  const config = definition.config ?? { vars: {} as Record<string, unknown> }
  const vars = { ...(config.vars ?? {}) }
  let seeded = false
  if (!Object.prototype.hasOwnProperty.call(vars, name)) {
    vars[name] = spec
    seeded = true
  }
  return {
    definition: { ...definition, config: { ...config, vars } },
    seeded,
  }
}
```

- [x] **Step 8.4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/pool-var.test.ts`
Expected: 4 passed

- [x] **Step 8.5: 写 CaseComposer/Canvas 集成失败测试**

创建 `src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.poolrail.test.ts`:

```ts
/**
 * CaseComposer — F9/F11 常量池 rail:
 * F9  步骤 0-2 右栏 rail 常驻,步骤 3(Canvas)rail 消失、panel 转挂
 *     col-info,且 Canvas 侧插入可播种 config.vars(集成链);
 * F11 RunDialog 打开时 DOM 内 panel 数量不变且 overlay 中无 panel。
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaseComposer from '@/views/CaseComposer.vue'
import * as api from '@/api/scenario-composer'
import type { Scenario } from '@/types/scenario-composer'
import { useScenarioDraftStore } from '@/stores/scenario-draft'

const mockRoute: { params: { scenarioId: string }; query: Record<string, string> } = {
  params: { scenarioId: 'sc-demo' },
  query: {},
}
vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => mockRoute,
    useRouter: () => ({ push: vi.fn(), replace: vi.fn().mockResolvedValue(undefined) }),
  }
})

const GEN_ENTRY = {
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', length: 6, head: 'GIMBAL728', separator: '-' },
  created_at: '',
  updated_at: '',
}
vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([GEN_ENTRY]),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
vi.mock('@/api/auth_sessions', () => ({
  list: vi.fn().mockResolvedValue([]),
}))

function sampleScenario(steps: unknown[]): Scenario {
  return {
    meta: {
      scenarioId: 'sc-demo',
      name: '订单创建 e2e',
      description: '',
      module: '订单',
      priority: 1,
      author: 'qa',
      owner: 'qa',
      tags: [],
      system: ['fin'],
      version: 'v0.1.0',
      expire: false,
      createTime: '2026-01-01T00:00:00Z',
    },
    steps: steps as Scenario['steps'],
    orchestration: { steps: [], resourceMeta: {} },
    dataSetCount: 0,
    stepCount: steps.length,
    tags: [],
  }
}

function mountPage() {
  return mount(CaseComposer, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

function nextBtn(w: ReturnType<typeof mount>) {
  return w
    .findAll('footer button.primary-btn')
    .find((b) => !b.classes().includes('outline'))
}

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(api, 'listEnvs').mockResolvedValue([])
  vi.spyOn(api, 'listDataSets').mockResolvedValue([])
  // constants/auth_sessions 走 vi.mock 工厂(restoreAllMocks 不影响工厂 mock)
})

describe('CaseComposer — 常量池 rail', () => {
  it('F9a: 步骤① rail 常驻(with-rail 布局 + panel 渲染条目)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario([]))
    const w = mountPage()
    await flushPromises()

    expect(w.find('.body-split.with-rail').exists()).toBe(true)
    const rail = w.find('.pool-rail')
    expect(rail.exists()).toBe(true)
    expect(rail.find('.cp-panel').exists()).toBe(true)
    expect(rail.find('[data-entry="bl_no"]').exists()).toBe(true)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F9b: 连续「下一步」到步骤④ — rail 消失,panel 转挂 Canvas col-info', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(sampleScenario([]))
    const w = mountPage()
    await flushPromises()

    for (let i = 0; i < 3; i++) {
      const btn = nextBtn(w)!
      expect(btn.text()).toContain('下一步')
      await btn.trigger('click')
      await flushPromises()
    }
    expect(w.find('.body-split.with-rail').exists()).toBe(false)
    expect(w.find('.pool-rail').exists()).toBe(false)
    const info = w.find('.col-info')
    expect(info.exists()).toBe(true)
    expect(info.find('.cp-panel').exists()).toBe(true)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F9c: Canvas 侧插入生成器 key → config.vars 播种(??= 集成链)', async () => {
    // 一个可渲染的最小 step:仅证明链路,detail 结构由 Canvas 既有测试覆盖
    vi.spyOn(api, 'getScenario').mockResolvedValue(
      sampleScenario([{ api: { service: 'settlement', method: 'POST', path: '/x' } }]),
    )
    const w = mountPage()
    await flushPromises()
    for (let i = 0; i < 3; i++) {
      await nextBtn(w)!.trigger('click')
      await flushPromises()
    }

    const input = w.element.querySelector('input') as HTMLInputElement | null
    expect(input).toBeTruthy()
    input!.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    await w.find('.col-info [data-entry="bl_no"] .act-insert-key').trigger('click')
    await flushPromises()

    const draft = useScenarioDraftStore()
    const vars = draft.draft?.definition?.config?.vars as Record<string, unknown>
    expect(vars?.['bl_no']).toEqual(GEN_ENTRY.spec)
    w.unmount()
    document.body.innerHTML = ''
  })

  it('F11: RunDialog 打开时 overlay 内无 panel(panel 数量不变)', async () => {
    vi.spyOn(api, 'getScenario').mockResolvedValue(
      sampleScenario([{ api: { service: 'settlement', method: 'POST', path: '/x' } }]),
    )
    const w = mountPage()
    await flushPromises()
    expect(document.querySelectorAll('.cp-panel').length).toBe(1)

    // 顶栏「运行」按钮(canRun: scenario + steps>0)
    const runBtn = w.find('header .primary-btn')
    expect(runBtn.attributes('disabled')).toBeUndefined()
    await runBtn.trigger('click')
    await flushPromises()

    expect(document.querySelectorAll('.el-overlay').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('.cp-panel').length).toBe(1) // 仍是 rail 那份
    expect(document.querySelectorAll('.el-overlay .cp-panel').length).toBe(0)
    w.unmount()
    document.body.innerHTML = ''
  })
})
```

注意: F9c/F11 的最小 step 形状若导致渲染报错(以 CaseComposer 加载/Canvas 渲染实测为准),改用 Canvas 既有测试文件里 `mkStep()` 的真实形状内联到这里(打开 `src/components/composer/__tests__/CaseComposerCanvas.test.ts` 抄字段),断言不变。

- [x] **Step 8.6: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/CaseComposer.poolrail.test.ts`
Expected: FAIL(`.body-split`/`.pool-rail`/`.col-info .cp-panel` 找不到)

- [x] **Step 8.7: 改 CaseComposer(template + script + CSS)**

`src/gimbal-platform/frontend/src/views/CaseComposer.vue` 五处修改:

① 模板根(L18)加 ref:

```html
<div ref="rootEl" class="composer-shell" :class="{ 'has-run-open': runDialogOpen }">
```

② body(L123-157)包 body-split,Canvas 加 seed-var 转发:

```html
<main class="body">
  <div class="body-split" :class="{ 'with-rail': showPoolRail }">
    <div class="body-main">
      <transition name="slide" mode="out-in">
        <!-- ① Meta -->
        <CaseComposerMeta
          v-if="stepIdx === 0"
          key="meta"
          v-model="definition.meta"
        />

        <!-- ② Resource -->
        <CaseComposerResource
          v-else-if="stepIdx === 1"
          key="resource"
          v-model:resource="definition.resource"
          v-model:resource-meta="orchestration.resourceMeta"
        />

        <!-- ③ Config -->
        <CaseComposerConfig
          v-else-if="stepIdx === 2"
          key="config"
          v-model="definition.config"
        />

        <!-- ④ Canvas -->
        <CaseComposerCanvas
          v-else
          key="canvas"
          v-model:steps="definition.steps"
          v-model:orchestration="orchestration"
          :scenario="scenario"
          @var-promote="onVarPromote"
          @seed-var="seedPoolVar"
        />
      </transition>
    </div>

    <!-- 常量池 rail(步骤 0-2;步骤 3 挂在 Canvas col-info,同一组件) -->
    <aside v-if="showPoolRail" class="pool-rail">
      <ConstantPoolPanel :entries="constantsStore.entries" @seed-var="seedPoolVar" />
    </aside>
  </div>
</main>
```

③ imports(在 RunDialog import 之后补):

```ts
import ConstantPoolPanel from '@/components/composer/ConstantPoolPanel.vue'
import { provideInsertTarget, useInsertTarget } from '@/composables/useInsertTarget'
import { seedPoolVarIntoDefinition } from '@/utils/pool-var'
import { useConstantsStore } from '@/stores/constants'
```

④ script 状态(onVarPromote 函数旁新增;`stepIdx` 定义之后加 computed):

```ts
const constantsStore = useConstantsStore()
const rootEl = ref<HTMLElement | null>(null)
const inserter = useInsertTarget()
provideInsertTarget(inserter)

/** 常量池 rail: 步骤 0-2(步骤 3 面板挂在 Canvas col-info) */
const showPoolRail = computed(() => stepIdx.value < 3)

/** 常量池播种(生成器 key 插入链): 快照拷贝进 config.vars,已存在不覆盖。 */
function seedPoolVar(name: string, spec: Record<string, unknown>): void {
  const result = seedPoolVarIntoDefinition(definition.value, name, spec)
  definition.value = result.definition
  if (!result.seeded) {
    ElMessage.info(`config.vars 已有同名变量 ${name},使用现有值`)
  }
}
```

(`definition` 是该文件既有场景定义 ref,onVarPromote L354-361 同款写法;其类型(ScenarioView 族)本就含 `config`,满足 `seedPoolVarIntoDefinition` 的泛型约束 —— 若个别类型声明缺 `config` 字段导致 vue-tsc 报错,以 `seedPoolVarIntoDefinition(definition.value as Parameters<typeof seedPoolVarIntoDefinition>[0], name, spec)` 收窄。)

⑤ 既有 onMounted 回调内追加两行、既有 onUnmounted 回调内追加一行(onMounted 内在 `if (rootEl.value) inserter.start(rootEl.value)` 之后接 ensureEntries;onUnmounted 加 `inserter.stop()`):

```ts
  if (rootEl.value) inserter.start(rootEl.value)
  void constantsStore.ensureEntries().catch(() => {})
```

⑥ `<style>` 末尾追加:

```css
/* ── 常量池 rail(步骤 0-2 右栏,body-split 布局;步骤 3 挂 Canvas col-info)── */
.body-split {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
  height: 100%;
  min-height: 0;
}
.body-split.with-rail {
  grid-template-columns: minmax(0, 1fr) minmax(240px, 300px);
}
.body-main { min-width: 0; min-height: 0; }
.pool-rail {
  position: sticky;
  top: 8px;
  align-self: start;
  max-height: calc(100vh - 16px);
  overflow: auto;
}
@media (max-width: 1280px) {
  .body-split.with-rail { grid-template-columns: minmax(0, 1fr); }
  .pool-rail { position: static; max-height: none; }
}
```

- [x] **Step 8.8: 改 Canvas(col-info 常驻 + seedVar 转发)**

`src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue` 三处:

① imports 补:

```ts
import ConstantPoolPanel from './ConstantPoolPanel.vue'
import { useConstantsStore } from '@/stores/constants'
```

② script(与其他 store 使用同区):

```ts
const constantsStore = useConstantsStore()
```

既有 onMounted 回调内追加(CaseComposer rail 之外的第二拉取点;store 内 in-flight/已有数据短路保证只发一次):

```ts
  void constantsStore.ensureEntries().catch(() => {})
```

③ emits 定义追加一项(既有 `'varPromote'` 之后):

```ts
  'seedVar': [name: string, spec: Record<string, unknown>],
```

④ `<aside class="col col-info">` 内,`v-if="currentStep"` info-body 块与其 `v-else` 空态块之后(`</aside>` 之前,即 aside 最后一个子元素)追加:

```html
      <!-- 常量池(编排页常驻;VRP 之下,无选中 step 时也在) -->
      <ConstantPoolPanel
        :entries="constantsStore.entries"
        @seed-var="(n: string, s: Record<string, unknown>) => emit('seedVar', n, s)"
      />
```

(`emit` 是该文件既有 `const emit = defineEmits<...>()` 变量;若模板内联箭头函数与 ESLint 模板规则冲突,改为 methods 区转发函数 `onPoolSeedVar` 同效。)

- [x] **Step 8.9: Canvas 测试文件追加 F12/F13**

在 `src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts`:

顶部 import 区补(与既有 import 合并;`mkStep`/`mkOrch`/`activePinia`/`ElementPlus` 该文件已有):

```ts
import { provide, defineComponent, h, ref } from 'vue'
import { useInsertTarget, INSERT_TARGET_KEY } from '@/composables/useInsertTarget'
import { useConstantsStore } from '@/stores/constants'
import type { ConstantEntry } from '@/types/constants'
```

vi.mock 区(既有两个 vi.mock 旁)追加:

```ts
vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([]),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn(),
}))
```

文件末尾追加 describe(挂载方式镜像该文件既有 `mountCanvas` 的 Parent 包装,仅多 provide insert target):

```ts
describe('CaseComposerCanvas — 常量池 col-info 常驻(F12/F13)', () => {
  const GEN: ConstantEntry = {
    id: 1,
    name: 'bl_no',
    description: '',
    entry_kind: 'generator',
    value: null,
    spec: { kind: 'random_decorated', length: 6 },
    created_at: '',
    updated_at: '',
  }

  function mountCanvasWithPool(entries: ConstantEntry[]) {
    const store = useConstantsStore()
    store.entries = entries
    const inserter = useInsertTarget()
    inserter.start(document.body)
    const Parent = defineComponent({
      setup() {
        provide(INSERT_TARGET_KEY, inserter)
        const steps = ref([mkStep()])
        const orch = ref(mkOrch())
        return () =>
          h(CaseComposerCanvas, {
            steps: steps.value,
            orchestration: orch.value,
            'onUpdate:steps': (v: unknown) => {
              steps.value = v as typeof steps.value
            },
            'onUpdate:orchestration': (v: unknown) => {
              orch.value = v as typeof orch.value
            },
          })
      },
    })
    return mount(Parent, {
      global: { plugins: [ElementPlus, activePinia] },
      attachTo: document.body,
    })
  }

  it('F12: panel 常驻 col-info(VRP/info-empty 之后、aside 最后一个子元素)', async () => {
    const w = mountCanvasWithPool([GEN])
    await flushPromises()
    const info = w.find('.col-info')
    expect(info.exists()).toBe(true)
    const panel = info.find('.cp-panel')
    expect(panel.exists()).toBe(true) // 无选中 step 时也常驻
    expect(info.element.lastElementChild!.classList.contains('cp-panel')).toBe(true)
    w.unmount()
  })

  it('F13: panel 插入生成器 key → Canvas 转发 seedVar 事件', async () => {
    const w = mountCanvasWithPool([GEN])
    await flushPromises()
    const input = w.element.querySelector('input') as HTMLInputElement
    expect(input).toBeTruthy()
    input.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    await w.find('[data-entry="bl_no"] .act-insert-key').trigger('click')
    const canvas = w.findComponent(CaseComposerCanvas)
    expect(canvas.emitted('seedVar')).toBeTruthy()
    const [[name, spec]] = canvas.emitted('seedVar')!
    expect(name).toBe('bl_no')
    expect(spec).toEqual(GEN.spec)
    w.unmount()
  })
})
```

(`CaseComposerCanvas`/`mkStep`/`mkOrch`/`flushPromises` 用该文件既有导入;若 `mkStep()` 需要 body 字段才能渲染出 input,以其现签名为准传参 —— F13 断言不依赖具体字段。)

- [x] **Step 8.10: 跑本任务全部测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/utils/__tests__/pool-var.test.ts src/views/__tests__/CaseComposer.poolrail.test.ts src/components/composer/__tests__/CaseComposerCanvas.test.ts src/components/composer/__tests__/ConstantPoolPanel.test.ts`
Expected: 全部 passed(含 Canvas 既有用例)

- [x] **Step 8.11: Commit**

```bash
git add src/gimbal-platform/frontend/src/utils/pool-var.ts src/gimbal-platform/frontend/src/utils/__tests__/pool-var.test.ts src/gimbal-platform/frontend/src/views/CaseComposer.vue src/gimbal-platform/frontend/src/components/composer/CaseComposerCanvas.vue src/gimbal-platform/frontend/src/components/composer/__tests__/CaseComposerCanvas.test.ts src/gimbal-platform/frontend/src/views/__tests__/CaseComposer.poolrail.test.ts
git commit -m "feat(frontend): 常量池 rail/col-info 双挂载 + config.vars 快照播种(??= 语义)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: 前端管理页 `ConstantsPool.vue`

**Files:**
- Create: `src/gimbal-platform/frontend/src/views/ConstantsPool.vue`
- Test: `src/gimbal-platform/frontend/src/views/__tests__/ConstantsPool.test.ts`

**Interfaces:**
- Consumes: T6 store(`entries`/`catalog`/`catalogError`/`ensureEntries`/`ensureCatalog`/CRUD)、`getGeneratorKindFull`、`copyText`、`ElMessageBox`。
- Produces: `/constants` 页面(Task 10 路由指向)。测试选择器契约:目录卡 `.kind-card[data-kind]`、降级条 `.degraded`、条目表 `[data-testid="entries-table"]`、行操作 `[data-action="edit"|"delete"]`、弹框 `[data-testid="entry-dialog"]`、表单字段 `[data-field="<名>"]`、kind 芯片 `.kind-chip[data-kind]`、spec 预览 `[data-testid="spec-preview"]`、提交 `[data-action="submit"]`。

- [x] **Step 9.1: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/views/__tests__/ConstantsPool.test.ts`:

```ts
/**
 * ConstantsPool 管理页 — F14-F18:
 * F14 目录卡片渲染(kind/summary,展开拉 full);
 * F15 字面量新增(默认 string 类型,POST 载荷含 value 文本);
 * F16 生成器新增(目录驱动动态表单 + spec 预览,POST 载荷含 spec);
 * F17 编辑预填 + 删除确认流;
 * F18 目录降级(降级条 + 生成器不可选;字面量 CRUD 不受影响)。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus, { ElMessageBox } from 'element-plus'
import ConstantsPool from '@/views/ConstantsPool.vue'
import * as constantsApi from '@/api/constants'
import * as catalogApi from '@/api/generator_catalog'

vi.mock('@/api/constants', () => ({
  list: vi.fn().mockResolvedValue([]),
  create: vi.fn(),
  patch: vi.fn(),
  remove: vi.fn().mockResolvedValue(undefined),
}))
vi.mock('@/api/generator_catalog', () => ({
  listGeneratorKinds: vi.fn(),
  getGeneratorKindFull: vi.fn(),
}))
vi.mock('element-plus', async (importOriginal) => {
  const actual = await importOriginal<typeof import('element-plus')>()
  return { ...actual, ElMessageBox: { confirm: vi.fn().mockResolvedValue('confirm') } }
})

const SEQ_FULL = {
  kind: 'seq',
  summary: '自增序号',
  description: '执行内自增序号:prefix 前缀 + width 位零填充,从 start 起。',
  params: [
    { name: 'prefix', type: 'string', required: false, default: '', enum: null, min: null, max: null, description: '序号前缀' },
    { name: 'width', type: 'integer', required: false, default: 6, enum: null, min: 1, max: 20, description: '零填充宽度' },
    { name: 'start', type: 'integer', required: false, default: 1, enum: null, min: null, max: null, description: '起始值' },
  ],
  example: { kind: 'seq', prefix: 'BL', width: 6, start: 1 },
}

const GEN_ROW = {
  id: 1,
  name: 'bl_no',
  description: '业务单号',
  entry_kind: 'generator',
  value: null,
  spec: { kind: 'random_decorated', length: 6, head: 'GIMBAL728' },
  created_at: '2026-08-26T00:00:00Z',
  updated_at: '2026-08-26T00:00:00Z',
}

function mountPage() {
  return mount(ConstantsPool, {
    global: { plugins: [ElementPlus, createPinia()] },
    attachTo: document.body,
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  vi.mocked(catalogApi.listGeneratorKinds).mockResolvedValue([
    { kind: 'uuid', summary: 'UUID' },
    { kind: 'seq', summary: '自增序号' },
  ])
  vi.mocked(catalogApi.getGeneratorKindFull).mockResolvedValue(SEQ_FULL)
  vi.clearAllMocks()
})

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ConstantsPool — 目录', () => {
  it('F14: 渲染 kind 卡片;展开拉 full 并渲染参数表与示例', async () => {
    const w = mountPage()
    await flushPromises()
    const cards = w.findAll('.kind-card')
    expect(cards).toHaveLength(2)
    expect(cards[1].attributes('data-kind')).toBe('seq')
    expect(cards[1].text()).toContain('自增序号')

    await cards[1].find('.kind-head').trigger('click')
    await flushPromises()
    expect(catalogApi.getGeneratorKindFull).toHaveBeenCalledWith('seq')
    expect(w.find('[data-param="width"]').text()).toContain('零填充宽度')
    expect(w.text()).toContain('"kind": "seq"') // 示例 JSON
    w.unmount()
  })

  it('F18: 目录不可用 — 降级条 + 生成器类型禁用,条目表仍渲染', async () => {
    vi.mocked(catalogApi.listGeneratorKinds).mockRejectedValue(new Error('plate down'))
    vi.mocked(constantsApi.list).mockResolvedValue([GEN_ROW as never])
    const w = mountPage()
    await flushPromises()

    expect(w.find('.degraded').exists()).toBe(true)
    const radios = w.findAll('.el-radio-button')
    expect(radios.some((r) => r.classes().includes('is-disabled'))).toBe(true)

    await w.find('[data-action="pool-create"]').trigger('click') // 字面量 CRUD 入口仍在
    expect(w.find('[data-testid="entry-dialog"]').exists()).toBe(true)
    expect(w.findAll('.el-table__row')).toHaveLength(1)
    w.unmount()
  })
})

describe('ConstantsPool — 条目 CRUD', () => {
  it('F15: 新增字面量(默认 string)→ create 载荷含值文本', async () => {
    vi.mocked(constantsApi.create).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="pool-create"]').trigger('click')
    await flushPromises()
    await w.find('[data-field="name"] input').setValue('bank_id')
    await w.find('[data-field="valueStr"] input').setValue('319666690256273408')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()

    expect(constantsApi.create).toHaveBeenCalledWith({
      name: 'bank_id',
      description: '',
      entry_kind: 'literal',
      value: '319666690256273408',
    })
    w.unmount()
  })

  it('F16: 新增生成器 — kind 芯片 → 动态参数(默认预填)+ spec 预览 → create 含 spec', async () => {
    vi.mocked(constantsApi.create).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="pool-create"]').trigger('click')
    await flushPromises()
    await w.find('[data-field="entry_kind"] input[value="generator"]').trigger('click')
    await flushPromises()
    await w.find('.kind-chip[data-kind="seq"]').trigger('click')
    await flushPromises()
    expect(w.find('[data-field="param-prefix"] input').exists()).toBe(true)
    // 默认预填: prefix='' 被剔除, width/start 取默认
    expect(w.find('[data-testid="spec-preview"]').text()).toContain('"kind":"seq"')

    await w.find('[data-field="name"] input').setValue('order_seq')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()

    expect(constantsApi.create).toHaveBeenCalledWith({
      name: 'order_seq',
      description: '',
      entry_kind: 'generator',
      spec: { kind: 'seq', width: 6, start: 1 },
    })
    w.unmount()
  })

  it('F17: 编辑预填 + 删除确认', async () => {
    vi.mocked(constantsApi.list).mockResolvedValue([GEN_ROW as never])
    vi.mocked(catalogApi.getGeneratorKindFull).mockResolvedValue(SEQ_FULL)
    vi.mocked(constantsApi.patch).mockResolvedValue(GEN_ROW as never)
    const w = mountPage()
    await flushPromises()

    await w.find('[data-action="edit"]').trigger('click')
    await flushPromises()
    const nameInput = w.find('[data-field="name"] input')
    expect((nameInput.element as HTMLInputElement).value).toBe('bl_no')
    expect(w.find('[data-testid="spec-preview"]').text()).toContain('random_decorated')
    await w.find('[data-action="submit"]').trigger('click')
    await flushPromises()
    expect(constantsApi.patch).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ description: '业务单号' }),
    )

    await w.find('[data-action="delete"]').trigger('click')
    await flushPromises()
    expect(ElMessageBox.confirm).toHaveBeenCalled()
    expect(constantsApi.remove).toHaveBeenCalledWith(1)
    w.unmount()
  })
})
```

(注意: F18 的 `[data-action="pool-create"]` 是新增按钮选择器契约;若实现时按钮改名,同步改测试 —— 两者都在本任务内。)

- [x] **Step 9.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/ConstantsPool.test.ts`
Expected: FAIL(无法解析 `@/views/ConstantsPool.vue`)

- [x] **Step 9.3: 写管理页组件(全文)**

创建 `src/gimbal-platform/frontend/src/views/ConstantsPool.vue`:

```vue
<!--
  ConstantsPool.vue — 常量池管理页(/constants)

  上半: 生成器模板目录(只读,plate 代理;kind 可折叠卡片: 说明/参数表/
  示例 JSON 复制)。下半: 我的常量池(el-table CRUD;新增/编辑共享弹框 —
  字面量四型值控件 / 生成器目录驱动动态参数表单 + 实时 spec 预览)。
  降级: 目录不可用 → 模板区降级条 + 生成器类型禁用;字面量 CRUD 不受影响。
-->
<template>
  <div class="constants-page">
    <header class="page-head">
      <h1>常量池</h1>
      <p class="muted">常用字面值与生成器声明 — 编排页右栏「常量池」面板可直接复制/插入</p>
    </header>

    <!-- ── 生成器模板目录 ── -->
    <section class="card catalog">
      <div class="section-head">
        <h2>生成器模板目录</h2>
        <span v-if="constantsStore.catalogError" class="degraded">
          {{ constantsStore.catalogError }} — 目录暂不可用,字面量条目不受影响
        </span>
      </div>
      <div v-for="k in constantsStore.catalog" :key="k.kind" class="kind-card" :data-kind="k.kind">
        <button class="kind-head" @click="toggleKind(k.kind)">
          <span class="chevron" :class="{ open: openKinds.has(k.kind) }">▸</span>
          <code class="kind-name">{{ k.kind }}</code>
          <span class="kind-summary">{{ k.summary }}</span>
        </button>
        <div v-if="openKinds.has(k.kind)" class="kind-body">
          <template v-if="fulls[k.kind]">
            <p class="kind-desc">{{ fulls[k.kind]!.description }}</p>
            <table v-if="fulls[k.kind]!.params.length" class="params-table">
              <thead>
                <tr><th>参数</th><th>类型</th><th>必填</th><th>默认</th><th>可选值/范围</th><th>说明</th></tr>
              </thead>
              <tbody>
                <tr v-for="p in fulls[k.kind]!.params" :key="p.name" :data-param="p.name">
                  <td><code>{{ p.name }}</code></td>
                  <td>{{ p.type }}</td>
                  <td>{{ p.required ? '是' : '否' }}</td>
                  <td>{{ p.default === null || p.default === undefined ? '—' : JSON.stringify(p.default) }}</td>
                  <td>{{ paramRange(p) }}</td>
                  <td>{{ p.description }}</td>
                </tr>
              </tbody>
            </table>
            <p v-else class="muted">无参数</p>
            <div class="example-row">
              <pre class="example-json">{{ JSON.stringify(fulls[k.kind]!.example) }}</pre>
              <button class="ghost-btn" @click="copyExample(fulls[k.kind]!)">复制 JSON</button>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- ── 我的常量池 ── -->
    <section class="card entries">
      <div class="section-head">
        <h2>我的常量池</h2>
        <button class="primary-btn" data-action="pool-create" @click="openCreate">新增</button>
      </div>
      <el-table :data="constantsStore.entries" data-testid="entries-table">
        <el-table-column prop="name" label="名称" width="180">
          <template #default="{ row }"><code>{{ row.name }}</code></template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.entry_kind === 'generator' ? 'warning' : 'info'" size="small">
              {{ row.entry_kind === 'generator' ? '生成器' : '常量' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="内容">
          <template #default="{ row }">
            <code class="entry-value">{{ entryValueText(row) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" width="200" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <button class="ghost-btn" data-action="edit" @click="openEdit(row)">编辑</button>
            <button class="ghost-btn danger" data-action="delete" @click="onDelete(row)">删除</button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- ── 新增/编辑弹框 ── -->
    <el-dialog
      v-model="dialogOpen"
      :title="editing ? '编辑常量' : '新增常量'"
      width="560px"
      data-testid="entry-dialog"
    >
      <el-form label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" data-field="name" placeholder="A-Z a-z 0-9 _,1-64 字符" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" data-field="description" placeholder="可选" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.entry_kind" :disabled="editing" data-field="entry_kind">
            <el-radio-button value="literal">常量(字面值)</el-radio-button>
            <el-radio-button value="generator" :disabled="!!constantsStore.catalogError">
              生成器
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <template v-if="form.entry_kind === 'literal'">
          <el-form-item label="值类型">
            <el-select v-model="form.valueType" data-field="valueType">
              <el-option label="字符串" value="string" />
              <el-option label="整数" value="integer" />
              <el-option label="小数" value="decimal" />
              <el-option label="布尔" value="boolean" />
            </el-select>
          </el-form-item>
          <el-form-item label="值" required>
            <el-switch
              v-if="form.valueType === 'boolean'"
              v-model="form.valueBool"
              data-field="valueBool"
            />
            <el-input-number
              v-else-if="form.valueType !== 'string'"
              v-model="form.valueNum"
              data-field="valueNum"
            />
            <el-input v-else v-model="form.valueStr" data-field="valueStr" placeholder="字面值文本" />
          </el-form-item>
        </template>

        <template v-else>
          <el-form-item label="生成器" required>
            <div class="kind-chips">
              <button
                v-for="k in constantsStore.catalog"
                :key="k.kind"
                type="button"
                class="kind-chip"
                :class="{ active: form.genKind === k.kind }"
                :data-kind="k.kind"
                :title="k.summary"
                @click="selectGenKind(k.kind)"
              >{{ k.kind }}</button>
            </div>
          </el-form-item>
          <p v-if="constantsStore.catalogError" class="muted">目录不可用,无法配置生成器条目</p>
          <el-form-item
            v-for="p in genParams"
            :key="p.name"
            :label="p.name"
            :required="p.required"
          >
            <el-select
              v-if="p.enum"
              :model-value="form.genParams[p.name]"
              :data-field="`param-${p.name}`"
              @update:model-value="(v) => setParam(p.name, v)"
            >
              <el-option v-for="v in p.enum" :key="String(v)" :value="v" :label="String(v)" />
            </el-select>
            <el-switch
              v-else-if="p.type === 'boolean'"
              :model-value="form.genParams[p.name] === true"
              :data-field="`param-${p.name}`"
              @change="(v) => setParam(p.name, v === true)"
            />
            <el-input-number
              v-else-if="p.type === 'integer' || p.type === 'number'"
              :model-value="form.genParams[p.name] as number | undefined"
              :min="p.min ?? undefined"
              :max="p.max ?? undefined"
              :data-field="`param-${p.name}`"
              @update:model-value="(v) => setParam(p.name, v)"
            />
            <el-input
              v-else
              :model-value="String(form.genParams[p.name] ?? '')"
              :data-field="`param-${p.name}`"
              @update:model-value="(v) => setParam(p.name, v)"
            />
            <span class="muted param-hint">{{ p.description }}</span>
          </el-form-item>
          <el-form-item label="spec 预览">
            <div class="spec-preview">
              <pre data-testid="spec-preview">{{ specPreview }}</pre>
              <button class="ghost-btn" data-action="copy-spec" @click="copySpec">复制</button>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <button class="ghost-btn" @click="dialogOpen = false">取消</button>
        <button class="primary-btn" data-action="submit" :disabled="!canSubmit" @click="onSubmit">
          保存
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useConstantsStore } from '@/stores/constants'
import { getGeneratorKindFull } from '@/api/generator_catalog'
import { copyText } from '@/utils/clipboard'
import type {
  ConstantEntry,
  GeneratorKindDetailView,
  GeneratorParamDesc,
} from '@/types/constants'

const constantsStore = useConstantsStore()

onMounted(() => {
  void constantsStore.ensureEntries().catch(() => ElMessage.error('常量池加载失败'))
  void constantsStore.ensureCatalog()
})

// ── 目录(展开时拉 full,缓存) ──
const openKinds = ref(new Set<string>())
const fulls = ref<Record<string, GeneratorKindDetailView>>({})

async function toggleKind(kind: string): Promise<void> {
  const next = new Set(openKinds.value)
  if (next.has(kind)) {
    next.delete(kind)
  } else {
    next.add(kind)
    if (!fulls.value[kind]) await ensureFull(kind)
  }
  openKinds.value = next
}

async function ensureFull(kind: string): Promise<void> {
  if (fulls.value[kind]) return
  try {
    fulls.value = { ...fulls.value, [kind]: await getGeneratorKindFull(kind) }
  } catch {
    ElMessage.error(`加载 ${kind} 说明失败`)
  }
}

function paramRange(p: GeneratorParamDesc): string {
  if (p.enum) return p.enum.map(String).join(' / ')
  if (p.min !== null && p.max !== null) return `${p.min} ~ ${p.max}`
  if (p.min !== null) return `≥ ${p.min}`
  if (p.max !== null) return `≤ ${p.max}`
  return '—'
}

function copyExample(full: GeneratorKindDetailView): void {
  void copyText(JSON.stringify(full.example)).then((ok) => {
    if (ok) ElMessage.success('已复制示例 JSON')
  })
}

// ── 条目表 ──
function entryValueText(row: ConstantEntry): string {
  return row.entry_kind === 'generator' ? JSON.stringify(row.spec) : String(row.value)
}

async function onDelete(row: ConstantEntry): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除常量「${row.name}」?`, '删除确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await constantsStore.removeEntry(row.id)
    ElMessage.success('已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

// ── 新增/编辑弹框 ──
const dialogOpen = ref(false)
const editing = ref<ConstantEntry | null>(null)

interface EntryForm {
  name: string
  description: string
  entry_kind: 'literal' | 'generator'
  valueType: 'string' | 'integer' | 'decimal' | 'boolean'
  valueStr: string
  valueNum: number
  valueBool: boolean
  genKind: string
  genParams: Record<string, unknown>
}

const EMPTY_FORM: EntryForm = {
  name: '',
  description: '',
  entry_kind: 'literal',
  valueType: 'string',
  valueStr: '',
  valueNum: 0,
  valueBool: false,
  genKind: '',
  genParams: {},
}
const form = reactive<EntryForm>({ ...EMPTY_FORM })

const genFull = computed(() => fulls.value[form.genKind] ?? null)
const genParams = computed<GeneratorParamDesc[]>(() => genFull.value?.params ?? [])

const NAME_RE = /^[A-Za-z0-9_]{1,64}$/
const canSubmit = computed(() => {
  if (!NAME_RE.test(form.name)) return false
  if (
    constantsStore.entries.some((e) => e.name === form.name && e.id !== editing.value?.id)
  ) {
    return false
  }
  if (form.entry_kind === 'literal') {
    return form.valueType === 'string' ? form.valueStr.trim().length > 0 : true
  }
  return !!form.genKind
})

const specPreview = computed(() => JSON.stringify(buildSpec()))

function setParam(name: string, v: unknown): void {
  form.genParams[name] = v
}

function buildSpec(): Record<string, unknown> | null {
  if (form.entry_kind !== 'generator' || !form.genKind) return null
  const spec: Record<string, unknown> = { kind: form.genKind }
  for (const p of genParams.value) {
    const v = form.genParams[p.name]
    if (v !== undefined && v !== null && v !== '') spec[p.name] = v
  }
  return spec
}

/** 新建流程选 kind: 拉 full + 默认值预填(编辑流程的预填在 openEdit,不走此 watch)。 */
watch(
  () => form.genKind,
  async (kind) => {
    if (!kind || editing.value) return
    await ensureFull(kind)
    const defaults: Record<string, unknown> = {}
    for (const p of fulls.value[kind]?.params ?? []) {
      if (p.default !== null && p.default !== undefined) defaults[p.name] = p.default
    }
    form.genParams = defaults
  },
)

function selectGenKind(kind: string): void {
  form.genKind = kind
}

function openCreate(): void {
  editing.value = null
  Object.assign(form, EMPTY_FORM, { genParams: {} })
  dialogOpen.value = true
}

function openEdit(row: ConstantEntry): void {
  editing.value = row
  Object.assign(form, EMPTY_FORM, {
    name: row.name,
    description: row.description,
    entry_kind: row.entry_kind,
  })
  if (row.entry_kind === 'literal') {
    const v = row.value
    if (typeof v === 'boolean') form.valueType = 'boolean'
    else if (typeof v === 'number') {
      form.valueType = Number.isInteger(v) ? 'integer' : 'decimal'
    } else form.valueType = 'string'
    form.valueStr = typeof v === 'string' ? v : String(v ?? '')
    form.valueNum = typeof v === 'number' ? v : 0
    form.valueBool = v === true
  } else {
    const spec = row.spec ?? {}
    form.genKind = String(spec.kind ?? '')
    const params: Record<string, unknown> = { ...spec }
    delete params.kind
    form.genParams = params
    void ensureFull(form.genKind)
  }
  dialogOpen.value = true
}

function literalValueFromForm(): unknown {
  switch (form.valueType) {
    case 'boolean':
      return form.valueBool
    case 'integer':
      return Math.trunc(form.valueNum)
    case 'decimal':
      return form.valueNum
    default:
      return form.valueStr
  }
}

async function onSubmit(): Promise<void> {
  try {
    if (editing.value) {
      const payload: Record<string, unknown> = { description: form.description }
      if (form.entry_kind === 'literal') payload.value = literalValueFromForm()
      else payload.spec = buildSpec()
      await constantsStore.patchEntry(editing.value.id, payload)
      ElMessage.success('已保存')
    } else if (form.entry_kind === 'literal') {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'literal',
        value: literalValueFromForm(),
      })
      ElMessage.success('已新增')
    } else {
      await constantsStore.createEntry({
        name: form.name,
        description: form.description,
        entry_kind: 'generator',
        spec: buildSpec() ?? undefined,
      })
      ElMessage.success('已新增')
    }
    dialogOpen.value = false
  } catch (e) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

function copySpec(): void {
  const spec = buildSpec()
  if (!spec) return
  void copyText(JSON.stringify(spec)).then((ok) => {
    if (ok) ElMessage.success('已复制 spec')
  })
}
</script>

<style scoped>
.constants-page {
  max-width: 1080px;
  margin: 0 auto;
  padding: 20px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-head h1 { font-size: 18px; margin-bottom: 4px; }
.muted { color: var(--c-text-tertiary); font-size: 12px; }
.card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-radius: 10px;
  padding: 14px 16px;
}
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.section-head h2 { font-size: 14px; }
.degraded { color: #b45309; font-size: 12px; }
.kind-card { border: 1px solid var(--c-border); border-radius: 8px; margin-bottom: 8px; }
.kind-head {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 12.5px;
  text-align: left;
}
.chevron { display: inline-block; transition: transform 0.15s ease; color: var(--c-text-tertiary); }
.chevron.open { transform: rotate(90deg); }
.kind-name { font-family: var(--font-mono); font-weight: 600; }
.kind-summary { color: var(--c-text-secondary, #64748b); }
.kind-body { padding: 0 12px 10px; }
.kind-desc { font-size: 12px; margin: 4px 0 8px; }
.params-table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
.params-table th,
.params-table td { border: 1px solid var(--c-border); padding: 3px 8px; text-align: left; }
.params-table th { background: var(--c-bg-secondary); font-weight: 600; }
.example-row { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.example-json {
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
}
.entry-value {
  font-family: var(--font-mono);
  font-size: 11.5px;
  word-break: break-all;
}
.kind-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.kind-chip {
  border: 1px solid var(--c-border);
  background: var(--c-bg-secondary);
  border-radius: 12px;
  padding: 2px 10px;
  font-family: var(--font-mono);
  font-size: 11.5px;
  cursor: pointer;
}
.kind-chip.active {
  background: #ede9fe;
  border-color: #7c3aed;
  color: #4c1d95;
}
.param-hint { display: block; margin-top: 2px; }
.spec-preview { display: flex; align-items: center; gap: 8px; width: 100%; }
.spec-preview pre {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 11px;
  background: var(--c-bg-secondary);
  border-radius: 6px;
  padding: 6px 10px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
.ghost-btn.danger { color: #dc2626; }
</style>
```

(`primary-btn`/`ghost-btn` 若是全局样式(既有视图在用同 class),此处沿用;若是某组件局部样式,在 scoped 里补最小定义 —— 以既有页面实际为准。)

- [x] **Step 9.4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/views/__tests__/ConstantsPool.test.ts`
Expected: 5 passed

- [x] **Step 9.5: Commit**

```bash
git add src/gimbal-platform/frontend/src/views/ConstantsPool.vue src/gimbal-platform/frontend/src/views/__tests__/ConstantsPool.test.ts
git commit -m "feat(frontend): 常量池管理页 — 目录文档卡片 + 目录驱动动态表单 + spec 预览/降级

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: 路由 + TopNav 入口 + 全量回归

**Files:**
- Modify: `src/gimbal-platform/frontend/src/router/index.ts`(routes 数组,`/auths` 之后)
- Modify: `src/gimbal-platform/frontend/src/components/TopNav.vue`(icons import + allEntries)
- Test: `src/gimbal-platform/frontend/src/components/__tests__/TopNav.pool.test.ts`

**Interfaces:**
- Consumes: T9 `ConstantsPool.vue`;router 既有 `meta: { requiresAuth: true }` 守卫约定;TopNav 既有 `NavEntry` 结构 `{ path, label, icon, adminOnly? }`(常量池对所有登录用户可见 —— 无 adminOnly)。
- Produces: 可导航的 `/constants` 页(端到端闭环)。

- [x] **Step 10.1: 写失败测试(全文)**

创建 `src/gimbal-platform/frontend/src/components/__tests__/TopNav.pool.test.ts`:

```ts
/**
 * TopNav — F20: 「常量池」入口对 member/admin 均可见,指向 /constants。
 * adaptations store 在 admin 下会拉 badge — mock 掉 api(拒绝即静默落 lastError)。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'
import TopNav from '@/components/TopNav.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('vue-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-router')>()
  return {
    ...actual,
    useRoute: () => ({ path: '/scenarios' }),
    useRouter: () => ({ push: vi.fn() }),
  }
})
vi.mock('@/api/adaptations', () => ({
  catalogDiff: vi.fn().mockRejectedValue(new Error('offline')),
  errMsg: vi.fn(() => '目录服务不可用'),
}))

beforeEach(() => {
  setActivePinia(createPinia())
})

function mountNav(isAdmin: boolean) {
  const auth = useAuthStore()
  auth.currentUser = {
    username: 'alice',
    display_name: 'Alice',
    is_admin: isAdmin,
  } as never
  return mount(TopNav, {
    global: {
      plugins: [ElementPlus],
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
      },
    },
  })
}

describe('TopNav — 常量池入口(F20)', () => {
  it('member 与 admin 都能看到「常量池」入口,指向 /constants', () => {
    for (const isAdmin of [false, true]) {
      const w = mountNav(isAdmin)
      const link = w.findAll('a.nav-entry').find((a) => a.text().includes('常量池'))
      expect(link, `isAdmin=${isAdmin}`).toBeTruthy()
      expect(link!.attributes('href')).toBe('/constants')
      w.unmount()
    }
  })
})
```

注意: `auth.currentUser` 的形状以 `src/stores/auth.ts` 实际 User 类型为准(缺字段则以其必填字段补齐,cast `as never` 保留)。

- [x] **Step 10.2: 跑测试确认失败**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/__tests__/TopNav.pool.test.ts`
Expected: FAIL(找不到含「常量池」的入口)

- [x] **Step 10.3: 改 router 与 TopNav**

`src/gimbal-platform/frontend/src/router/index.ts` — routes 数组 `/auths` 条目之后插入(与相邻条目同构;若相邻路由带 `name`,同样补 `name: 'constants'`):

```ts
    {
      path: '/constants',
      component: () => import('@/views/ConstantsPool.vue'),
      meta: { requiresAuth: true },
    },
```

`src/gimbal-platform/frontend/src/components/TopNav.vue` — 两处:

icons import(L47-53)补 `Coin`:

```ts
import {
  Coin,
  Collection,
  Connection,
  DataAnalysis,
  Lock,
  Setting,
} from '@element-plus/icons-vue'
```

allEntries(L80-87)在 认证管理 之后、用户管理 之前插入:

```ts
  { path: '/constants', label: '常量池', icon: Coin },
```

- [x] **Step 10.4: 跑测试确认通过**

Run: `cd src/gimbal-platform/frontend && npx vitest run src/components/__tests__/TopNav.pool.test.ts`
Expected: 1 passed

- [x] **Step 10.5: 三端全量回归 + 类型检查**

```bash
python -m pytest tests/plate -q
cd src/gimbal-platform/backend && python -m pytest tests -q
cd ../frontend && npx vitest run
npx vue-tsc --noEmit
```

Expected: 三套件全绿(只增不减)、vue-tsc 零错误。vue-tsc 若报 ConstantsPool 模板内 `as number | undefined` 相关错误,把该 `:model-value` 换成 `:model-value="typeof form.genParams[p.name] === 'number' ? (form.genParams[p.name] as number) : undefined"`(等价写法,以编译器口味为准)。

- [x] **Step 10.6: Commit**

```bash
git add src/gimbal-platform/frontend/src/router/index.ts src/gimbal-platform/frontend/src/components/TopNav.vue src/gimbal-platform/frontend/src/components/__tests__/TopNav.pool.test.ts
git commit -m "feat(frontend): /constants 路由 + TopNav 常量池入口 — 常量池端到端闭环

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 回归清单(执行完 10 个任务后)

| 套件 | 命令 | 门槛 |
|---|---|---|
| plate | `python -m pytest tests/plate -q` | 全绿,含 `test_v3_no_reverse_import.py` |
| backend | `cd src/gimbal-platform/backend && python -m pytest tests -q` | 全绿 |
| frontend | `cd src/gimbal-platform/frontend && npx vitest run` | 全绿(新增 ~28 用例) |
| 类型 | `cd src/gimbal-platform/frontend && npx vue-tsc --noEmit` | 零错误 |

非目标(不做):引擎 `src/gimbal` 任何改动;RunDialog 内出现 panel;常量池跨用户共享;generator 参数合法性后端校验;列表服务端化分页。

## Spec 覆盖对照(自审记录)

| Spec 章节 | 承接任务 |
|---|---|
| §plate dim 规格(URL/信封/视图形状/9 kind/sequence 别名不单列) | T1 |
| §引擎事实锚点(Phase 1.5/3、spec 仅 config.vars 求值) | T1 镜像注释 + T8 pool-var 注释 |
| §constant_entries 表结构(owner 隔离/name 正则/互斥/entry_kind 不可变) | T2 |
| §后端代理(/generator-catalog、502/404 映射) | T3 |
| §前端架构(store 双消费方/独立降级/in-flight 去重) | T6 |
| §Panel 双挂载(步骤 0-2 rail / 步骤 3 col-info 常驻 VRP 之下) | T7/T8 |
| §复制/插入交互(三载荷/无目标提示/插入不播种 value) | T7(F4-F8) |
| §播种快照语义(??=/不回灌/已存在提示) | T8(F10、F9c) |
| §DOM 焦点跟踪(选择器排除/原生 input 事件/断连清理) | T5(F1-F3) |
| §管理页(目录卡片/字面量四型/目录驱动动态表单/spec 预览/降级条) | T9(F14-F18) |
| §RunDialog 不出现 | T8(F11,结构性 + DOM 断言) |
| §路由与入口 | T10(F20) |
| §测试策略 P1-P7/B1-B11/F1-F20 | T1-T10 各 Test 文件 |


