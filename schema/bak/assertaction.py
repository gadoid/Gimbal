class AssertRule(BaseModel):
    path: str | None = None
    op: str = "eq"
    expected: Any = None
    message: str | None = None

class AssertAction(BaseAction):
    type: Literal["assert"]
    
    target: Literal["response", "database", "variable", "request_outcome"]
    
    # 三种模式
    from_: str | None = Field(None, alias="from")
    rules: list[AssertRule] | None = None
    
    # 简单单条
    path: str | None = None
    op: str | None = None
    expected: Any = None
    
    # database 专用
    sql: str | None = None
    sql_from: str | None = None
    params: dict = {}
    
    # response 快捷断言
    status_code: int | dict | None = None
    time_ms: dict | None = None
    
    on_failure: Literal["abort", "continue", "ignore", "accumulate"] = "accumulate"
    
    @model_validator(mode="after")
    def check_mode(self):
        modes = [
            self.from_ is not None,
            self.rules is not None,
            self.path is not None or self.op is not None,
            self.status_code is not None or self.time_ms is not None,
        ]
        if not any(modes):
            raise ValueError(
                "assert requires one of: from / rules / (path+op+expected) / status_code|time_ms"
            )
        return self