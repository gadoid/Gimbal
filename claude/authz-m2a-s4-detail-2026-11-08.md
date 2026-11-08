# M2a S4 carry 分层 — 实施细化（2026-11-08）

- 依据：`authz-m2a-plan-2026-11-07.md` §二 S4 行、§三 S4、裁定 D3 与「区模型收敛」
- 代码基线：`feat/authz-m1` @ `296c3a72`（S3 全部收口，head 迁移 `0045_auth_slot_bindings`）
- 迁移序号：**S4 = 0046**

---

## 〇、调研结论（决定了切法）

| # | 现状 | 对 S4 的含义 |
|---|---|---|
| H1 | 两表零作用域列:`carry_service_bindings (service_name, field_path)`、`carry_global_defaults (field_path)`;只有 updated_by_* 审计列 | 直接加 scope/scope_id + 换唯一键 |
| H2 | 运行时合并:`build_carry_context(db, definition, ui_field_states)` 无身份;层内 别名键 > 基础服务键,`_apply_carry` 再吃全局默认;`${...}` 串原样透传给引擎 | 作用域作外层(D3):tier 序 = 公共项目层 < (项目层 ∨ 个人层),层内键层级不动;身份从调用方穿进 |
| H3 | 调用方(_fanout / unit_carry_contexts / 集成 / 导入)都有 owner/scenario 上下文,只是没穿进 carry | 加 `project_id`/`user_id` 形参逐点接线 |
| H4 | 个人别名只在**场景导入**产生(owner_user_id=导入人),且导入随即把 carry 行写在别名键下 | 0046 迁移:个人别名键下的行 → 属主个人层;其余 → 公共项目层 |
| H5 | `${slot.X.field}` 今天零消费;account_fields 只存取;引擎 `${...}` 名字空间是 service/auth/var | 平台侧**派发前**替换(_apply_carry 注入值 + run 副本里的模板字面值);未知槽/字段原样透传(fail-visible) |
| H6 | dev 存量:236 行 bindings 全部键在共享基础服务 `fin-service`,0 行全局默认,公共项目 id=1 | 迁移简单;仍按通用规则写 |

## 一、模型与语义

**scope**:`'project' | 'user'`(**没有独立 global** —— 裁定:全局 = 公共项目的项目层,
scope_id = 公共项目 id)。`scope_id`:Integer NOT NULL(多态指向 projects.id /
users.id,应用层校验,不落 FK)。两表唯一键加前缀:
`(scope, scope_id, service_name, field_path)` / `(scope, scope_id, field_path)`。

**运行时 tier 序**(D3 + 区模型收敛):
- 私有区场景(project_id 空):公共项目层 < 执行人个人层
- 普通项目场景:公共项目层 < 本项目层(不吃个人层)
层内沿用现行键层级(别名键 > 基础服务键;全局默认表在层内兜底)。
旧库存量行全在公共项目层 → 无人带新上下文时 tier 序只有一层,行为逐行同旧链。

**`${slot.X.field}`**(F6):平台侧派发前替换 —— carry 注入值与 run 副本模板
字面值里的 `${slot.<槽名>.<字段>}` → 执行人槽绑定的 account_fields 字段值
(未命中原样保留,引擎报错可见)。

**API**:
- 读(`/carry/bindings`、`/defaults`):公共项目层 + 我所在项目层 + 我的个人层
  (响应带 scope/scopeId)
- 写:`scope=global`(默认,兼容旧客户端)= 公共项目层,ops.write;
  `scope=project&projectId=`= 项目层,padmin;
  `scope=user` = 个人层,CurrentUser 本人
- drift/fields 面随读过滤;审计 detail 带 scope

## 二、子切片

### S4.0 模型 + 迁移 0046
- 两表加 scope/scope_id + 换唯一键;回填:个人别名键下 → ('user', 属主);
  其余 → ('project', 公共项目);fresh 守卫;downgrade 按「公共层优先去重」收敛
- 测试:回填三形态(个人别名行 / 共享行 / 无公共项目)+ 新键冲突 + downgrade

### S4.1 运行时分层
- carry_store 读写带 scope;`build_carry_context(..., *, project_id, user_id)`
  双层合并(公共层恒在)
- 接线:prepare_exec(+project_id)← _fanout(配方带 scenario 项目)← dispatch;
  graph 逐单元(单元场景项目);集成(scen.project_id);导入(导入人,私有区)
- 测试:tier 覆盖(个人层不进项目区 / 项目层覆盖公共层 / 层内别名键仍赢)

### S4.2 API 作用域 + ${slot.X.field}
- 读写三面 + 审计;ResolvedAuth 带 account_fields;
  materialize_run_copy 派发前替换(注入值 + 字面值)
- 测试:三面权限矩阵;替换命中/未命中透传;导入回归

### S4.3 前端(最小面)
- api 类型与 scope 参数;CarryConfig 加「全局默认 / 我的默认」页签
  (项目层编辑 UI 归 S7 项目管理页)

## 三、清理项
- `_apply_carry` 注释「全局默认」措辞改「公共项目层默认」
- 旧 PUT 无 scope 形态 = global(不删,兼容)

## 四、不在 S4
- 编排页 carry 提示的别名层修复(F5)与四处统一(S5)
- 项目层编辑 UI(S7 项目管理页)

---

## 五、实施记录(2026-11-08)

| 子片 | 门禁 |
|---|---|
| S4.0 模型 + 迁移 0046 | 迁移 17/17(含范围存活/新键/降级去重) |
| S4.1 运行时分层 | 本批;新测 4 例(tier/项目区不吃个人层/槽位替换/API 三面) |
| S4.2 API + ${slot} | 并入 S4.1 提交 |
| S4.3 前端最小面 | 前端四门 1317/tsc/eslint/build |

落地要点:

- **迁移 0046**:两表加 scope/scope_id、唯一键加前缀(约束名沿用旧名,
  与 create_all 同形);回填 全部行 → 公共项目层、个人别名键行 → 属主
  个人层;downgrade 公共层优先去重(个人配置不回落全局,防越权扩大)。
- **carry_store ``scope=None`` 缺省 = 公共项目层**:与旧「全局表」语义
  同型 —— 适配批次(adaptation_carry_ops)与存量读面零改动即落新层。
- **tier 合并在 build_carry_context**(签名加 project_id/user_id):
  公共层恒在;项目区不吃个人层;层内键层级(别名键 > base 键 > 层默认)
  不动。接线:dispatch 配方带 scenario_project_id → _fanout →
  prepare_exec;graph 逐单元(unit_metas);集成 scen.project_id;
  导入分析按导入人(precheck/analyze_services 透传)。
- **导入写面落个人层**(carry_store_put scope=('user', 导入人))——
  与 0046 的 F3 迁移同口径;相关导入测试断言改为按属主层读。
- **${slot.X.field}**:ResolvedAuth 带 account_fields;
  materialize_run_copy 末段对整个 run 副本做一次递归替换(含 carry
  注入值与模板字面值);未命中原样保留(fail-visible,引擎报错可见)。
- **API**:读面可见层并集(公共 + 我所在项目 + 我的个人层,tier 序合并
  + 行级 scope 标签);写面 scope=global(Admin+)/project(padmin,
  Admin+ 旁路)/user(本人);drift 看公共层;审计 detail 带层。
- 前端:api/carry.ts 默认值读写带 scope;CarryConfig 加「全局默认/
  我的默认」层页签(过期断言改写);项目层编辑 UI 留 S7。

### 已知留到后续

- 编排页 carry 提示的别名层修复(F5)与四处统一解析(S5)
- 项目层 carry 编辑 UI(S7 项目管理页)
