<?php
class OrderController extends BaseController
{
    public function orderAdd()
    {
        $requestData = getRequestParam();
        // 真源实测(task-10):规则经局部变量间接绑定
        $rule = OrderValidator::$orderAddRules;
        if ($requestData['entrust_status'] == 1) {
            unset($rule['num']);
        }
        $errorMsg = $this->paramVerification($rule, false);
        $this->returnSuccess();
    }

    public function orderEdit()
    {
        $requestData = getRequestParam();
        $pol = getDataString($requestData, "pol");
        $bl = $requestData["bl_no"];
        $this->paramVerification(OrderValidator::$orderEditRules);
        $this->returnSuccess();
    }

    // task-10 真源形状:链式服务只透传主键(仿 orderBookUpdate→createDocumentBook→orderBook)
    public function orderDoc()
    {
        $requestData = getRequestParam();
        OrderDocService::getInstance()->makeDoc($requestData['order_id']);
        $this->returnSuccess();
    }

    public function orderSelf()
    {
        OrderSvc::getInstance()->selfFetch();
        $this->returnSuccess();
    }
}
