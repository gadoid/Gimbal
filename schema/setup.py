from pydantic import BaseModel, Field 
from typing import Literal , Annotated, Union
from .ref import RefBase

class Setup(BaseModel) :
    kind : Literal["setup"] = "setup"


class SetupRef(RefBase) :
    kind : Literal["setup_ref"] = "setup_ref"


SetupUnion = Annotated[
    Union[Setup,SetupRef] ,
    Field(discriminator="kind")
]


if __name__ == "__main__":
    # 测试 Setup 实例化
    setup = Setup()
    print(f"Setup 测试: kind={setup.kind}")

    # 测试 SetupRef 实例化
    setup_ref = SetupRef(ref="setup_ref_1")
    print(f"SetupRef 测试: ref={setup_ref.ref}")
