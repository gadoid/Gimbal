"""fin.order_fee.batch_pay_settle_object_edit —— 孪生生成器产物(请求面;行为面归场景用例)。

来源: 代码生成 | 基线: fin-test@2026-09-15 | 生成时间: 2026-09-20T04:38:13+00:00
needs_capture(首跑经 gimbal 执行回填): order_fee_real_id, order_id, customer_address_cn, customer_contact_name, customer_contact_phone, main_sort, pol_cn, pol_country, pol_country_cn, pod_cn, pot, pot_cn, del, del_cn, country_name, ocean_type, airline_type, terms_payment, terms_transport, terms_shipment, pay_type, customer_order_sn, packer, volume_desc, sea_trans_currency, shipper, consignee, notifier, ship_mark, commodity, notes, discount_rule, discount_ratio, discount_currency, fee_miss_name, effective_by, audit_type, customer_put_date_desc
溯源统计: column=190, rule=2, 无zh=2 | fe_high=0, enum=0
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

ORDER_FEE_BATCH_PAY_SETTLE_OBJECT_EDIT: Final[EndpointSpec] = EndpointSpec(
    id='fin.order_fee.batch_pay_settle_object_edit',
    system='fin',
    service='fin-service',
    name='OrderFee.batchPaySettleObjectEdit',
    description='OrderFee.batchPaySettleObjectEdit' + ' [generated:fin-test@2026-09-15]',
    api=ApiSpec(
        service='fin-service',
        method='POST',
        path='/api/order/orderFee/batchPaySettleObjectEdit',
        headers={},
        consumes=[],
        produces=[],
    ),
    request=RequestSpec(
        body_type='json',
        declarations=[
            DeclarationEntry(name='order_fee_real_id', path=f'$.order_fee_real_id', type='integer', state='carry', ui_kind='number', required=True, description='费用id'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='order_id', path=f'$.order_id', type='integer', state='carry', ui_kind='number', required=True, default='0', description='订单id'),  # zh_ambiguous, needs_capture:value_source
            DeclarationEntry(name='order_no', path=f'$.order_no', type='string', state='carry', ui_kind='text', description='业务订单ID'),
            DeclarationEntry(name='customer_id', path=f'$.customer_id', type='integer', state='carry', ui_kind='number', description='客户ID'),
            DeclarationEntry(name='customer_name', path=f'$.customer_name', type='string', state='carry', ui_kind='text', description='下单客户名称'),
            DeclarationEntry(name='customer_category', path=f'$.customer_category', type='string', state='carry', ui_kind='text', description='客户分类'),
            DeclarationEntry(name='customer_tax_number', path=f'$.customer_tax_number', type='string', state='carry', ui_kind='text', description='客户社会信用代码'),
            DeclarationEntry(name='customer_address_cn', path=f'$.customer_address_cn', type='string', state='carry', ui_kind='text', description='客户中文地址'),  # needs_capture:value_source
            DeclarationEntry(name='sale_id', path=f'$.sale_id', type='integer', state='carry', ui_kind='number', description='销售ID  关联sys_user'),
            DeclarationEntry(name='sale_name', path=f'$.sale_name', type='string', state='carry', ui_kind='text', description='销售名字'),
            DeclarationEntry(name='service_id', path=f'$.service_id', type='integer', state='carry', ui_kind='number', description='客服ID  关联sys_user'),
            DeclarationEntry(name='client_expand_id', path=f'$.client_expand_id', type='integer', state='carry', ui_kind='number', description='直客拓展用户id'),
            DeclarationEntry(name='client_expand_name', path=f'$.client_expand_name', type='string', state='carry', ui_kind='text', description='直客拓展用户名称'),
            DeclarationEntry(name='service_name', path=f'$.service_name', type='string', state='carry', ui_kind='text', description='客服名字'),
            DeclarationEntry(name='operator_id', path=f'$.operator_id', type='integer', state='carry', ui_kind='number', description='操作ID'),
            DeclarationEntry(name='operator_name', path=f'$.operator_name', type='string', state='carry', ui_kind='text', description='操作名字'),
            DeclarationEntry(name='customer_contact_id', path=f'$.customer_contact_id', type='integer', state='carry', ui_kind='number', description='客户联系人ID'),
            DeclarationEntry(name='customer_contact_name', path=f'$.customer_contact_name', type='string', state='carry', ui_kind='text', description='客户联系人名字'),  # needs_capture:value_source
            DeclarationEntry(name='customer_contact_phone', path=f'$.customer_contact_phone', type='string', state='carry', ui_kind='text', description='客户联系人电话'),  # needs_capture:value_source
            DeclarationEntry(name='customer_main_id', path=f'$.customer_main_id', type='integer', state='carry', ui_kind='number', description='对客主体  sys_main 外键'),
            DeclarationEntry(name='customer_main_name', path=f'$.customer_main_name', type='string', state='carry', ui_kind='text', description='对客主体名称'),
            DeclarationEntry(name='business_main_id', path=f'$.business_main_id', type='integer', state='carry', ui_kind='number', description='对商主体  sys_main 外键'),
            DeclarationEntry(name='business_main_name', path=f'$.business_main_name', type='string', state='carry', ui_kind='text', description='对商主体名称'),
            DeclarationEntry(name='main_sort', path=f'$.main_sort', type='string', state='carry', ui_kind='text', description='主体顺序'),  # needs_capture:value_source
            DeclarationEntry(name='bl_no', path=f'$.bl_no', type='string', state='carry', ui_kind='text', description='提单号'),
            DeclarationEntry(name='policy_type', path=f'$.policy_type', type='string', state='carry', ui_kind='text', description='政策类型'),
            DeclarationEntry(name='fund_code', path=f'$.fund_code', type='string', state='carry', ui_kind='text', description='资方代码'),
            DeclarationEntry(name='fund_name', path=f'$.fund_name', type='string', state='carry', ui_kind='text', description='资方名称'),
            DeclarationEntry(name='policy_id', path=f'$.policy_id', type='integer', state='carry', ui_kind='number', description='服务策略ID'),
            DeclarationEntry(name='policy_name', path=f'$.policy_name', type='string', state='carry', ui_kind='text', description='服务策略名称'),
            DeclarationEntry(name='business_type', path=f'$.business_type', type='string', state='carry', ui_kind='text', description='业务类型'),
            DeclarationEntry(name='trade_term', path=f'$.trade_term', type='string', state='carry', ui_kind='text', description='成交方式'),
            DeclarationEntry(name='carrier_id', path=f'$.carrier_id', type='integer', state='carry', ui_kind='number', description='船公司  / 承运人ID'),
            DeclarationEntry(name='carrier', path=f'$.carrier', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='etd', path=f'$.etd', type='integer', state='carry', ui_kind='number', description='预计开航日'),
            DeclarationEntry(name='atd', path=f'$.atd', type='integer', state='carry', ui_kind='number', description='实际开航日'),
            DeclarationEntry(name='track_bl_no', path=f'$.track_bl_no', type='string', state='carry', ui_kind='text', description='运踪提单号'),
            DeclarationEntry(name='track_atd', path=f'$.track_atd', type='integer', state='carry', ui_kind='number', description='运踪ATD'),
            DeclarationEntry(name='track_eta', path=f'$.track_eta', type='integer', state='carry', ui_kind='number', description='运踪eta(预计到达时间)'),
            DeclarationEntry(name='track_ata', path=f'$.track_ata', type='integer', state='carry', ui_kind='number', description='运踪ata(实际到达时间)'),
            DeclarationEntry(name='track_stcs', path=f'$.track_stcs', type='integer', state='carry', ui_kind='number', description='运踪stcs(提重柜\\/提货时间)'),
            DeclarationEntry(name='track_ship_name', path=f'$.track_ship_name', type='string', state='carry', ui_kind='text', description='运踪船名'),
            DeclarationEntry(name='track_voy', path=f'$.track_voy', type='string', state='carry', ui_kind='text', description='运踪航次'),
            DeclarationEntry(name='finance_date', path=f'$.finance_date', type='integer', state='carry', ui_kind='number', description='财务日期'),
            DeclarationEntry(name='ship_name', path=f'$.ship_name', type='string', state='carry', ui_kind='text', description='船名'),
            DeclarationEntry(name='voy', path=f'$.voy', type='string', state='carry', ui_kind='text', description='航次'),
            DeclarationEntry(name='pol', path=f'$.pol', type='string', state='carry', ui_kind='text', description='起运港'),
            DeclarationEntry(name='pol_cn', path=f'$.pol_cn', type='string', state='carry', ui_kind='text', description='起运港-中文'),  # needs_capture:value_source
            DeclarationEntry(name='pol_country_id', path=f'$.pol_country_id', type='integer', state='carry', ui_kind='number', description='起运港国家ID'),
            DeclarationEntry(name='pol_country', path=f'$.pol_country', type='string', state='carry', ui_kind='text', description='起运港国家'),  # needs_capture:value_source
            DeclarationEntry(name='pol_country_cn', path=f'$.pol_country_cn', type='string', state='carry', ui_kind='text', description='起运港国家-中文'),  # needs_capture:value_source
            DeclarationEntry(name='pod', path=f'$.pod', type='string', state='carry', ui_kind='text', description='卸货港'),
            DeclarationEntry(name='pod_cn', path=f'$.pod_cn', type='string', state='carry', ui_kind='text', description='卸货港-中文'),  # needs_capture:value_source
            DeclarationEntry(name='pot', path=f'$.pot', type='string', state='carry', ui_kind='text', description='中转港'),  # needs_capture:value_source
            DeclarationEntry(name='pot_cn', path=f'$.pot_cn', type='string', state='carry', ui_kind='text', description='中转港-中文'),  # needs_capture:value_source
            DeclarationEntry(name='del', path=f'$.del', type='string', state='carry', ui_kind='text', description='目的港'),  # needs_capture:value_source
            DeclarationEntry(name='del_cn', path=f'$.del_cn', type='string', state='carry', ui_kind='text', description='目的港-中文'),  # needs_capture:value_source
            DeclarationEntry(name='country_id', path=f'$.country_id', type='integer', state='carry', ui_kind='number', description='目的地国家ID'),
            DeclarationEntry(name='country_name', path=f'$.country_name', type='string', state='carry', ui_kind='text', description='目的地国家'),  # needs_capture:value_source
            DeclarationEntry(name='country_name_cn', path=f'$.country_name_cn', type='string', state='carry', ui_kind='text', description='目的地国家-中文'),
            DeclarationEntry(name='ocean_type', path=f'$.ocean_type', type='string', state='carry', ui_kind='text', description='远洋 / 近洋'),  # needs_capture:value_source
            DeclarationEntry(name='airline_type', path=f'$.airline_type', type='string', state='carry', ui_kind='text', description='航线分类'),  # needs_capture:value_source
            DeclarationEntry(name='terms_payment', path=f'$.terms_payment', type='string', state='carry', ui_kind='text', description='结汇方式'),  # needs_capture:value_source
            DeclarationEntry(name='terms_transport', path=f'$.terms_transport', type='string', state='carry', ui_kind='text', description='运输条款'),  # needs_capture:value_source
            DeclarationEntry(name='terms_shipment', path=f'$.terms_shipment', type='string', state='carry', ui_kind='text', description='装运条款'),  # needs_capture:value_source
            DeclarationEntry(name='pay_type', path=f'$.pay_type', type='string', state='carry', ui_kind='text', description='付款方式'),  # needs_capture:value_source
            DeclarationEntry(name='customer_order_sn', path=f'$.customer_order_sn', type='string', state='carry', ui_kind='text', description='客户单号'),  # needs_capture:value_source
            DeclarationEntry(name='cargo_type', path=f'$.cargo_type', type='string', state='carry', ui_kind='text', description='货物类型'),
            DeclarationEntry(name='num', path=f'$.num', type='integer', state='carry', ui_kind='number', description='件数'),
            DeclarationEntry(name='packer', path=f'$.packer', type='string', state='carry', ui_kind='text', description='包装'),  # needs_capture:value_source
            DeclarationEntry(name='gross_weight', path=f'$.gross_weight', type='number', state='carry', ui_kind='number', description='毛重'),
            DeclarationEntry(name='bulk', path=f'$.bulk', type='number', state='carry', ui_kind='number', description='体积'),
            DeclarationEntry(name='volume', path=f'$.volume', type='string', state='carry', ui_kind='text', description='箱型箱量'),
            DeclarationEntry(name='volume_desc', path=f'$.volume_desc', type='string', state='carry', ui_kind='text', description='箱型箱量描述'),  # needs_capture:value_source
            DeclarationEntry(name='teu', path=f'$.teu', type='string', state='carry', ui_kind='text', description='折TEU'),
            DeclarationEntry(name='sea_trans_cost', path=f'$.sea_trans_cost', type='number', state='carry', ui_kind='number', description='海运费总价'),
            DeclarationEntry(name='sea_trans_currency', path=f'$.sea_trans_currency', type='string', state='carry', ui_kind='text', description='海运费币制'),  # needs_capture:value_source
            DeclarationEntry(name='shipper', path=f'$.shipper', type='string', state='carry', ui_kind='text', description='发货人'),  # needs_capture:value_source
            DeclarationEntry(name='consignee', path=f'$.consignee', type='string', state='carry', ui_kind='text', description='收货人'),  # needs_capture:value_source
            DeclarationEntry(name='notifier', path=f'$.notifier', type='string', state='carry', ui_kind='text', description='通知人'),  # needs_capture:value_source
            DeclarationEntry(name='ship_mark', path=f'$.ship_mark', type='string', state='carry', ui_kind='text', description='唛头'),  # needs_capture:value_source
            DeclarationEntry(name='commodity', path=f'$.commodity', type='string', state='carry', ui_kind='textarea', description='品名'),  # needs_capture:value_source
            DeclarationEntry(name='notes', path=f'$.notes', type='string', state='carry', ui_kind='text', description='托书备注'),  # needs_capture:value_source
            DeclarationEntry(name='customer_period', path=f'$.customer_period', type='integer', state='carry', ui_kind='number', description='客户账期'),
            DeclarationEntry(name='customer_settlement_date', path=f'$.customer_settlement_date', type='integer', state='carry', ui_kind='number', description='客户结算日'),
            DeclarationEntry(name='period_rule', path=f'$.period_rule', type='integer', state='carry', ui_kind='number', description='账期截转规则 1截转下月计算账期 2按ATD本月计算账期'),
            DeclarationEntry(name='term_rule_name', path=f'$.term_rule_name', type='string', state='carry', ui_kind='text', description='账期规则名称'),
            DeclarationEntry(name='customer_due_date', path=f'$.customer_due_date', type='integer', state='carry', ui_kind='number', description='客户到期日'),
            DeclarationEntry(name='customer_put_date', path=f'$.customer_put_date', type='integer', state='carry', ui_kind='number', description='客户应收日'),
            DeclarationEntry(name='customer_payment_collection_date', path=f'$.customer_payment_collection_date', type='integer', state='carry', ui_kind='number', description='客户回款日'),
            DeclarationEntry(name='customer_put_date_manual', path=f'$.customer_put_date_manual', type='integer', state='carry', ui_kind='number', description='客户应收日是否手动设置过 1是'),
            DeclarationEntry(name='customer_put_writeoff_date', path=f'$.customer_put_writeoff_date', type='integer', state='carry', ui_kind='number', description='对客应收核销时间'),
            DeclarationEntry(name='supplier_due_date', path=f'$.supplier_due_date', type='integer', state='carry', ui_kind='number', description='供应商到期日'),
            DeclarationEntry(name='discount_start', path=f'$.discount_start', type='integer', state='carry', ui_kind='number', description='折扣开始时间'),
            DeclarationEntry(name='discount_rule', path=f'$.discount_rule', type='string', state='carry', ui_kind='text', description='折扣规则'),  # needs_capture:value_source
            DeclarationEntry(name='discount_end', path=f'$.discount_end', type='integer', state='carry', ui_kind='number', description='折扣结束时间'),
            DeclarationEntry(name='discount_ratio', path=f'$.discount_ratio', type='string', state='carry', ui_kind='text', description='折扣比例'),  # needs_capture:value_source
            DeclarationEntry(name='discount_status', path=f'$.discount_status', type='integer', state='carry', ui_kind='number', description='折扣标识   0正常  1异常  2全不参与补贴 3不符合的折扣规则 4折扣规则过期 5未维护ATD'),
            DeclarationEntry(name='discount_currency', path=f'$.discount_currency', type='string', state='carry', ui_kind='text', description='折扣币种'),  # needs_capture:value_source
            DeclarationEntry(name='book_upload_date', path=f'$.book_upload_date', type='integer', state='carry', ui_kind='number', description='报关单上传日期'),
            DeclarationEntry(name='trans_cost_put_preserve_date', path=f'$.trans_cost_put_preserve_date', type='integer', state='carry', ui_kind='number', description='应收运费维护日期'),
            DeclarationEntry(name='bl_no_upload_date', path=f'$.bl_no_upload_date', type='integer', state='carry', ui_kind='number', description='提单上传日期'),
            DeclarationEntry(name='supplier_invoice_date', path=f'$.supplier_invoice_date', type='integer', state='carry', ui_kind='number', description='供应商账单日期'),
            DeclarationEntry(name='supplier_invoice_taketime', path=f'$.supplier_invoice_taketime', type='integer', state='carry', ui_kind='number', description='供应商账单耗时'),
            DeclarationEntry(name='real_cost_date', path=f'$.real_cost_date', type='integer', state='carry', ui_kind='number', description='真实费用提交日期'),
            DeclarationEntry(name='customer_invoice_request_date', path=f'$.customer_invoice_request_date', type='integer', state='carry', ui_kind='number', description='提交开票申请日期（对客应收）'),
            DeclarationEntry(name='first_financing_doc_ok_date', path=f'$.first_financing_doc_ok_date', type='integer', state='carry', ui_kind='number', description='一融材料齐全日期'),
            DeclarationEntry(name='second_financing_doc_ok_date', path=f'$.second_financing_doc_ok_date', type='integer', state='carry', ui_kind='number', description='二融材料齐全日期'),
            DeclarationEntry(name='insurance_doc_ok_date', path=f'$.insurance_doc_ok_date', type='integer', state='carry', ui_kind='number', description='保后材料齐全日期'),
            DeclarationEntry(name='customer_confirm_date', path=f'$.customer_confirm_date', type='integer', state='carry', ui_kind='number', description='客户确认日期'),
            DeclarationEntry(name='is_delayed_recovery', path=f'$.is_delayed_recovery', type='integer', state='carry', ui_kind='number', description='是否超期回款 1是'),
            DeclarationEntry(name='delayed_recovery_usd', path=f'$.delayed_recovery_usd', type='number', state='carry', ui_kind='number', description='超期回款金额（USD）'),
            DeclarationEntry(name='delayed_recovery_cny', path=f'$.delayed_recovery_cny', type='number', state='carry', ui_kind='number', description='超期回款金额（CNY）'),
            DeclarationEntry(name='delayed_time', path=f'$.delayed_time', type='integer', state='carry', ui_kind='number', description='超期时长'),
            DeclarationEntry(name='expect_fee_status', path=f'$.expect_fee_status', type='integer', state='carry', ui_kind='number', description='实际费用状态  0创建中  1 审核中  2已锁定  3审核驳回 4撤销 5作废'),
            DeclarationEntry(name='real_fee_status', path=f'$.real_fee_status', type='integer', state='carry', ui_kind='number', description='业务订单状态(原实际费用状态)  0创建中  1 审核中  2已锁定  3审核驳回 4撤销 5作废'),
            DeclarationEntry(name='fee_lock_status', path=f'$.fee_lock_status', type='integer', state='carry', ui_kind='number', description='费用状态(锁定状态) 0创建中 1 部分锁定 2全部锁定'),
            DeclarationEntry(name='pay_account_status', path=f'$.pay_account_status', type='integer', state='carry', ui_kind='number', description='应付对账状态  0未对账  1对账完成  2部分完成'),
            DeclarationEntry(name='account_status', path=f'$.account_status', type='integer', state='carry', ui_kind='number', description='对账状态  0未对账  1对账完成  2部分完成'),
            DeclarationEntry(name='real_pay_usd', path=f'$.real_pay_usd', type='number', state='carry', ui_kind='number', description='应付美金'),
            DeclarationEntry(name='real_pay_cny', path=f'$.real_pay_cny', type='number', state='carry', ui_kind='number', description='应付人民币'),
            DeclarationEntry(name='real_put_usd', path=f'$.real_put_usd', type='number', state='carry', ui_kind='number', description='应收美金'),
            DeclarationEntry(name='real_put_cny', path=f'$.real_put_cny', type='number', state='carry', ui_kind='number', description='应收人民币'),
            DeclarationEntry(name='real_put_discount_rate', path=f'$.real_put_discount_rate', type='number', state='carry', ui_kind='number', description='应收折扣比例'),
            DeclarationEntry(name='exchange_rate', path=f'$.exchange_rate', type='number', state='carry', ui_kind='number', description='记账汇率'),
            DeclarationEntry(name='folde_pay_usd', path=f'$.folde_pay_usd', type='number', state='carry', ui_kind='number', description='应付美金折币  real_pay_usd  *  exchange_rate'),
            DeclarationEntry(name='folde_put_usd', path=f'$.folde_put_usd', type='number', state='carry', ui_kind='number', description='应收美金折币 real_put_usd  *  exchange_rate'),
            DeclarationEntry(name='folde_pay_total', path=f'$.folde_pay_total', type='number', state='carry', ui_kind='number', description='应付折币合计  folde_pay_usd + real_pay_cny'),
            DeclarationEntry(name='folde_put_total', path=f'$.folde_put_total', type='number', state='carry', ui_kind='number', description='应收折币合计  folde_put_usd  + real_put_cny'),
            DeclarationEntry(name='gross_margin', path=f'$.gross_margin', type='number', state='carry', ui_kind='number', description='毛利 folde_put_total - folde_pay_total'),
            DeclarationEntry(name='gross_margin_rate', path=f'$.gross_margin_rate', type='number', state='carry', ui_kind='number', description='毛利率'),
            DeclarationEntry(name='is_special_pay', path=f'$.is_special_pay', type='integer', state='carry', ui_kind='number', description='供应商垫付申请 0 未申请 1 已申请 2申请中'),
            DeclarationEntry(name='is_loan_before_invoice', path=f'$.is_loan_before_invoice', type='integer', state='carry', ui_kind='number', description='未放款开票申请  0未申请   1已申请  2申请中'),
            DeclarationEntry(name='is_fee_miss', path=f'$.is_fee_miss', type='integer', state='carry', ui_kind='number', description='是否费用缺失 1是'),
            DeclarationEntry(name='fee_miss_name', path=f'$.fee_miss_name', type='string', state='carry', ui_kind='text', description='缺失费用名称'),  # needs_capture:value_source
            DeclarationEntry(name='service_items', path=f'$.service_items', type='string', state='carry', ui_kind='text', description='服务项目'),
            DeclarationEntry(name='status', path=f'$.status', type='integer', state='carry', ui_kind='number', description='订单生效状态(原订单状态) 1草稿 2生效 3作废'),
            DeclarationEntry(name='cancel_remark', path=f'$.cancel_remark', type='string', state='carry', ui_kind='text', description='作废原因'),
            DeclarationEntry(name='cancel_time', path=f'$.cancel_time', type='integer', state='carry', ui_kind='number', description='作废时间'),
            DeclarationEntry(name='effective_id', path=f'$.effective_id', type='integer', state='carry', ui_kind='number', description='生效人ID'),
            DeclarationEntry(name='effective_by', path=f'$.effective_by', type='string', state='carry', ui_kind='text', description='生效人名字'),  # needs_capture:value_source
            DeclarationEntry(name='effective_time', path=f'$.effective_time', type='integer', state='carry', ui_kind='number', description='订单生效时间'),
            DeclarationEntry(name='create_id', path=f'$.create_id', type='integer', state='carry', ui_kind='number', description='创建人ID'),
            DeclarationEntry(name='create_by', path=f'$.create_by', type='string', state='carry', ui_kind='text', description='创建人'),
            DeclarationEntry(name='create_time', path=f'$.create_time', type='integer', state='carry', ui_kind='number', description='创建时间'),
            DeclarationEntry(name='update_id', path=f'$.update_id', type='integer', state='carry', ui_kind='number', description='更新人ID'),
            DeclarationEntry(name='update_by', path=f'$.update_by', type='string', state='carry', ui_kind='text', description='更新人'),
            DeclarationEntry(name='update_time', path=f'$.update_time', type='integer', state='carry', ui_kind='number', description='更新时间'),
            DeclarationEntry(name='delete_time', path=f'$.delete_time', type='integer', state='carry', ui_kind='number', description='删除时间'),
            DeclarationEntry(name='business_time', path=f'$.business_time', type='integer', state='carry', ui_kind='number', description='业务发生时间'),
            DeclarationEntry(name='main_ids', path=f'$.main_ids', type='string', state='carry', ui_kind='text', description='主体顺序ID'),
            DeclarationEntry(name='reverse_status', path=f'$.reverse_status', type='integer', state='carry', ui_kind='number', description='是否倒找 0否1是'),
            DeclarationEntry(name='proprietary_business_status', path=f'$.proprietary_business_status', type='integer', state='carry', ui_kind='number', description='是否自营业务 0否1是'),
            DeclarationEntry(name='m_delivery_type', path=f'$.m_delivery_type', type='string', state='carry', ui_kind='text', description='M放货方式'),
            DeclarationEntry(name='loan_status', path=f'$.loan_status', type='string', state='carry', ui_kind='text', description='融资状态  1融资成功 2融资失败  3部分融资'),
            DeclarationEntry(name='first_status', path=f'$.first_status', type='string', state='carry', ui_kind='text', description='一融支用状态 0-支用失败 1-支用成功 2-放款成功'),
            DeclarationEntry(name='second_status', path=f'$.second_status', type='string', state='carry', ui_kind='text', description='二融支用状态 0-支用失败 1-支用成功 2-放款成功'),
            DeclarationEntry(name='loan_pay_status', path=f'$.loan_pay_status', type='string', state='carry', ui_kind='text', description=' 是否放款 1是 2否'),
            DeclarationEntry(name='change_type', path=f'$.change_type', type='integer', state='carry', ui_kind='number', description='订单变更类型 1变更服务政策 2变更服务策略'),
            DeclarationEntry(name='copy_order_id', path=f'$.copy_order_id', type='integer', state='carry', ui_kind='number', description='复制原始订单ID'),
            DeclarationEntry(name='real_fee_locked', path=f'$.real_fee_locked', type='integer', state='carry', ui_kind='number', description='实际费用是否锁定过  0否1是'),
            DeclarationEntry(name='is_usd_project', path=f'$.is_usd_project', type='integer', state='carry', ui_kind='number', description='是否为美元项目 1是 0否'),
            DeclarationEntry(name='pay_status', path=f'$.pay_status', type='integer', state='carry', ui_kind='number', description='放款状态  1未放款 2已放款 3部分放款 '),
            DeclarationEntry(name='is_sync_es', path=f'$.is_sync_es', type='integer', state='carry', ui_kind='number', description='是否同步es 0未同步 1已同步 '),
            DeclarationEntry(name='expect_discount_status', path=f'$.expect_discount_status', type='integer', state='carry', ui_kind='number', description='预估费用折扣标识   0正常  1异常  2全不参与补贴 3不符合的折扣规则 4折扣规则过期 5未维护ATD'),
            DeclarationEntry(name='real_discount_status', path=f'$.real_discount_status', type='integer', state='carry', ui_kind='number', description='实际费用费用折扣标识   0正常  1异常  2全不参与补贴 3不符合的折扣规则 4折扣规则过期 5未维护ATD'),
            DeclarationEntry(name='entrust_status', path=f'$.entrust_status', type='integer', state='carry', ui_kind='number', description='1未分发 2已分发'),
            DeclarationEntry(name='remark', path=f'$.remark', type='string', state='carry', ui_kind='text', description='备注'),
            DeclarationEntry(name='audit_type', path=f'$.audit_type', type='string', state='carry', ui_kind='text', description='在途审批类型'),  # needs_capture:value_source
            DeclarationEntry(name='is_system_generate', path=f'$.is_system_generate', type='integer', state='carry', ui_kind='number', description='是否系统自动生成 0否1是'),
            DeclarationEntry(name='is_financing', path=f'$.is_financing', type='integer', state='carry', ui_kind='number', description='是否进入融资流程 0否 1是'),
            DeclarationEntry(name='confirm_status', path=f'$.confirm_status', type='integer', state='carry', ui_kind='number', description='推送费用状态  0无状态  1 审核中  2已推送  3审核驳回 4撤销'),
            DeclarationEntry(name='is_traverse', path=f'$.is_traverse', type='integer', state='carry', ui_kind='number', description='是否穿行  0未穿行  1已穿行'),
            DeclarationEntry(name='financing_apply_amount', path=f'$.financing_apply_amount', type='number', state='carry', ui_kind='number', description='融资申请金额'),
            DeclarationEntry(name='financing_apply_amount_cny', path=f'$.financing_apply_amount_cny', type='number', state='carry', ui_kind='number', description='融资申请金额人民币'),
            DeclarationEntry(name='financing_apply_amount_usd', path=f'$.financing_apply_amount_usd', type='number', state='carry', ui_kind='number', description='融资申请金额美金'),
            DeclarationEntry(name='sys_upttime', path=f'$.sys_upttime', type='string', state='carry', ui_kind='text'),
            DeclarationEntry(name='settle_type', path=f'$.settle_type', type='integer', state='carry', ui_kind='number', description='结算方式 1月结 2票结'),
            DeclarationEntry(name='period_delay_type', path=f'$.period_delay_type', type='integer', state='carry', ui_kind='number', description='客户账期类型 1延长 2不延长'),
            DeclarationEntry(name='receive_time_limit', path=f'$.receive_time_limit', type='integer', state='carry', ui_kind='number', description='回款时效'),
            DeclarationEntry(name='customer_put_date_desc', path=f'$.customer_put_date_desc', type='string', state='carry', ui_kind='text', description='应收日计算规则描述'),  # needs_capture:value_source
            DeclarationEntry(name='deposit_type', path=f'$.deposit_type', type='integer', state='carry', ui_kind='number', description='保证金类型  1有 2无'),
            DeclarationEntry(name='deposit_refund_day', path=f'$.deposit_refund_day', type='integer', state='carry', ui_kind='number', description='保证金退还周期'),
            DeclarationEntry(name='deposit_settlement_date', path=f'$.deposit_settlement_date', type='integer', state='carry', ui_kind='number', description='保证金结算日'),
            DeclarationEntry(name='deposit_refund_month', path=f'$.deposit_refund_month', type='integer', state='carry', ui_kind='number', description='保证金退还月'),
            DeclarationEntry(name='payment_type', path=f'$.payment_type', type='integer', state='carry', ui_kind='number', description='付款类型 1确定性付款 2非确定性付款'),
            DeclarationEntry(name='product_name', path=f'$.product_name', type='string', state='carry', ui_kind='text', description='客户产品名称'),
            DeclarationEntry(name='product_id', path=f'$.product_id', type='integer', state='carry', ui_kind='number', description='客户产品ID'),
            DeclarationEntry(name='revoke_status', path=f'$.revoke_status', type='integer', state='carry', ui_kind='number', description='撤单状态 1撤单中 2撤单成功 3撤单失败 4有意向撤单'),
            DeclarationEntry(name='revoke_type', path=f'$.revoke_type', type='string', state='carry', ui_kind='text', description='撤单原因 枚举revoke_order_type'),
            DeclarationEntry(name='asset_status', path=f'$.asset_status', type='integer', state='carry', ui_kind='number', description='资产状态 1可撤回 2不可撤回'),
            DeclarationEntry(name='revoke_failure_reason', path=f'$.revoke_failure_reason', type='string', state='carry', ui_kind='text', description='撤单失败原因'),
            DeclarationEntry(name='repayment_date', path=f'$.repayment_date', type='integer', state='carry', ui_kind='number', description='还资方日'),
            DeclarationEntry(name='repay_warn_time', path=f'$.repay_warn_time', type='integer', state='carry', ui_kind='number', description='最低回款预警时间'),
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
