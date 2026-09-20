<?php
class OrderValidator
{
    // 真源实测形状(task-10):双引号值/双引号键/无尾注注释行
    public static $orderAddRules = [
        'customer_id'         => "require|num", //客户ID
        "order_sn"            => 'exist', //客户单号
        'order_id'            => "require|num",
        //        'settle_type'         => 'present|num|in:1,2',
        'num'                 => 'exist|num', //件数
    ];

    public static $orderEditRules = [
        'remark'              => 'present', //备注
        //        'business_type' => "present|length_max:32",//业务类型
    ];

    // order 族容器信号真源形状(OrderValidator::checkContainer):
    // check 方法持请求形参,getDataArray 读数组键 —— 不走 foreach+paramVerification
    public static function checkContainer(array $requestData)
    {
        $containerArr = getDataArray($requestData, "container");
        foreach ($containerArr as $k => $v) {
            if (empty($v["container_type"])) {
                throw new Exception("箱型箱量缺失");
            }
        }
    }
}
