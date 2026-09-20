"""fin.audit.audit_invoice_batch_export —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): assign_no, assign_type, create_id, create_time, customer_id, main_id, receive_account_no, account_batch_name, supplier_id, cancel_remark
溯源统计: frontend=37, column=11, lang=3, 无zh=3, derived=2 | fe_high=40, enum=0
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

AUDIT_AUDIT_INVOICE_BATCH_EXPORT: Final[EndpointSpec] = EndpointSpec(
    id='fin.audit.audit_invoice_batch_export',
    system='fin',
    service='fin-service',
    name='Audit.auditInvoiceBatchExport',
    description='Audit.auditInvoiceBatchExport' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/home/audit/auditInvoiceBatchExport',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='assign_no', path=f'$.assign_no', type='string', state='carry', ui_kind='text', description='任务编号'),  # needs_capture:value_source
            DeclarationEntry(name='assign_type', path=f'$.assign_type', type='string', state='carry', ui_kind='select', description='任务类型'),  # needs_capture:value_source
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='form', ui_kind='select', default='0', description='发起人'),  # zh_ambiguous
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='发起时间'),  # zh_ambiguous
            DeclarationEntry(name='executor_id', path=f'$.executor_id', type='integer', state='carry', ui_kind='select', default='0', description='处理人'),
            DeclarationEntry(name='executor_time', path=f'$.executor_time', type='integer', state='carry', ui_kind='text', default='0', description='处理时间'),
            DeclarationEntry(name='audit_no', path=f'$.audit_no', type='string', state='form', ui_kind='text', description='审批编号'),
            DeclarationEntry(name='audit_type', path=f'$.audit_type', type='string', state='form', ui_kind='select', description='审批类型'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='form', ui_kind='select', default='1', description='审核状态'),
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='form', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='select', default='0', description='关联身份'),
            DeclarationEntry(name='link_apply_no', path=f'$.link_apply_no', type='string', state='carry', ui_kind='text', description='关联对向申请ID'),
            DeclarationEntry(name='link_audit_status', path=f'$.link_audit_status', type='integer', state='carry', ui_kind='select', default='0', description='关联应收审核状态'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='text', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='select', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='select', description='币制'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='string', state='carry', ui_kind='select', description='批次状态'),
            DeclarationEntry(name='expedite_status', path=f'$.expedite_status', type='integer', state='form', ui_kind='select', default='0', description='催办状态'),
            DeclarationEntry(name='executor', path=f'$.executor', type='string', state='carry', ui_kind='select', description='处理人'),
            DeclarationEntry(name='execute_time', path=f'$.execute_time', type='string', state='carry', ui_kind='text', description='处理时间'),
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID'),
            DeclarationEntry(name='receive_account_no', path=f'$.receive_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='account_batch_name', path=f'$.account_batch_name', type='string', state='carry', ui_kind='text', description='对账批次名称'),  # needs_capture:value_source
            DeclarationEntry(name='etd', path=f'$.etd', type='string', state='carry', ui_kind='text', description='预计开航（ETD）'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='carry', ui_kind='text', default='0', description='实际开航（ATD）'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='select', default='0', description='应收结算对象'),
            DeclarationEntry(name='batch_identity', path=f'$.batch_identity', type='string', state='carry', ui_kind='select', description='批次身份'),
            DeclarationEntry(name='main_batch_no', path=f'$.main_batch_no', type='string', state='carry', ui_kind='text', description='对账主批次ID'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='integer', state='carry', ui_kind='select', default='0', description='对账轮次状态'),
            DeclarationEntry(name='account_by', path=f'$.account_by', type='integer', state='carry', ui_kind='select', description='对账完成人'),
            DeclarationEntry(name='account_time', path=f'$.account_time', type='integer', state='carry', ui_kind='text', description='对账完成时间'),
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID'),
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='select', description='开票申请状态'),
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='link_batch_no', path=f'$.link_batch_no', type='string', state='carry', ui_kind='text', description='关联对向批次ID'),
            DeclarationEntry(name='invoice_status', path=f'$.invoice_status', type='integer', state='carry', ui_kind='select', default='0', description='登记状态'),
            DeclarationEntry(name='invoice_no', path=f'$.invoice_no', type='string', state='carry', ui_kind='text', description='关联发票号'),
            DeclarationEntry(name='writeoff_status', path=f'$.writeoff_status', type='integer', state='carry', ui_kind='select', default='1', description='核销状态'),
            DeclarationEntry(name='active_tab', path=f'$.active_tab', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='is_all', path=f'$.is_all', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='create_time_start', path=f'$.create_time_start', type='string', state='form', ui_kind='text', description='发起时间开始'),
            DeclarationEntry(name='create_time_end', path=f'$.create_time_end', type='string', state='form', ui_kind='text', description='发起时间结束'),
            DeclarationEntry(name='check_ids', path=f'$.check_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='supplier_id', path=f'$.supplier_id', type='integer', state='form', ui_kind='number', default='0', description='变更账期供应商ID'),  # zh_ambiguous
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='form', ui_kind='text', description='提单号'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='form', ui_kind='text', description='撤销描述'),  # zh_ambiguous
            DeclarationEntry(name='invoice_batch_no', path=f'$.invoice_batch_no', type='string', state='form', ui_kind='text', description='开票批次编号'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应收结算对象ID'),
            DeclarationEntry(name='invoice_apply_currency', path=f'$.invoice_apply_currency', type='string', state='form', ui_kind='text', description='开票申请币制'),
            DeclarationEntry(name='writeoff_no', path=f'$.writeoff_no', type='string', state='form', ui_kind='text', description='应收核销记录编号'),
            DeclarationEntry(name='pay_demand_no', path=f'$.pay_demand_no', type='string', state='form', ui_kind='text', description='付款需求编号'),
            DeclarationEntry(name='account_no', path=f'$.account_no', type='string', state='form', ui_kind='text', description='对账批次编号'),
            DeclarationEntry(name='source_type', path=f'$.source_type', type='integer', state='form', ui_kind='number', default='1', description='来源类型(应收批次)1自主创建 2应付联动发起(0910)'),
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
