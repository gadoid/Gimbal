<?php
class OrderTaskService
{
    public function pushTask($payload)
    {
        if (isset($payload['etd'])) { return true; }
        return getDataArray($payload, 'service_items', []);
    }
}
