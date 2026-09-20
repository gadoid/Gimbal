"""fin.king_dee.get_account_book_info —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): (无)
溯源统计: 无zh=4, column=4 | fe_high=0, enum=0
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

KING_DEE_GET_ACCOUNT_BOOK_INFO: Final[EndpointSpec] = EndpointSpec(
    id='fin.king_dee.get_account_book_info',
    system='fin',
    service='fin-service',
    name='KingDee.getAccountBookInfo',
    description='KingDee.getAccountBookInfo' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/kingDee/getAccountBookInfo',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='king_dee_id', path=f'$.king_dee_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='data_type', path=f'$.data_type', type='string', state='carry', ui_kind='text', description='数据类型customer 客户/supplier 供应商'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='carry', ui_kind='text', description='社会统一信用代码'),
            DeclarationEntry(name='king_dee_number', path=f'$.king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶编码'),
            DeclarationEntry(name='org_king_dee_number', path=f'$.org_king_dee_number', type='string', state='carry', ui_kind='text', description='金蝶编码（组织）'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='org_king_dee_id', path=f'$.org_king_dee_id', type='integer', state='carry', ui_kind='number'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
        ],
    ),
    responses={
        200: ResponseSpec(
            status=200,
            description='成功(信封统一;data 行形状归场景用例)',
            declarations=[
            DeclarationEntry(name='code', path='$.code', type='number',
                             required=False, ui_kind='number',
                             description='业务状态码(200=成功)', assertable=True),
            DeclarationEntry(name='msg', path='$.msg', type='string',
                             required=False, ui_kind='text',
                             description='业务提示信息', assertable=True),
            DeclarationEntry(name='data', path='$.data', type='object',
                             required=False, ui_kind='json',
                             description='业务数据(行形状归场景用例)', assertable=True),
            DeclarationEntry(name='request_id', path='$.request_id', type='string',
                             required=False, ui_kind='text',
                             description='请求追踪ID', assertable=True),

            ],
        ),
    },
    version=FIN_DEFAULT_VERSION,
    metadata=EndpointMetadata(
        module=FIN_DEFAULT_MODULE,
        owner=FIN_DEFAULT_OWNER,
        tags=list(FIN_DEFAULT_TAGS),
    ),
)
