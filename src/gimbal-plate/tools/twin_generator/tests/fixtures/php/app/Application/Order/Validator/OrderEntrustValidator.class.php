<?php
class OrderEntrustValidator
{
    public static $orderAddRules = [
        'customer_id'         => 'require|num', //客户ID
        // 'carrier'                => 'present', //船公司/承运人
        'bl_no'               => 'present|alpha_dish|length_max:32', //提单号
        'settle_type'         => 'exist|num|in:1,2', //结算类型
        'num'                 => 'exist|num', //件数
    ];
}
