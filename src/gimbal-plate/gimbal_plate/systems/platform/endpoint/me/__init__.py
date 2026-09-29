"""platform 契约的 me 域。

按域分目录是 platform 对 fin 形制的偏离:fin 18 个端点单层平铺,platform
123 个 —— 单层没法导航。代价是这个 __init__.py 不能少,少了装包后
`...platform.endpoint.<域>.<动作>` 这个 import path 就断了(开发时 namespace
package 还能凑合)。"""
