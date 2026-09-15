<?php
class OrderSvc
{
    public function book($requestData = [], $orderId = 0)
    {
        $pol = $requestData['pol'];
        $oid = getDataInt($requestData, 'order_id');
        return $pol . $oid;
    }

    public function selfFetch()
    {
        $requestData = getRequestParam();
        $row = D("Order")->find();
        return $requestData['etd'] . getDataString($row, 'bl_no');
    }
}
