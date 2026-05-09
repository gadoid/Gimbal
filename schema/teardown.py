from pydantic import BaseModel, Field 
from typing import Literal , Annotated, Union
from .ref import RefBase

class Teardown(BaseModel) :
    kind : Literal["teardown"] = "teardown"


class TeardownRef(RefBase) :
    kind : Literal["teardown_ref"] = "teardown_ref"



TeardownUnion = Annotated[
    Union[Teardown,TeardownRef] ,
    Field(discriminator="kind")
]


if __name__ == "__main__":
    # 测试 Teardown 实例化
    teardown = Teardown()
    print(f"Teardown 测试: kind={teardown.kind}")

    # 测试 TeardownRef 实例化
    teardown_ref = TeardownRef(ref="teardown_ref_1")
    print(f"TeardownRef 测试: ref={teardown_ref.ref}")
