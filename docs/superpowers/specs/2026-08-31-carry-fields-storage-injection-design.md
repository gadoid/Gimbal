# 非绑定字段(传递默认字段)的存储与注入设计

> 状态:设计已与编排者确认,待实现
> 日期:2026-08-31
> 影响范围:`gimbal_plate/schema/endpoint/io_spec.py` · `gimbal-platform/backend/app/services/run_materialize.py` · `run_dispatcher.py` · platform PG 新表 · 前端编排器与配置页
> 关联:[PRD-case-composer.md](../../PRD-case-composer.md) §5.4 Type C · [FIELD-UI-MAPPING.md](../../FIELD-UI-MAPPING.md) §3.5 · [ENDPOINT_SPEC_V2.md](../../../src/gimbal-plate/gimbal_plate/design/ENDPOINT_SPEC_V2.md)

---

## 0. 背景与问题

大的传输接口中存在描述性字段(备注、通知人等):不参与业务核心,但须随请求发送、可能被检查。现状问题:

- 值的唯一居所是每个 step `request.body` 的字面量拷贝(编排时 `deepDefaults` 把 Type C schema default 拷进去);
- 同一业务多次调用同一接口 → 多份独立拷贝,改一处不改其余(不一致);
- plate 契约默认变更 → 存量 step 不跟随(拷贝遮蔽);
- 字段的可变性没有显式声明(配没配 schema default 纯属偶然)。

**目标**:统一存储位置、主业务流程(编排者)无感、可配、(预留)订单组绑定。

## 1. 模型总览(已确认)

```
plate 契约(只声明字段面,不带值)
  EndpointSpec.carry = [$.remark, $.notifyUsers, $.appCode, ...]
        │
        │ 编排/执行时查字段面(契约门控:接口没声明的字段不注入)
        ▼
platform 值层(统一存储,页面可配)
  ① 服务绑定表   track-trace-service → {remark: "压测-张三", notifyUsers: "李四"}
  ② 全局默认表   {appCode: "TRACE-V2", remark: "压测", ...}
        │
        ▼
  解析链:  body 显式值  >  (数据集行值,二期预留)  >  服务绑定值  >  全局默认值
        │
        ▼
  materialize 单点填充(执行/导出同源,case 快照/replay 可见终值)
```

**已拍板的决策**(讨论过程结论):

| # | 决策 | 理由 |
|---|---|---|
| D1 | 运行期物化,非编排期落值 | 编排期落死值会让绑定配置形同虚设(拷贝遮蔽);运行期解析才让"可配"语义完整——改绑定,下次执行即生效 |
| D2 | plate 契约只声明字段面,不带值 | 值全部收进 platform:改默认值不动 plate 发版;"fixed 写死"语义收敛为"全局默认表兜底"(配置级固定) |
| D3 | 与服务名绑定,门控按契约字段面 | 描述字段本是服务报文规范层约定,服务粒度符合域直觉;契约门控防盲注 |
| D4 | 不用 IOFieldBinding 承载 | `fields[]` 语义纯度 = 表单面;carry 是传递面,两拨类型两拨元信息 |
| D5 | 注入点 = materialize_run_copy | 既有"执行/导出共用唯一物化点"安全缝;快照前合并保证可检查性;gimbal 零改动 |
| D6 | 解析链预留数据集行覆盖层 | 订单组绑定("一组数据绑一个订单")二期插入不动架构 |

## 2. 契约层:EndpointSpec.carry(plate)

### 2.1 CarryEntry 定义

```python
class CarryEntry(BaseModel):
    """非绑定传递字段:不进表单,值随 platform 配置走。"""
    model_config = ConfigDict(extra="forbid")

    description: str = ""
    # path 复用外层 dict 的键(见 §2.2),不在 entry 内重复
```

```python
class RequestSpec(BaseModel):
    ...
    fields: list[IOFieldBinding] = ...   # 业务面:表单字段
    carry: dict[str, CarryEntry] = {}    # 传递面:非绑定字段(path → entry)
```

