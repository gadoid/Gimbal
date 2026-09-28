"""tests 根包标记。

正式包(而非命名空间包)是必须的:platform_compat 测试会把
``src/gimbal-platform/backend`` 加进 sys.path,而 backend 下存在同名
正式包 ``backend/tests`` —— 命名空间包会被路径上任何位置的正式包
``tests`` 压制,导致 ``tests.plate.*`` 绝对导入在合跑时解析到 backend。
本文件让仓库根的 ``tests`` 成为正式包,位于 sys.path 最前,优先级稳定。
"""
