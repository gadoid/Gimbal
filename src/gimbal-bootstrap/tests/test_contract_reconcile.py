"""契约 ↔ 实测响应对账。

契约是从 OpenAPI 生成的，真实响应是平台跑出来的 —— 两者会漂。生成器说
某个 path 可断言，不等于引擎真能在那个 path 上求到值。这道对账就是回答
「生成出来的声明，哪几条是真能用的」。

求值器必须是 **gimbal 自己的 JSONPath**：用例断言最终由引擎求值，对账
换个求值器，结论就不能用来判断断言能不能写。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from gimbal.utils.jsonpath import get  # noqa: E402

from gimbal_bootstrap.contract_reconcile import (  # noqa: E402
    instantiable_paths,
    reconcile,
    walk_response_paths,
)

LIST_DECLS = [
    {
        "name": "items",
        "path": "$.items",
        "type": "array",
        "assertable": True,
        "children": [
            {
                "name": "id",
                "path": "$.items.id",
                "type": "string",
                "assertable": True,
            },
            {
                "name": "meta",
                "path": "$.items.meta",
                "type": "object",
                "assertable": True,
                "children": [
                    {
                        "name": "name",
                        "path": "$.items.meta.name",
                        "type": "string",
                        "assertable": True,
                    }
                ],
            },
        ],
    },
    {"name": "total", "path": "$.total", "type": "integer", "assertable": True},
]


def test_array_children_instantiate_to_index_zero():
    """模板态 path 不带 [i]，但断言要能真的取到第一行。

    plate 目录里 children 必须是模板态（校验器硬性要求），实例下标本就是
    渲染器的事 —— 对账器就是那个渲染器。少了这一步，声明树写对了也断言不了。
    """
    paths = {p for p, _t, _empty in instantiable_paths(LIST_DECLS)}
    assert paths == {
        "$.items",
        "$.items[0].id",
        "$.items[0].meta",
        "$.items[0].meta.name",
        "$.total",
    }


def test_reconcile_separates_hits_from_misses():
    """声明有的、响应也有的 = 命中；声明有而响应没有 = 落空。

    落空不等于契约错（字段可选、query 参数没给会走另一条路），但它是
    「这条断言写下去会挂」的信号，必须被看见。
    """
    response = {"items": [{"id": "a1", "meta": {"name": "n1"}}], "total": 1}
    report = reconcile(LIST_DECLS, response)
    assert "$.items[0].id" in report.hits
    assert "$.items[0].meta.name" in report.hits
    assert report.misses == []


def test_reconcile_reports_a_declared_field_the_response_lacks():
    response = {"items": [{"id": "a1", "meta": {}}], "total": 1}
    report = reconcile(LIST_DECLS, response)
    assert report.misses == ["$.items[0].meta.name"]


def test_an_empty_array_is_not_a_miss():
    """空集合时行字段无从验证。

    把它算成落空，等于对每个带列表的端点报一堆假警报，警报一多就没人看了。
    """
    response = {"items": [], "total": 0}
    report = reconcile(LIST_DECLS, response)
    assert report.misses == []
    assert report.unverifiable, "空数组下的行字段应记为无法验证，而不是消失"


def test_a_response_that_is_itself_an_array_resolves_top_level_fields():
    """GET /api/data-sets 的响应就是数组。

    契约把元素字段提到顶层（path `$.id`），求值时得落到第一行上，否则
    每个字段都误判成落空 —— 而实际全都能取到。
    """
    decls = [
        {"name": "datasetId", "path": "$.datasetId", "type": "string",
         "assertable": True},
        {"name": "name", "path": "$.name", "type": "string", "assertable": True},
    ]
    report = reconcile(decls, [{"datasetId": "d1", "name": "ds"}])
    assert report.misses == []
    assert "$.datasetId" in report.hits


def test_reconcile_reports_response_fields_the_contract_never_declared():
    """反向：响应里有、契约没写的字段 —— 契约缺口。

    正向对账只能证明「写了的能用」，证明不了「该写的都写了」。这才是
    自举用例作者真正会踩的坑：字段明明在响应里，契约查不到。
    """
    response = {
        "items": [{"id": "a1", "meta": {"name": "n1"}, "surprise": 7}],
        "total": 1,
        "bonus": True,
    }
    report = reconcile(LIST_DECLS, response)
    assert "$.items[0].surprise" in report.undeclared
    assert "$.bonus" in report.undeclared


def test_keys_of_a_dynamic_map_are_not_reported_as_contract_gaps():
    """map 的键是运行时决定的，契约穷举不了。

    `ActivityOut.sources` 是 `additionalProperties: {type: boolean}` ——
    响应当初有 adaptations/executions/scenarios 三个域，将来有什么域
    取决于跑过什么。把它们报成"契约缺"，真正该说的"这个 map 声明了但键
    动态"反而被淹掉。
    """
    decls = [{"name": "sources", "path": "$.sources", "type": "object",
              "assertable": True}]
    report = reconcile(decls, {"sources": {"adaptations": True, "scenarios": False}})
    assert report.undeclared == []
    assert report.dynamic_keys == [
        "$.sources.adaptations",
        "$.sources.scenarios",
    ]


def test_a_declared_object_that_has_children_is_not_a_dynamic_map():
    """有 children 的 object 是**已建模**的：它下面的字段没声明就是真缺口。

    判据是「声明了自己没 children」还是「声明了 children」，不是「父路径
    在不在契约里」—— 后者会把 `$.items[0].meta.surprise` 也误判成动态键。
    """
    response = {"items": [{"id": "a1", "meta": {"name": "n1", "surprise": 7}}],
                "total": 1}
    report = reconcile(LIST_DECLS, response)
    assert report.undeclared == ["$.items[0].meta.surprise"]


def test_undelared_is_normalized_for_a_response_that_is_itself_an_array():
    """根数组响应的反向对账也要拆根下标，且不能切出 `$..`。

    `$[0].` 是 5 个字符 —— 按 4 切会留下一个孤零零的点，产出的
    `$..datasetId` 跟契约里的任何 path 都不匹配，于是每个字段都成了
    "契约缺"，报告直接失去意义。
    """
    decls = [
        {"name": "datasetId", "path": "$.datasetId", "type": "string",
         "assertable": True},
        {
            "name": "preview", "path": "$.preview", "type": "array",
            "assertable": True,
            "children": [
                {"name": "page_no", "path": "$.preview.page_no", "type": "integer",
                 "assertable": True},
            ],
        },
    ]
    response = [
        {"datasetId": "d1", "preview": [{"page_no": 1, "sort_order": "desc"}]},
    ]
    report = reconcile(decls, response)
    assert report.undeclared == ["$.preview[0].sort_order"]


def test_undelared_ignores_rows_beyond_the_first():
    """契约只对**首行**建模（children 模板态 + [0] 实例化）。

    响应有 11 行不等于契约缺 10 行 —— 不把下标折叠回首行，反向对账会
    报出 10 份一模一样的假缺口，噪音一大这份报告就没人看了。
    """
    response = {
        "items": [
            {"id": f"a{i}", "meta": {"name": f"n{i}"}} for i in range(11)
        ],
        "total": 11,
    }
    report = reconcile(LIST_DECLS, response)
    assert report.undeclared == []


def test_undelared_still_reports_a_field_missing_from_the_contract():
    response = {
        "items": [
            {"id": "a1", "meta": {"name": "n1"}, "surprise": 1},
            {"id": "a2", "meta": {"name": "n2"}, "surprise": 2},
        ],
        "total": 2,
    }
    report = reconcile(LIST_DECLS, response)
    assert report.undeclared == ["$.items[0].surprise"]


def test_undelared_ignores_elements_of_a_collection():
    """集合长度可变（tags 有 0..N 个），逐个元素算缺口是假警报。

    契约声明的是 `tags` 这个容器，不是它的第 1、2、3 个元素。
    """
    decls = [{"name": "tags", "path": "$.tags", "type": "array", "assertable": True}]
    report = reconcile(decls, {"tags": ["a", "b", "c"]})
    assert report.undeclared == []


def test_undelared_keeps_object_fields_that_sit_inside_a_collection():
    """`preview[0].page_no` 里的 page_no 是对象字段，不是集合元素 —— 要留下。"""
    decls = [
        {
            "name": "preview", "path": "$.preview", "type": "array",
            "assertable": True,
            "children": [
                {"name": "page_no", "path": "$.preview.page_no", "type": "integer",
                 "assertable": True},
            ],
        }
    ]
    response = {"preview": [{"page_no": 1, "extra": 9}]}
    report = reconcile(decls, response)
    assert report.undeclared == ["$.preview[0].extra"]


def test_walk_response_paths_reads_scalar_leaves_only():
    """叶子才值得对账：容器本身命中没意义（它总是存在）。"""
    doc = {"a": {"b": [1, 2]}, "c": "x"}
    assert set(walk_response_paths(doc)) == {"$.a.b[0]", "$.a.b[1]", "$.c"}


def test_reconcile_never_raises_on_a_path_the_engine_rejects():
    """对账器自己崩了，整份报告就没了 —— 比报告里有假警报更糟。

    实例化 path 由 name 沿树累积，name 带上 `x[bad]` 就拼出引擎不认的
    `$.x[bad]`，求值抛 JsonPathError。记成 unevaluable，继续往下走。
    """
    from gimbal.utils.jsonpath import JsonPathError  # noqa: PLC0415

    decls = [{"name": "x[bad]", "path": "$.x[bad]", "type": "string", "assertable": True}]
    with pytest.raises(JsonPathError):
        get({"x": 1}, "$.x[bad]")

    report = reconcile(decls, {"x": 1})
    assert report.misses == []
    assert report.unevaluable == ["$.x[bad]"]


@pytest.mark.parametrize("path", ["$.items[0].id", "$.total"])
def test_instantiated_paths_are_accepted_by_the_engine_evaluator(path):
    """展平后的 path 必须是引擎真认的形态。

    对账器和引擎用同一个求值器，这门保证的是「展平逻辑没把 path 拼坏」。
    """
    from gimbal.utils.jsonpath import get  # noqa: PLC0415

    doc = {"items": [{"id": "a1"}], "total": 1}
    assert get(doc, path) is not None
