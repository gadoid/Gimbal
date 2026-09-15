"""fin.dict_type.dict_type_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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
            DeclarationEntry(name='dict_name', path=f'$.dict_name', type='string', state='form', required=True, description='字典名称'),
            DeclarationEntry(name='dict_type', path=f'$.dict_type', type='string', state='form', required=True, description='字典类型'),
            DeclarationEntry(name='show_style', path=f'$.show_style', type='string', state='form', required=True, default='list', description='展示状态  list 列表   tree 多级'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', description='备注'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form'),
            DeclarationEntry(name='dict_id', path=f'$.dict_id', type='integer', state='form', description='字典主键'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
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
