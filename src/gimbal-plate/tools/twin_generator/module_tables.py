"""T3.3:模块-表映射 —— 跨表 zh 的上下文选表依据。

v1 缺口 4:同名列(如 enable/status)在几百张表存在,CSV 首现表
注释被错绑。选表两源并集:
1. 表名模式:sys_<module>% (Order → sys_order*,Audit → sys_audit*);
2. 源码引用:controller 文件里 M('X')/D('X') → sys_<x>(ThinkPHP
   3.2 约定,sys 为表前缀,模型名小写下划线化)。

s3 选列顺序:模块表过滤 → 唯一命中用之 → 多候选取注释非空 → 平局
flag zh_ambiguous → 零命中回退全局首现。
"""
from __future__ import annotations

import re
from pathlib import Path

_RE_MODEL_REF = re.compile(r"\b[MD]\('(\w+)'\)")


def _snake(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def module_tables(app_root: Path, module: str) -> set[str]:
    """模块的候选表**前缀**集合(sys_order 前缀命中 sys_order_fee_real 等)。

    M('X') 引用也作前缀处理:M('Customer') 放行 sys_customer_* 实体族
    —— 模块页面用到的列注释属于该模块的语义上下文。
    """
    tables = {f"sys_{module.lower()}"}
    for mf in sorted(app_root.glob(f"{module}/Controller/*.class.php")) \
            + sorted(app_root.glob(f"{module}/Model/*.class.php")):
        s = mf.read_text(encoding="utf-8", errors="replace")
        for m in _RE_MODEL_REF.finditer(s):
            tables.add(f"sys_{_snake(m.group(1))}")
    return tables


def build_index(app_root: Path, modules: list[str]) -> dict[str, set[str]]:
    """模块名 → 表名集合(一次构建,管线内复用)。"""
    return {mod: module_tables(app_root, mod) for mod in modules}
