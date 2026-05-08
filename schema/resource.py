from pydantic import BaseModel, Field
from typing import Any , Literal , Annotated , Union

class Resource(BaseModel):
    """ 资源模型 """


class Mock(Resource):
    kind : Literal["mock"] = "mock"
    name : str = Field(description="mock服务名")
    image : str = Field(description="容器镜像")
    config : dict[str, Any] = Field(description="服务配置")
    portMapping : dict[int,int] = Field(description="端口映射")

class File(Resource):
    kind : Literal["fileref"] = "fileref"
    name : str = Field(description="文件资源名")
    path : str = Field(description="路径或ref")

ResourceUnion = Annotated[
    Union[Mock,File],
    Field(discriminator="kind")
]