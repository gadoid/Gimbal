from pydantic import BaseModel,Field
from typing import Any, Optional, Literal , Union , Annotated, Dict
from .ref import RefBase

class Request(BaseModel) :
    kind : Literal["request"] = "request"
    body : dict[str, Any] = Field(default_factory=dict)

class RequestRef(RefBase) :
    kind : Literal["request_ref"] = "request_ref"

RequestUnion = Annotated[
    Union[Request,RequestRef],
    Field(discriminator="kind")
]