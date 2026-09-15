"""fin.track.receive_track —— 孪生生成器产物(请求面;行为面归场景用例)。

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

TRACK_RECEIVE_TRACK: Final[EndpointSpec] = EndpointSpec(
    id='fin.track.receive_track',
    system='fin',
    service='fin-service',
    name='Track.receiveTrack',
    description='Track.receiveTrack' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/api/track/receiveTrack',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='keyid', path=f'$.keyid', type='string', state='form'),
            DeclarationEntry(name='nodes', path=f'$.nodes', type='string', state='form'),
            DeclarationEntry(name='mapUrl', path=f'$.mapUrl', type='string', state='form'),
            DeclarationEntry(name='track_id', path=f'$.track_id', type='integer', state='form', default='0', description='订阅id'),
            DeclarationEntry(name='reference_no', path=f'$.reference_no', type='string', state='form', description='订阅号 提单号'),
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='form', default='0', description='业务订单ID'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='form', description='承运人'),
            DeclarationEntry(name='endStatus', path=f'$.endStatus', type='string', state='form'),
            DeclarationEntry(name='trackStatus', path=f'$.trackStatus', type='string', state='form'),
            DeclarationEntry(name='dlptTime', path=f'$.dlptTime', type='string', state='form'),
            DeclarationEntry(name='vesselName', path=f'$.vesselName', type='string', state='form'),
            DeclarationEntry(name='voyage', path=f'$.voyage', type='string', state='form', description='航次'),
            DeclarationEntry(name='eta', path=f'$.eta', type='integer', state='form', default='0', description='预计到达目的港时间'),
            DeclarationEntry(name='etd', path=f'$.etd', type='string', state='form'),
            DeclarationEntry(name='ata', path=f'$.ata', type='integer', state='form', default='0', description='实际抵达目的港时间'),
            DeclarationEntry(name='podCd', path=f'$.podCd', type='string', state='form'),
            DeclarationEntry(name='pod', path=f'$.pod', type='string', state='form', description='卸货港'),
            DeclarationEntry(name='deliveryAddress', path=f'$.deliveryAddress', type='string', state='form'),
            DeclarationEntry(name='firstETA', path=f'$.firstETA', type='string', state='form'),
            DeclarationEntry(name='etaPLD', path=f'$.etaPLD', type='string', state='form'),
            DeclarationEntry(name='ataPLD', path=f'$.ataPLD', type='string', state='form'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='form', default='0', description='状态 1未通知 2已通知'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='form', description='起运港'),
            DeclarationEntry(name='polCd', path=f'$.polCd', type='string', state='form'),
            DeclarationEntry(name='pld', path=f'$.pld', type='string', state='form', description='交货地名称'),
            DeclarationEntry(name='pldCd', path=f'$.pldCd', type='string', state='form'),
            DeclarationEntry(name='errorStatus', path=f'$.errorStatus', type='string', state='form'),
            DeclarationEntry(name='errorMessage', path=f'$.errorMessage', type='string', state='form'),
            DeclarationEntry(name='referenceCtnrNo', path=f'$.referenceCtnrNo', type='string', state='form'),
            DeclarationEntry(name='ctnrNo', path=f'$.ctnrNo', type='string', state='form'),
            DeclarationEntry(name='carrierCd', path=f'$.carrierCd', type='string', state='form'),
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
