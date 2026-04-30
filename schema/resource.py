from pydantic import BaseModel, Field, model_validator,ConfigDict
from typing import Any, Optional
import re



class Resource(BaseModel):
    """ 资源模型 """
    mocks : list[MockSpec] = Field([], description= "mock服务声明")
    fixture : list[FixtureRef] = Field([], description= "数据夹具引用")
    files : list[Fileref] = Field([], description="文件资源")

class MockSpec(BaseModel):
    name : str = Field(description="mock服务名")
    image : str = Field(description="容器镜像")
    config : dict[str, Any] = Field(description="服务配置")
    portMapping : dict[int,int] = Field(description="端口映射")

class FixtureRef(BaseModel):
    name : str = Field(description= "夹具名" )
    source : str = Field(description= "夹具来源" )
    target : str = Field(description= "目标位置" ) 

class Fileref(BaseModel):
    name : str = Field(description="文件资源名")
    path : str = Field(description="路径或ref")
    