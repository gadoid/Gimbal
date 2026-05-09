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
