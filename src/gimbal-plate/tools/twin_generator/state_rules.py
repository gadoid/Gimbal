"""state 判据单一真源(S4 赋值与 S5 渲染共用,防两处漂移)。

判据:read → form(后端实际读取 = 表单可见);
     其余 → carry(不渲染,值表注入)。
needs_value/enum 分支属 S4 职责,不在此复述。
"""
from __future__ import annotations


def state_of(field) -> str:
    """FieldIR → 'form' | 'carry'。"""
    return "form" if field.read else "carry"
