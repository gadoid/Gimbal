from pydantic import BaseModel,Field
from typing import Any, Literal, Union, Dict, List

class Request(BaseModel) :
    kind : Literal["request"] = "request"
    # body 支持三种形态：
    #   - str: 原始文本（text/xml、text/plain 等），由 api.headers.Content-Type 控制
    #   - dict: JSON 对象（application/json，httpx 兜底）
    #   - list: JSON 数组（批量请求等场景，application/json）
    # 阶段 1：仅放开 str 形态，Content-Type 仍由调用方在 api.headers 显式声明。
    # 阶段 2：将通过 RawRequest/JsonRequest/FormRequest 子类化把 Content-Type 责任内化进 schema。
    body : Union[str, Dict[str, Any], List[Any]] = Field(default_factory=dict)

RequestUnion = Request


if __name__ == "__main__":
    # 测试 Request 实例化
    request = Request(body={"userId": 123, "name": "test"})
    print(f"Request 测试: body={request.body}")