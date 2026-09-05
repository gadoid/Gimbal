"""fin.account.query_balance —— fin 系统账户服务查询余额接口契约。"""""

from typing import Final

from gimbal_plate.systems.fin.system_info import (
    FIN_DEFAULT_AUTHOR,
    FIN_DEFAULT_MODULE,
    FIN_DEFAULT_OWNER,
    FIN_DEFAULT_PRIORITY,
    FIN_DEFAULT_TAGS,
    FIN_DEFAULT_VERSION,
    FIN_SYSTEM,
)
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    ResponseSpec,
    EndpointMetadata,
)
from gimbal_plate.systems.fin.models import QueryBalanceResponse

ACCOUNT_QUERY_BALANCE: Final[EndpointSpec] = EndpointSpec(
    id="fin.account.query_balance",
    system=FIN_SYSTEM,
    service="fin-service",
    name="查询账户余额",
    description="fin 账户服务查询指定账户的当前余额",
    api=ApiSpec(
        service="fin-service",
        method="GET",
        path="/api/v1/fin/account/balance",
        auth="bearer",
        timeout_seconds=5.0,
    ),
    responses={
        200: ResponseSpec.declare(QueryBalanceResponse, status=200, description='成功'),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
