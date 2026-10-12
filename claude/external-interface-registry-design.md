# 外部接口登记批 · 设计方案(v1.0 草案)

> 日期:2026-10-12　基线:`feat/plate-s1 @ ddc2eb40`
> 状态:**D1/D2/D3 已拍板(2026-10-12,本文件 §10)**,v1.0 定稿开工
> 依据:P1.0 三态接入拍板(external 落平台、plate 零改动)、2026-10-12 用户四项拍板
> (外部接口登记下一批=本批;倒排两盲区随批;G1 随批;pydantic-settings 随批顺手)。
> 原则:延续 P1.0 边界——**plate 侧与 M2 形态零改动**(external 不进 meta.system、
> 不进版本管理、不进对象池);登记的是「接口形状」不是「版本」。

## 0. 问题

external 步骤(第三方服务)现状 = 步骤内联手工维护(method/path/headers/body 存在
步骤定义里),执行链已通(service_aliases 解析 base_url),缺的是:

1. **结构化渲染**:编排器对 external 步骤无契约表单(无锚点 → 不读 plate /full,
   表单退化为 JSON);
2. **保存校验**:external 步骤的 body 无 schema 比对(多余/缺必填/类型不查);
3. **可发现性**:影响查询(倒排索引)对 external 步骤只有锚点行,断言引用全盲;
4. **G1**:执行器认证写死 md5(`call.py:185`),plate `binding.auth` 枚举
   (none/bearer/basic/cookie/custom)声明了但执行器从不消费。

## 1. 落点与边界(已定,不再议)

| 项 | 裁定 | 出处 |
|---|---|---|
| 目录的家 | **平台**(新表),不进 plate | P1.0 拍板(external 不进 meta.system/M11) |
| 三态语义不变 | kind=external 不触发预览、不阻塞集成、不入基线 | P1.0/版本模型 §6 |
| 集成卡合流 | 一次定义两处消费:集成任务的「外部系统定义」读同一目录(service 别名 + 接口目录) | P1.0 拍板 |
| plate ServiceDefinition.kind(G6) | **不合流**——那是集成线把 GitLab/Jenkins 收进 plate 管理的另一条路;本批 external 维持平台登记 | 本方案边界(见 §8) |
| M2 形态 | 零改动(不加 Call.auth 字段、不升代际);G1 在执行器/导出侧消费既有信息 | P1.0 + M2 §5 纪律 |

## 2. 数据模型(X1)

### 2.1 新表 `external_endpoints`(alembic 0021,与 via_vars 列同批)

```
external_endpoints
├─ id: int PK
├─ alias_name: str(128)  → service_aliases.alias_name FK
│    (登记前提:该别名 kind=external;plate 别名拒绝——错误码 alias_not_external)
├─ name: str(128)        接口名(别名内唯一,UK(alias_name, name))
├─ title: str(256)       展示名
├─ method: str(8)        GET|POST|PUT|PATCH|DELETE
├─ path: str(512)        URL 模式(/api/v1/orders/{id} —— 花括号为路径参数)
├─ request_schema: JSONB 可空
│    标准 JSON Schema(draft-07 子集;描述 request body;空 = 无形状约束)
├─ auth: str(16) default 'none'
│    语义对齐 plate binding.auth 枚举(none/bearer/basic/cookie/custom)——
│    描述被测接口自身的认证要求,保存校验与集成卡提示用;**执行器不读它**
│    (执行侧凭证注入走既有 service_bindings/credential_alias 链,G1 见 §6)
├─ notes: text 可空
├─ created_by / created_at / updated_at
└─ UK(alias_name, name);Index(alias_name)
```

**为什么是 JSON Schema 而不是 plate declarations 树**:① OpenAPI 导入零转换
(requestBody.content.*.schema 原样落);② 标准形态,登记方手写/工具生成两便;
③ declarations 树只服务表单渲染,由**后端单一转换函数**出(§4.2),不双写。

### 2.2 索引硬化(X3,同批 alembic)

