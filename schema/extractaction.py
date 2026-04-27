class ExtractAction(BaseAction):
    type: Literal["extract"]
    
    key: str
    from_: Literal["response", "database", "variable"] = Field(alias="from")
    
    path: str | None = None
    sql: str | None = None
    sql_from: str | None = None
    expression: str | None = None
    params: dict = {}
    
    transform: str | None = None
    default: Any = None
    required: bool = True
    scope: Literal["scenario", "step"] = "scenario"
    
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
    
    @model_validator(mode="after")
    def check_source(self):
        rules = {
            "response": ["path"],
            "database": ["sql", "sql_from"],
            "variable": ["expression"],
        }
        required_fields = rules[self.from_]
        provided = [f for f in required_fields if getattr(self, f) is not None]
        if not provided:
            raise ValueError(
                f"extract from='{self.from_}' requires one of: {required_fields}"
            )
        return self