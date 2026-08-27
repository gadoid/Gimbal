"""验证 IOFieldBinding 加载时归一 + platform 导出层二次归一。"""
import sys
sys.path.insert(0, r'd:/Gimbal/Gimbal/src/gimbal-plate')

from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding, RequestSpec, ResponseSpec
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec
from gimbal_plate.schema.endpoint.api_spec import ApiSpec
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata

ep = EndpointSpec(
    id='ep_order_add', system='fin', service='tidb-test-service',
    name='\u65b0\u5efa\u59d4\u6258\u8ba2\u8231\u5355', description='\u59d4\u6258\u8ba2\u8231\u5355\u7684\u65b0\u5efa/\u9a8c\u4ef7\u63a5\u53e3',
    api=ApiSpec(service='tidb-test-service', method='POST',
                path='/api/order/orderEntrust/orderAdd', timeout_seconds=30),
    version='1.0.0',
    metadata=EndpointMetadata(module='order', tags=['order','entrust'], owner='codfish', priority=1,
                             success_criteria='\u8fd4\u56deHTTP 200', business_notes='check/submit'),
    request=RequestSpec(body_type='json', schema_={}, fields=[
        IOFieldBinding(name='customer_id', path='customer_id', required=True,  ui_kind='text'),
        IOFieldBinding(name='bl_no',       path='bl_no',       required=True,  ui_kind='text',   source_kind='lookup'),
        IOFieldBinding(name='ship_name',   path='ship_name',   required=False, ui_kind='text'),
        IOFieldBinding(name='action',      path='action',      required=True,  ui_kind='select', enum=['check','submit']),
    ]),
    responses={200: ResponseSpec(status=200, fields=[
        IOFieldBinding(name='code',     path='code',          required=True,  ui_kind='number'),
        IOFieldBinding(name='message',  path='message',       required=False, ui_kind='text'),
        IOFieldBinding(name='order_id', path='$.data.order_id', required=False, ui_kind='text'),
    ], assertable_fields=['$.code','$.message','$.data.order_id'])},
)

d = ep.model_dump(mode='json', exclude_none=True)
print('=== request.fields[].path (\u6e90\u6570\u636e\u5168\u662f\u77ed\u540d) ===')
for f in d['request']['fields']:
    print('  {:18s} -> {}'.format(f['name'], f['path']))
print()
print('=== responses[200].fields[].path (\u6e90\u6570\u636e\u5168\u662f\u77ed\u540d) ===')
for f in d['responses']['200']['fields']:
    print('  {:18s} -> {}'.format(f['name'], f['path']))
print()
print('=== assertable_fields (\u539f\u672c\u5c31\u662f $.xxx) ===')
print(' ', d['responses']['200']['assertable_fields'])

# \u68c0\u67e5\u5168\u90e8 path \u90fd\u4ee5 $. \u9886\u5934
all_paths = []
for f in d['request']['fields']:
    all_paths.append(('req', f['name'], f['path']))
for f in d['responses']['200']['fields']:
    all_paths.append(('resp', f['name'], f['path']))
for p in d['responses']['200']['assertable_fields']:
    all_paths.append(('assert', '-', p))

bad = [(loc, name, p) for loc, name, p in all_paths if not p.startswith('$.')]
if bad:
    print('\nFAIL \u8fd8\u6709\u672a\u5f52\u4e00\u7684:', bad)
    sys.exit(1)
print('\nALL OK: \u6240\u6709 path \u90fd\u5df2\u5f52\u4e00\u4e3a $.xxx \u5f62\u6001')