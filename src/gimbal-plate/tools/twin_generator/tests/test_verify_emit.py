"""T6.3 verify 子命令:import/唯一性/信封断言。"""
from pathlib import Path

from twin_generator.verify_emit import verify_dir


def test_verify_ok(tmp_path):
    from twin_generator.ir import ActionIR, FieldIR
    from twin_generator.s5_emit import render_endpoint
    act = ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")
    f = tmp_path / "order_entrust_order_add.py"
    f.write_text(render_endpoint(act, [FieldIR(key="action", zh="动作")],
                                 baseline="b"), encoding="utf-8")
    r = verify_dir(tmp_path)
    assert r["files"] == 1 and r["ok"] == 1 and r["errors"] == []


def test_verify_dup_and_envelope(tmp_path):
    from twin_generator.ir import ActionIR, FieldIR
    from twin_generator.s5_emit import render_endpoint
    act = ActionIR(module="Order", controller="OrderEntrust", action="orderAdd")
    src = render_endpoint(act, [FieldIR(key="action", zh="动作")], baseline="b")
    (tmp_path / "a.py").write_text(src, encoding="utf-8")
    # 同 id 同 path 第二份 → 撞车
    (tmp_path / "b.py").write_text(src, encoding="utf-8")
    # 信封破坏:assertable 摘掉
    (tmp_path / "c.py").write_text(
        src.replace("assertable=True", "assertable=False"), encoding="utf-8")
    r = verify_dir(tmp_path)
    assert r["files"] == 3 and r["ok"] == 1      # a.py 首现合法;b/c 报错
    files_with_err = {e["file"] for e in r["errors"]}
    assert {"b.py", "c.py"} == files_with_err
    b_errs = next(e for e in r["errors"] if e["file"] == "b.py")["errors"]
    assert any("id 重复" in s for s in b_errs)
    c_errs = next(e for e in r["errors"] if e["file"] == "c.py")["errors"]
    assert any("assertable" in s for s in c_errs)
