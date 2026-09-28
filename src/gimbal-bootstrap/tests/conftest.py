"""让测试能 import 仓内相邻的 gimbal_plate。

不 `pip install -e` —— 那会改用户环境。仓内相对路径足够，且契约验证本来
就该贴着这份 checkout 跑，而不是某个已安装的旧版本。
"""

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
for _p in (_REPO / "src" / "gimbal-plate",):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
