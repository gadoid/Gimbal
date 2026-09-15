"""fin.production_finance.sync_supplier_user_account —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-15T11:13:18+00:00
needs_capture(首跑经 gimbal 执行回填): dlgt_mobile_no, status, id_no, id_no_type, name, add_time
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

PRODUCTION_FINANCE_SYNC_SUPPLIER_USER_ACCOUNT: Final[EndpointSpec] = EndpointSpec(
    id='fin.production_finance.sync_supplier_user_account',
    system='fin',
    service='fin-service',
    name='ProductionFinance.syncSupplierUserAccount',
    description='ProductionFinance.syncSupplierUserAccount' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/operation/productionFinance/syncSupplierUserAccount',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='dlgt_mobile_no', path=f'$.dlgt_mobile_no', type='string', state='carry', required=True, description='手机号'),  # needs_capture:value_source
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', required=True, default='0', description='状态 1未通知 2已通知', enum=['0', '1']),  # needs_capture:enum_required
            DeclarationEntry(name='id_no', path=f'$.id_no', type='string', state='carry', required=True, description='证件号'),  # needs_capture:value_source
            DeclarationEntry(name='id_no_type', path=f'$.id_no_type', type='integer', state='carry', required=True, default='10', description='证件类型  10身份证 11护照', enum=['10', '11']),  # needs_capture:enum_required
            DeclarationEntry(name='name', path=f'$.name', type='string', state='carry', required=True, description='姓名'),  # needs_capture:value_source
            DeclarationEntry(name='add_time', path=f'$.add_time', type='integer', state='carry', required=True),  # needs_capture:value_source
            DeclarationEntry(name='customer_source', path=f'$.customer_source', type='string', state='form', description='客商类型 01 外贸客户 02供应商'),
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
