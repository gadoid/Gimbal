from pydantic import BaseModel,Field
from typing import Any, Optional, Literal , Union , Annotated, Dict,List
from .ref import RefBase

class Request(BaseModel) :
    kind : Literal["request"] = "request"
    body : Union[Dict[str, Any], List[Any]] = Field(default_factory=dict)

class RequestRef(RefBase) :
    kind : Literal["request_ref"] = "request_ref"

RequestUnion = Annotated[
    Union[Request,RequestRef],
    Field(discriminator="kind")
]


if __name__ == "__main__":
    # 测试 Request 实例化
    request = Request(body={"userId": 123, "name": "test"})
    print(f"Request 测试: body={request.body}")

    # 测试 RequestRef 实例化
    request_ref = RequestRef(ref="request_ref_1")
    print(f"RequestRef 测试: ref={request_ref.ref}")