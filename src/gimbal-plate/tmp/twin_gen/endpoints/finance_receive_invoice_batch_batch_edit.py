"""fin.receive_invoice_batch.batch_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_fee_real_id, main_id, pay_settle_object_id, rate_type, customer_id, put_settle_object_id, invoice_form, invoice_type, receive_invoice_batch_id, put_settle_object, pay_settle_object, order_sub_id, pay_account_no, account_batch_name, create_time, account_simple_name, account_status, currency, create_id, receive_account_no, remark, bank_account, writeoff_name, writeoff_mode, pay_invoice_batch_id, finance_date, pay_date, service_project, fee_status, fee_type
溯源统计: column=69, 无zh=44, lang=19, frontend=15 | fe_high=102, enum=1
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

RECEIVE_INVOICE_BATCH_BATCH_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.receive_invoice_batch.batch_edit',
    system='fin',
    service='fin-service',
    name='操作',
    description='操作' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/finance/receiveInvoiceBatch/batchEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_fee_real_id', path=f'$.order_fee_real_id', type='integer', state='form', ui_kind='number', description='费用'),  # zh_ambiguous
            DeclarationEntry(name='style', path=f'$.style', type='integer', state='form', ui_kind='number', description='开票申请样式'),
            DeclarationEntry(name='apply_type', path=f'$.apply_type', type='integer', state='form', ui_kind='number', description='开票申请类型'),
            DeclarationEntry(name='main_id', path=f'$.main_id', type='integer', state='form', ui_kind='number', default='0', description='费用主体'),  # zh_ambiguous
            DeclarationEntry(name='pay_settle_object_id', path=f'$.pay_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='usd_file_id', path=f'$.usd_file_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='cny_file_id', path=f'$.cny_file_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='rate_type', path=f'$.rate_type', type='integer', state='carry', ui_kind='number', description='汇率类型'),  # zh_ambiguous
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='form', ui_kind='number', default='0', description='下单客户名称'),  # zh_ambiguous
            DeclarationEntry(name='put_settle_object_id', path=f'$.put_settle_object_id', type='integer', state='form', ui_kind='number', default='0', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='invoice_items', path=f'$.invoice_items', type='string', state='carry', ui_kind='text', description='发票项目'),
            DeclarationEntry(name='usd_is_turn', path=f'$.usd_is_turn', type='string', state='form', ui_kind='text', description='美金是否折币'),
            DeclarationEntry(name='invoice_form', path=f'$.invoice_form', type='string', state='carry', ui_kind='text', description='开票形式'),  # zh_ambiguous
            DeclarationEntry(name='invoice_type', path=f'$.invoice_type', type='string', state='carry', ui_kind='text', description='发票类型'),  # zh_ambiguous
            DeclarationEntry(name='invoice_rate_type', path=f'$.invoice_rate_type', type='string', state='carry', ui_kind='text', description='发票税率'),
            DeclarationEntry(name='cny_file', path=f'$.cny_file', type='string', state='carry', ui_kind='file'),
            DeclarationEntry(name='usd_file', path=f'$.usd_file', type='string', state='carry', ui_kind='file'),
            DeclarationEntry(name='debitno_file', path=f'$.debitno_file', type='string', state='carry', ui_kind='file'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='turn_rate', path=f'$.turn_rate', type='number', state='form', ui_kind='number', description='折币汇率'),
            DeclarationEntry(name='appoint_rate', path=f'$.appoint_rate', type='number', state='form', ui_kind='number', description='指定汇率'),
            DeclarationEntry(name='merge_with_cny', path=f'$.merge_with_cny', type='string', state='form', ui_kind='text', description='是否与人民币合并 1是 2否'),
            DeclarationEntry(name='selectRadio', path=f'$.selectRadio', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='receive_invoice_batch_id', path=f'$.receive_invoice_batch_id', type='integer', state='form', ui_kind='number', default='0', description='应收开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='batch_apply_name', path=f'$.batch_apply_name', type='string', state='carry', ui_kind='text', description='开票申请名称'),
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
            DeclarationEntry(name='usd_requiredn_invoice_title_type', path=f'$.usd_requiredn_invoice_title_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='apply_list', path=f'$.apply_list', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='put_settle_object', path=f'$.put_settle_object', type='string', state='carry', ui_kind='text', description='应收结算对象'),  # zh_ambiguous
            DeclarationEntry(name='main_name_cn', path=f'$.main_name_cn', type='string', state='carry', ui_kind='text', description='费用主体-全称'),
            DeclarationEntry(name='pay_settle_object', path=f'$.pay_settle_object', type='string', state='carry', ui_kind='text', description='应付结算对象'),  # zh_ambiguous
            DeclarationEntry(name='cost_usd', path=f'$.cost_usd', type='number', state='carry', ui_kind='number', description='费用金额（USD）'),
            DeclarationEntry(name='cost_cny', path=f'$.cost_cny', type='number', state='carry', ui_kind='number', description='费用金额（CNY）'),
            DeclarationEntry(name='order_sub_id', path=f'$.order_sub_id', type='integer', state='form', ui_kind='number', default='0', description='子订单ID'),  # zh_ambiguous
            DeclarationEntry(name='sys_rate', path=f'$.sys_rate', type='number', state='form', ui_kind='number', description='系统汇率'),
            DeclarationEntry(name='pay_account_no', path=f'$.pay_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='account_batch_name', path=f'$.account_batch_name', type='string', state='carry', ui_kind='text', description='对账批次名称'),  # needs_capture:value_source
            DeclarationEntry(name='bl_nos', path=f'$.bl_nos', type='string', state='carry', ui_kind='text', description='提单号批量'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='text', default='0', description='创建时间'),  # zh_ambiguous
            DeclarationEntry(name='account_simple_name', path=f'$.account_simple_name', type='string', state='carry', ui_kind='text', description='对账批次简称'),  # needs_capture:value_source
            DeclarationEntry(name='etd', path=f'$.etd', type='integer', state='form', ui_kind='text', default='0', description='预计开航（ETD）'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='form', ui_kind='text', default='0', description='实际开航（ATD）'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='integer', state='carry', ui_kind='select', default='0', description='对账轮次状态'),  # zh_ambiguous
            DeclarationEntry(name='batch_identity', path=f'$.batch_identity', type='string', state='carry', ui_kind='select', description='批次身份'),
            DeclarationEntry(name='main_batch_no', path=f'$.main_batch_no', type='string', state='carry', ui_kind='text', description='对账主批次ID'),
            DeclarationEntry(name='currency', path=f'$.currency', type='string', state='form', ui_kind='select', description='币制'),  # zh_ambiguous
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='select', default='0', description='创建人'),  # zh_ambiguous
            DeclarationEntry(name='account_by', path=f'$.account_by', type='integer', state='carry', ui_kind='select', description='对账完成人'),
            DeclarationEntry(name='account_time', path=f'$.account_time', type='integer', state='carry', ui_kind='text', description='对账完成时间'),
            DeclarationEntry(name='receive_account_no', path=f'$.receive_account_no', type='string', state='carry', ui_kind='text', description='对账批次ID'),  # needs_capture:value_source
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),  # zh_ambiguous
            DeclarationEntry(name='bank_account', path=f'$.bank_account', type='string', state='carry', ui_kind='text', description='银行账号'),  # zh_ambiguous
            DeclarationEntry(name='finance_id', path=f'$.finance_id', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='action', path=f'$.action', type='string', state='form', ui_kind='select', default='submit', description='操作', enum=['check', 'submit']),
            DeclarationEntry(name='audit_note', path=f'$.audit_note', type='string', state='form', ui_kind='text', description='审批人备注'),
            DeclarationEntry(name='writeoff_object', path=f'$.writeoff_object', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='writeoff_name', path=f'$.writeoff_name', type='string', state='carry', ui_kind='text', description='应收核销记录名称'),  # needs_capture:value_source
            DeclarationEntry(name='fee_match_type', path=f'$.fee_match_type', type='integer', state='carry', ui_kind='number', default='0', description='匹配费用方式 1系统自动对应 2手动选择对应'),
            DeclarationEntry(name='writeoff_type', path=f'$.writeoff_type', type='integer', state='carry', ui_kind='number', default='0', description='核销类型 1正常核销 2强制核销'),
            DeclarationEntry(name='writeoff_mode', path=f'$.writeoff_mode', type='string', state='carry', ui_kind='text', description='核销方式 按费用核销fee 按发票核销 invoice 按提单核销order'),  # needs_capture:value_source
            DeclarationEntry(name='un_writeoff_amount_usd_total', path=f'$.un_writeoff_amount_usd_total', type='number', state='carry', ui_kind='number', default='0.00', description='未核销金额(USD)总计'),
            DeclarationEntry(name='un_writeoff_amount_cny_total', path=f'$.un_writeoff_amount_cny_total', type='number', state='carry', ui_kind='number', default='0.00', description='未核销金额(CNY)总计'),
            DeclarationEntry(name='use_writeoff_amount_usd_total', path=f'$.use_writeoff_amount_usd_total', type='number', state='carry', ui_kind='number', default='0.00', description='已核销金额(USD)总计'),
            DeclarationEntry(name='use_writeoff_amount_cny_total', path=f'$.use_writeoff_amount_cny_total', type='number', state='carry', ui_kind='number', default='0.00', description='已核销金额(CNY)总计'),
            DeclarationEntry(name='pay_invoice_batch_id', path=f'$.pay_invoice_batch_id', type='integer', state='carry', ui_kind='number', default='0', description='应付开票批次ID'),  # zh_ambiguous
            DeclarationEntry(name='fee_currency', path=f'$.fee_currency', type='string', state='form', ui_kind='text', description='费用币制'),
            DeclarationEntry(name='finance_date', path=f'$.finance_date', type='integer', state='carry', ui_kind='number', default='0', description='财务日期'),  # zh_ambiguous
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='integer', state='carry', ui_kind='number', default='0', description='账期截转规则 1截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='customer_account', path=f'$.customer_account', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='supplier_account', path=f'$.supplier_account', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='service_item', path=f'$.service_item', type='string', state='carry', ui_kind='text', description='服务项目'),
            DeclarationEntry(name='pay_date', path=f'$.pay_date', type='integer', state='carry', ui_kind='number', default='0', description='应付日'),  # zh_ambiguous
            DeclarationEntry(name='take_date', path=f'$.take_date', type='integer', state='carry', ui_kind='number', default='0', description='应收日'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='form', ui_kind='number', description='服务策略ID'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='carry', ui_kind='text', description='政策类型'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='carry', ui_kind='text', description='作废原因'),
            DeclarationEntry(name='order_supplier_id', path=f'$.order_supplier_id', type='integer', state='form', ui_kind='number'),
            DeclarationEntry(name='modify_type', path=f'$.modify_type', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='service_project', path=f'$.service_project', type='string', state='form', ui_kind='text', description='服务项目'),  # zh_ambiguous
            DeclarationEntry(name='old_put_settle_object_id', path=f'$.old_put_settle_object_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='modify_pay_type', path=f'$.modify_pay_type', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='pay_currency', path=f'$.pay_currency', type='string', state='carry', ui_kind='text', description='应付金额币制'),
            DeclarationEntry(name='pay_service_project', path=f'$.pay_service_project', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='old_pay_settle_object_id', path=f'$.old_pay_settle_object_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='titleSlotOrder', path=f'$.titleSlotOrder', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='widthSlotOrder', path=f'$.widthSlotOrder', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='batchPreview', path=f'$.batchPreview', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='batch_type', path=f'$.batch_type', type='integer', state='form', ui_kind='number', description='选开票用按费用还是按提单'),
            DeclarationEntry(name='usd_require', path=f'$.usd_require', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='cny_require', path=f'$.cny_require', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='select_node_user', path=f'$.select_node_user', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='audit_msg', path=f'$.audit_msg', type='string', state='form', ui_kind='text', description='审批回显信息'),
            DeclarationEntry(name='batch_order_remark', path=f'$.batch_order_remark', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='flow_type', path=f'$.flow_type', type='string', state='form', ui_kind='text', description='审批流配置类型'),
            DeclarationEntry(name='relation_id', path=f'$.relation_id', type='integer', state='form', ui_kind='number', description='关联ID'),
            DeclarationEntry(name='fee_status', path=f'$.fee_status', type='integer', state='form', ui_kind='number', default='0', description='费用状态  0未锁定   1已锁定 2已作废 锁定后无法解锁不可修改'),  # zh_ambiguous
            DeclarationEntry(name='order_sub_customer_id', path=f'$.order_sub_customer_id', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='cost_ids', path=f'$.cost_ids', type='string', state='form', ui_kind='text'),
            DeclarationEntry(name='fee_type', path=f'$.fee_type', type='integer', state='form', ui_kind='number', default='0', description='费用类型 0标准费用 1特殊费用 2调节费用'),  # zh_ambiguous
            DeclarationEntry(name='receive_invoice_batch_no', path=f'$.receive_invoice_batch_no', type='string', state='carry', ui_kind='text', description='开票批次ID编号'),
            DeclarationEntry(name='receive_invoice_apply_id', path=f'$.receive_invoice_apply_id', type='string', state='carry', ui_kind='text', description='开票申请ID'),
            DeclarationEntry(name='receive_invoice_apply_no', path=f'$.receive_invoice_apply_no', type='string', state='carry', ui_kind='text', description='开票申请ID编号'),
            DeclarationEntry(name='batch_same_status', path=f'$.batch_same_status', type='integer', state='carry', ui_kind='number', description='是否有对向关联批次 0没有 1有'),
            DeclarationEntry(name='pay_invoice_batch_no', path=f'$.pay_invoice_batch_no', type='string', state='carry', ui_kind='text', description='应付开票批次编号'),
            DeclarationEntry(name='debit_note_id_no', path=f'$.debit_note_id_no', type='string', state='carry', ui_kind='textarea', description='Debit NoteID编号'),
            DeclarationEntry(name='batch_apply_simple', path=f'$.batch_apply_simple', type='string', state='carry', ui_kind='text', description='开票申请简称'),
            DeclarationEntry(name='invoice_rate', path=f'$.invoice_rate', type='integer', state='carry', ui_kind='number', description='发票税率'),
            DeclarationEntry(name='main_name', path=f'$.main_name', type='string', state='carry', ui_kind='text', description='费用主体'),
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='string', state='carry', ui_kind='text', description='对客订单主体id'),
            DeclarationEntry(name='customer_main_name', path=f'$.customer_main_name', type='string', state='carry', ui_kind='text', description='对客订单主体'),
            DeclarationEntry(name='business_main_id', path=f'$.business_main_id', type='string', state='carry', ui_kind='text', description='对商订单主体ID'),
            DeclarationEntry(name='business_main_name', path=f'$.business_main_name', type='string', state='carry', ui_kind='text', description='对商订单主体'),
            DeclarationEntry(name='book_supplier_id', path=f'$.book_supplier_id', type='string', state='carry', ui_kind='text', description='订舱供应商   关联sys_supplier表'),
            DeclarationEntry(name='book_supplier_name', path=f'$.book_supplier_name', type='string', state='carry', ui_kind='text', description='订舱供应商名称'),
            DeclarationEntry(name='turn_cost_usd', path=f'$.turn_cost_usd', type='number', state='carry', ui_kind='number', description='折币后金额合计（USD）'),
            DeclarationEntry(name='turn_cost_cny', path=f'$.turn_cost_cny', type='number', state='carry', ui_kind='number', description='折币后金额合计（CNY）'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
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
