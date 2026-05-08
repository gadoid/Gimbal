from pydantic import BaseModel,Field
from typing import Any, Optional, Literal , Union , Annotated, Dict
from .ref import RefBase

class RequestRef(RefBase) :
    kind : Literal["requestref"] = "requestref"

RequestUnion = Annotated[
    Union[Dict,RequestRef],
    Field(discriminator="kind")
]