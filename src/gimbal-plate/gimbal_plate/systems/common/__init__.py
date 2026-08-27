"""systems.common —— 所有被测系统共享的 Meta / Config 模板工厂。

按 V3 PLATE_V3_DESIGN.md §3:
- 系统无关的最低公共默认(author/owner/expire/requirementRef/version/createTime
  等),提供给所有 systems/<系统>/ 调用
- 不包含任何具体系统的 services / users / vars

设计要点:
- 工厂函数式封装,**不是 Meta 子类**(§1 schema 封闭原则)
- 各系统按"调用 common + 覆盖系统专属字段"组合得到自己的模板
- common 默认值永远可在调用方用 kwargs 覆盖

典型用法:
    from systems.common.meta import common_meta_template
    from systems.common.config import common_config_template
"""