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

    // task-10 评审 Important-1:Order 模块动作无显式绑定,batchChangeRelatedRules
    // 在 Customer(CustomerValidator)与 Order(OrderEntrustValidator)撞名 ——
    // 兜底必须取同模块,否则串到别模块的规则集
    public function batchChangeRelated()
    {
        $requestData = getRequestParam();
        $this->returnSuccess();
    }
}
