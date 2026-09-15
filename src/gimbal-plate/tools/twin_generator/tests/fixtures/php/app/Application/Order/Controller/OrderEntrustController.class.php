<?php
class OrderEntrustController extends BaseController
{
    public function orderAdd()
    {
        $requestData = getRequestParam();
        $errorMsg = $this->paramVerification(OrderEntrustValidator::$orderAddRules, false);
        $errorMsg = array_merge($errorMsg, OrderEntrustValidator::checkSupplier($requestData));
        if (!empty($errorMsg)) { throwValidator($errorMsg); }
        OrderEntrustService::getInstance()->orderUpdate($requestData);
        $this->returnSuccess();
    }

    public function orderPage()
    {
        $requestData = getRequestParam();
        $this->returnSuccess(OrderEntrustService::getInstance()->orderPage($requestData));
    }

    protected function _internal() { }
    public function __construct() { }
}
