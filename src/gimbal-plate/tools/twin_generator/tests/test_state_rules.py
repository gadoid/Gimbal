"""T0.2 回归钉:state 判据单一真源 —— S4 赋值与 S5 渲染不漂移。"""
from twin_generator.ir import FieldIR
from twin_generator.s4_state import assign
from twin_generator.state_rules import state_of


def _fields():
    return [
        FieldIR(key="a", read=True),
        FieldIR(key="b", read=False, required=True),
        FieldIR(key="c", read=False),
    ]


def test_state_of_read_maps_to_form():
    assert state_of(FieldIR(key="x", read=True)) == "form"
    assert state_of(FieldIR(key="x", read=False)) == "carry"


def test_s4_assign_agrees_with_state_of():
    fields = _fields()
    class _Act:
        id = "fin.x.y"
    assign({"fin.x.y": fields}, [_Act()], _catalog(), [])
    for f in fields:
        assert f.state == state_of(f)


def test_s5_render_reads_s4_state_only():
    """_render_state 不再复述 read 判据:裸 FieldIR(未跑 S4)用默认 carry。"""
    from twin_generator.s5_emit import _render_state
    f = FieldIR(key="x", read=True)          # 未跑 S4:state 仍是默认 carry
    assert _render_state(f) == "carry"


def _catalog():
    from twin_generator.schema_source import ColumnCatalog, ColumnInfo
    return ColumnCatalog([ColumnInfo(
        table="sys_x", column="zzz", col_type="varchar(32)",
        nullable=True, default=None, comment="")])
