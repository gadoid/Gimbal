from pydantic import BaseModel,Field
from typing import Any, Optional, Literal , Union , Annotated
from .ref import RefBase

class Api(BaseModel) :
    kind : Literal["api"] = "api"
    service : str 
    method : Literal["GET","POST","PUT","DELETE","PATCH"]
    path : str
    headers : dict[str, str] = Field(default_factory=dict,description="头信息字典")
    timeout : float = 30

class ApiRef(RefBase) :
    kind : Literal["api_ref"] = "api_ref"

ApiUnion = Annotated[
    Union[Api, ApiRef],
    Field(discriminator = "kind"),
]


if __name__ == "__main__":
    # 测试 Api 实例化
    api = Api(
        service="user-service",
        method="GET",
        path="/api/users/{id}"
    )
    print(f"Api 测试: service={api.service}, method={api.method}, path={api.path}")

    # 测试 ApiRef 实例化
    api_ref = ApiRef(ref="api_ref_1")
    print(f"ApiRef 测试: ref={api_ref.ref}")

