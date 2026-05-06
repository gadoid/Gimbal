class ChaosAction(BaseAction):
    type: Literal["chaos"]
    
    from_: str | None = Field(None, alias="from")
    inline: dict | None = None
    
    action: Literal["inject", "clear", "trigger"] = "inject"
    params: dict = {}
    
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
    
    @model_validator(mode="after")
    def check_source(self):
        if (self.from_ is None) == (self.inline is None):
            raise ValueError("chaos requires exactly one of: from / inline")
        return self