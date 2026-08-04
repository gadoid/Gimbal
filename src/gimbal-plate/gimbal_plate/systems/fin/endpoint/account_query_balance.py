"""fin.account.query_balance —— fin 系统账户服务查询余额接口契约。"""""
from gimbal_plate.schema.endpoint import (
    ApiSpec,
    EndpointSpec,
    ResponseSpec,
)
from gimbal_plate.systems.fin.models import QueryBalanceResponse

ACCOUNT_QUERY_BALANCE = EndpointSpec(
    id="fin.account.query_balance",
    system="fin",
    service="account",
    name="查询账户余额",
    description="fin 账户服务查询指定账户的当前余额",
    api=ApiSpec(
        service="account",
        method="GET",
        path="/api/v1/fin/account/balance",
        auth="bearer",
        timeout_seconds=5.0,
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description="成功",
            model=QueryBalanceResponse,
        ),
    },
    version="1.0.0",
)
