<?php
class CustomerController extends BaseController
{
    public function batchChangeRelated()
    {
        $requestData = getRequestParam();
        $this->returnSuccess();
    }
}
