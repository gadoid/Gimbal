# fin SUT 请求面孪生生成器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 fin-test ThinkPHP 源码 + 测试库 schema 四源静态生成 Plate `EndpointSpec` 目录(请求面孪生第一代),行为面零逆向。

**Architecture:** 独立构建期工具 `src/gimbal-plate/tools/twin_generator/`(运行时不 import),五阶段管线 S1路由→S2键面→S3语义→S4状态→S5装订;产物默认落 `gimbal-tmp/twin_gen/`(永不提交),人工 gate 后经 `--install-dir` 落 `gimbal_plate/systems/fin/endpoint_generated/`(自动发现包,不碰他人改动的 `endpoint/__init__.py`)。

**Tech Stack:** Python 3.14 + tree-sitter 0.26 / tree-sitter-php(已装并验证:入口 `Language(tree_sitter_php.language_php())`)+ pydantic 2.12.5(沿 plate)+ pytest。

**Spec:** `docs/superpowers/specs/2026-09-15-sut-request-surface-twin-generator-design.md`(911cf45a;本计划含 §5 目录条修订,见 Task 11)

## Global Constraints

- 所有 Python 文件/命令 UTF-8:跑工具与测试前 `export PYTHONIOENCODING=utf-8 PYTHONUTF8=1`(Windows 控制台中文防乱码,已踩坑)。
- 生成期零 HTTP:工具只读本地文件(D:\fin-test 源码/schema),绝不对 SUT 发请求。
- 测试一律用 `tests/fixtures/` 迷你样本,绝不触碰真实 `D:\fin-test` 与真实 `gimbal-tmp` 产物。
- `gimbal-tmp/` 永不提交;`reports/test-report.html` 永不触碰;`src/gimbal-plate/gimbal_plate/systems/fin/endpoint/__init__.py` 是他人未提交改动**绝不编辑**(Task 11 用 sibling 包绕开)。
- 提交选择性暂存:仅 `git add` 任务文件;commit message 尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 已实证的底层事实(直接用,不重查):
  - 路由:`/api/<module>/<controllerCamel>/<action>` ↔ `Application/<Module>/Controller/<ControllerCamel>Controller.class.php::<action>`(controller 段 = 类名去 `Controller` 后首字母小写;如 `order/orderEntrust/orderAdd` ↔ `Order/OrderEntrustController::orderAdd`)。
  - `getRequestParam()` = `I("param.")` 优先、空则 `php://input` JSON —— 键面权威 = JSON body。
  - Validator 三档(读 vendored 库 `Common/Library/PHPValidator/Common/Validator.class.php` 实现):`require`=值非空;`present`=值非空(带 status/entrust_status 豁免分支,按非空对待);`exist`=键存在(值可空)。
  - tree-sitter-php 节点名(本机 probe 实录):`class_declaration`→`declaration_list`→`method_declaration`(子:`visibility_modifier`,`name`,`formal_parameters`,`compound_statement`);`property_element`(子:`name`,`array_element_initializer`(两个 `string` 子),`comment` 兄弟节点);`const_declaration`→`const_element`(`name`,`integer`/`string`);调用:`function_call_expression`(`name`+`arguments`→`argument`),`member_call_expression`(基座可为 `scoped_call_expression`/`variable_name`,`->`,`name`,`arguments`),`subscript_expression`(`variable_name`+`string`);`assignment_expression`;`object_creation_expression`。string 字面量的裸值取其 `string_content` 子节点文本。
  - `DeclarationEntry`:`name/path/type/state/required/default/example/description/enum/ui_kind/source_kind/value_source/assertable/children`,`extra="forbid"`,name 须 ASCII 标识符,path 归一 `$.xxx`,type 限六原语,enum×value_source 互斥。
  - `ValueSource(view, column="", group="")`;`EndpointSpec(id/system/service/name/description/api/request/responses/query_views/metadata)`;`ApiSpec(service/method/path/headers/timeout_seconds/auth/produces/consumes)`;`RequestSpec(body_type/declarations)`;`ResponseSpec(status/description/declarations)`。
  - 视图目录:`gimbal_plate.service.query_views.build_query_view_index(endpoints) -> list[dict]`,行含 `name`/`columns`。

**v1 范围裁定(对 spec 的两处显式缩水,非遗漏):**
- Enum 类抽取仅作报告候选(Task 6 `load_enums`),不自动挂到字段 enum —— spec §9 开放问题「Enum↔字段匹配置信度阈值」未决,先只吃 Validator `in:` 规则;
- value_source 消歧的「外键线索辅助」(spec §3 S4)v1 不实现 —— 同名匹配 + `disambiguation.md` 消歧队列兜底,外键线索留作二期增强。

---

### Task 1: PHP 解析基座 php_ast.py

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/__init__.py`(空文件,一行 docstring)
- Create: `src/gimbal-plate/tools/twin_generator/php_ast.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/conftest.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/sample_validator.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_php_ast.py`

**Interfaces:**
- Produces: `load(path) -> ParsedFile`;`ParsedFile.walk()`(DFS 生成器,yield 节点);`text_of(pf, node) -> str`;`classes(pf) -> list[tuple[str, node, node]]`(类名, 类节点, declaration_list 节点)。后续所有阶段消费这四个。

- [ ] **Step 1: 建 fixture 与 conftest**

`tests/fixtures/php/sample_validator.php`(真实 fin Validator 缩影,后续 Task 4 复用):

```php
<?php
class OrderEntrustValidator
{
    public static $orderAddRules = [
        'customer_id'         => 'require|num', //客户ID
        // 'carrier'                => 'present', //船公司/承运人
        'bl_no'               => 'present|alpha_dish|length_max:32', //提单号
        'settle_type'         => 'exist|num|in:1,2', //结算类型
        'num'                 => 'exist|num', //件数
    ];
}
```

`tests/conftest.py`:

```python
"""共用:UTF-8 环境钉死 + sys.path 自举 + fixture 根路径。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# tools/ 入 path → 所有测试统一 `from twin_generator.xxx import ...`
# (模块内部是包相对导入 `from .php_ast import`,顶层裸名导入必炸)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FIXTURES = Path(__file__).parent / "fixtures"
```

- [ ] **Step 2: 写失败测试**

`tests/test_php_ast.py`:

```python
from twin_generator.php_ast import load, text_of, classes
from conftest import FIXTURES

PHP = FIXTURES / "php" / "sample_validator.php"


def test_load_and_classes():
    pf = load(PHP)
    assert not pf.tree.root_node.has_error
    cls = classes(pf)
    assert len(cls) == 1
    name, cnode, decl = cls[0]
    assert name == "OrderEntrustValidator"
    # declaration_list 内可找到方法/属性节点(类型抽查)
    types = [n.type for n in pf.walk()]
    assert "property_element" in types
    assert "comment" in types


def test_text_of_and_walk():
    pf = load(PHP)
    strs = [text_of(pf, n) for n in pf.walk() if n.type == "string"]
    assert "'customer_id'" in strs          # 带引号原文
    assert "'require|num'" in strs
```

- [ ] **Step 3: 验证失败**

```bash
cd src/gimbal-plate/tools/twin_generator && export PYTHONIOENCODING=utf-8 PYTHONUTF8=1 && python -m pytest tests/test_php_ast.py -v
```
Expected: FAIL(`ModuleNotFoundError: No module named 'php_ast'` 或收集错误)。若 pytest 缺失先 `pip install pytest`。

- [ ] **Step 4: 实现 php_ast.py**

```python
"""tree-sitter PHP 解析基座:文件→语法树 + 节点文本/遍历/类定位助手。

节点类型事实(probe 实录,见 plan Global Constraints):
class_declaration→declaration_list→method_declaration/property_element/
const_declaration;调用族 function_call_expression/member_call_expression/
scoped_call_expression/subscript_expression。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import tree_sitter_php
from tree_sitter import Language, Parser, Node


@lru_cache(maxsize=1)
def _parser() -> Parser:
    return Parser(Language(tree_sitter_php.language_php()))


@dataclass
class ParsedFile:
    path: Path
    tree: object
    src: bytes

    def walk(self):
        yield from _walk(self.tree.root_node)


