"""fin.dict_type.dict_type_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): status, create_time
溯源统计: column=6, frontend=4, 无zh=2 | fe_high=5, enum=0
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

DICT_TYPE_DICT_TYPE_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.dict_type.dict_type_edit',
    system='fin',
    service='fin-service',
    name='DictType.dictTypeEdit',
    description='DictType.dictTypeEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/dictType/dictTypeEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='dict_name', path=f'$.dict_name', type='string', state='form', ui_kind='text', description='字典名称'),
            DeclarationEntry(name='dict_type', path=f'$.dict_type', type='string', state='form', ui_kind='text', description='字典类型'),
            DeclarationEntry(name='show_style', path=f'$.show_style', type='string', state='form', ui_kind='text', default='list', description='展示状态  list 列表   tree 多级'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', ui_kind='text', description='备注'),
            DeclarationEntry(name='dict_id', path=f'$.dict_id', type='integer', state='form', ui_kind='number', description='字典主键'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', ui_kind='select', default='0', description='状态'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建者'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新者'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='string', state='carry', ui_kind='text', description='更新时间'),
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
