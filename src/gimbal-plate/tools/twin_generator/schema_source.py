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
