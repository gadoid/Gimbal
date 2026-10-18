# 批0 存量盘点档(2026-10-18)

> 依据:归一方案 v1.0 §3.5;实施计划 v1.1 §2 A 串。数据库:`gimbal-pg-15432`(docker,`gimbal/gimbal`);查询经 `docker exec … psql`,一次性不入库脚本(C9)。
> 结论速览:**①②③④⑤ 均非 0(与 v1.0「预期 0」的假设不符,均为 2026-10-13 之后产生的集成线测试种子数据);⑥ = 0**。三个连带影响见文末「检查点」。

## 六项出数

| # | 项 | 数 | 明细 |
|---|---|---|---|
| A1 | `external_endpoints` 行数 | **2** | 均 alias `jira-x`:GET `/rest/api/2/issue/{key}`(qs=f)、POST `/rest/api/2/search`(qs=f) |
| A2 | 审计 `external_endpoint.query_safe` 行数 | **2** | 与 A1 对应的标记变更审计 |
| A3 | external 别名及 `base_service` | **1 条** | `jira-x`(kind=external,**base=jira 已显式**,url=https://jira.example);另有 plate 别名 `fin-service-test`(base=fin-service) |
| A4 | 存量 `ext:` 锚点场景数 | **2** | `sc-v2-qs`、`sc-v2-qs2`(Y5 只读闸测试种子) |
| A5 | 无锚点外部裸调用步骤数 | **11** | `fin.order` ×8(`sc-s2-login/order/pay/refund/notify` ×5、`sc-dbg-a/bgx54025` ×3);`stub` ×3(`sc-fc2/fc3/fcheck`)—— 两服务名**均无对应别名** |
| A6 | 存量裸线声明场景数 | **0** | R13 影响面确认为 0(测试执行路径今天就被 `resolve_effective` 拒,声明侧也无存量) |

## 检查点(按实施计划 §8)

1. **D-N 检查点触发(A5=11 非 0)**:明细全部落在调试/种子场景(`sc-s2-*` 二件套样例、`sc-fc*` 功能检查种子、`sc-dbg*` 调试),且 `fin.order`/`stub` 无别名、执行时本就走 base_url 缺口报错路径。**重开 D-N 供 owner 裁定**:a) 维持合法(建议:全部为种子数据,平台未上线,无收紧收益);b) 收紧为必须锚定(与 §3.3 重锚定同批;`fin.order`/`stub` 无别名,自动补声明走不通,需人工处置或直接清理种子场景)。
2. **过渡期存在(A4=2 非 0)**:批2 删闸 `ext:` 分支 → 批3 迁移之间,`sc-v2-qs`/`sc-v2-qs2` 处于过渡期行为区(§3.5:带内联 GET 放行/POST 拒/无内联 fail-closed——两场景的 ext: 步骤 qs=f 且为 GET/POST 各一,正好覆盖过渡期两侧行为)。
3. **批3 迁移量修正(v1.0 §3.5 预期全部落空)**:③ `jira-x` 的 `base_service=jira` 已显式(免人工选,仅核验);④ 2 个 `ext:` 场景需改写为 plate 锚点 + `meta.plate[jira]=integration`——**前提是 jira 系统先按 v1.0 写入 plate**(2 条端点定义即 A1 明细);C9 一次性迁移脚本需要产生(非 0)。

## B13 记录性两条(实施计划 §2)

- plate 全局端点列表不分页(`per_page` 参数无效):非问题,第三方端点接入后无截断风险。
- 现存口径张力:`anchored_systems`(`run_semantics.py:20-27`)不过滤 `ext:` 前缀,仅锚 `ext:` 的场景按代码会被判预览,与模块注释相悖;C12 后自然消解。
