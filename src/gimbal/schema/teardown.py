from pydantic import BaseModel
from typing import Literal

class Teardown(BaseModel) :
    kind : Literal["teardown"] = "teardown"


TeardownUnion = Teardown


if __name__ == "__main__":
    # 测试 Teardown 实例化
    teardown = Teardown()
    print(f"Teardown 测试: kind={teardown.kind}")
