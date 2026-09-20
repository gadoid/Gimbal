<?php
class CustomerController extends BaseController
{
    public function batchChangeRelated()
    {
        $requestData = getRequestParam();
        $this->returnSuccess();
    }

    public function checkBase()
    {
        $requestData = getRequestParam();
        //检测服务团队(行容器权威样式:checkBase 五组同款)
        foreach ($requestData['customer_team'] as $k => $v) {
            $resultMsg = CustomerService::getInstance()->paramVerification( CustomerValidator::$customerServiceTeamAddRules,$v,'customer_team',$k);
            if (count($resultMsg)>0){
                $error[] = $resultMsg;
            }
        }
    }
}
