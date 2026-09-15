"""fin.relate.change_period_rule —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
"""
from typing import Final

from gimbal_plate.systems.fin.system_info import (
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
    DeclarationEntry,
    RequestSpec,
    ResponseSpec,
    EndpointMetadata,
    ValueSource,
)

RELATE_CHANGE_PERIOD_RULE: Final[EndpointSpec] = EndpointSpec(
    id='fin.relate.change_period_rule',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/customer/relate/changePeriodRule',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='check', description='操作目的'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='string', state='form', default='1', description='废弃 125日后订单截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='customer_relate_id', path=f'$.customer_relate_id', type='integer', state='form'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', description='审批回显信息'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', description='审批人备注'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', default='0', description='业务ID'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
