<?php
class OrderEntrustValidator
{
    public static $orderAddRules = [
        'service_id'          => 'present', //客服ID
    ];

    public static $batchChangeRelatedRules = [
        'order_ids'           => 'present', //订单ID集
    ];
}