def _walk(node: Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def load(path: str | Path) -> ParsedFile:
    p = Path(path)
    return ParsedFile(path=p, tree=_parser().parse(p.read_bytes()), src=p.read_bytes())


def text_of(pf: ParsedFile, node: Node) -> str:
    """节点原文(带引号/引号符,如 'require|num')。"""
    return pf.src[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def classes(pf: ParsedFile) -> list[tuple[str, Node, Node]]:
    """[(类名, class_declaration, declaration_list)],不含匿名/错误节点。"""
    out = []
    for n in pf.walk():
        if n.type != "class_declaration":
            continue
        name = next((c for c in n.children if c.type == "name"), None)
        decl = next((c for c in n.children if c.type == "declaration_list"), None)
        if name is not None and decl is not None:
            out.append((text_of(pf, name), n, decl))
    return out
```

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_php_ast.py -v
```
Expected: 2 passed。

```bash
git add src/gimbal-plate/tools/twin_generator/__init__.py src/gimbal-plate/tools/twin_generator/php_ast.py src/gimbal-plate/tools/twin_generator/tests/
git commit -m "feat(twin-gen): php_ast 基座 — tree-sitter PHP 解析/遍历/类定位

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 2: IR 数据模型 + schema CSV 加载

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/ir.py`
- Create: `src/gimbal-plate/tools/twin_generator/schema_source.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/schema/fin_test_search.csv`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_ir_schema.py`

**Interfaces:**
- Consumes: Task 1 无依赖(纯数据)。
- Produces:
  - `RuleEntry(key, rules, zh="", active=True)` + `.required()/.must_include()/.enum_values()/.max_length()`
  - `Read(key, default=None, via="")`
  - `ActionIR(module, controller, action)` + `.path/.id/.const_name`、可变字段 `ruleset/rules/validator_checks/callees/reads`
  - `FieldIR`(S3/S4 合成,字段见代码)
  - `load_columns(csv_path) -> ColumnCatalog`:`ColumnInfo(table, column, col_type, nullable, default, comment)`;`ColumnCatalog.by_name: dict[str, list[ColumnInfo]]`、`.not_null_no_default(column) -> bool`(全表一致才 True,排除 `create_time/update_time`)

- [ ] **Step 1: fixture CSV**(Navicat 导出形状缩影,含引号/空默认/中文):

`tests/fixtures/schema/fin_test_search.csv`:

```csv
"TABLE_NAME","COLUMN_NAME","COLUMN_TYPE","IS_NULLABLE","COLUMN_DEFAULT","COLUMN_COMMENT"
"sys_order","order_id","bigint","NO",,""
"sys_order","bl_no","varchar(50)","NO","","业务订单ID"
"sys_order","customer_id","bigint","NO","0","客户ID"
"sys_order","etd","int","NO","0","预计开航日"
"sys_order","gross_weight","decimal(10,2)","YES",,"毛重"
"sys_order","create_time","datetime","NO",,"创建时间"
```

- [ ] **Step 2: 失败测试**

`tests/test_ir_schema.py`:

```python
from twin_generator.ir import RuleEntry, ActionIR
from twin_generator.schema_source import load_columns
from conftest import FIXTURES


def test_rule_entry_derivations():
    r = RuleEntry("settle_type", "exist|num|in:1,2", zh="结算类型")
    assert r.required() is False            # exist≠非空
    assert r.must_include() is True         # 键须存在
    assert r.enum_values() == ["1", "2"]
    assert RuleEntry("customer_id", "require|num").required() is True
    assert RuleEntry("bl_no", "present|length_max:32").required() is True
    assert RuleEntry("bl_no", "present|length_max:32").max_length() == 32


def test_action_ir_naming():
    a = ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")
    assert a.path == "/api/order/orderEntrust/orderAdd"
    assert a.id == "fin.order_entrust.order_add"
    assert a.const_name == "ORDER_ENTRUST_ORDER_ADD"


def test_load_columns():
    cat = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    cust = cat.by_name["customer_id"][0]
    assert (cust.table, cust.comment, cust.default) == ("sys_order", "客户ID", "0")
    # not_null_no_default:全表一致且无默认才 True;create_time 排除
    assert cat.not_null_no_default("bl_no") is True      # NO + "" 空默认
    assert cat.not_null_no_default("customer_id") is False  # 默认 '0'
    assert cat.not_null_no_default("etd") is False          # 默认 '0'
    assert cat.not_null_no_default("create_time") is False  # 排除清单
```

- [ ] **Step 3: 验证失败**(同 Task 1 方式,`ModuleNotFoundError`)

- [ ] **Step 4: 实现**

`ir.py`:

```python
"""管线中间表示(IR):S1..S4 各阶段的流通货币。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


def snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


@dataclass
class RuleEntry:
    """Validator 规则行(含被注释行:active=False 但 zh 仍有值)。"""
    key: str
    rules: str
    zh: str = ""
    active: bool = True

    def parts(self) -> list[str]:
        return [p.strip() for p in self.rules.split("|") if p.strip()]

    def required(self) -> bool:
        """require|present → 值非空(present 的 status 豁免分支按非空对待)。"""
        return any(p in ("require", "present") for p in self.parts())

    def must_include(self) -> bool:
        """exist → 键必须在(值可空)。"""
        return any(p == "exist" for p in self.parts())

    def enum_values(self) -> list[str] | None:
        for p in self.parts():
            if p.startswith("in:"):
                return [v.strip() for v in p[3:].split(",") if v.strip()]
        return None

    def max_length(self) -> int | None:
        for p in self.parts():
            if p.startswith("length_max:"):
                return int(p.split(":", 1)[1])
        return None


@dataclass
class Read:
    """S2b 键读标记。via ∈ getData|subscript|isset。"""
    key: str
    default: str | None = None
    via: str = ""


@dataclass
class ActionIR:
    module: str
    controller: str          # 类名去 Controller(OrderEntrust)
    action: str
    # S1 填:规则绑定与静态校验/服务调用边
    ruleset: tuple[str, str] | None = None     # (Validator 类名, 属性名如 orderAddRules)
    validator_checks: list[str] = field(default_factory=list)   # checkXxx 方法名
    callees: list[tuple[str, str]] = field(default_factory=list)  # (类名, 方法名)
    # S2 填
    rules: list[RuleEntry] = field(default_factory=list)
    reads: dict[str, Read] = field(default_factory=dict)
    method: str = "POST"

    @property
    def path(self) -> str:
        c = self.controller[0].lower() + self.controller[1:]
        return f"/api/{self.module.lower()}/{c}/{self.action}"

    @property
    def id(self) -> str:
        return f"fin.{snake(self.controller)}.{snake(self.action)}"

    @property
    def const_name(self) -> str:
        return snake(self.controller).upper() + "_" + snake(self.action).upper()


@dataclass
class FieldIR:
    """S3 语义富化 + S4 状态赋值后的单字段全貌。"""
    key: str
    read: bool = False
    required: bool = False
    must_include: bool = False
    zh: str = ""
    zh_source: str = ""            # rule|column|derived|enum|""
    type_: str = "string"
    enum_values: list | None = None
    default: object = None
    col_comment: str = ""
    col_type: str = ""
    tables: list[str] = field(default_factory=list)
    # S4 赋值
    state: str = "carry"
    value_source: tuple[str, str] | None = None   # (view, column)
    flags: list[str] = field(default_factory=list)  # needs_capture:value_source 等
```

`schema_source.py`:

```python
"""S4 源:fin_test_search.csv(information_schema 导出)加载。"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# 引擎自填列:NOT NULL 但从不要求请求携带
_ENGINE_COLUMNS = {"create_time", "update_time"}


@dataclass
class ColumnInfo:
    table: str
    column: str
    col_type: str
    nullable: bool
    default: str | None
    comment: str


class ColumnCatalog:
    def __init__(self, rows: list[ColumnInfo]):
        self.by_name: dict[str, list[ColumnInfo]] = {}
        for r in rows:
            self.by_name.setdefault(r.column, []).append(r)

    def not_null_no_default(self, column: str) -> bool:
        """该列名在全部出现表中都 NOT NULL 且无默认 → 第三判据成立。
        引擎列(create_time/update_time)恒 False。"""
        if column in _ENGINE_COLUMNS:
            return False
        rows = self.by_name.get(column)
        return bool(rows) and all(
            (not r.nullable) and r.default in (None, "") for r in rows
        )


def load_columns(csv_path: str | Path) -> ColumnCatalog:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return ColumnCatalog([
            ColumnInfo(
                table=row["TABLE_NAME"],
                column=row["COLUMN_NAME"],
                col_type=row["COLUMN_TYPE"],
                nullable=row["IS_NULLABLE"] == "YES",
                default=row["COLUMN_DEFAULT"] or None,
                comment=row["COLUMN_COMMENT"],
            )
            for row in csv.DictReader(f)
        ])
```

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_ir_schema.py -v
git add src/gimbal-plate/tools/twin_generator/ir.py src/gimbal-plate/tools/twin_generator/schema_source.py src/gimbal-plate/tools/twin_generator/tests/
git commit -m "feat(twin-gen): IR 数据模型 + schema CSV 加载 — 规则派生/命名约定/列目录

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 3: S1 路由发现(Controller 扫描)

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s1_routes.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Order/Controller/OrderEntrustController.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Order/Controller/BaseController.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Script/Controller/TaskController.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s1_routes.py`

**Interfaces:**
- Consumes: `php_ast.load/walk/text_of/classes`、`ir.ActionIR`。
- Produces: `scan_actions(app_root: Path) -> list[ActionIR]`(含 ruleset/validator_checks/callees 绑定;rules/read 留空给 S2)。

- [ ] **Step 1: fixtures**

`fixtures/php/app/Application/Order/Controller/OrderEntrustController.class.php`:

```php
<?php
class OrderEntrustController extends BaseController
{
    public function orderAdd()
    {
        $requestData = getRequestParam();
        $errorMsg = $this->paramVerification(OrderEntrustValidator::$orderAddRules, false);
        $errorMsg = array_merge($errorMsg, OrderEntrustValidator::checkSupplier($requestData));
        if (!empty($errorMsg)) { throwValidator($errorMsg); }
        OrderEntrustService::getInstance()->orderUpdate($requestData);
        $this->returnSuccess();
    }

    public function orderPage()
    {
        $requestData = getRequestParam();
        $this->returnSuccess(OrderEntrustService::getInstance()->orderPage($requestData));
    }

    protected function _internal() { }
    public function __construct() { }
}
```

`fixtures/php/app/Application/Order/Controller/BaseController.class.php`:

```php
<?php
class BaseController
{
    public function returnSuccess($data = []) { }
}
```

`fixtures/php/app/Application/Script/Controller/TaskController.class.php`(排除模块):

```php
<?php
class TaskController
{
    public function run() { }
}
```

- [ ] **Step 2: 失败测试**

`tests/test_s1_routes.py`:

```python
from pathlib import Path

from twin_generator.s1_routes import scan_actions
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def test_scan_actions():
    actions = scan_actions(APP)
    by_id = {a.id: a for a in actions}
    # Script 模块排除;_internal/__construct 排除;Base 排除
    assert set(by_id) == {"fin.order_entrust.order_add", "fin.order_entrust.order_page"}
    a = by_id["fin.order_entrust.order_add"]
    assert a.path == "/api/order/orderEntrust/orderAdd"
    assert a.method == "POST"
    assert a.ruleset == ("OrderEntrustValidator", "orderAddRules")
    assert a.validator_checks == ["checkSupplier"]
    assert a.callees == [("OrderEntrustService", "orderUpdate")]
    page = by_id["fin.order_entrust.order_page"]
    assert page.ruleset is None and page.callees == [("OrderEntrustService", "orderPage")]
```

- [ ] **Step 3: 验证失败**

- [ ] **Step 4: 实现 s1_routes.py**

```python
"""S1 路由发现:Application/*/Controller/*.class.php → ActionIR 清单。

约定(plan Global Constraints,26 个手建 endpoint 实证):
path = /api/<module小写>/<controller去Controller首字母小写>/<action>;
排除模块 Script/Template/Event/Corn/Common;排除 Base* 类、_ 前缀/魔术方法、
非 public 方法。控制器体内解析:paramVerification(Xxx::$prop) 绑定、
XxxValidator::checkYyy() 静态校验、Xxx::getInstance()->yyy()/new Xxx() 服务边。
"""
from __future__ import annotations

import re
from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes
from .ir import ActionIR

EXCLUDED_MODULES = {"Script", "Template", "Event", "Corn", "Common"}
_MAGIC = {"__construct", "__destruct", "__get", "__set", "__call", "__clone"}

_RE_RULESET = re.compile(r"^(\w+)::\$(\w+)$")           # 节点级文本,安全


def _is_public(method_node, pf: ParsedFile) -> bool:
    texts = [text_of(pf, c) for c in method_node.children
             if c.type in ("visibility_modifier", "static_modifier")]
    return any(t == "public" for t in texts) and not any(
        "static" in t for t in texts)


def _method_name(method_node, pf: ParsedFile) -> str | None:
    n = next((c for c in method_node.children if c.type == "name"), None)
    return text_of(pf, n) if n else None


def scan_actions(app_root: Path) -> list[ActionIR]:
    out: list[ActionIR] = []
    for ctl_file in sorted(app_root.glob("*/Controller/*.class.php")):
        module = ctl_file.parent.parent.name
        if module in EXCLUDED_MODULES:
            continue
        pf = load(ctl_file)
        for cname, _cnode, decl in classes(pf):
            if cname.startswith("Base"):
                continue
            controller = cname[:-10] if cname.endswith("Controller") else cname
            for child in decl.children:
                if child.type != "method_declaration":
                    continue
                mname = _method_name(child, pf)
                if (not mname or mname.startswith("_") or mname in _MAGIC
                        or not _is_public(child, pf)):
                    continue
                act = _bind(load(ctl_file), child, module, controller, mname)
                out.append(act)
    return out


def _bind(pf: ParsedFile, method_node, module: str, controller: str, action: str) -> ActionIR:
    act = ActionIR(module=module, controller=controller, action=action)
    stack = [method_node]
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        t = n.type
        if t == "function_call_expression" and _callee(pf, n) == "paramVerification":
            args = [c for c in n.children if c.type == "arguments"]
            for arg in _arg_nodes(args[0]) if args else []:
                m = _RE_RULESET.match(text_of(pf, arg).strip())
                if m:
                    act.ruleset = (m.group(1), m.group(2))
        elif t == "scoped_call_expression":
            names = [c for c in n.children if c.type == "name"]
            if len(names) == 2:
                cls, meth = text_of(pf, names[0]), text_of(pf, names[1])
                if cls.endswith("Validator") and meth.startswith("check"):
                    act.validator_checks.append(meth)
        elif t == "member_call_expression":
            base = n.children[0] if n.children else None
            if base is not None and base.type == "scoped_call_expression":
                inner = [c for c in base.children if c.type == "name"]
                meth = next((c for c in n.children if c.type == "name"), None)
                if len(inner) >= 1 and meth is not None:
                    act.callees.append((text_of(pf, inner[0]), text_of(pf, meth)))
    return act


def _callee(pf: ParsedFile, call_node) -> str:
    n = next((c for c in call_node.children if c.type == "name"), None)
    return text_of(pf, n) if n else ""


def _arg_nodes(args_node) -> list:
    return [c for c in args_node.children if c.type == "argument"]
```

注意:修饰符节点形状若与 probe 实录有出入(`static_modifier` 是否独立节点),以测试为准修正 —— 测试是行为的唯一裁判。

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s1_routes.py -v
git add src/gimbal-plate/tools/twin_generator/s1_routes.py src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app src/gimbal-plate/tools/twin_generator/tests/test_s1_routes.py
git commit -m "feat(twin-gen): S1 路由发现 — Controller 扫描/规则绑定/校验与服务边

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 4: S2a Validator 规则抽取

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s2_validator.py`
- Test: 复用 `tests/fixtures/php/sample_validator.php`(Task 1)
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s2_validator.py`

**Interfaces:**
- Consumes: `php_ast`、`ir.RuleEntry`。
- Produces: `parse_rules_file(path) -> dict[str, list[RuleEntry]]`(属性名→条目,含 active=False 被注释条目);`attach_rules(actions, app_root) -> None`(按 ruleset 显式绑定装配;无绑定按 `$<action>Rules`/`$<action>Rule` 命名兜底)。

- [ ] **Step 1: 失败测试**

`tests/test_s2_validator.py`:

```python
from twin_generator.s2_validator import parse_rules_file, attach_rules
from twin_generator.s1_routes import scan_actions
from conftest import FIXTURES


def test_parse_rules_file():
    rules = parse_rules_file(FIXTURES / "php" / "sample_validator.php")
    entries = rules["orderAddRules"]
    by_key = {e.key: e for e in entries}
    assert by_key["customer_id"].required() and by_key["customer_id"].zh == "客户ID"
    # 被注释行:active=False 但键/规则/中文都在
    carrier = by_key["carrier"]
    assert carrier.active is False and carrier.zh == "船公司/承运人"
    assert by_key["settle_type"].enum_values() == ["1", "2"]
    assert by_key["bl_no"].max_length() == 32


def test_attach_rules():
    app = FIXTURES / "php" / "app" / "Application"
    # fixture app 需有 Validator:补一个最小文件(见 Step 2 注)
    actions = scan_actions(app)
    attach_rules(actions, app)
    add = next(a for a in actions if a.action == "orderAdd")
    assert {e.key for e in add.rules} >= {"customer_id", "carrier", "bl_no"}
    page = next(a for a in actions if a.action == "orderPage")
    assert page.rules == []          # 无绑定无同名规则集
```

- [ ] **Step 2: 补 fixture**

`fixtures/php/app/Application/Order/Validator/OrderEntrustValidator.class.php`(把 sample_validator.php 的类原样放进模块目录,S1/S2 共享同一棵 fixture 树)。

- [ ] **Step 3: 验证失败**

- [ ] **Step 4: 实现 s2_validator.py**

```python
"""S2a:Validator $xxxRules 数组抽取 —— 活跃行 + 被注释行(中文注释都在)。

行结构(tree-sitter):property_element 子节点序列
[..., array_element_initializer(两个 string), comment(同行行尾), ...];
被注释规则行是独立 comment 节点,文本形如
  // 'carrier' => 'present', //船公司/承运人
comment 节点内部用正则解析(节点级文本,安全)。
"""
from __future__ import annotations

import re
from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes
from .ir import RuleEntry, ActionIR

_RE_COMMENTED_RULE = re.compile(
    r"//\s*'([A-Za-z0-9_]+)'\s*=>\s*'([^']*)'.*?//\s*(.+)$"
)


def parse_rules_file(path: Path) -> dict[str, list[RuleEntry]]:
    pf = load(path)
    out: dict[str, list[RuleEntry]] = {}
    for _name, _cnode, decl in classes(pf):
        _parse_decl(pf, decl, out)
    return out


def _parse_decl(pf: ParsedFile, decl, out: dict) -> None:
    for prop in decl.children:
        if prop.type != "property_element":
            continue
        name_n = next((c for c in prop.children if c.type == "name"), None)
        if name_n is None:
            continue
        entries: list[RuleEntry] = []
        children = list(prop.children)
        for i, node in enumerate(children):
            if node.type == "array_element_initializer":
                strs = [c for c in node.children if c.type == "string"]
                if len(strs) != 2:
                    continue
                zh = ""
                nxt = children[i + 1] if i + 1 < len(children) else None
                if nxt is not None and nxt.type == "comment" \
                        and nxt.start_point[0] == node.start_point[0]:
                    zh = _strip_comment(text_of(pf, nxt))
                entries.append(RuleEntry(
                    key=_unquote(text_of(pf, strs[0])),
                    rules=_unquote(text_of(pf, strs[1])),
                    zh=zh, active=True,
                ))
            elif node.type == "comment":
                m = _RE_COMMENTED_RULE.search(text_of(pf, node))
                if m:
                    entries.append(RuleEntry(
                        key=m.group(1), rules=m.group(2),
                        zh=m.group(3).strip(), active=False,
                    ))
        out[text_of(pf, name_n)] = entries


def _strip_comment(t: str) -> str:
    return t.lstrip("/ ").strip()


def _unquote(t: str) -> str:
    inner = t[1:-1] if len(t) >= 2 and t[0] in "'\"" else t
    return inner


def attach_rules(actions: list[ActionIR], app_root: Path) -> None:
    """显式 ruleset 绑定优先;无绑定时按 $<action>Rules / $<action>Rule 兜底。
    Validator 文件按 Application/*/Validator/*.class.php 扫描一次建索引。"""
    index: dict[str, dict[str, list[RuleEntry]]] = {}   # 类名 → prop → entries
    for f in sorted(app_root.glob("*/Validator/*.class.php")):
        for cname, *_ in classes(load(f)):
            index[cname] = parse_rules_file(f)
    for act in actions:
        if act.ruleset:
            cls, prop = act.ruleset
            act.rules = list(index.get(cls, {}).get(prop, []))
            continue
        for suffix in ("Rules", "Rule"):
            for cls, props in index.items():
                hit = props.get(act.action + suffix)
                if hit:
                    act.rules = list(hit)
                    break
            if act.rules:
                break
```

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s2_validator.py -v
git add src/gimbal-plate/tools/twin_generator/s2_validator.py src/gimbal-plate/tools/twin_generator/tests/
git commit -m "feat(twin-gen): S2a Validator 规则抽取 — 活跃/被注释行 + 显式绑定与命名兜底

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 5: S2b Service 读取树(调用图 + 键读收集)

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s2_reads.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Order/Service/OrderEntrustService.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Order/Service/OrderTaskService.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s2_reads.py`

**Interfaces:**
- Consumes: `php_ast`、`ir.ActionIR/Read`;Task 3 的 `ActionIR.callees/validator_checks`。
- Produces: `collect_reads(actions, app_root) -> None`(写 `action.reads: dict[key, Read]`)。键读三类:`getData*($var,'k'[,'default'])` → via=getData;`$var['k']`(known-var 下标)→ via=subscript;`isset/empty($var['k'])` → via=isset。known-var 传播:入口 `requestData` + 形参链(调用点实参是 known-var → 被调方对应形参入 known)+ 同方法内 `$x = $requestData` 别名。

- [ ] **Step 1: fixtures**

`fixtures/php/app/Application/Order/Service/OrderEntrustService.class.php`:

```php
<?php
class OrderEntrustService
{
    public function orderUpdate($requestData)
    {
        $data = $requestData;
        $action = getDataString($data, 'action', 'submit');
        $cid = getDataInt($data, 'customer_id', 0);
        $bl = $requestData['bl_no'];
        $cn = $requestData['customer_name'];
        if (!empty($requestData['container'])) { $x = 1; }
        OrderTaskService::getInstance()->pushTask($requestData);
        return $action . $bl;
    }

    public function orderPage($requestData)
    {
        $status = getDataString($requestData, 'status', '1');
        return [$status];
    }
}
```

`fixtures/php/app/Application/Order/Service/OrderTaskService.class.php`:

```php
<?php
class OrderTaskService
{
    public function pushTask($payload)
    {
        if (isset($payload['etd'])) { return true; }
        return getDataArray($payload, 'service_items', []);
    }
}
```

- [ ] **Step 2: 失败测试**

`tests/test_s2_reads.py`:

```python
from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import attach_rules
from twin_generator.s2_reads import collect_reads
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def _actions():
    acts = scan_actions(APP)
    attach_rules(acts, APP)
    collect_reads(acts, APP)
    return {a.action: a for a in acts}


def test_reads_via_getdata_and_default():
    acts = _actions()
    r = acts["orderAdd"].reads
    assert r["action"].via == "getData" and r["action"].default == "submit"  # 别名 $data 也追到
    assert r["bl_no"].via == "subscript"
    assert r["container"].via == "isset"
    # 跨服务边 + 形参链($requestData → $payload)
    assert r["etd"].via == "isset"
    assert r["service_items"].via == "getData"
    assert "status" in acts["orderPage"].reads
```

- [ ] **Step 3: 验证失败**

- [ ] **Step 4: 实现 s2_reads.py**

```python
"""S2b:Service/Validator 读取树 —— 控制器动作为根的调用图 BFS + 键读收集。

精确度取舍(写入文档而非隐瞒):known-var 单级别名($x = $requestData);
数组解包/foreach/extract 不追(残差由 S5 对照报告兜底)。
"""
from __future__ import annotations

from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes
from .ir import ActionIR, Read

_GET_DATA = {"getDataString", "getDataInt", "getDataFloat",
             "getDataArray", "getDataBool"}
_ISSET = {"isset", "empty"}


class _ClassIndex:
    """类名 → 方法名 → (method_node, ParsedFile);全 Application 扫描。"""

    def __init__(self, app_root: Path):
        self.methods: dict[str, dict[str, tuple]] = {}
        for f in sorted(app_root.rglob("*.class.php")):
            pf = load(f)
            for cname, _c, decl in classes(pf):
                bucket = self.methods.setdefault(cname, {})
                for m in decl.children:
                    if m.type != "method_declaration":
                        continue
                    n = next((c for c in m.children if c.type == "name"), None)
                    if n:
                        bucket[text_of(pf, n)] = (m, pf)


def _var_name(pf: ParsedFile, node) -> str:
    """variable_name 节点的裸名(去 $)。"""
    for c in node.children:
        if c.type == "name":
            return text_of(pf, c)
    return text_of(pf, node).lstrip("$")


def _params(pf: ParsedFile, method_node) -> list[str]:
    out = []
    fp = next((c for c in method_node.children if c.type == "formal_parameters"), None)
    if fp:
        for p in fp.children:
            if p.type == "simple_parameter":
                vn = next((c for c in p.children if c.type == "variable_name"), None)
                if vn:
                    out.append(_var_name(pf, vn))
    return out


def _string_content(pf: ParsedFile, str_node) -> str:
    sc = next((c for c in str_node.children if c.type == "string_content"), None)
    return text_of(pf, sc) if sc else text_of(pf, str_node).strip("'")


def _collect(pf: ParsedFile, method_node, known: set[str], edges: list,
             reads: dict[str, Read]) -> None:
    """单方法体一次遍历:读三类 + 调用边(带实参位置) + 单级别名。"""
    skip: set[int] = set()          # isset/empty 已消费的 subscript 节点
    stack = list(method_node.children)
    while stack:
        n = stack.pop()
        stack.extend(n.children)
        t = n.type
        if t == "function_call_expression":
            name = ""
            for c in n.children:
                if c.type == "name":
                    name = text_of(pf, c)
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            args = [c for c in args_node.children if c.type == "argument"] if args_node else []
            if name in _GET_DATA and len(args) >= 2:
                key_n = _first_string(args[1])
                if key_n is not None and _arg_var(pf, args[0]) in known:
                    default = None
                    if len(args) >= 3:
                        dn = _first_string(args[2])
                        default = _string_content(pf, dn) if dn else None
                    key = _string_content(pf, key_n)
                    reads.setdefault(key, Read(key=key, default=default, via="getData"))
            elif name in _ISSET and args:
                a0 = args[0]
                if a0.type == "subscript_expression":
                    sub = _subscript_parts(pf, a0)
                    if sub and sub[0] in known:
                        reads.setdefault(sub[1], Read(key=sub[1], via="isset"))
                        skip.add(a0.id)
        elif t == "subscript_expression":
            if n.id not in skip:
                sub = _subscript_parts(pf, n)
                if sub and sub[0] in known:
                    reads.setdefault(sub[1], Read(key=sub[1], via="subscript"))
        elif t == "assignment_expression":
            kids = n.children
            if len(kids) >= 2 and kids[0].type == "variable_name" \
                    and kids[1].type == "variable_name":
                src = _var_name(pf, kids[1])
                if src in known:
                    known.add(_var_name(pf, kids[0]))
        elif t == "member_call_expression":
            base = n.children[0] if n.children else None
            meth = next((c for c in n.children if c.type == "name"), None)
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            if base is not None and base.type == "scoped_call_expression" and meth:
                cls = next((c for c in base.children if c.type == "name"), None)
                if cls:
                    _edge(edges, text_of(pf, cls), text_of(pf, meth),
                          _arg_positions(pf, args_node, known))
        elif t == "scoped_call_expression":
            # 直接静态调用(如 Validator::checkXxx($requestData))
            names = [c for c in n.children if c.type == "name"]
            args_node = next((c for c in n.children if c.type == "arguments"), None)
            if len(names) == 2 and text_of(pf, names[1]) != "getInstance":
                _edge(edges, text_of(pf, names[0]), text_of(pf, names[1]),
                      _arg_positions(pf, args_node, known))
        elif t == "object_creation_expression":
            name = next((c for c in n.children if c.type == "name"), None)
            if name:
                _edge(edges, text_of(pf, name), "__construct", [])


def _edge(edges, cls: str, meth: str, arg_pos: list[int]) -> None:
    edges.append((cls, meth, arg_pos))


def _arg_positions(pf: ParsedFile, args_node, known: set[str]) -> list[int]:
    """实参里哪些位置传的是 known-var(位置索引从 0 计)。"""
    out = []
    if args_node is None:
        return out
    for i, a in enumerate(c for c in args_node.children if c.type == "argument"):
        if _arg_var(pf, a) in known:
            out.append(i)
    return out


def _arg_var(pf: ParsedFile, arg) -> str:
    """实参(argument 节点包一层表达式)内取 variable_name 裸名;非变量返回 ''。"""
    node = arg
    if arg.type == "argument":
        node = next((c for c in arg.children if c.type == "variable_name"), None)
        if node is None:
            return ""
    return _var_name(pf, node) if node is not None and node.type == "variable_name" else ""


def _first_string(arg):
    """argument 内第一个 string 字面量节点;没有(如 [] 默认参)返回 None。"""
    return next((c for c in arg.children if c.type == "string"), None)


def _subscript_parts(pf: ParsedFile, node) -> tuple[str, str] | None:
    """subscript_expression → (变量裸名, 字符串键);非字符串键返回 None。"""
    var = key = None
    for c in node.children:
        if c.type == "variable_name":
            var = _var_name(pf, c)
        elif c.type == "string":
            key = _string_content(pf, c)
    return (var, key) if var and key else None


def collect_reads(actions: list[ActionIR], app_root: Path) -> None:
    idx = _ClassIndex(app_root)
    for act in actions:
        ctl_class = act.controller + "Controller"
        visited: set[tuple[str, str]] = set()
        reads: dict[str, Read] = {}
        # 队列:(类, 方法, 进入时已知的变量名集)
        queue: list[tuple[str, str, frozenset]] = [
            (ctl_class, act.action, frozenset({"requestData"}))
        ]
        for cls, meth in [(c, m) for c, m in act.callees]:
            queue.append((cls, meth, frozenset({"requestData"})))
        for chk in act.validator_checks:
            queue.append((act.controller + "Validator", chk,
                          frozenset({"requestData"})))
        while queue:
            cls, meth, known = queue.pop(0)
            if (cls, meth) in visited:
                continue
            visited.add((cls, meth))
            entry = idx.methods.get(cls, {}).get(meth)
            if not entry:
                continue
            node, pf = entry
            k = set(known) | set(_params(pf, node))
            edges: list[tuple[str, str, list[int]]] = []
            _collect(pf, node, k, edges, reads)
            for e_cls, e_meth, positions in edges:
                entry2 = idx.methods.get(e_cls, {}).get(e_meth)
                if not entry2:
                    continue
                callee_params = _params(entry2[1], entry2[0])
                linked = {callee_params[p] for p in positions
                          if p < len(callee_params)}
                queue.append((e_cls, e_meth, frozenset(linked)))
        act.reads = reads
```

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s2_reads.py -v
git add src/gimbal-plate/tools/twin_generator/s2_reads.py src/gimbal-plate/tools/twin_generator/tests/
git commit -m "feat(twin-gen): S2b 读取树 — 调用图 BFS + known-var 传播 + 三类键读

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 6: S3 语义富化(zh 合并/类型/默认/Enum)

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s3_semantics.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/fixtures/php/app/Application/Common/Enum/OrderEnum.class.php`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s3_semantics.py`

**Interfaces:**
- Consumes: S1/S2 产物(`actions`)、`schema_source.ColumnCatalog`。
- Produces: `load_enums(app_root) -> dict[str, list[tuple[str, str]]]`(常量名→(值,中文),仅报告用);`enrich(actions, catalog) -> dict[str, list[FieldIR]]`(action.id → 字段清单)。zh 优先级 `rule > column > derived(_name 派生) > ""`;type 映射:col_type `int/bigint/tinyint` → `integer`、`decimal/float/double` → `number`、其余 `string`;default 取 read.default,退 column.default(非空)。

- [ ] **Step 1: fixture**

`fixtures/php/app/Application/Common/Enum/OrderEnum.class.php`:

```php
<?php
class OrderEnum
{
    const EXPECT_CREATING = 0; //创建中
    const EXPECT_AUDITING = 1; //审核中
    const SETTLE_MONTHLY = 1; //月结
}
```

- [ ] **Step 2: 失败测试**

`tests/test_s3_semantics.py`:

```python
from twin_generator.s1_routes import scan_actions
from twin_generator.s2_validator import attach_rules
from twin_generator.s2_reads import collect_reads
from twin_generator.s3_semantics import enrich, load_enums
from twin_generator.schema_source import load_columns
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def test_enrich():
    acts = scan_actions(APP)
    attach_rules(acts, APP)
    collect_reads(acts, APP)
    enums = load_enums(APP)
    assert ("0", "创建中") in enums["EXPECT_CREATING"]
    fields = enrich(acts, load_columns(FIXTURES / "schema" / "fin_test_search.csv"))
    by_key = {f.key: f for f in fields["fin.order_entrust.order_add"]}
    # zh 优先级:rule(客户ID) > column > derived
    assert by_key["customer_id"].zh == "客户ID" and by_key["customer_id"].zh_source == "rule"
    # customer_id 被读(getData)→ read=True
    assert by_key["customer_id"].read is True
    # bl_no:rule 注释「提单号」优先于 column「业务订单ID」
    assert by_key["bl_no"].zh == "提单号"
    # 被注释行 carrier:无 column 匹配 → zh 来自 rule 注释
    assert by_key["carrier"].zh == "船公司/承运人"
    # 类型:etd column int → integer;default 来自 getDataString 第三参
    assert by_key["etd"].type_ == "integer"
    assert by_key["action"].default == "submit"
    # enum:rule in: 优先且为字符串
    assert by_key["settle_type"].enum_values == ["1", "2"]
    # _name 派生:customer_name 无任何源 → 客户ID+名称
    assert by_key["customer_name"].zh == "客户ID名称" and by_key["customer_name"].zh_source == "derived"
```

- [ ] **Step 3: 验证失败**

- [ ] **Step 4: 实现 s3_semantics.py**

```python
"""S3:语义富化 —— zh 合并(rule>column>derived)/type 映射/默认值/enum(rule)。

Enum 类抽取仅作报告候选(v1 不自动挂 enum,scope 控制);字段集 =
活跃规则键 ∪ 被注释规则键 ∪ 读取键。
"""
from __future__ import annotations

from pathlib import Path

from .php_ast import ParsedFile, load, text_of, classes
from .ir import ActionIR, FieldIR, RuleEntry
from .schema_source import ColumnCatalog

_INT_TYPES = ("int", "bigint", "tinyint", "smallint", "mediumint")
_NUM_TYPES = ("decimal", "float", "double")


def load_enums(app_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Common/Enum/*.class.php:常量名 → [(值, 中文)](报告候选用)。"""
    out: dict[str, list[tuple[str, str]]] = {}
    for f in sorted((app_root / "Common" / "Enum").glob("*.class.php")):
        pf = load(f)
        for _n, _c, decl in classes(pf):
            children = list(decl.children)
            for i, node in enumerate(children):
                if node.type != "const_declaration":
                    continue
                for el in node.children:
                    if el.type != "const_element":
                        continue
                    name = next((c for c in el.children if c.type == "name"), None)
                    if name is None:
                        continue
                    val_n = next((c for c in el.children
                                  if c.type in ("integer", "string")), None)
                    nxt = children[i + 1] if i + 1 < len(children) else None
                    zh = ""
                    if nxt is not None and nxt.type == "comment" \
                            and nxt.start_point[0] == node.start_point[0]:
                        zh = text_of(pf, nxt).lstrip("/ ").strip()
                    if val_n is not None:
                        out.setdefault(text_of(pf, name), []).append(
                            (text_of(pf, val_n).strip("'\""), zh))
    return out


def _type_of(col_type: str) -> str:
    base = col_type.split("(")[0].lower()
    if base in _INT_TYPES:
        return "integer"
    if base in _NUM_TYPES:
        return "number"
    return "string"


def _rule_index(rules: list[RuleEntry]) -> dict[str, RuleEntry]:
    out: dict[str, RuleEntry] = {}
    for r in rules:                     # 活跃行优先(后写覆盖时保活跃)
        if r.active:
            out[r.key] = r
    for r in rules:
        out.setdefault(r.key, r)
    return out


def enrich(actions: list[ActionIR], catalog: ColumnCatalog
           ) -> dict[str, list[FieldIR]]:
    all_fields: dict[str, list[FieldIR]] = {}
    for act in actions:
        ridx = _rule_index(act.rules)
        keys: list[str] = []
        for k in list(ridx) + list(act.reads):
            if k not in keys:
                keys.append(k)
        fields: list[FieldIR] = []
        for key in keys:
            rule = ridx.get(key)
            read = act.reads.get(key)
            cols = catalog.by_name.get(key, [])
            f = FieldIR(
                key=key,
                read=read is not None,
                required=bool(rule and rule.required()),
                must_include=bool(rule and (rule.required() or rule.must_include())),
                zh=rule.zh if rule and rule.zh else "",
                zh_source="rule" if rule and rule.zh else "",
                enum_values=rule.enum_values() if rule else None,
                default=read.default if read and read.default is not None else None,
                col_comment=cols[0].comment if cols else "",
                col_type=cols[0].col_type if cols else "",
                tables=[c.table for c in cols],
            )
            if not f.zh and cols and cols[0].comment:
                f.zh, f.zh_source = cols[0].comment, "column"
            if not f.zh and key.endswith("_name"):
                base_key = key[:-5]           # customer_name → customer
                for cand in (base_key, base_key + "_id"):
                    base = ridx.get(cand)
                    if base and base.zh:
                        f.zh, f.zh_source = base.zh + "名称", "derived"
                        break
            f.type_ = _type_of(f.col_type) if f.col_type else "string"
            if f.default is None and cols and cols[0].default:
                f.default = cols[0].default
            fields.append(f)
        all_fields[act.id] = fields
    return all_fields
```

- [ ] **Step 5: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s3_semantics.py -v
git add src/gimbal-plate/tools/twin_generator/s3_semantics.py src/gimbal-plate/tools/twin_generator/tests/
git commit -m "feat(twin-gen): S3 语义富化 — zh 四源合并/类型映射/默认值/enum

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 7: S4 状态赋值 + value_source 匹配

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s4_state.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s4_state.py`

**Interfaces:**
- Consumes: Task 6 的 `dict[action_id, list[FieldIR]]`、`ColumnCatalog`、视图目录行(`list[dict]`,形状同 `build_query_view_index` 输出,测试里传字面量,CLI 里 import plate 取真源)。
- Produces: `assign(all_fields, actions, catalog, view_rows) -> DisambigReport`;就地写 `FieldIR.state/value_source/flags`。判据(spec §2):`read → form`;`!read && required|must_include|catalog.not_null_no_default → carry+须挂 value_source`(enum 字段互斥跳过);其余 `carry`。同名匹配:恰好 1 个视图含该列 → 挂;0 个 → `flags += ["needs_capture:value_source"]`;>1 → 同前 + 进消歧报告。

- [ ] **Step 1: 失败测试**

`tests/test_s4_state.py`:

```python
from twin_generator.ir import ActionIR, FieldIR
from twin_generator.schema_source import load_columns
from twin_generator.s4_state import assign
from conftest import FIXTURES

VIEW_ROWS = [
    {"name": "customer_list", "columns": ["customer_id", "customer_name", "bl_no"]},
    {"name": "customer_part", "columns": ["customer_id", "handover_form.client_expand_name"]},
]


def _fields():
    return [
        FieldIR(key="action", read=True, required=False),               # 读 → form
        FieldIR(key="customer_id", read=False, required=True),          # 必填未读 → carry+vs
        FieldIR(key="bl_no", read=False, must_include=True),            # exist → carry+vs
        FieldIR(key="carrier", read=False, required=False),             # 纯携带
        FieldIR(key="etd", read=False, required=False),
        FieldIR(key="settle_type", read=False, required=True,
                enum_values=["1", "2"]),                                # enum×vs 互斥
    ]


def test_assign():
    acts = [ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")]
    fields = {"fin.order_entrust.order_add": _fields()}
    cat = load_columns(FIXTURES / "schema" / "fin_test_search.csv")
    report = assign(fields, acts, cat, VIEW_ROWS)
    by = {f.key: f for f in fields["fin.order_entrust.order_add"]}
    assert by["action"].state == "form"
    # customer_id 两视图同名 → 消歧,不自动挂
    assert by["customer_id"].value_source is None
    assert "needs_capture:value_source" in by["customer_id"].flags
    assert ("fin.order_entrust.order_add", "customer_id",
            {"customer_list", "customer_part"}) in report.ambiguous
    # bl_no 恰一视图 → 挂上
    assert by["bl_no"].value_source == ("customer_list", "bl_no")
    # carrier/etd 纯 carry(etd 的 NOT NULL 有默认 '0',不触发)
    assert by["carrier"].state == "carry" and by["carrier"].flags == []
    assert by["etd"].state == "carry" and by["etd"].flags == []
    # enum 与 vs 互斥:必填但有 enum → 不挂 vs,标 needs_capture
    assert by["settle_type"].value_source is None
    assert "needs_capture:enum_required" in by["settle_type"].flags
```

- [ ] **Step 2: 验证失败**

- [ ] **Step 3: 实现 s4_state.py**

```python
"""S4:状态赋值(spec §2 白名单判据)+ value_source 同名匹配。

判据:read → form;
     !read && (required | must_include | not_null_no_default) → carry + 须挂 value_source;
     其余 → carry。
enum×value_source 互斥(io_spec):enum 字段跳过挂载,标 needs_capture:enum_required。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .ir import ActionIR, FieldIR
from .schema_source import ColumnCatalog


@dataclass
class DisambigReport:
    ambiguous: list = field(default_factory=list)   # (action_id, key, {视图名})


def assign(all_fields: dict, actions: list[ActionIR], catalog: ColumnCatalog,
           view_rows: list[dict]) -> DisambigReport:
    report = DisambigReport()
    for act in actions:
        for f in all_fields.get(act.id, []):
            if f.read:
                f.state = "form"
                continue
            f.state = "carry"
            needs_value = (f.required or f.must_include
                           or catalog.not_null_no_default(f.key))
            if not needs_value:
                continue
            if f.enum_values:
                f.flags.append("needs_capture:enum_required")
                continue
            hits = [r["name"] for r in view_rows if f.key in r["columns"]]
            if len(hits) == 1:
                f.value_source = (hits[0], f.key)
            else:
                f.flags.append("needs_capture:value_source")
                if len(hits) > 1:
                    report.ambiguous.append((act.id, f.key, set(hits)))
    return report
```

- [ ] **Step 4: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s4_state.py -v
git add src/gimbal-plate/tools/twin_generator/s4_state.py src/gimbal-plate/tools/twin_generator/tests/test_s4_state.py
git commit -m "feat(twin-gen): S4 状态赋值 — 白名单判据 + 同名匹配/消歧/enum 互斥

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 8: S5 装订(EndpointSpec 渲染 + 碰撞 + 对照)

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/s5_emit.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_s5_emit.py`

**Interfaces:**
- Consumes: S1-S4 全部产物;`existing_ids: set[str]`(CLI 从 plate 注册表取,测试传字面量)。
- Produces:
  - `render_endpoint(act: ActionIR, fields: list[FieldIR], baseline: str) -> str`(可 import 的 Python 源码文本;镜像手建文件结构)
  - `emit_all(actions, all_fields, out_dir, existing_ids, baseline) -> dict`(计数摘要:emitted/skipped/needs_capture 总数;逐文件写盘)
  - `compare_faces(all_fields, handbuilt: dict[str, dict]) -> str`(markdown 三分类差异报告;`handbuilt` = `{endpoint_id: {key: (state, zh, enum, required, vs)}}`)

- [ ] **Step 1: 失败测试**

`tests/test_s5_emit.py`:

```python
import importlib.util
import sys
from pathlib import Path

from twin_generator.ir import ActionIR, FieldIR
from twin_generator.s5_emit import render_endpoint, emit_all

# generated 文件 import gimbal_plate —— conftest 已插路径?本测试自己插:
REPO = Path(__file__).resolve().parents[5]   # tools/twin_generator/tests → repo
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))


def _act():
    return ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")


def _fields():
    return [
        FieldIR(key="action", read=True, zh="动作", default="submit"),
        FieldIR(key="customer_id", required=True, zh="客户ID",
                value_source=("customer_list", "customer_id")),
        FieldIR(key="carrier", zh="船公司/承运人",
                flags=["needs_capture:value_source"]),
    ]


def test_render_and_import(tmp_path):
    src_text = render_endpoint(_act(), _fields(), baseline="fin-test@2026-09-15")
    assert "ORDER_ENTRUST_ORDER_ADD" in src_text
    assert "needs_capture:value_source" in src_text
    f = tmp_path / "order_entrust_order_add.py"
    f.write_text(src_text, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gen_mod", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)            # pydantic 构造期校验即验收
    ep = mod.ORDER_ENTRUST_ORDER_ADD
    assert ep.id == "fin.order_entrust.order_add"
    assert ep.api.path == "/api/order/orderEntrust/orderAdd"
    by_name = {d.name: d for d in ep.request.declarations}
    assert by_name["action"].state == "form"
    assert by_name["customer_id"].state == "carry"
    assert by_name["customer_id"].value_source.view == "customer_list"
    assert by_name["customer_id"].required is True


def test_emit_all_collision_skip(tmp_path):
    acts = [_act()]
    fields = {"fin.order_entrust.order_add": _fields()}
    summary = emit_all(acts, fields, tmp_path, existing_ids={"fin.order_entrust.order_add"},
                       baseline="b")
    assert summary["skipped"] == 1 and summary["emitted"] == 0
    assert not list(tmp_path.glob("*.py"))
```

- [ ] **Step 2: 验证失败**

- [ ] **Step 3: 实现 s5_emit.py**

```python
"""S5:装订 —— EndpointSpec Python 源码渲染 + 碰撞跳过(手建优先)+ 对照报告。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .ir import ActionIR, FieldIR

_HEADER = '''"""{id} —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: {baseline} | 生成时间: {now}
needs_capture(首跑经 gimbal 执行回填): {nc}
"""
'''

_TEMPLATE = '''from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
    ValueSource,
)

{const}: Final[EndpointSpec] = EndpointSpec(
    id={id!r},
    system='fin',
    service='fin-service',
    name={zh!r},
    description={zh!r} + ' [generated:{baseline}]',
    api=ApiSpec(
        service='fin-service',
        method={method!r},
        path={path!r},
        headers={{}},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
{entries}
        ],
    ),
    responses={{
        200: ResponseSpec(
            status=200,
        ),
    }},
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
'''


def _entry_lines(fields: list[FieldIR]) -> str:
    lines = []
    for f in fields:
        kwargs = [f"name={f.key!r}", f"path=f'$.{f.key}'",
                  f"type={f.type_!r}", f"state={f.state!r}"]
        if f.required:
            kwargs.append("required=True")
        if f.default is not None:
            kwargs.append(f"default={f.default!r}")
        if f.zh:
            kwargs.append(f"description={f.zh!r}")
        if f.enum_values:
            kwargs.append(f"enum={f.enum_values!r}")
        if f.value_source:
            kwargs.append(
                f"value_source=ValueSource(view={f.value_source[0]!r}, "
                f"column={f.value_source[1]!r})")
        joined = ", ".join(kwargs)
        lines.append(f"            DeclarationEntry({joined}),")
    return "\n".join(lines) or "            # (无字段 — 键面为空)"


def render_endpoint(act: ActionIR, fields: list[FieldIR], baseline: str) -> str:
    nc = [f.key for f in fields if f.flags] or ["(无)"]
    zh = next((f.zh for f in fields if f.key == "action" and f.zh),
              f"{act.controller}.{act.action}")
    head = _HEADER.format(id=act.id, baseline=baseline,
                          now=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          nc=", ".join(nc))
    body = _TEMPLATE.format(
        const=act.const_name, id=act.id, zh=zh, baseline=baseline,
        method=act.method, path=act.path, entries=_entry_lines(fields))
    return head + body


def emit_all(actions: list[ActionIR], all_fields: dict, out_dir: Path,
             existing_ids: set[str], baseline: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    emitted = skipped = nc_total = 0
    for act in actions:
        if act.id in existing_ids:
            skipped += 1
            continue
        fields = all_fields.get(act.id, [])
        nc_total += sum(1 for f in fields if f.flags)
        fname = f"{act.module.lower()}_{act.const_name.lower()}.py"
        (out_dir / fname).write_text(
            render_endpoint(act, fields, baseline), encoding="utf-8")
        emitted += 1
    return {"emitted": emitted, "skipped": skipped,
            "needs_capture": nc_total}


def compare_faces(all_fields: dict, handbuilt: dict) -> str:
    """三分类差异报告:missing(生成漏)/extra(生成多)/diff(同键字段异)。"""
    lines = ["# 对照报告(生成 vs 手建 ground truth)", ""]
    for ep_id, hb_keys in sorted(handbuilt.items()):
        gen = {f.key: f for f in all_fields.get(ep_id, [])}
        missing = [k for k in hb_keys if k not in gen]
        extra = [k for k in gen if k not in hb_keys]
        diffs = []
        for k, (state, zh, enum, required, vs) in hb_keys.items():
            g = gen.get(k)
            if g and (g.state != state or g.zh != zh or g.enum_values != enum):
                diffs.append(
                    f"| {k} | 手建 state={state} zh={zh!r} enum={enum!r} "
                    f"| 生成 state={g.state} zh={g.zh!r} enum={g.enum_values!r} |")
        if missing or extra or diffs:
            lines += [f"## {ep_id}", ""]
            if missing:
                lines.append(f"- missing({len(missing)}): {', '.join(missing)}")
            if extra:
                lines.append(f"- extra({len(extra)}): {', '.join(extra)}")
            if diffs:
                lines += ["| 键 | 手建 | 生成 |", "|---|---|---|"] + diffs
            lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_s5_emit.py -v
git add src/gimbal-plate/tools/twin_generator/s5_emit.py src/gimbal-plate/tools/twin_generator/tests/test_s5_emit.py
git commit -m "feat(twin-gen): S5 装订 — EndpointSpec 渲染/碰撞跳过/对照三分类报告

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 9: CLI 串联 + 端到端

**Files:**
- Create: `src/gimbal-plate/tools/twin_generator/cli.py`
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_cli.py`

**Interfaces:**
- Consumes: S1-S5 全部;plate 注册表(带 sys.path 引导 + try/except,取不到则 existing_ids 空集 + view_rows 空表,工具仍可跑)。
- Produces: `main(argv=None) -> int`(0 成功);参数 `--app-root/--schema-csv/--out/--baseline/--only/--compare/--install-dir`。产物:`<out>/endpoints/*.py`、`<out>/routes.json`、`<out>/fields.json`、`<out>/disambiguation.md`、`<out>/compare_report.md`(仅 --compare)。

- [ ] **Step 1: 失败测试**

`tests/test_cli.py`:

```python
import json

from twin_generator import cli as cli_mod
from twin_generator.cli import main
from conftest import FIXTURES

APP = FIXTURES / "php" / "app" / "Application"


def test_end_to_end(tmp_path, monkeypatch):
    # fixture 的 fin.order_entrust.order_add 与真实手建 id 同名:
    # 放任 _plate_registry 取真源会触发碰撞跳过,断言 2 文件必失败。
    # 钉死空注册表(真实注册表在 Task 10 真源跑里检验)。
    monkeypatch.setattr(cli_mod, "_plate_registry", lambda: (set(), [], {}))
    rc = main([
        "--app-root", str(APP),
        "--schema-csv", str(FIXTURES / "schema" / "fin_test_search.csv"),
        "--out", str(tmp_path),
        "--baseline", "test",
    ])
    assert rc == 0
    assert json.loads((tmp_path / "routes.json").read_text(encoding="utf-8"))
    gen = list((tmp_path / "endpoints").glob("*.py"))
    assert len(gen) == 2                                # order_add + order_page
    assert (tmp_path / "disambiguation.md").exists()
```

- [ ] **Step 2: 验证失败**

- [ ] **Step 3: 实现 cli.py**

```python
"""孪生生成器 CLI:S1→S5 串联。

真实源默认值指向 D:\\fin-test;产物默认落 gimbal-tmp/twin_gen(永不提交)。
--install-dir 才写 gimbal_plate 包内(人工 gate 后)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .s1_routes import scan_actions
from .s2_validator import attach_rules
from .s2_reads import collect_reads
from .s3_semantics import enrich
from .s4_state import assign
from .s5_emit import emit_all, compare_faces

# cli.py → twin_generator → tools → gimbal-plate → src → repo 根
REPO = Path(__file__).resolve().parents[4]


def _plate_registry():
    """(existing_ids, view_rows, handbuilt_faces);plate 不可 import → 全空降级。"""
    sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))
    try:
        from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS
        from gimbal_plate.service.query_views import build_query_view_index
    except Exception:
        return set(), [], {}
    ids = {ep.id for ep in ALL_ENDPOINTS}
    views = build_query_view_index(ALL_ENDPOINTS)
    faces = {}
    for ep in ALL_ENDPOINTS:
        if ep.request is None:
            continue
        faces[ep.id] = {
            d.name: (d.state, d.description, d.enum, d.required,
                     d.value_source.view if d.value_source else None)
            for d in ep.request.declarations
        }
    return ids, views, faces


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fin SUT 请求面孪生生成器")
    ap.add_argument("--app-root", default=r"D:\fin-test\api\Application")
    ap.add_argument("--schema-csv", default=r"D:\fin-test\fin_test_search.csv")
    ap.add_argument("--out", default=str(REPO / "gimbal-tmp" / "twin_gen"))
    ap.add_argument("--baseline", default="fin-test@2026-09-15")
    ap.add_argument("--only", default="", help="逗号分隔 action 过滤(orderAdd,...)")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--install-dir", default="", help="人工 gate 后的正式落盘目录")
    args = ap.parse_args(argv)

    from .schema_source import load_columns
    app_root = Path(args.app_root)
    actions = scan_actions(app_root)
    if args.only:
        keep = {s.strip() for s in args.only.split(",") if s.strip()}
        actions = [a for a in actions if a.action in keep]
    attach_rules(actions, app_root)
    collect_reads(actions, app_root)
    catalog = load_columns(args.schema_csv)
    all_fields = enrich(actions, catalog)
    existing_ids, view_rows, faces = _plate_registry()
    report = assign(all_fields, actions, catalog, view_rows)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "routes.json").write_text(json.dumps(
        [{"id": a.id, "path": a.path, "rules": len(a.rules),
          "reads": len(a.reads)} for a in actions],
        ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "fields.json").write_text(json.dumps(
        {k: [f.__dict__ for f in v] for k, v in all_fields.items()},
        ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = ["# value_source 消歧队列", ""]
    for act_id, key, views in report.ambiguous:
        lines.append(f"- `{act_id}` :: `{key}` → {sorted(views)}")
    (out / "disambiguation.md").write_text("\n".join(lines), encoding="utf-8")

    target = Path(args.install_dir) if args.install_dir else out / "endpoints"
    summary = emit_all(actions, all_fields, target, existing_ids, args.baseline)
    print(f"emitted={summary['emitted']} skipped={summary['skipped']} "
          f"needs_capture={summary['needs_capture']}")

    if args.compare:
        md = compare_faces(all_fields, faces)
        (out / "compare_report.md").write_text(md, encoding="utf-8")
        print(f"compare_report → {out / 'compare_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: 验证通过并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests/test_cli.py -v && python -m pytest tests -v
git add src/gimbal-plate/tools/twin_generator/cli.py src/gimbal-plate/tools/twin_generator/tests/test_cli.py
git commit -m "feat(twin-gen): CLI 串联 — 五阶段管线端到端 + 报告产物

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 10: 真实源灰度跑 + ground-truth 对照(人工 gate)

**Files:**
- 无新代码;产物全落 `gimbal-tmp/twin_gen/`(永不提交)。
- 若真源暴露小 bug:修对应模块 + 补 fixture 回归测试(正常 TDD 节奏)。

- [ ] **Step 1: 全量跑(零 HTTP,只读本地)**

```bash
cd src/gimbal-plate/tools && export PYTHONIOENCODING=utf-8 PYTHONUTF8=1 && python -m twin_generator.cli 2>&1 | tail -5
```
(必须在 `tools/` 目录以 `-m twin_generator.cli` 跑 —— 包内是相对导入,`python cli.py` 直跑会 ImportError,那不是 bug 是入口姿势。)

- [ ] **Step 2: 对照跑(26 手建为 ground truth)**

对 `--only` 逐个手建接口名跑 `--compare`,或全量跑一次(碰撞接口照常生成到临时区,不落盘包内)。检查 `gimbal-tmp/twin_gen/compare_report.md`。

- [ ] **Step 3: 验收判据(spec §8)**

- 键集召回:手建每个接口的 declarations 键 ⊆ 生成键(missing=0 或逐条可解释);
- 语义一致率(name/description/enum/default)≥90%;
- state 分歧全部可解释(生成 form vs 手建 carry 且字段被读 → 记录为「form 候选待人工」类);
- 另抽 5 个新接口人工复核(键面/中文/enum 抽查)。
判据不满足 → 回对应阶段修 + fixture 回归,不降判据。

- [ ] **Step 4: 汇报 gate**

向用户呈 compare_report 三分类计数与 5 接口抽查结论,**等待放行**后才进 Task 11 落盘安装。(这是 spec §6 首跑真值同源的安全闸:批量入库 = 平台可见 = 可被编排执行。)

---

### Task 11: 安装接线(endpoint_generated 包 + spec 修订)

**Files:**
- Create: `src/gimbal-plate/gimbal_plate/systems/fin/endpoint_generated/__init__.py`
- Modify: `src/gimbal-plate/gimbal_plate/systems/fin/__init__.py`(干净文件;**绝不碰** `endpoint/__init__.py`)
- Modify: `docs/superpowers/specs/2026-09-15-sut-request-surface-twin-generator-design.md`(§5 目录条修订)
- Test: `src/gimbal-plate/tools/twin_generator/tests/test_install.py`

**Interfaces:**
- Produces: `ALL_GENERATED_ENDPOINTS`(自动发现 `endpoint_generated/*.py` 中模块级 `EndpointSpec` 常量);`fin.__init__.ALL_ENDPOINTS = 手建 + 生成`。

- [ ] **Step 1: 失败测试**

`tests/test_install.py`:

```python
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO / "src" / "gimbal-plate"))


def test_generated_package_discovery():
    from gimbal_plate.systems.fin import endpoint_generated as eg
    assert hasattr(eg, "ALL_GENERATED_ENDPOINTS")
    # 空包可导入、列表为 list、元素(若有)是 EndpointSpec
    from gimbal_plate.schema.endpoint import EndpointSpec
    assert isinstance(eg.ALL_GENERATED_ENDPOINTS, list)
    for ep in eg.ALL_GENERATED_ENDPOINTS:
        assert isinstance(ep, EndpointSpec)


def test_fin_aggregation_merges():
    from gimbal_plate.systems.fin import ALL_ENDPOINTS
    assert len({ep.id for ep in ALL_ENDPOINTS}) == len(ALL_ENDPOINTS)  # id 唯一
```

- [ ] **Step 2: 验证失败**

- [ ] **Step 3: 实现**

`endpoint_generated/__init__.py`:

```python
"""孪生生成器产物的自动发现聚合(人工 gate 后经 cli --install-dir 落盘于此)。

不逐个 import:glob 发现本目录 *.py(非下划线开头),importlib 加载,
收模块级 EndpointSpec 常量。生成文件自带构造期校验,坏文件 import 即炸 ——
这正是闸门。与手建 endpoint/__init__.py 互不相扰(那边是他人改动,永不碰)。
"""
import importlib.util
from pathlib import Path

from gimbal_plate.schema.endpoint import EndpointSpec

_DIR = Path(__file__).parent
ALL_GENERATED_ENDPOINTS: list[EndpointSpec] = []

for _f in sorted(_DIR.glob("*.py")):
    if _f.name.startswith("_"):
        continue
    _spec = importlib.util.spec_from_file_location(
        f"gimbal_plate.systems.fin.endpoint_generated.{_f.stem}", _f)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    for _name in dir(_mod):
        _obj = getattr(_mod, _name)
        if isinstance(_obj, EndpointSpec) and _obj.id not in (
                e.id for e in ALL_GENERATED_ENDPOINTS):
            ALL_GENERATED_ENDPOINTS.append(_obj)
```

`systems/fin/__init__.py` 末尾追加(保留原内容不动):

```python
# 孪生生成器产物(2026-09-15 spec):自动发现,人工 gate 后落盘;见 endpoint_generated/
from gimbal_plate.systems.fin.endpoint_generated import ALL_GENERATED_ENDPOINTS as _GENERATED

ALL_ENDPOINTS = ALL_ENDPOINTS + _GENERATED
```

注意:原 `fin/__init__.py` 若 `ALL_ENDPOINTS` 以 `from .endpoint import ALL_ENDPOINTS` 形式存在,追加行直接拼接;以实测文件内容为准,改动仅追加这两行。

spec §5 目录条改为:

```markdown
- 目录:`gimbal_plate/systems/fin/endpoint_generated/`(sibling 自动发现包;
  手建 `endpoint/` 聚合入口是他人未提交改动,绝不编辑 —— 2026-09-15 实施修订);
```

- [ ] **Step 4: 验证通过(含 plate 全量回归)并提交**

```bash
cd src/gimbal-plate/tools/twin_generator && python -m pytest tests -v
cd D:/Gimbal/Gimbal/src/gimbal-plate && python -c "from gimbal_plate.systems.fin import ALL_ENDPOINTS; print(len(ALL_ENDPOINTS))"
git add src/gimbal-plate/gimbal_plate/systems/fin/endpoint_generated/__init__.py src/gimbal-plate/gimbal_plate/systems/fin/__init__.py docs/superpowers/specs/2026-09-15-sut-request-surface-twin-generator-design.md src/gimbal-plate/tools/twin_generator/tests/test_install.py
git commit -m "feat(twin-gen): 安装接线 — endpoint_generated 自动发现包 + fin 聚合合并 + spec §5 修订

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## 验收总门(spec §8 映射)

1. Task 1-9:全测试绿(每任务独立测试周期);
2. Task 10:真实源 compare_report 达标(键集召回 100%/语义 ≥90%/state 可解释)+ 5 新接口抽查;
3. Task 11:plate 包导入无恙、id 唯一、既有 26 手建不受影响;
4. 全程零 HTTP、零对 `endpoint/__init__.py` 的触碰、`gimbal-tmp/` 零提交。
