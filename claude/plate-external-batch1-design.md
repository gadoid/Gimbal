# 批1 一页纸小设计 · 外部定义归一 plate(已确认)

> 日期:2026-10-16　基线:《外部定义归一 plate 改造方案》v0.8.1(43e8eb2d)
> 状态:**已被归一方案 v1.0 取代,待按 v1.0 重写(2026-10-18)**—— 九项细则基于 v0.8.1 机制(照常 release / `ext:` 内联执行 / 漂移检测),与 v1.0(不发版 + `integration` ref + 同路径执行)冲突;重写稿以 `external-definition-unification-design.md` v1.0 为准,仍有效结论(kind 不进执行产物、signer 留执行侧、line 豁免 common)由重写稿承接
> 性质:批1 实现细则 + 批2 两项机制(处置表/匹配器)的定案;全部承自方案已定决策,本页只细化到实现级

---

## 1. 外部别名 `base_service` 显式接收与校验(批1,平台)

- `service_aliases.py:92-96`:external 分支删除 `base = alias_name`;创建/更新时 kind=external 必须显式传入 `base_service`;
- 两项校验:① 所选服务存在于 plate 目录(`catalog_service_names` 全量,含 external);② 经值域映射后与所指系统 kind 一致(external 别名→external 系统,plate 别名→sut 系统);失败 422,错误信息带系统 kind 实值;
- sut 别名 `derive_base` 路径零改动;存量 external 别名不在批1 动(批3 回填,方案 §3.4);
- UI:别名页 `base_service` 下拉按 kind 过滤。

## 2. kind 值域映射(批1)

- `plate ↔ sut` 写死在单一函数(如 `service_kinds.py`),台账登记;禁止散写第二份。字段两史:平台侧 `service_aliases.kind`(plate|external)已有(0019);plate 侧 `ServiceDefinition.kind`(sut|external)批1 新增。

## 3. plate `ServiceDefinition.kind` 字段(批1,M2 一次性适配)

- `system.md` 的 `gimbal:system` 块新增 `kind` key;存量三系统(common/fin/platform)**显式写 `sut`**(★微决策:不留缺省回退,缺 kind = 定义错误);
- kind 与 `EndpointMetadata` 同类:业务元信息,**不进执行产物**(case.json/call 投影零变化);唯一进构件的场合 = release **manifest**(供「release 后 kind 不可变」比对)。

## 4. external 的 `line` 规则(批1,plate check)

- kind=external 的 `system.md` **不得写 `line`**(写了 check 拒收);sut 必须写(现行不变);
- **豁免 common**(2026-10-16 评审补):common 不单独发版(N3,`release.py:387`)、无独立版本线,免写 `line`;common 标 `sut` 在过滤面行为正确(非 external,排除面天然不含;sut-only 面维持现状,批1 盘点逐面核验)。

## 5. release 后 kind 不可变(批1,plate check)

- check 对比该系统最近 release manifest 的 kind,不一致即拒收,提示「换 kind = 新系统名重新接入」;common 无独立 release,规则天然不触发。

## 6. signer 边界(批1,声明面)

- plate 只声明 `auth: <形态>` + 可选 `signer: <名称>`(字符串);实现注册表在执行器(`@register_authenticator`);未注册名称在执行期报 auth 错,plate 零执行逻辑。

## 7. 漂移处置表(批2 机制,定案)

- 检查点移出 `if identity_mode == "platform"` 分支:两模式都执行「读投影 + 漂移检测」;三条件闸仅平台模式判定(方案 §2.2);
- ★微决策:个人模式漂移阻断的 `run_status` = **`contract`**(内联形态与定义不符 = 契约面;不用 channel),lastError 前缀「漂移检测未通过:」。

## 8. 形态匹配器(批2 机制,定案)

- method 相等(★微决策:**忽略大小写**,与导入重锚定反查口径一致);
- path 先剥 query string 再按 `/` 分段:段字面相等,或 内联段含 `${...}` 且定义段为 `{param}` → 通配通过;
- body 不参与;匹配发生在变量展开前(执行前/预检时)。

## 9. D-F 编排器分组入口(批2 交付,形态已定 v0.8.1)

- 同一选单两组:「被测接口」(纯 sut)/「第三方集成」(kind=external 别名 → 所指系统 latest 端点);
- 选中生成 `ext:<alias>.<name>` + 按定义填充内联形态(与 D-E「按 latest 重填」同一填充函数);
- 步骤卡与分组标题带「latest 解析」标注防混淆。

---

## 附:影响面结论(评审澄清三问之三)

**存量用例零影响**:kind 不进场景载荷、不进执行产物,存量场景零迁移;影响集中在 plate 定义面(方言/loader/check/manifest)与平台消费面(投影多透出一个 kind 字段,加法),新行为全部长在新面上,由批1 过滤面逐面断言 + `/api/service` 反向断言管住。
