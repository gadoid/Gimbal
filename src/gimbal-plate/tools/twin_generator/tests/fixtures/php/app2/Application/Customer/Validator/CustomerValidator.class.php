<?php
class CustomerValidator
{
    public static $batchChangeRelatedRules = [
        'related_id'          => 'present', //关联ID
    ];

    public static $customerServiceTeamAddRules = [
        'team_role'           => 'require', //团队角色
        'team_user_id'        => 'present', //团队成员ID
    ];
}
