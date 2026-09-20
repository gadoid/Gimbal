"""fin.pay_invoice_batch.apply_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): pay_invoice_apply_id, invoice_form, invoice_type, currency, amount_total_usd, amount_total_cny, turn_amount_total_cny, turn_amount_total_usd, bank_account, invoice_rate, remark, dn_invoice_title_type, rate_type
溯源统计: column=65, 无zh=24, lang=20 | fe_high=52, enum=0
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

PAY_INVOICE_BATCH_APPLY_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.pay_invoice_batch.apply_edit',
    system='fin',
    service='fin-service',
    name='PayInvoiceBatch.applyEdit',
    description='PayInvoiceBatch.applyEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/payInvoiceBatch/applyEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='pay_invoice_apply_id', path=f'$.pay_invoice_apply_id', type='integer', state='form', ui_kind='number', required=True, default='0', description='应付开票申请ID'),  # zh_ambiguous
            DeclarationEntry(name='rate', path=f'$.rate', type='number', state='form', ui_kind='number', description='汇率'),
            DeclarationEntry(name='invoice_apply_simple', path=f'$.invoice_apply_simple', type='string', state='form', ui_kind='text', description='开票申请简称'),
            DeclarationEntry(name='invoice_form', path=f'$.invoice_form', type='string', state='form', ui_kind='text', required=True, description='开票形式'),  # zh_ambiguous
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='string', state='form', ui_kind='text', required=True, description='发票类型'),  # zh_ambiguous
            DeclarationEntry(name='seller_id', path=f'$.seller_id', type='integer', state='form', ui_kind='number', required=True, description='销售方ID'),
            DeclarationEntry(name='seller_name', path=f'$.seller_name', type='string', state='form', ui_kind='text', required=True, description='销售方名称'),
            DeclarationEntry(name='rate_list', path=f'$.rate_list', type='string', state='form', ui_kind='text', required=True, description='发票项目与税率'),
            DeclarationEntry(name='truck_remark', path=f'$.truck_remark', type='string', state='form', ui_kind='text', description='拖车费/运费其他备注内容'),
            DeclarationEntry(name='require_other', path=f'$.require_other', type='string', state='form', ui_kind='text', description='其他开票要求'),
            DeclarationEntry(name='file_list', path=f'$.file_list', type='string', state='form', ui_kind='text', description='上传附件'),
            DeclarationEntry(name='fast_remark', path=f'$.fast_remark', type='string', state='form', ui_kind='text', description='快速备注'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='carry', ui_kind='text', description='币值  '),  # zh_ambiguous
            DeclarationEntry(name='amount_total_usd', path=f'$.amount_total_usd', type='number', state='carry', ui_kind='number', description='金额-美金'),  # zh_ambiguous
            DeclarationEntry(name='amount_total_cny', path=f'$.amount_total_cny', type='number', state='carry', ui_kind='number', description='金额-人民币'),  # zh_ambiguous
            DeclarationEntry(name='turn_amount_total_cny', path=f'$.turn_amount_total_cny', type='number', state='carry', ui_kind='number', description='折币-金额-人民币'),  # zh_ambiguous
            DeclarationEntry(name='turn_amount_total_usd', path=f'$.turn_amount_total_usd', type='number', state='carry', ui_kind='number', description='折币-金额-美金'),  # zh_ambiguous
            DeclarationEntry(name='turn_amount_total', path=f'$.turn_amount_total', type='number', state='carry', ui_kind='number', description='开票申请金额,折币金额合计'),
            DeclarationEntry(name='invoice_apply_name', path=f'$.invoice_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='purchaser_id', path=f'$.purchaser_id', type='integer', state='carry', ui_kind='number', description='购买方ID'),
            DeclarationEntry(name='purchaser_head_cn', path=f'$.purchaser_head_cn', type='string', state='carry', ui_kind='text', description='购买方中文抬头'),
            DeclarationEntry(name='purchaser_tax_number', path=f'$.purchaser_tax_number', type='string', state='carry', ui_kind='text', description='购买方纳税人识别号'),
            DeclarationEntry(name='bank_account', path=f'$.bank_account', type='string', state='carry', ui_kind='text', description='银行账号'),  # zh_ambiguous
            DeclarationEntry(name='seller_info', path=f'$.seller_info', type='string', state='form', ui_kind='textarea', description='销售方信息'),
            DeclarationEntry(name='invoice_items', path=f'$.invoice_items', type='string', state='carry', ui_kind='text', description='发票项目'),
            DeclarationEntry(name='invoice_rate_type', path=f'$.invoice_rate_type', type='string', state='form', ui_kind='text', description='发票税率'),
            DeclarationEntry(name='invoice_rate', path=f'$.invoice_rate', type='integer', state='form', ui_kind='number', description='发票税率'),  # zh_ambiguous
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),  # zh_ambiguous
            DeclarationEntry(name='dn_invoice_title_type', path=f'$.dn_invoice_title_type', type='integer', state='carry', ui_kind='number', default='0', description='Debit Note标题类型 0 DEBIT NOTE 1 INVOICE'),  # zh_ambiguous
            DeclarationEntry(name='usd_file_id', path=f'$.usd_file_id', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_file_id', path=f'$.cny_file_id', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='debitno_file_id', path=f'$.debitno_file_id', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='batch_order_remark', path=f'$.batch_order_remark', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='trade_terms', path=f'$.trade_terms', type='string', state='carry', ui_kind='text', description='贸易条款'),
            DeclarationEntry(name='purchaser_name', path=f'$.purchaser_name', type='string', state='carry', ui_kind='text', description='购买方名称'),
            DeclarationEntry(name='usd_requireinvoice_form', path=f'$.usd_requireinvoice_form', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireinvoice_type', path=f'$.usd_requireinvoice_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requiretruck_remark', path=f'$.usd_requiretruck_remark', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireinvoice_items_count', path=f'$.usd_requireinvoice_items_count', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireinvoice_items', path=f'$.usd_requireinvoice_items', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireinvoice_rate', path=f'$.usd_requireinvoice_rate', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireinvoice_rate_type', path=f'$.usd_requireinvoice_rate_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='usd_requireseller_name', path=f'$.usd_requireseller_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_form', path=f'$.cny_requireinvoice_form', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_type', path=f'$.cny_requireinvoice_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requiretruck_remark', path=f'$.cny_requiretruck_remark', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_items_count', path=f'$.cny_requireinvoice_items_count', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_items', path=f'$.cny_requireinvoice_items', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_rate', path=f'$.cny_requireinvoice_rate', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireinvoice_rate_type', path=f'$.cny_requireinvoice_rate_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='cny_requireseller_name', path=f'$.cny_requireseller_name', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='buyer_info', path=f'$.buyer_info', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='allchooselist', path=f'$.allchooselist', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='feeList', path=f'$.feeList', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='rate_type', path=f'$.rate_type', type='integer', state='form', ui_kind='number', description='汇率类型'),  # zh_ambiguous
            DeclarationEntry(name='pay_invoice_batch_id', path=f'$.pay_invoice_batch_id', type='string', state='carry', ui_kind='text', description='开票批次ID'),
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID编号'),
            DeclarationEntry(name='pay_invoice_apply_no', path=f'$.pay_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID编号'),
            DeclarationEntry(name='batch_same_status', path=f'$.batch_same_status', type='integer', state='carry', ui_kind='number', description='是否有对向关联批次 0没有 1有'),
            DeclarationEntry(name='receive_invoice_batch_id', path=f'$.receive_invoice_batch_id', type='integer', state='carry', ui_kind='number', description='应收开票批次ID'),
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='应收开票批次编号'),
            DeclarationEntry(name='debit_note_id_no', path=f'$.debit_note_id_no', type='string', state='carry', ui_kind='text', description='Debit NoteID编号'),
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
            DeclarationEntry(name='batch_apply_simple', path=f'$.batch_apply_simple', type='string', state='carry', ui_kind='text', description='开票申请简称'),
            DeclarationEntry(name='style', path=f'$.style', type='integer', state='carry', ui_kind='number', description='开票申请样式 1正式发票 2Debit Note'),
            DeclarationEntry(name='apply_type', path=f'$.apply_type', type='integer', state='carry', ui_kind='number', description='开票申请类型 1同一下单客户 2跨下单客户'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='string', state='carry', ui_kind='text', description='下单客户id'),
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='string', state='carry', ui_kind='text', description='应收结算对象ID'),
            DeclarationEntry(name='put_settle_object', path=f'$.put_settle_object', type='string', state='carry', ui_kind='text', description='应收结算对象'),
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='string', state='carry', ui_kind='text', description='应付结算对象ID'),
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='carry', ui_kind='text', description='应付结算对象名称'),
            DeclarationEntry(name='batch_type', path=f'$.batch_type', type='integer', state='carry', ui_kind='number', description='选中费用  1 按费用  2按提单'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='carry', ui_kind='number', description='费用主体ID'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='carry', ui_kind='text', description='费用主体'),
            DeclarationEntry(name='main_name_cn', path=f'$.main_name_cn', type='string', state='carry', ui_kind='text', description='费用主体-全称'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='string', state='carry', ui_kind='text', description='对客订单主体id'),
            DeclarationEntry(name='customer_main_name', path=f'$.customer_main_name', type='string', state='carry', ui_kind='text', description='对客订单主体'),
            DeclarationEntry(name='business_main_id', path=f'$.business_main_id', type='string', state='carry', ui_kind='text', description='对商订单主体ID'),
            DeclarationEntry(name='business_main_name', path=f'$.business_main_name', type='string', state='carry', ui_kind='text', description='对商订单主体'),
            DeclarationEntry(name='book_supplier_id', path=f'$.book_supplier_id', type='string', state='carry', ui_kind='text', description='订舱供应商   关联sys_supplier表'),
            DeclarationEntry(name='book_supplier_name', path=f'$.book_supplier_name', type='string', state='carry', ui_kind='text', description='订舱供应商名称'),
            DeclarationEntry(name='cost_usd', path=f'$.cost_usd', type='number', state='carry', ui_kind='number', description='费用金额（USD）'),
            DeclarationEntry(name='cost_cny', path=f'$.cost_cny', type='number', state='carry', ui_kind='number', description='费用金额（CNY）'),
            DeclarationEntry(name='turn_cost_usd', path=f'$.turn_cost_usd', type='number', state='carry', ui_kind='number', description='折币后金额合计（USD）'),
            DeclarationEntry(name='turn_cost_cny', path=f'$.turn_cost_cny', type='number', state='carry', ui_kind='number', description='折币后金额合计（CNY）'),
            DeclarationEntry(name='usd_is_turn', path=f'$.usd_is_turn', type='integer', state='carry', ui_kind='number', description='美金是否折币 1是 2否'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='integer', state='carry', ui_kind='number', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='turn_rate', path=f'$.turn_rate', type='number', state='carry', ui_kind='number', description='折币汇率'),
            DeclarationEntry(name='sys_rate', path=f'$.sys_rate', type='number', state='carry', ui_kind='number', description='系统汇率'),
            DeclarationEntry(name='appoint_rate', path=f'$.appoint_rate', type='number', state='carry', ui_kind='number', description='指定汇率'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人id'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人id'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='batch_status', path=f'$.batch_status', type='integer', state='carry', ui_kind='number', description='批次状态 1已生效 2已作废'),
            DeclarationEntry(name='audit_status', path=f'$.audit_status', type='integer', state='carry', ui_kind='number', description='审核状态 0无状态 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='cancel_status', path=f'$.cancel_status', type='integer', state='carry', ui_kind='number', description='作废状态'),
            DeclarationEntry(name='audit_id', path=f'$.audit_id', type='integer', state='carry', ui_kind='number', description='审核人ID'),
            DeclarationEntry(name='audit_by', path=f'$.audit_by', type='string', state='carry', ui_kind='text', description='审核人名称'),
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='carry', ui_kind='textarea', description='提单号'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='link_apply_nos', path=f'$.link_apply_nos', type='string', state='carry', ui_kind='text', description='关联对向申请编号,与link_apply_ids按位对应'),
            DeclarationEntry(name='link_role', path=f'$.link_role', type='integer', state='carry', ui_kind='number', description='关联身份 0无 1发起方 2被关联方'),
            DeclarationEntry(name='link_apply_ids', path=f'$.link_apply_ids', type='string', state='carry', ui_kind='text', description='关联对向申请ID,历史数据多个逗号拼接,新链路一对一'),
            DeclarationEntry(name='link_audit_status', path=f'$.link_audit_status', type='integer', state='carry', ui_kind='number', description='关联应收审核状态,应付批次用,同步对向应收批次审核状态 0无 1审核中 2审核通过 3审核驳回 4审核撤销'),
            DeclarationEntry(name='source_type', path=f'$.source_type', type='integer', state='carry', ui_kind='number', description='来源类型,应收批次用 1自主创建 2应付联动发起'),
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
