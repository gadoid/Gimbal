"""platform.endpoint_catalog.get_by_endpoint_id_full —— Get Full Endpoint

`GET /api/endpoint-catalog/{endpoint_id}/full`

Proxy ``GET {plate}/api/endpoint/{id}/full``.

走 ``plate_client.get_endpoint_full`` —— 与 dispatch 侧**同一条缓存条目**,
故编辑器浏览与 dispatch 判定看到的是**同一份快照**(阶段二·① I)。超时随之
统一为那条软取的 3s(``DECLARED_PATHS_TIMEOUT_SEC``),不再是
``PLATE_TIMEOUT_SEC`` 的 30s。

返回 = plate 的 item **原样** + 一个后端算好的 ``declared_surface``:
声明侧可注入面的**扁平字符串集合**(归一化、容器前缀、模板形态全部展开)。
前端据此不再自己算声明半(§2.2)。item 另有消费者(候选树 UI),故**只增
字段、不裁 item**;展开成新 dict 而非就地改 —— 缓存里那份 item 是进程级
共享只读面(``EndpointFull.item`` 的契约)。

``declared_surface`` 为 ``None`` ⇒ 该端点的**声明面**不可解析(降级),前端
从严只认 body 面。**不用 [] 冒充**:空目录(真无声明,给 ``["$"]``)与降级
是两件事。契约 item 本身不可得时本路由直接 502/404,客户端看不到这个字段。

item 只要是 dict 就原样透传(**空 item ``{}`` 也算**):它得到一个空声明树
与 ``["$"]``,不视为错误 —— 不得用真值判等把 ``{}`` 并成 ``None``(§5)。

字段面由 gimbal-bootstrap 的 contract_gen 从平台 OpenAPI 生成。这个文件
**可以手改** —— 实测核订的语义（description / ui_kind / required）写在
这里，重新生成默认不覆盖；要覆盖用 --force。
"""

from typing import Final

from gimbal_plate.schema.endpoint import (
    ApiSpec,
    DeclarationEntry,
    EndpointMetadata,
    EndpointSpec,
    RequestSpec,
    ResponseSpec,
)
from gimbal_plate.systems.platform.system_info import (
    PLATFORM_DEFAULT_OWNER,
    PLATFORM_DEFAULT_TAGS,
    PLATFORM_DEFAULT_VERSION,
    PLATFORM_SERVICE,
    PLATFORM_SYSTEM,
)

ENDPOINT_CATALOG_GET_BY_ENDPOINT_ID_FULL: Final[EndpointSpec] = EndpointSpec(
    id="platform.endpoint_catalog.get_by_endpoint_id_full",
    system=PLATFORM_SYSTEM,
    service=PLATFORM_SERVICE,
    name="Get Full Endpoint",
    description="Proxy ``GET {plate}/api/endpoint/{id}/full``.\n\n走 ``plate_client.get_endpoint_full`` —— 与 dispatch 侧**同一条缓存条目**,\n故编辑器浏览与 dispatch 判定看到的是**同一份快照**(阶段二·① I)。超时随之\n统一为那条软取的 3s(``DECLARED_PATHS_TIMEOUT_SEC``),不再是\n``PLATE_TIMEOUT_SEC`` 的 30s。\n\n返回 = plate 的 item **原样** + 一个后端算好的 ``declared_surface``:\n声明侧可注入面的**扁平字符串集合**(归一化、容器前缀、模板形态全部展开)。\n前端据此不再自己算声明半(§2.2)。item 另有消费者(候选树 UI),故**只增\n字段、不裁 item**;展开成新 dict 而非就地改 —— 缓存里那份 item 是进程级\n共享只读面(``EndpointFull.item`` 的契约)。\n\n``declared_surface`` 为 ``None`` ⇒ 该端点的**声明面**不可解析(降级),前端\n从严只认 body 面。**不用 [] 冒充**:空目录(真无声明,给 ``[\"$\"]``)与降级\n是两件事。契约 item 本身不可得时本路由直接 502/404,客户端看不到这个字段。\n\nitem 只要是 dict 就原样透传(**空 item ``{}`` 也算**):它得到一个空声明树\n与 ``[\"$\"]``,不视为错误 —— 不得用真值判等把 ``{}`` 并成 ``None``(§5)。",
    api=ApiSpec(
        service=PLATFORM_SERVICE,
        method="GET",
        path="/api/endpoint-catalog/{endpoint_id}/full",
        auth="bearer",
        timeout_seconds=30.0,
    ),
    request=RequestSpec(
        body_type="none",
        declarations=[]
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="Successful Response",
            declarations=[]
        ),
    },
    version=PLATFORM_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module="endpoint-catalog",
        owner=PLATFORM_DEFAULT_OWNER,
        tags=list(PLATFORM_DEFAULT_TAGS),
    ),
)
