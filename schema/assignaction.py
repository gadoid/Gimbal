class AssignAction(BaseAction):
    type: Literal["assign"]
    
    target: Literal["body", "headers", "query", "path_params"]
    
    # 单字段模式
    path: str | None = None
    value: Any = None
    expression: str | None = None
    
    # 批量模式
    fields: dict | None = None
    
    merge_strategy: Literal["replace", "deep_merge"] = "replace"
    on_missing: Literal["create", "skip", "fail"] = "create"
    
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
    
    @model_validator(mode="after")
    def check_mode(self):
        single = self.path is not None
        batch = self.fields is not None
        if single == batch:  # 同时是 / 同时否 都不行
            raise ValueError("assign requires either (path + value/expression) or (fields)")
        if single:
            value_sources = [self.value is not None, self.expression is not None]
            if sum(value_sources) != 1:
                raise ValueError("single-field assign requires exactly one of: value / expression")
        return self