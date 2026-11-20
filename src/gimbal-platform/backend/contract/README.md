# REST 契约快照(审计批次⑤轻量切片,登记册 B5)

后端 REST 契约的两份**入库快照**,漂移即红(守卫 = plate-ci 显式步骤 +
`backend/tests/test_api_contract.py`):

| 文件 | 内容 | 守卫面 |
|---|---|---|
| `openapi.json` | `create_app().openapi()` 原样落盘(199 路径 / 213 schema;2026-11-20 阶段 2 入库时点) | 请求/响应形状 |
| `error-codes.json` | AST 静态提取的错误码清单(215 码 / 442 位点 / 35 动态位点;2026-11-20 阶段 2c 双源检索入库时点) | 错误码/状态码/detail 形状 |

*计数为本轮入库时点,演进后以 `check` 重生产物为准。*

错误码提取覆盖四类间接形态:`_codes.py` 整型码、带码业务异常类
(`self.code = code`)raise 位点、透传 helper(`_bad` 型)调用位点、
`at.ERR_*` 模块常量。非字面量位点登记进 `dynamic` 面(取值由对应
异常/helper 调用位点枚举,位点增删即契约变化)。

## 契约变更流程

```bash
python scripts/gen_api_contract.py gen     # 重生快照入库
python scripts/gen_api_contract.py check   # 漂移比对(漂移非零退出)
```

路由/模型/错误码改动 → 守卫红 → `gen` 重生 → 快照 diff 随提交评审
(这就是契约变更的评审面;改动是否兼容由评审判断,守卫只保证「无意识
漂移进不来」)。

治本全量(前端 37 个 `api/*.ts` 手写镜像的 codegen 单源化、错误码表
前端接入)见 `docs/known-issues/TRANSITIONAL-REGISTRY.md` B5。