`scenario_endpoint_refs` 加列 `via_vars: JSONB 可空`(全部 `${var.NAME}` 列表);
`via_var`(首变量)保留 —— 兼容读,消费方迁移后改读新列(表见 §5)。

## 3. 锚点语法(X2)—— ✅ 已定 A(2026-10-12 拍板)

external 步骤锚点 = `ext:<alias>.<name>`(写入既有 `step.endpoint` 字段,
M2 已有、平台视图字段)。冒号前缀与 plate 接口 id 空间(`<system>.<service>.
<name>` 点分)显式区分;`split(".")[0]` 系统前缀判定永不命中 ext;
`split(":")[0]=="ext"` 一眼可判。

**plate 兼容性(两方案同)**:dispatch/compose 发送 plate `/convert` 前
**剥离 ext 锚点**(读侧消费完即剥)——不赌 plate reproject 对未知 endpoint
前缀的行为,plate 侧严格零感知(与「无锚点原样通过」同款出口)。

## 4. 读侧与校验(X2)

### 4.1 目录读面(新路由族 `/api/external-endpoints`)

- `GET /api/external-endpoints?alias=&q=&page=` 列表(服务信息页/编排器下拉);
- `POST/PUT/DELETE` CRUD(kind=external 校验;别名非 external → 409 alias_not_external);
- `GET /api/external-endpoints/{alias}/{name}` 详情(出 §4.2 契约视图);
- `POST /api/external-endpoints/import-openapi` —— 上传 OpenAPI 文档(JSON/YAML)+
  目标别名 → 逐 path×method 建条目(已存在的同名条目跳过并报告;server URL
  写进别名 base_url 若为空)。预检(dry-run)+ apply 两段,沿用迁移纪律。

### 4.2 契约视图(表单数据源,与 plate /full 同形)

`{id: "ext:<alias>.<name>", method, path, request: {declarations: <树>}}` —— 
declarations 树由 `jsonschema_to_declarations(schema)` 转换:
- `properties.name` → `{name, path: "$.name", type, state: "form", required}`;
- `properties.x.properties.y` → 子节点挂 `children`(与 plate 目录树同形);
- `required` 数组 → 节点 required;`type` 映射(string/number/boolean/integer);
- 无 schema → `declarations: []`(表单退化自由编辑,与现状同,不炸)。

前端 `useEndpointFull` 加一条读分支:锚点 `ext:` 前缀 → 读平台目录详情,
缓存键同款;**编排器表单/字段状态/保存链零改造**(数据源同形)。

### 4.3 保存校验

`run_precheck` / dispatch 前的既有校验钩子里加 external 分支:
body 逐步骤比对 JSON Schema(多余字段警告、必填缺失与类型不符 422 阻塞)——
复用 M3 比对的输出语义,实现走 `jsonschema` 校验器(已在依赖面?待核实,
缺则加)或手写子集比对(**推荐手写子集**:只支持 object/string/number/boolean/
array + required,与转换器同一套类型映射,不引运行时依赖)。
✅ **external 校验失败不阻塞保存、只告警**(2026-10-12 拍板 D2:登记是
增强不是权威,第三方 schema 可能过时,不卡死保存)。

## 5. 倒排索引硬化(X3)

`endpoint_ref_index.parse_refs` 两处扩展:

1. **断言侧**:遍历 `payload.assertion_registry.entries[].path`
   `{stepIndex, source, jsonpath}` → 每条目一行:`source="assertion"`、
   `field_name=jsonpath 根段`、`endpoint_id=该步骤锚点(含 ext: 锚)`、
   via_var(s) 不适用(NULL)。断言条目 jsonpath 指向的是**响应**(source=
   body/headers 语义不同),故独立 source 值,不与字段行混淆。
2. **via_vars**:字段值内全部 `${var.NAME}` 收进 `via_vars`(JSON 数组),
   `via_var` 保留首变量(兼容)。影响查询(plates 删改接口时「谁引用了」)
   消费方改读新列,WHERE 用 JSONB contains。

