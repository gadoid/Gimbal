<?php
class OrderDocService
{
    // 真源形状(task-10):链式调用不透传请求体,只传主键
    public function makeDoc($orderId)
    {
        $list = OrderSvc::getInstance()->book([], $orderId);
        $orderDO = D("Order")->find();
        $no = getDataString($orderDO, 'order_no');
        return $list . $no;
    }
}