- 键为归一化 JSONPath(`$.remark`),复用 `_path.normalize`,与 fields[].path / strategy target 同词汇;
- **无 value / 无 variability / 无 ui_kind / 无 source_kind** —— 值在 platform(D2),表单语义不适用(D4);
- `_validate` 追加:carry 键与 `fields[].path` 交集为空(一个字段不得同时出现在两个面);
- `/api/endpoint/{id}/full` 序列化带出 `request.carry`,light 视图不含。

### 2.2 三分类穷尽

body 字段从此显式三分类,消除"裸躺 schema 靠 default 暗示语义"的状态:

| 分类 | 位置 | 值通道 |
|---|---|---|
| 业务字段 | `fields[]`(IOFieldBinding) | 表单编辑,编排者逐 step 写 body |
| 传递字段 | `carry` | platform 两层值表,materialize 填充 |
| 未声明 | 两者皆无 | 编排器黄警提示(存量 Type C 收敛目标) |

**迁移语义**:现存 Type C(schema 有、fields 无)按"未声明"处理——不阻塞执行,编排器标黄;接口维护者逐步把它们声明进 carry。schema(model/schema_)仍是结构真源,carry 是值通道声明,二者不重复记录值。

## 3. platform 值层存储

### 3.1 数据模型(PG 新表)

```
carry_service_binding   服务绑定表
  id            PK
  service_name  str, idx      # 目录服务名(deriveBase 解析产物,非用户引用键)
  field_path    str           # $.remark
  value         str|null      # 值;支持 ${var.x} 模板(逃生门:个别字段按场景微调)
  updated_by / updated_at
  UNIQUE(service_name, field_path)

carry_global_default     全局默认表(公用默认数据集)
  id            PK
  field_path    str, uniq     # $.appCode
  value         str|null
  updated_by / updated_at
```

### 3.2 API 面

- `GET/PUT /api/carry/defaults` —— 全局默认表整表读写;
- `GET /api/carry/bindings` / `GET/PUT /api/carry/bindings/{service}` —— 按服务读写;
- `GET /api/carry/bindings/{service}/fields` —— 该服务所有接口的 carry 字段面并集(后端查 plate `/full` 聚合,供配置页拉清单);
- 写权限:平台配置维护者(与 RunDialog 环境绑定同级别)。

## 4. 注入:materialize_run_copy 扩展

### 4.1 保持纯函数(预解析注入)

materialize 是纯函数(执行/导出同源等价测试锁死)。plate 查询是 IO,不进 materialize —— fanout/export 在 **dispatch 阶段预解析**,把结果作为参数传入:

```python
def materialize_run_copy(
    converted, *,
    service_bindings=None, resolved_auths=None, built_in_users=None,
    carry_context: CarryContext | None = None,     # 新增
) -> dict: ...

@dataclass(frozen=True)
class CarryContext:
    """dispatch 阶段预解析的注入上下文(纯值)。"""
    # step 索引 → 该 endpoint 声明的 carry 字段面(查 plate,经 view_hints.endpoint_id 锚点)
    step_fields: dict[int, frozenset[str]]
    service_bindings: dict[str, dict[str, str]]    # 目录服务名 → {path: 值}
    global_defaults: dict[str, str]                # path → 值
```

### 4.2 填充规则(无差别单条规则)

对每个 step:

1. 服务名解析:`deriveBase(step.api.service)` 得目录服务名;**解析失败 → 该 step 跳过填充 + 黄警**(沿用服务引用既有降级哲学,不阻塞执行);
2. 契约门控:候选 = `carry_context.step_fields[i]`(该 endpoint 声明的字段面);无锚点信息的 step(存量无 view_hints)→ 候选取服务绑定表 ∪ 全局默认表的键(降级门控,服务内字段面基本对齐的前提);
3. 取值链(逐键):`body 已有该键 → 跳过` > `服务绑定值` > `全局默认值`;两层都无 → 跳过(该字段本次不注入);
4. 写入:`setByPath(body, path, value)` —— 嵌套路径天然支持;值为 `${var.x}` 模板时,gimbal 运行时照常解析(与 body 既有模板同一通路)。

