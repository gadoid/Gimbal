"""fin.main.main_add —— 孪生生成器产物(请求面;行为面归场景用例)。

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

MAIN_MAIN_ADD: Final[EndpointSpec] = EndpointSpec(
    id='fin.main.main_add',
    system='fin',
    service='fin-service',
    name='操作目的',
    description='操作目的' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/main/mainAdd',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', default='0', description='费用主体ID'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', default='submit', description='操作目的'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='form', description='费用主体名称'),
            DeclarationEntry(name='main_name_cn', path=f'$.main_name_cn', type='string', state='form'),
            DeclarationEntry(name='main_name_en', path=f'$.main_name_en', type='string', state='form', description='主体英文名称'),
            DeclarationEntry(name='tax_number', path=f'$.tax_number', type='string', state='form', description='税号'),
            DeclarationEntry(name='enterprise_type', path=f'$.enterprise_type', type='integer', state='form', default='1', description='企业身份  1境内企业 2境外企业 3境外企业-港澳台企业 4境外企业-海外企业'),
            DeclarationEntry(name='identity', path=f'$.identity', type='string', state='form', description='身份'),
            DeclarationEntry(name='is_generate', path=f'$.is_generate', type='string', state='form', description='是否生成凭证 1是，0否'),
            DeclarationEntry(name='is_sync', path=f'$.is_sync', type='string', state='form', description='是否同步 1是，0否'),
            DeclarationEntry(name='simplified_code', path=f'$.simplified_code', type='string', state='form', description='简码'),
            DeclarationEntry(name='country_en_id', path=f'$.country_en_id', type='string', state='form', description='英文国家ID'),
            DeclarationEntry(name='country_en', path=f'$.country_en', type='string', state='form', description='英文国家名称'),
            DeclarationEntry(name='address_en', path=f'$.address_en', type='string', state='form'),
            DeclarationEntry(name='province_code', path=f'$.province_code', type='string', state='form'),
            DeclarationEntry(name='province_name', path=f'$.province_name', type='string', state='form'),
            DeclarationEntry(name='city_code', path=f'$.city_code', type='string', state='form'),
            DeclarationEntry(name='city_name', path=f'$.city_name', type='string', state='form'),
            DeclarationEntry(name='county_code', path=f'$.county_code', type='string', state='form'),
            DeclarationEntry(name='county_name', path=f'$.county_name', type='string', state='form'),
            DeclarationEntry(name='address_cn', path=f'$.address_cn', type='string', state='form'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='form', description='备注'),
            DeclarationEntry(name='curator_user_id', path=f'$.curator_user_id', type='string', state='form', description='主体负责人'),
            DeclarationEntry(name='contact_data', path=f'$.contact_data', type='string', state='form'),
            DeclarationEntry(name='finance_data', path=f'$.finance_data', type='string', state='form'),
            DeclarationEntry(name='bank_data', path=f'$.bank_data', type='string', state='form'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', default='0', description='服务策略ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', default='0', description='客户ID'),
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
