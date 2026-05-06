from typing import Literal, Any
from pydantic import Field, model_validator
from baseaction import BaseAction

class SqlAction(BaseAction):
    type: Literal["sql"]
    
    from_: str | None = Field(None, alias="from")
    inline: str | None = None
    inline_list: list[str] | None = None
    
    datasource: str = "default"
    params: dict = {}
    in_transaction: bool = False
    
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
    
    @model_validator(mode="after")
    def check_source_exclusive(self):
        sources = [self.from_, self.inline, self.inline_list]
        if sum(s is not None for s in sources) != 1:
            raise ValueError("sql action requires exactly one of: from / inline / inline_list")
        return self