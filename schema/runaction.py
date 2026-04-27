class WaitAction(BaseAction):
    type: Literal["wait"]
    
    duration_ms: int | None = None
    until_sql: str | None = None
    until_response: dict | None = None
    until_variable: dict | None = None
    
    timeout_ms: int = 30000
    interval_ms: int = 500
    params: dict = {}
    
    on_failure: Literal["abort", "continue", "ignore"] = "abort"
    
    @model_validator(mode="after")
    def check_mode(self):
        modes = [
            self.duration_ms is not None,
            self.until_sql is not None,
            self.until_response is not None,
            self.until_variable is not None,
        ]
        if sum(modes) != 1:
            raise ValueError("wait requires exactly one of: duration_ms / until_sql / until_response / until_variable")
        return self