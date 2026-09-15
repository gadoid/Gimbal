"""共用:UTF-8 环境钉死 + sys.path 自举 + fixture 根路径。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# tools/ 入 path → 所有测试统一 `from twin_generator.xxx import ...`
# (模块内部是包相对导入 `from .php_ast import`,顶层裸名导入必炸)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

FIXTURES = Path(__file__).parent / "fixtures"
