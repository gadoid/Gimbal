from pydantic import BaseModel,Field
from typing import Any, Optional, Literal , Union , Annotated
from .ref import RefBase

class Api(BaseModel) :
    service : str 
    method : Literal["GET","POST","PUT","DELETE","PATHCH"]
    path : str
    headers : dict[str, str] = Field(default_factory=dict,description="头信息字典")
    timeout : float = 30

class ApiRef(RefBase) :
    kind : Literal["apiref"] = "apiref"

ApiUnion = Annotated[
    Union[Api, ApiRef],
    Field(discriminator = "kind"),
]

