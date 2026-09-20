"""S3.1:Lang 语言包解析 —— 字段 zh 的第二优先源。

ThinkPHP 3.2 机制(实探 D:\\fin-test):
- Common/Lang/zh-cn.php(525 条):按 `if ($controller == "xxx")` 分块,
  每块 `$lang = array('key' => '中文', ...)` 覆盖式赋值 —— 控制器只吃
  自己块的映射;前端 L('key') 渲染表格列/表单 label;
- <Module>/Lang/zh-cn.php(如 Operation,51 条):模块级直给,无分块,
  优先级高于 Common(ThinkPHP 模块 Lang 先查)。

值只收字符串:数组值(如 fee_afp_success 的分段文案)和行为消息
(LOGIN_SMS_ERROR 等)不是字段 zh —— 字段键均为小写下划线,重合概率
极低,不做额外过滤。

zh 合并链(s3_semantics):rule > lang > fe_form(high) > fe_label(medium)
> export_header > column(上下文选表) > derived。
"""
from __future__ import annotations

import re
from pathlib import Path

# 'key' => '中文'(双单引号任序;值必须纯字符串 —— 数组值不收)
_RE_PAIR = re.compile(
    r"['\"](\w+)['\"]\s*=>\s*['\"]([^'\"]+)['\"]\s*,")
# if / else if 条件块头(条件可含多个 $controller == "a" || ...)
_RE_IF = re.compile(r'if\s*\(([^)]*\$controller[^)]*)\)\s*\{')
_RE_COND_NAME = re.compile(r'\$controller\s*==\s*["\'](\w+)["\']')
_RE_LANG_ASSIGN = re.compile(r'\$lang\s*=\s*(?:array\(|\[)')
# 顶层块尾:行首缩进 + ] ; 或 ) ;(嵌套数组闭尾带逗号,不误触)
_RE_BLOCK_END = re.compile(r'\n\s*\];|\n\s*\);')


def _pairs(block: str) -> dict[str, str]:
    return {k: v for k, v in _RE_PAIR.findall(block)}


def _parse_common(s: str) -> dict[str, dict[str, str]]:
    """按 if/else if 控制器分块收对;一个块可服务多个控制器(||)。"""
    out: dict[str, dict[str, str]] = {}
    for m in _RE_IF.finditer(s):
        ctrls = [c.lower() for c in _RE_COND_NAME.findall(m.group(1))]
        if not ctrls:
            continue
        rest = s[m.end():]
        am = _RE_LANG_ASSIGN.search(rest)
        if not am:
            continue
        body = rest[am.end():]
        em = _RE_BLOCK_END.search(body)
        if em:
            body = body[:em.start()]
        pairs = _pairs(body)
        for c in ctrls:
            out.setdefault(c, {}).update(pairs)
    return out


def load_langs(app_root: Path) -> tuple[dict[str, dict[str, str]],
                                        dict[str, dict[str, str]]]:
    """→ (common_by_ctrl, module_langs)。

    common_by_ctrl:控制器名小写 → {key: zh}(Common/Lang/zh-cn.php 分块);
    module_langs:模块名 → {key: zh}(<Module>/Lang/zh-cn.php 直给)。
    """
    common_by_ctrl: dict[str, dict[str, str]] = {}
    f = app_root / "Common" / "Lang" / "zh-cn.php"
    if f.exists():
        common_by_ctrl = _parse_common(
            f.read_text(encoding="utf-8", errors="replace"))

    module_langs: dict[str, dict[str, str]] = {}
    for mf in sorted(app_root.glob("*/Lang/zh-cn.php")):
        mod = mf.parent.parent.name
        if mod == "Common":
            continue
        s = mf.read_text(encoding="utf-8", errors="replace")
        s = _RE_IF.sub("", s)      # 去 controller 分块头,余文直收
        module_langs[mod] = _pairs(s)
    return common_by_ctrl, module_langs


def lang_zh(controller: str, module: str,
            common_by_ctrl: dict[str, dict[str, str]],
            module_langs: dict[str, dict[str, str]]) -> dict[str, str]:
    """单端点的 Lang zh 视图(模块级覆盖 Common)。"""
    out: dict[str, str] = {}
    out.update(common_by_ctrl.get(controller.lower(), {}))
    out.update(module_langs.get(module, {}))
    return out


# T3.4:导出表头数组(private $xxxHeader = [...]; 类属性)
_RE_HEADER = re.compile(
    r"private\s+\$(\w*Header)\s*=\s*\[(?P<body>.*?)\n\s*\];", re.S)
_RE_HEADER_PAIR = re.compile(r"^\s*'(\w+)'\s*=>\s*'([^']+)'\s*,?\s*$", re.M)


def load_headers(app_root: Path) -> dict[str, dict[str, str]]:
    """扫全部 controller 的 private $xxxHeader 数组。

    → 控制器名小写 → {key: zh}。注释行(`// 'key' => ...`)天然不匹配
    行首引号锚定,被注释的表头不收。按 controller 全局消费(导出/列表
    同源,是字段 zh 的强语义源)。
    """
    out: dict[str, dict[str, str]] = {}
    for cf in sorted(app_root.glob("*/Controller/*.class.php")):
        ctrl = cf.name.replace("Controller.class.php", "").lower()
        s = cf.read_text(encoding="utf-8", errors="replace")
        for m in _RE_HEADER.finditer(s):
            out.setdefault(ctrl, {}).update(
                {k: v for k, v in _RE_HEADER_PAIR.findall(m.group("body"))})
    return out
