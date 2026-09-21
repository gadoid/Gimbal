from pydantic import BaseModel
from typing import Literal

class Setup(BaseModel) :
    kind : Literal["setup"] = "setup"


SetupUnion = Setup


if __name__ == "__main__":
    # 测试 Setup 实例化
    setup = Setup()
    print(f"Setup 测试: kind={setup.kind}")
