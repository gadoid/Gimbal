"""fin.exchange_rate.exchange_rate_add —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): exchange_rate_no, main_id, create_id, create_time, update_id, update_time
溯源统计: frontend=6, lang=5, 无zh=4, frontend_label=1, column=1 | fe_high=9, enum=1
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

EXCHANGE_RATE_EXCHANGE_RATE_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.exchange_rate.exchange_rate_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/exchangeRate/exchangeRateAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='month', path=f'$.month', type='string', state='form', ui_kind='text', description='汇率月份'),
            DeclarationEntry(name='original_currency', path=f'$.original_currency', type='string', state='form', ui_kind='select', description='原始币制'),
            DeclarationEntry(name='target_currency', path=f'$.target_currency', type='string', state='form', ui_kind='select', description='目标币制'),
            DeclarationEntry(name='exchange_rate', path=f'$.exchange_rate', type='number', state='form', ui_kind='number', default='0.0000', description='换算汇率'),
            DeclarationEntry(name='main_ids', path=f'$.main_ids', type='string', state='form', ui_kind='text', description='关联主体'),
            DeclarationEntry(name='exchange_rate_no', path=f'$.exchange_rate_no', type='string', state='carry', ui_kind='text', description='汇率ID'),  # needs_capture:value_source
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', ui_kind='select', default='0', description='关联主体'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='select', description='更新人'),  # zh_ambiguous
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='text', default='0', description='更新时间'),  # zh_ambiguous
            DeclarationEntry(name='exchange_rate_id', path=f'$.exchange_rate_id', type='integer', state='form', ui_kind='number', description='汇率ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='check', description='操作目的', enum=['check', 'submit']),
            DeclarationEntry(name='main_name_cn', path=f'$.main_name_cn', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text'),
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
