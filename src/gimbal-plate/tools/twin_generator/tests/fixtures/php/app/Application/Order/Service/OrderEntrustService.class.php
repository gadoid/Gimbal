<?php
class OrderEntrustService
{
    public function orderUpdate($requestData)
    {
        $data = $requestData;
        $action = getDataString($data, 'action', 'submit');
        $cid = getDataInt($data, 'customer_id', 0);
        $bl = $requestData['bl_no'];
        $cn = $requestData['customer_name'];
        if (!empty($requestData['container'])) { $x = 1; }
        OrderTaskService::getInstance()->pushTask($requestData);
        return $action . $bl;
    }

    public function orderPage($requestData)
    {
        $status = getDataString($requestData, 'status', '1');
        return [$status];
    }
}
