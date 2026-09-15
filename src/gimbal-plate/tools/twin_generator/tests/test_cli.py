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