**值类型**:PG 两表 value 统一存 str。注入时按契约字段类型做一次宽松转换(数值型字段转 number / 布尔型转 boolean,转换失败保留原串)——与数据集行值 `_coerce_row_value` 的既有哲学一致(参照 vars 基线类型推断)。

### 4.3 导出链同源

导出(preview-plate overlay)走同一 materialize + 同一 carry_context 构造 → 导出物 body 含按当前绑定状态物化的值,脱平台自包含。导出是绑定值的**当时快照**,之后绑定变更不回改已导出文件(导出物快照语义,既有惯例)。

## 5. 编排期无感 + 只读预览

- FieldForm 主区、「其他字段」折叠区**不再出现** carry 字段(编排者零感知零维护);
- step 卡片挂只读提示"将注入 N 个非绑定字段"(字段面 ∩ 值表非空集),悬停可见清单与取值来源(服务绑定/全局默认);
- `deepDefaults` **停止**把 Type C schema default 拷进初始 body(该职责移交 carry 通道;绑定字段 default/example 拷贝行为不变)。

## 6. 配置入口(平台页面)

- 位置:平台导航新增"传递字段配置"入口(用户确认:平台须留对应入口;实现可分期,数据模型与 API 一期到位);
- **服务绑定页**:选服务(目录服务名)→ 自动拉该服务 carry 字段面并集(§3.2)→ 逐字段填值 → 存 `carry_service_binding`;界面同时展示全局默认值作 placeholder(未填时可见兜底);
- **全局默认区**:同页"全局默认"标签页,整表编辑;
- 编辑即生效:无缓存,下次执行/导出按新值物化(D1)。

## 7. 二期预留(本期不实现,不堵死)

| 预留 | 链位 | 说明 |
|---|---|---|
| 订单组绑定 | 取值链中间插"数据集行值" | materialize 在 fanout 逐行循环内,行值参与取值顺手;一期链位注释标明 |
| 环境分 profile | 服务绑定表加 env 维度 | 测试/生产通知人不同时启用 |
| 精确门控全覆盖 | — | 一期已按锚点门控,存量无锚点 step 用降级门控(§4.2.2),存量逐步补锚点后收敛 |

## 8. 兼容

- **存量场景**:body 已有值的键不被填充(填缺失语义),行为零变化;
- **gimbal 核心 schema 零改动**:carry 是 platform 侧概念,materialize 缝隙消费完,gimbal 只见完整 body;
- **等价测试**:materialize 新增参数默认 None(无 carry 上下文时行为与现状完全一致),既有黄金等价用例不破;
- **未声明字段**(Type C 存量):不注入、不阻塞,编排器黄警。

## 9. 测试策略

- plate:`CarryEntry` 校验(path 归一 / 与 fields[] 互斥 / extra=forbid)、`/full` 序列化含 carry、light 视图不含;
- materialize:纯函数逐规则用例(body 已有跳过 / 服务绑定优先 / 默认兜底 / 两层皆无跳过 / 嵌套路径 / 模板值透传 / 服务名解析失败降级黄警 / carry_context=None 行为等价现状);
- 等价:执行链与导出链同 carry_context → 逐字段相同输出(黄金等价用例扩展);
- API:两表 CRUD、字段面聚合端点;
- 前端:deepDefaults 不再拷 Type C 默认、step 只读注入提示、配置页读写流。

## 10. 验收

- [ ] plate `RequestSpec.carry` + CarryEntry 落地,校验与序列化如 §2;
- [ ] platform 两表 + API 如 §3;
- [ ] materialize carry_context 参数与填充规则如 §4,纯函数保持,等价测试扩展通过;
- [ ] deepDefaults 收敛 + 编排器只读提示如 §5;
- [ ] 配置入口页面如 §6(可分期,一期至少 API + 最小页面);
- [ ] 存量场景回归零变化;
- [ ] 二期链位(行覆盖 / env profile)以注释与表结构评审预留,不实现。
