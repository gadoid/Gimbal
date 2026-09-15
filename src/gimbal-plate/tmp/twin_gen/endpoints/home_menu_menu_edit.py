"""fin.menu.menu_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

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

MENU_MENU_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.menu.menu_edit',
    system='fin',
    service='fin-service',
    name='Menu.menuEdit',
    description='Menu.menuEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/menu/menuEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='menu_name', path=f'$.menu_name', type='string', state='form', required=True, description='菜单名称'),
            DeclarationEntry(name='order_num', path=f'$.order_num', type='integer', state='form', required=True, default='0', description='显示顺序'),
            DeclarationEntry(name='operator', path=f'$.operator', type='string', state='form'),
            DeclarationEntry(name='menu_id', path=f'$.menu_id', type='integer', state='form', description='菜单ID'),
            DeclarationEntry(name='parent_id', path=f'$.parent_id', type='integer', state='form', default='0', description='父菜单ID'),
            DeclarationEntry(name='path', path=f'$.path', type='string', state='form', description='路由地址'),
            DeclarationEntry(name='component', path=f'$.component', type='string', state='form', description='组件路径'),
            DeclarationEntry(name='is_frame', path=f'$.is_frame', type='integer', state='form', default='1', description='是否为外链（0是 1否）'),
            DeclarationEntry(name='is_cache', path=f'$.is_cache', type='integer', state='form', default='0', description='是否缓存（0缓存 1不缓存）'),
            DeclarationEntry(name='menu_type', path=f'$.menu_type', type='string', state='form', description='菜单类型（M目录 C菜单 F按钮）'),
            DeclarationEntry(name='visible', path=f'$.visible', type='string', state='form', default='0', description='菜单状态（0显示 1隐藏）'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='perms', path=f'$.perms', type='string', state='form', description='权限标识'),
            DeclarationEntry(name='icon', path=f'$.icon', type='string', state='form', default='#', description='菜单图标'),
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