断言侧行入索引后,`sync_scenario` 幂等性/删除链不变(同表同主键结构)。

## 6. G1:执行器认证施加(X4)

现状:`call.py:165 login()` 只产 `token=md5(session.token+timestamp)`,
plate `binding.auth` 五枚举零消费;评审确认 G1 属实(自举线前置:
platform 自举端点声明 bearer,执行器只会 md5)。

修法(**按 2026-10-09 架构评审待拍板建议 B**——保留枚举语义,签名器具名):

1. **执行器分派**:`login()` 按会话凭证形状分派 —— token_type=bearer →
   `Authorization: Bearer <token>`;basic → `Authorization: Basic base64(u:p)`;
   cookie → `Cookie: <token_type>=<token>`(或 session 自带 cookie 字段);
   无分派命中 → 保留现 md5 签名头(具名 `auth_signer="md5sign"`,
   特征化用例不破)。
2. **形状从哪来**:平台物化 users 时已带 UserCredential(url/username/password/
   token_type/…,M2 生成物)——执行器读会话的 `token_type`/凭证形状即可,
   **不需要 plate 透传 binding.auth**(M2 零改动的关键:auth 施加由凭证
   形状驱动,binding.auth 声明仅继续服务画像投影)。
3. `auth_signer` 记录进明细行(G7 的 error_kind 语义铺垫,但不做 G7——
   G7 并 task3c)。

验收:platform 自举场景(bearer 声明)经凭证 token_type=bearer 执行时
头为 Bearer;既有 md5 场景(特征化)逐字节不变。

## 7. plate 启动配置化(X5,pydantic-settings)

`run_plate.py` 读 `.env`/环境变量(`PLATE_ARTIFACTS_PATH` 已是进程环境变量;
补 `PLATE_HOST/PLATE_PORT/PLATE_LOG_LEVEL`),uvicorn 参数从 settings 出;
`gimbal_plate` 不引 pydantic-settings 依赖(纯 launcher 局部读,零包依赖面)。

## 8. 不做与边界

- **plate ServiceDefinition.kind(G6)/GitLab/Jenkins 系统定义**:集成线 P2 自己的
  排期;本批 external 全部走平台目录。若未来某外部系统要进 plate 管理,
  属「系统接入运行手册」的正向接入(注册系统树→评审→发版),与 external
  目录是两条路,不互斥。
- **G2(outputs)/G7(error_kind)/personal 模式**:不属本批(已拍板去向)。
- **M2/Call 形态、代际**:零改动。
- **external 接口的「版本」**:目录无版本概念(第三方 API 版本体现在 path/
  另建别名);不引入修订/冷化语义。

## 9. 波次与验收门

| # | 内容 | 规模 | 验收 |
|---|---|---|---|
| X1 | 表+CRUD+OpenAPI 导入(演练/apply) | M | CRUD 用例;导入幂等报告 |
| X2 | ext 锚点 + 契约视图 + 表单 + 保存校验 | M | 编排器 external 步骤结构化表单可渲染;校验分态;三侧零回归 |
| X3 | 索引两盲区 | S | 断言行/via_vars 入索引;影响查询可见断言引用 |
| X4 | G1 分派+具名化 | S/M | bearer/basic/cookie 三态用例;md5 特征化不破 |
| X5 | run_plate 配置化 | S | 环境变量生效 |

提交分组:X1 → (X2) → X3 → X4 → X5;每组过三侧门(后端 pytest / 前端
vitest+vue-tsc / plate pytest 不涉及则后端两门)。

## 10. 决策记录(2026-10-12 用户拍板)

- **D1 锚点语法 = A** `ext:<alias>.<name>`(冒号前缀,零撞名面)。
- **D2 保存校验强度 = 告警放行**(不 422;多余/缺必填/类型不符全告警)。
- **D3 via_vars 列形态 = 新 JSONB 列**(via_var 首变量保留兼容读;用户跳过,
  按推荐项执行)。
