# 状态迁移写点并发审计(C9)· 2026-11-23

> 登记册 C9:「状态迁移写点全量并发审计未做 | 理论竞态面(已知点已
> CAS)| 按第 7 类方法扫」。本档为全量写点清单化审计:每写点一行,
> 守卫形态 + 判定;发现项随批修复。审计基线 = feat/service-registry @
> 本批工作树(legacy 链已退役,恒 server 单链)。

## 写点清单与守卫判定

| # | 写点 | 守卫形态 | 判定 |
|---|---|---|---|
| 1 | `Execution.status` 终态迁移 | `transition_execution`(N2 唯一终态迁移:条件 UPDATE 非终态 WHERE + `transition_with_retry` 撤锁重试) | ✓ 已 CAS(N2 批) |
| 2 | `ExecutionJob.cancel_requested` | 条件 UPDATE(`status IN (queued, running)`)+ rowcount 判定;进程内 `_cancel_hint` 仅快速通道,DB 位权威 | ✓ |
| 3 | `execution_rows` 终态回写 | seq 主键 upsert(at-most-once;B3 批已核,graph 恢复路径同形) | ✓ |
| 4 | webhook 投递 `delivered/failed` | `with_for_update(skip_locked=True)` 投递循环(单飞,锁内改状态) | ✓ |
| 5 | integration instance 摘要(lastRunAt/failStreak) | `db.refresh(inst, with_for_update=True)` | ✓ |
| 6 | 项目令牌/访问令牌生命周期 | 写前 `with_for_update` 行锁 | ✓ |
| 7 | suite 成员/内容写 | rev 乐观锁(冲突 409 附最新内容,`routers/suites.py` §rev) | ✓ |
| 8 | suite 发布/下架 | rev 乐观锁同款 + 发布状态门 | ✓ |
| 9 | **promotions approve/reject/withdraw** | ~~读-判-写(无锁)~~ | **✗→✓ 本批修复** |
| 10 | adaptation op/batch 状态(applied/skipped/conflict/completed/rolled_back) | applying 状态门(409)+ 批内单 worker 顺序推进;回滚同门 | ✓(单写者形态) |
| 11 | `UserStar` 收藏翻转 | unique (user, scenario) + upsert(并发幂等) | ✓ |
| 12 | `revoke_grants`(promotion 回滚删授权) | 共享行按 promotion id 整删 —— 多 promotion 共享条目时过度删除 | 挂账在档(E 区,revoke_grants 粒度;「撤销已批准」扩展前须先修) |

## 发现与处置

**唯一真竞态:promotions 裁决 TOCTOU(C9-1)**

- 形态:`approve/reject/withdraw` 三端点均为「载入 → 判 status ==
  pending → 复制/落授权 → 改 status → commit」,无行锁无 CAS。
- 后果:并发双击/双管理员同时通过 pending 检查 →
  `execute_promotion_copy` 双份副本 + 双份 identity grants;
  reject/withdraw 并发同理(后写覆盖 + 通知双发)。
- 触发面:窄(项目管理员双开标签页裁决/网络重放),但 grants 是
  安全面资产,双份授权行属越权面扩大。
- **处置(本批)**:三端点 `_load_promo` 后 `db.refresh(promo,
  with_for_update=True)` 行锁串行化 —— 状态判定与复制/授权写原子化
  (先例:integration_runner 实例行锁)。13 项 promotions 测试
  (含本批 audit log 断言)全绿。

## 其余面结论

- 已知点确实已 CAS(登记册预判成立);全仓行锁使用集中在投递/
  令牌/integration 三处,语义均为「写前持锁到 commit」。
- `revoke_grants` 粒度维持 E 区挂账(现有状态机 reject/withdraw 仅
  pending 可达、无授权可删,不可达即无害;扩展「撤销已批准」时先修)。
- 引擎侧执行单 run 409(server 单 run 设计)+ 平台槽位池借还,
  属资源闸而非状态迁移面,不在本表。
