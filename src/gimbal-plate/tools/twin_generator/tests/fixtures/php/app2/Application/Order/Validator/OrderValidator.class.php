<?php
class OrderValidator
{
    // 真源实测形状(task-10):双引号值/双引号键/无尾注注释行
    public static $orderAddRules = [
        'customer_id'         => "require|num", //客户ID
        "order_sn"            => 'exist', //客户单号
        'order_id'            => "require|num",
        //        'settle_type'         => 'present|num|in:1,2',
        'num'                 => 'exist|num', //件数
    ];

    public static $orderEditRules = [
        'remark'              => 'present', //备注
    ];
}
