from pydantic import BaseModel, Field
from typing import  Literal


class RetryPolicy(BaseModel):
    """ 重试策略配置模型 """
    kind : Literal["retry_policy"] = "retry_policy"
    maxAttempts : int = Field(1,description= "最大尝试次数")
    backoffSeconds : float = Field(20, description= "退避基础时长")
    retryOn : list[str] = Field(default_factory= list ,description= "触发重试的条件标签") # 定义一组error code


