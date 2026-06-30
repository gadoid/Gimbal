"""``python -m Plate.api_doc`` 入口。

等价于 ``plate doc`` CLI,但不需要装包。
"""
from __future__ import annotations

from Plate.api_doc.cli import main

raise SystemExit(main())