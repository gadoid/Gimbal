from pydantic import BaseModel, Field
from typing import Any , Literal , Annotated , Union

class Resource(BaseModel):
    """ 资源模型 """
    name: str = Field(..., description="资源名称")

class Mock(Resource):
    kind : Literal["mock"] = "mock"
    image : str = Field(description="容器镜像")
    config : dict[str, Any] = Field(description="服务配置")
    portMapping : dict[int,int] = Field(description="端口映射")

class File(Resource):
    kind : Literal["file"] = "file"
    path : str = Field(description="路径")

ResourceUnion = Annotated[
    Union[Mock,File],
    Field(discriminator="kind")
]


if __name__ == "__main__":
    # 测试 Resource 实例化
    resource = Resource(name="test_resource")
    print(f"Resource 测试: name={resource.name}")

    # 测试 Mock 实例化
    mock = Mock(
        name="test_mock",
        image="nginx:latest",
        config={"port": 80},
        portMapping={80: 8080}
    )
    print(f"Mock 测试: name={mock.name}, image={mock.image}")

    # 测试 File 实例化
    file = File(name="test_file", path="/tmp/test.txt")
    print(f"File 测试: name={file.name}, path={file.path}")