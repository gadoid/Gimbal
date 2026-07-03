# fin 模块(金融服务契约包)

> 路径:`src/Plate/fin/`
> 文档版本:对应源码 commit `e0be7bf` 之后的 fin 包内容(31 个端点)
> 文档目标读者:第一次接触 Gimbal Plate 子系统的工程师 / 测试架构师 / 自动化平台作者

## 0. 写在最前面(给"完全不了解的人"的话)

如果你从来没听过 `Gimbal` / `Plate` / `fin` 这三个名词,请先按以下顺序阅读:

1. [../overview.md](../overview.md) — 整个 Plate 子系统是什么、解决什么问题、为什么这么设计
2. [../core/README.md](../core/README.md) — `registry` 是什么、怎么收集服务、怎么解析端点
3. [../spec/README.md](../spec/README.md) — `EndpointSpec` 是什么、字段含义、契约保真护栏

读完这三份文档之后,你应该能理解下面这句话:

> **"fin 是一个 Plate 服务(打包在 `Plate/fin/` 下),它以 31 个 `EndpointSpec` 的形式声明了"委托单 → 订单 → 订单费 → 审核 → 收款 → 收票 → 核销"这一条业务主链上 Gin 后端暴露的全部 HTTP 端点;同时,所有 31 套请求/响应结构在 `models.py` 中以 Pydantic v2 数据类形式落盘,供 mock / AI skill / 文档生成器复用。"**

下面是这份文档的目录。本文档的承诺:**每一个数据类、每一个 spec、每一个 `category` 决策、每一条 binding,都解释"它是什么"和"为什么这样写它"**。

```
1. 模块定位与目录结构
2. __init__.py        ─ 31 个 spec 的 re-export + 通用 envelope
3. endpoints.py       ─ 31 个 EndpointSpec 实例
4. models.py          ─ 全部 Pydantic 数据类(请求 / 响应 / 共享类型)
5. dannotations/__init__.py ─ L2 人工注释层
6. 31 个端点的全景业务图
7. 设计哲学与决策记录
8. 典型使用示例
9. 不变量总结
10. 设计权衡与未来工作
```

---

## 1. 模块定位与目录结构

`Plate/fin/` 是一个 **完整的服务契约包**(Service Contract Package)。它的存在意义是把"业务后端(假设叫 fin-api)的 31 个端点的请求/响应形状"在 Plate 子系统内做成 **机器可读的纯 Python 资产**,从而被以下消费者复用:

| 消费者          | 怎么用 fin                                    |
| --------------- | --------------------------------------------- |
| Mock 服务器     | 把 `EndpointSpec.request` 喂给 `PlateClient`  |
| AI skill / Agent| 通过 `registry.resolve("fin", method, path)` 查 `summary` / `tags` / `bindings` |
| 文档生成器      | `api_doc` 子模块读取 spec,渲染 Markdown 表格  |
| 兼容性回归      | `manifest.compute_checksum` 拿 31 个 spec 的 SHA256 校验完整性 |

目录物理布局(在 PR-C 单轨化之后):

```
Plate/fin/
├── __init__.py          ← re-export 31 个 EndpointSpec + CommonResponseEnvelope
├── endpoints.py         ← 31 个 EndpointSpec 模块级常量(全大写 / 全 snake_case 命名)
├── models.py            ← 所有 Pydantic 数据类(_Base / 共享 / per-endpoint)
└── dannotations/
    └── __init__.py      ← L2 人工注释层(本 PR 为空壳)
```

> **为什么把 endpoints 和 models 拆成两个文件而不是一个?**
> 答案来自 `spec.py` 的"物理分层"原则(见 [../spec/README.md](../spec/README.md) 的 L1/L2 章节):`endpoints.py` 是"机器可重生的元数据",`models.py` 是"人类从 wire 抓下来后精修的形状",两者用 `__init__.py` 粘起来但物理隔离 — 未来如果用 codegen 自动生成 `endpoints.py`,只需要 import 不需要碰 `models.py`。

---

## 2. `__init__.py` ── 31 个 spec 的 re-export + 通用 envelope

**职责**:把 `endpoints.py` 里 31 个 `EndpointSpec` 模块级常量 + `models.py` 里的 `CommonResponseEnvelope` 统一导出,作为 `from Plate.fin import orderDetail` 这种"按名取 spec"语法的物质基础。

### 2.1 文件物理结构(8 个 ASCII 段)

| 段号 | 行号范围 | 内容                                |
| ---- | -------- | ----------------------------------- |
| 1    | L1–L15   | 模块 docstring(目录结构 + 典型用法) |
| 2    | L16–L57  | 31 个 `EndpointSpec` 名字的 re-import |
| 3    | L60      | `CommonResponseEnvelope` 的 re-import |
| 4    | L62–L98  | `__all__` 列表                      |

### 2.2 31 个名字的归类(从 `endpoints.py` 同名常量同步过来)

下表覆盖了 31 个 spec 在业务主链上的角色分组(顺序就是文件里 `__all__` 的顺序,也是 `endpoints.py` 中 9 个 ASCII 注释段的顺序):

| #   | 名称                              | 业务组        | category     | mutates_state |
| --- | --------------------------------- | ------------- | ------------ | ------------- |
| 1   | `orderEntrustOrderPage`           | orderEntrust  | QUERY        | False         |
| 2   | `orderEntrustOrderAdd`            | orderEntrust  | BUSINESS     | True          |
| 3   | `orderDetail`                     | order         | QUERY        | False         |
| 4   | `orderAdd`                        | order         | BUSINESS     | True          |
| 5   | `orderBook`                       | order         | BUSINESS     | True          |
| 6   | `checkGenerateOrderSub`           | order         | QUERY        | False         |
| 7   | `generateOrderSub`                | order         | BUSINESS     | True          |
| 8   | `changeInvoiceApply`              | order         | BUSINESS     | True          |
| 9   | `orderConfirmAccount`             | order         | BUSINESS     | True          |
| 10  | `toggleRealAmount`                | orderFee      | BUSINESS     | True          |
| 11  | `bookRealAmountEdit`              | orderFee      | BUSINESS     | True          |
| 12  | `realAmountLockSubmit`            | orderFee      | BUSINESS     | True          |
| 13  | `auditPage`                       | home/audit    | QUERY        | False         |
| 14  | `auditDetail`                     | home/audit    | QUERY        | False         |
| 15  | `auditExecute`                    | home/audit    | BUSINESS     | True          |
| 16  | `financePutList`                  | finance/accFee| QUERY        | False         |
| 17  | `orderReceiveAccountEdit`         | finance/recv  | BUSINESS     | True          |
| 18  | `receiveAccountDetail`            | finance/recv  | QUERY        | False         |
| 19  | `receiveConfirmList`              | finance/recv  | QUERY        | False         |
| 20  | `accountConfirm`                  | finance/recv  | BUSINESS     | True          |
| 21  | `applyPage`                       | ReceiveBatch  | QUERY        | False         |
| 22  | `checkStep1`                      | ReceiveBatch  | QUERY        | False         |
| 23  | `checkStep2`                      | ReceiveBatch  | QUERY        | False         |
| 24  | `batchOrderEdit`                  | ReceiveBatch  | BUSINESS     | True          |
| 25  | `batchDetail`                     | ReceiveBatch  | QUERY        | False         |
| 26  | `applyDetail`                     | ReceiveBatch  | QUERY        | False         |
| 27  | `invoiceAddCheck`                 | receiveInv    | QUERY        | False         |
| 28  | `invoiceAdd`                      | receiveInv    | BUSINESS     | True          |
| 29  | `orderFeePage`                    | writeoff      | QUERY        | False         |
| 30  | `writeoffBatch`                   | writeoff      | BUSINESS     | True          |
| 31  | `writeoffPage`                    | writeoff      | QUERY        | False         |

> 数量级校验:BUSINESS = 14、QUERY = 17、TOOL = 0 — 与 `endpoints.py` 文件 docstring 中的"PR-C review 拍板"分布完全一致。

### 2.3 `CommonResponseEnvelope` 的意义

`CommonResponseEnvelope` 是 31 个端点里 **每一个** 都引用的"通用响应壳"。它的字段:

```python
class CommonResponseEnvelope(_Base):
    code: int | None = None        # 业务返回码(0 / 非 0)
    msg: str | None = None         # 中文/英文错误信息
    request_id: str | None = None  # 链路追踪 ID
    data: Any | None = None        # 业务负载 —— 各端点形状不同
```

为什么它在 `fin/__init__.py` 里 re-export 而不是只在 `models.py` 里?

- 上层消费方可能想"import 通用壳但不需要 import 全部 31 个 spec"(例如某个 mock 脚本只需要做 envelope 层面的检查)
- 它是横切关注点(cross-cutting concern),不应该藏在 `models.py` 内
- `api_doc/render.py` 在渲染 envelope 字段时,只 import 这个名字就够了

### 2.4 命名约定的"为什么"

- **小驼峰首字母大写**:`orderDetail` 而不是 `order_detail`,直接复用原 Gin handler 命名 — 这样 wire 抓包 / handler 名 / spec 名三者无翻译成本
- **没有 `Ep` / `Spec` 后缀**:这 31 个名字是模块级常量,导入路径 `Plate.fin.orderDetail` 已经暗示它是 spec,不需要在名字里再重复一次
- **`OrderAdd` / `OrderEntrustOrderAdd` 区分**:哪怕动词都是 "Add",业务实体不同就完整拼出 — 缩写在 6 个月后没人看得懂

---

## 3. `endpoints.py` ── 31 个 EndpointSpec 实例

**职责**:把 31 个端点以 **模块级常量** 的形式钉在 Python 进程地址空间内,供 `registry.collect("fin")` 在第一次访问 fin 服务时 `dir()` 式拉取并灌进 registry。

### 3.1 文件物理结构

`endpoints.py` 由 9 个 ASCII 段(`# ═══...═══` 隔开)组成,每段对应一个业务组:

```
1. orderEntrust ── 委托单(2 个端点)
2. order        ── 订单主数据(7 个端点)
3. orderFee     ── 订单费用(3 个端点)
4. home/audit   ── 审核工作台(3 个端点)
5. finance/accountFee      ── 财务手续费(1 个端点)
6. finance/receiveAccount  ── 收款账户(4 个端点)
7. finance/ReceiveInvoiceBatch ── 收票批量(6 个端点,注意大小写不规则)
8. finance/receiveInvoice  ── 收票(2 个端点)
9. finance/receiveWriteoff ── 收款核销(3 个端点)
```

> **为什么 `ReceiveInvoiceBatch` 路径首字母大写,而其他 8 个组都是小写?**
> 这是 **真实 Gin 路由表的字面照抄** — 早期后端同学写路由时手抖把这个 segment 写成了大写,后来业务依赖了这个 URL 形式,改不动了。Plate 设计的原则是 **"契约 = 实际 wire"**,所以不"修正"它、不"归一化"它,而是用一行注释把它钉在文档里(见 endpoints.py L355 的注释 "路径大小写不规则,保留")。

### 3.2 每个 EndpointSpec 的字段意义

`EndpointSpec` 的完整字段定义见 [../spec/README.md](../spec/README.md)。下面以 `# 4.2 auditDetail` 为例,把所有字段的实际取值列出来:

```python
auditDetail = EndpointSpec(
    method="POST",                                                # HTTP method
    path="/api/home/audit/auditDetail",                           # wire path
    category=EndpointCategory.QUERY,                              # 业务分类
    mutates_state=False,                                          # CT 主动探测用
    request=AuditDetailRequest,                                   # 请求数据类
    responses={200: CommonResponseEnvelope},                      # 响应表
    response_data_models={200: AuditDetailData},                  # 200 的 data 形状
    bindings=(                                                   # 跨端点数据流
        FieldBinding(
            from_path=("data", "audit_id"),
            to_path=("audit_id",),
            required=True,
        ),
    ),
    summary="审核详情查询",                                       # 中文一句话
    tags=["audit", "detail", "query"],                            # 业务标签
)
```

| 字段                  | 这个 spec 怎么填                                  | 为什么这样填                                          |
| --------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| `method`              | 全部 31 个都是 `POST`                              | 后端一律用 POST + JSON body(没有 GET/RESTful 风格)     |
| `path`                | 字面照抄 Gin 路由                                 | wire 必须 1:1 复现,大小写不修正                       |
| `category`            | `BUSINESS` / `QUERY` / `TOOL`                     | 用于 AI skill 决策"能不能主动 call 它"                 |
| `mutates_state`       | BUSINESS = True,QUERY = False,TOOL = False        | CT 框架做"主动探测"时跳过 mutates_state=True 的端点     |
| `request`             | `XxxRequest`(`models.py` 定义)                    | mock 时校验入参形状                                    |
| `responses`           | `{200: CommonResponseEnvelope}`                   | 所有 200 共享 envelope                                |
| `response_data_models`| 仅"高频/有 data 形状"的端点填(8 个)              | 见下文 §3.4 详解                                       |
| `bindings`            | 5 个端点有(`auditDetail`/`checkStep1`/`checkStep2`/`batchDetail`/`applyDetail`) | 声明"上游端点 data 里的某个字段喂给本端点 request"      |
| `summary`             | 中文,人读                                        | AI skill 上下文用                                      |
| `tags`                | 业务标签,3–4 个英文小写词                        | mock 路由 / 上下文过滤用                              |

### 3.3 `category` 决策的"为什么"

PR-C review 拍板了 **BUSINESS=14、QUERY=17、TOOL=0** 的分布。决策原则:

- **BUSINESS**:调用它会改写后端持久层数据(创建 / 修改 / 提交 / 锁定)
- **QUERY**:纯读,不改后端数据(分页 / 详情 / 校验)
- **TOOL**:原意是"工具型端点,既不改数据也不读业务数据(比如服务端 ping)",fin 服务没有

几个边界案例的归类:

| 端点                | 分类       | 归类理由                                              |
| ------------------- | ---------- | ----------------------------------------------------- |
| `checkGenerateOrderSub` | QUERY    | 后端实现是 dry-run,不改数据库;但语义上"准备生成子单"有歧义。决策按"不写库"归 QUERY |
| `checkStep1`/`checkStep2` | QUERY | 后端是 validation,不改库                              |
| `auditExecute`      | BUSINESS   | 改审核状态(写库)                                     |
| `toggleRealAmount`  | BUSINESS   | 改金额确认状态(写库)                                 |
| `changeInvoiceApply`| BUSINESS   | 启动一个新审核流(写库)                               |

### 3.4 `response_data_models` 为什么只有 8 个端点填了?

填了的 8 个:`orderEntrustOrderPage` / `orderDetail` / `checkGenerateOrderSub` / `orderConfirmAccount` / `toggleRealAmount` / `orderReceiveAccountEdit` / `receiveAccountDetail` / `auditPage` / `auditDetail` / `applyPage` / `writeoffPage` ... 实际是 11 个。

为什么不 31 个全填?

1. **数据形状不明确**:有些端点的 `data` 是 `null`,或者在不同请求下形状会变(比如 `batchOrderEdit` 写完后只回 `{code, msg, request_id}` 不带 `data`)
2. **业务负载太大**:比如 `OrderDetailData` 实际有 200+ 字段(ES 文档全字段),`OrderEntrustOrderPageItem` 同样 200+,模型只挑了 7 个最关键字段
3. **响应里的 list 元素用 `Any`**:例如 `_ApplyPageItem` 实际有 40+ 字段,精确建模收益低(下游消费方一般只读 2–3 个)

不填 `response_data_models` 的端点,`response.data` 退化成 `Any | None`,mock 框架做"shape 校验"时会放过它。这是 **有意为之** 的"低保真",因为精确建模的 ROI 不高。

### 3.5 `bindings` 字段的 5 个用例详解

`bindings` 是 Plate 子系统的 **跨端点数据流声明**(详见 [../binding/README.md](../binding/README.md))。在 fin 的 31 个 spec 中,有 5 个端点声明了 binding:

| spec             | from_path                          | to_path                       | 业务含义                                          |
| ---------------- | ---------------------------------- | ----------------------------- | ------------------------------------------------- |
| `auditDetail`    | `("data", "audit_id")`             | `("audit_id",)`               | auditPage 分页列表里的 audit_id 直接喂 auditDetail |
| `checkStep1`     | `("data", "receive_invoice_batch_id")` | `("receive_invoice_batch_id",)` | applyPage 列表里的 batch_id 直接喂 checkStep1    |
| `checkStep2`     | 同上                              | 同上                          | applyPage → checkStep2 的数据流                   |
| `batchDetail`    | 同上                              | 同上                          | applyPage → batchDetail 的数据流                  |
| `applyDetail`    | `("data", "receive_invoice_apply_id")` | `("receive_invoice_apply_id",)` | applyPage 列表里的 apply_id 直接喂 applyDetail   |

> **为什么 5 个 binding 全部来自 `applyPage` / `auditPage` 列表?**
> 因为这两个是 **入口查询端点**,它们的响应 `data[].xxx_id` 是后端所有"详情类"端点的入口参数。在 mock 框架里,AI skill 不需要关心这个 ID 从哪儿来 — binding 声明让 mock 自动从"上一次调用"的响应里抽出 ID,塞进"下一次调用"的请求。这是 **Plate 把"调用图"建模在 spec 里、而不是建模在业务代码里** 的关键体现。

---

## 4. `models.py` ── 全部 Pydantic 数据类

**职责**:把 31 个端点的请求体、响应 `data` 体,以 Pydantic v2 `BaseModel` 子类的形式落盘。**只描述形状,不做任何业务校验**。

### 4.1 文件结构(1331 行,11 个 ASCII 段 + 导出段)

```
L1–L40    通用:docstring + _SAFE_CONFIG + _Base
L42–L60   通用模型:Params / CommonResponseEnvelope
L62–L99   1. orderEntrust/orderPage
L100–L123 2. orderEntrust/orderAdd + PermissiveRequest
L126–L148 3. order/orderDetail
L151–L233 4. orderFee/toggleRealAmount(嵌套结构最复杂的几个)
L235–L290 5. orderFee/bookRealAmountEdit
L292–L333 6. order/checkGenerateOrderSub
L335–L341 7. order/generateOrderSub
L344–L356 8. orderFee/realAmountLockSubmit
L359–L411 9. home/audit/auditPage
L414–L513 10. home/audit/auditDetail(有 @model_validator 处理 `del` 关键字)
L516–L525 11. home/audit/auditExecute
L527–L546 12. order/changeInvoiceApply
L548–L594 13. order/orderConfirmAccount
L596–L678 14. finance/accountFee/financePutList
L680–L711 15. finance/receiveAccount/orderReceiveAccountEdit
L713–L728 16. finance/receiveAccount/receiveAccountDetail
L730–L764 17. finance/receiveAccount/receiveConfirmList
L766–L775 18. finance/receiveAccount/accountConfirm
L777–L864 19. Finance/ReceiveInvoiceBatch/applyPage
L866–L928 20. checkStep1
L930–L993 21. checkStep2
L996–L1065 22. batchOrderEdit
L1067–L1074 23. batchDetail
L1076–L1083 24. applyDetail
L1085–L1116 25. finance/receiveInvoice/invoiceAddCheck
L1118–L1137 26. invoiceAdd(用 @model_validator 把 list 包成 dict)
L1140–L1148 27. finance/receiveWriteoff/orderFeePage
L1150–L1177 28. writeoffBatch
L1179–L1257 29. writeoffPage
L1262–L1330 __all__ 导出列表
```

### 4.2 `_SAFE_CONFIG` 与 `_Base` ── "契约保真"基类

```python
_SAFE_CONFIG: ConfigDict = ConfigDict(
    extra="forbid",                  # 拒绝未声明字段
    str_strip_whitespace=False,      # 保留 wire 上的空白
    coerce_numbers_to_str=False,     # 不把数字偷偷变字符串
    use_enum_values=False,           # 保留 enum 原型,不取 .value
)


class _Base(BaseModel):
    model_config = _SAFE_CONFIG
```

`_SAFE_CONFIG` 与 `spec.py` 里的 `_FORBIDDEN_CONFIG_KEYS` 是孪生概念。两者协同保证:

- `extra="forbid"` — 拒绝模型里没声明的字段(mock 时多塞一个 key 就报错)
- `str_strip_whitespace=False` — wire 上的 `"foo "` 不被偷偷改成 `"foo"`
- `coerce_numbers_to_str=False` — `"1"` 不会被偷偷改成 `1`
- `use_enum_values=False` — `Enum.A` 在 dump 时仍是 `Enum.A`,不是 `"A"`

**为什么这些默认都要关?** Pydantic 的默认行为倾向于"宽容+归一化",但在做 API 契约测试时,宽容 = 漏检 = 后端悄悄改字段你也看不出来。Plate 选 **严格保真** 的另一面。

### 4.3 `CommonResponseEnvelope` 与 `Params`

`CommonResponseEnvelope` 已在 §2.3 详述。`Params` 是一个空类(只继承 `_Base`):

```python
class Params(_Base):
    """通用分页 ``params`` 容器(原接口常出现 ``{}``,列字段用以表达可能键)。"""
    model_config = _SAFE_CONFIG
```

它存在的意义是:`extra="forbid"` 模式下,`OrderEntrustOrderPageRequest.params: Params` 字段如果不声明类型,Pydantic 会拒收 `{}`。声明一个空 `_Base` 子类就是告诉 Pydantic"空 dict 也是合法的 Params"。

### 4.4 `PermissiveRequest` ── 高字段数端点的兜底

```python
class PermissiveRequest(_Base):
    """通用"高字段数 + 多类型"请求体,用于字段 > 100 的端点。"""
    model_config = ConfigDict(extra="ignore")
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)


# 3 个高字段数端点共用此模型
OrderEntrustOrderAddRequest = PermissiveRequest
OrderAddRequest = PermissiveRequest
OrderBookRequest = PermissiveRequest
```

> **为什么不精确建模 `orderAdd` / `orderBook`?**
> 这两个端点的 wire 抓样本体积 200+ 字段,其中大量字段在同一样本里类型不一致(同一字段可能是 `str` / `int` / `null` / `list[dict]`)— 这意味着后端对这些字段的 schema 是不严格控的。如果强行声明每个字段的类型,模型会和真实 wire 漂移。`PermissiveRequest` 表达"我承认我不知道里面是什么形状",mock 框架对它只做"合法 JSON + 能解析"两个最低保证。

### 4.5 `_AuditExt` 的 `del` 关键字处理

```python
class _AuditExt(_Base):
    model_config = ConfigDict(extra="ignore")
    del_: str | None = None  # wire key: "del"(Python 关键字,改名 + alias)

    @model_validator(mode="before")
    @classmethod
    def _accept_del_alias(cls, data: Any) -> Any:
        """接受 ``"del"`` 原始键:本字段在 wire 中名为 ``del``(Python 关键字)。"""
        if isinstance(data, dict) and "del" in data and "del_" not in data:
            data = {**data, "del_": data.pop("del")}
        return data
```

这是 **全文件唯一一处显式 @model_validator**(另一个是 `InvoiceAddRequest` 的 list-wrap)。

**为什么不用 `Field(alias="del")`?** 因为本类整体是 `extra="ignore"`,而 Pydantic v2 + alias 在 ignore 模式下行为不稳定(在某些版本下 alias 会被当成"未知字段"丢掉)。改用 `model_validator(mode="before")` 在最早期把 `del` 重命名到 `del_`,这是 **显式且可读** 的处理路径。

**为什么不直接用 `del_` 让 mock 自己用 `del_`?** 因为 wire 抓样是 `del`,如果 mock 框架要把"测试入参"反向 dump 回 wire 格式,字段名必须等于 wire 字段名 — `del_` 在 dump 阶段会变成 `del_`,跟 wire 不一致,后端拒收。所以字段名 `del_` 只是 Python 侧内部表达,真正的 wire key 在 Pydantic 模型上由 mode="before" 的 validator 在入参时做 `del` → `del_` 翻译。

### 4.6 `InvoiceAddRequest` 的 list-wrap

```python
class InvoiceAddRequest(_Base):
    @model_validator(mode="before")
    @classmethod
    def _wrap_list(cls, data: Any) -> Any:
        if isinstance(data, list):
            return {"_root": data}
        return data

    _root: list[Any] | None = None
```

> **为什么需要这层 wrap?**
> `invoiceAdd` 的 wire body 实际是 `list[dict]`,而不是通常的 `dict`。Pydantic v2 BaseModel 默认从 `dict` 构造,不能直接接 list — 必须先包成 `{"_root": list}` 内部表达,再让 Pydantic 解析 `_root` 字段。下划线前缀 `_root` 是 Pydantic v2 内部对 RootModel 的隐式命名习惯 — 表示"这个字段就是根"。

### 4.7 9 个共享辅助类的"轻量命名"约定

很多私有类(以 `_` 开头)被多个响应类引用,比如:

| 私有类                | 被谁用                                              |
| --------------------- | --------------------------------------------------- |
| `_MoneyBlock`         | `_SettleSideItem`                                   |
| `_SettleSideItem`     | `ToggleRealAmountData`                              |
| `_AmountSummary`      | `ToggleRealAmountData`                              |
| `_StandardListItem`   | `_ToSideAmount`                                     |
| `_ToSideAmount`       | `_ToSideBlock`                                      |
| `_ToSideBlock`        | `BookRealAmountEditRequest`                         |
| `_FeeItem`            | `CheckGenerateOrderSubData`                         |
| `_OrderBookItem`      | `CheckGenerateOrderSubData`                         |
| `_AuditBasic`         | `AuditDetailData`                                   |
| `_AuditContent`       | `AuditDetailData`                                   |
| `_AuditRecordItem`    | `AuditDetailData`                                   |
| `_AuditExt`           | `AuditDetailData`(带 `del` 关键字处理)              |
| `_AuditProcessItem`   | `AuditDetailData`                                   |
| `_CarbonCopyItem`     | `AuditDetailData`                                   |
| `_FinancePutListItem` | `FinancePutListData`                                |
| `_ReceiveConfirmListItem` | `ReceiveConfirmList` 注释提示 "data: list[...]"    |
| `_ApplyPageItem`      | `ApplyPageData`                                     |
| `_ApplyPageTotalData` | `ApplyPageData`                                     |
| `_WriteoffPageItem`   | `WriteoffPageData`                                  |
| `_WriteoffPageTotalData` | `WriteoffPageData`                              |
| `_ConfirmAccountCurrencyBlock` | `OrderConfirmAccountData`                   |
| `_ConfirmAccountBlock`| `OrderConfirmAccountData`                           |
| `_ChangeInvoiceAuditMsg` | `ChangeInvoiceApplyRequest`                      |

下划线前缀表示"模块私有,不应被外部 import"。文件级 `__all__` 没有导出它们,只导出真正的 31 套端点 Request/Data 类。

### 4.8 命名约定的细节

| 字段命名                  | 例子                            | 为什么这样                                            |
| ------------------------- | ------------------------------- | ----------------------------------------------------- |
| 完全照抄 wire 字段名      | `cny_file` / `usd_file`         | 不做 camelCase ↔ snake_case 转换                     |
| Python 关键字加下划线后缀 | `del_`                          | 字段名等于 wire,但 Python 不能用 `del`               |
| 时间字段全部 `str | None` | `create_time: str | None = None` | 后端时间字段无统一格式(有 ISO、有 `yyyy-MM-dd HH:mm:ss`、有时间戳字符串) |
| 金额字段全部 `str | None` | `unit_price: str | None = None` | 后端用字符串存金额(避免 float 精度漂移)               |
| 难以类型化的字段用 `Any`  | `audit_msg: Any | None = None`  | 实际 wire 中是嵌套对象、字符串、列表、字典都出现过     |
| `extra="ignore"` 而非 `forbid` | 数据模型基本都用 ignore  | 业务数据类字段集大,精确建模 ROI 低,放过未知 key      |
| `extra="forbid"` 仅在 `_Base` 用 | 仅在基类默认             | 基础请求类需要严格(mock 时早报错)                    |

### 4.9 31 套数据类的全清单

下表是 `models.py` 中全部的 31 套 `Request` / `Data` 类(按 endpoints 顺序):

| #   | endpoint                              | Request 类                | Data 类                  |
| --- | ------------------------------------- | ------------------------- | ------------------------ |
| 1   | `orderEntrustOrderPage`               | `OrderEntrustOrderPageRequest` | `OrderEntrustOrderPageData` |
| 2   | `orderEntrustOrderAdd`                | `OrderEntrustOrderAddRequest` (≡ PermissiveRequest) | —                        |
| 3   | `orderDetail`                         | `OrderDetailRequest`      | `OrderDetailData`        |
| 4   | `orderAdd`                            | `OrderAddRequest` (≡ PermissiveRequest) | —                        |
| 5   | `orderBook`                           | `OrderBookRequest` (≡ PermissiveRequest) | —                        |
| 6   | `checkGenerateOrderSub`               | `CheckGenerateOrderSubRequest` | `CheckGenerateOrderSubData` |
| 7   | `generateOrderSub`                    | `GenerateOrderSubRequest` | —                        |
| 8   | `changeInvoiceApply`                  | `ChangeInvoiceApplyRequest` | —                      |
| 9   | `orderConfirmAccount`                 | `OrderConfirmAccountRequest` | `OrderConfirmAccountData` |
| 10  | `toggleRealAmount`                    | `ToggleRealAmountRequest` | `ToggleRealAmountData`   |
| 11  | `bookRealAmountEdit`                  | `BookRealAmountEditRequest` | —                      |
| 12  | `realAmountLockSubmit`                | `RealAmountLockSubmitRequest` | —                    |
| 13  | `auditPage`                           | `AuditPageRequest`        | `AuditPageData`          |
| 14  | `auditDetail`                         | `AuditDetailRequest`      | `AuditDetailData`        |
| 15  | `auditExecute`                        | `AuditExecuteRequest`     | —                        |
| 16  | `financePutList`                      | `FinancePutListRequest`   | `FinancePutListData`     |
| 17  | `orderReceiveAccountEdit`             | `OrderReceiveAccountEditRequest` | `OrderReceiveAccountData` |
| 18  | `receiveAccountDetail`                | `ReceiveAccountDetailRequest` | `ReceiveAccountDetailData` |
| 19  | `receiveConfirmList`                  | `ReceiveConfirmListRequest` | — (注释提示 data: list[_ReceiveConfirmListItem]) |
| 20  | `accountConfirm`                      | `AccountConfirmRequest`   | —                        |
| 21  | `applyPage`                           | `ApplyPageRequest`        | `ApplyPageData`          |
| 22  | `checkStep1`                          | `CheckStep1Request`       | —                        |
| 23  | `checkStep2`                          | `CheckStep2Request`       | —                        |
| 24  | `batchOrderEdit`                      | `BatchOrderEditRequest`   | —                        |
| 25  | `batchDetail`                         | `BatchDetailRequest`      | —                        |
| 26  | `applyDetail`                         | `ApplyDetailRequest`      | —                        |
| 27  | `invoiceAddCheck`                     | `InvoiceAddCheckRequest`  | —                        |
| 28  | `invoiceAdd`                          | `InvoiceAddRequest` (list-wrap validator) | — |
| 29  | `orderFeePage`                        | `OrderFeePageRequest`     | —                        |
| 30  | `writeoffBatch`                       | `WriteoffBatchRequest`    | —                        |
| 31  | `writeoffPage`                        | `WriteoffPageRequest`     | `WriteoffPageData`       |

`—` 表示 endpoints.py 没有填 `response_data_models`,模型层也不提供 Data 类(因为后端实际 response.data 是 `null` 或形状不稳定)。

---

## 5. `dannotations/__init__.py` ── L2 人工注释层

**职责**:存放 31 个端点的"人工注释"(L2 物理层),与 L1 的 `endpoints.py` 物理分离。注释包括:summary 补充、限流说明、时区说明、依赖关系、参见端点等。

### 5.1 文件当前状态:空壳

```python
_DOCS: dict[str, EndpointDoc] = {
    # 例(后续 PR 补):
    # "/api/order/order/orderDetail": EndpointDoc(
    #     summary="按订单 ID 查询订单详情,返回订单全字段快照",
    #     notes=("限流:每用户 10 QPS", "时区:所有时间字段为 UTC+8"),
    #     requires=("已登录", "订单属于当前用户"),
    #     see_also=("/api/order/order/addOrder",),
    # ),
}


def get_doc(path: str) -> EndpointDoc | None:
    """按 path 查 L2 doc;不存在返回 None。"""
    return _DOCS.get(path)


__all__ = ["EndpointDoc", "_DOCS", "get_doc"]
```

### 5.2 为什么 `get_doc` 返回 `None` 而不是抛 `KeyError`?

`EndpointDoc` 是"装饰性"信息:文档生成器(比如 `api_doc/render.py`)对每个 spec 问一次"你有没有注释?",**没有就给个空 doc,不要打断流程**。如果抛 `KeyError`,消费方被迫写 `try/except`,反而把"装饰性信息"和"必须存在的元数据"混为一谈。这是 Plate **"显式区分 L1 / L2,缺 L2 不影响 L1 使用"** 原则的体现。

### 5.3 key 用什么?

`EndpointSpec.path`(全路径,如 `"/api/order/order/orderDetail"`)。**不**用 spec 模块级常量的名字(`orderDetail`),因为:

- 同名 spec 可能在不同服务里复用(虽然现在没出现)
- 路由的全局唯一性靠的是 path,不是变量名
- 文档生成器拿到 wire path 就能直接查 L2 注释

### 5.4 后续 PR 怎么补

按 `applyPage` → `auditPage` → `orderDetail` 三个高频端点优先补,后续按业务组渐进补齐。每个 `EndpointDoc` 必须包含:

- `summary` — 不超过 120 字符的中文一句话(详见 [../doc/README.md](../doc/README.md))
- `notes` — 限流、时区、特殊行为
- `requires` — 前置条件(登录状态、权限、数据依赖)
- `see_also` — 关联端点 path(可用于 AI skill 推荐"下一步该调什么")

PR-EOP review pipeline 会校验 **L1/L2 对称性**:有 spec 无 doc 允许(渐进补),有 doc 无 spec 报错(说明 doc 引用了不存在的端点)。

---

## 6. 31 个端点的全景业务图

下面这张表是 fin 服务的"业务主链"全图,按 `endpoints.py` 9 段分组,展示每个端点的角色:

### 6.1 委托单阶段(`orderEntrust`,2 个端点)

| 端点                   | 类别      | 业务角色                                           |
| ---------------------- | --------- | -------------------------------------------------- |
| `orderEntrustOrderPage` | QUERY    | 委托单分页查询(入口)                              |
| `orderEntrustOrderAdd` | BUSINESS  | 委托单创建(产生委托单 ID)                        |

### 6.2 订单主数据阶段(`order`,7 个端点)

| 端点                       | 类别      | 业务角色                                              |
| -------------------------- | --------- | ----------------------------------------------------- |
| `orderDetail`              | QUERY     | 订单详情查询(查全字段)                              |
| `orderAdd`                 | BUSINESS  | 订单新增(承接委托单 ID)                              |
| `orderBook`                | BUSINESS  | 订单订舱(关联船期文件)                              |
| `checkGenerateOrderSub`    | QUERY     | 生成子单前预检(费用、订舱文件 dry-run)              |
| `generateOrderSub`         | BUSINESS  | 正式生成子单(写库)                                  |
| `changeInvoiceApply`       | BUSINESS  | 发起改票审核申请(进入审核流)                        |
| `orderConfirmAccount`      | BUSINESS  | 订单确认收款账户(填入财务收款信息)                  |

### 6.3 订单费用阶段(`orderFee`,3 个端点)

| 端点                       | 类别      | 业务角色                                              |
| -------------------------- | --------- | ----------------------------------------------------- |
| `toggleRealAmount`         | BUSINESS  | 实际金额确认(写金额)                                 |
| `bookRealAmountEdit`       | BUSINESS  | 订舱金额修改(改费用清单)                            |
| `realAmountLockSubmit`     | BUSINESS  | 实际金额锁定提交(冻结金额,触发核销)                |

### 6.4 审核工作台阶段(`home/audit`,3 个端点)

| 端点             | 类别      | 业务角色                                                            |
| ---------------- | --------- | ------------------------------------------------------------------- |
| `auditPage`      | QUERY     | 审核分页查询(跨业务组的"待办"列表)                                |
| `auditDetail`    | QUERY     | 审核详情查询(读 auditPage 的 audit_id)                             |
| `auditExecute`   | BUSINESS  | 执行审核(通过/驳回,写库)                                          |

### 6.5 财务手续费阶段(`finance/accountFee`,1 个端点)

| 端点               | 类别   | 业务角色                              |
| ------------------ | ------ | ------------------------------------- |
| `financePutList`   | QUERY  | 财务手续费列表查询(支持 BL/客户筛选) |

### 6.6 收款账户阶段(`finance/receiveAccount`,4 个端点)

| 端点                         | 类别     | 业务角色                                       |
| ---------------------------- | -------- | ---------------------------------------------- |
| `orderReceiveAccountEdit`    | BUSINESS | 订单收款账户编辑(建立或修改)                  |
| `receiveAccountDetail`       | QUERY    | 收款账户详情查询                              |
| `receiveConfirmList`         | QUERY    | 收款确认列表查询(等待确认的子单)              |
| `accountConfirm`             | BUSINESS | 确认收款(写库)                                |

### 6.7 收票批量阶段(`Finance/ReceiveInvoiceBatch`,6 个端点,路径大写不规则)

| 端点               | 类别      | 业务角色                                              |
| ------------------ | --------- | ----------------------------------------------------- |
| `applyPage`        | QUERY     | 批量收票申请分页查询(总览入口)                      |
| `checkStep1`       | QUERY     | 批量收票校验 Step1(读 applyPage 的 batch_id)        |
| `checkStep2`       | QUERY     | 批量收票校验 Step2(读 applyPage 的 batch_id)        |
| `batchOrderEdit`   | BUSINESS  | 批量订单编辑(写库)                                  |
| `batchDetail`      | QUERY     | 批量详情查询(读 applyPage 的 batch_id)              |
| `applyDetail`      | QUERY     | 批量申请详情查询(读 applyPage 的 apply_id)          |

### 6.8 收票阶段(`finance/receiveInvoice`,2 个端点)

| 端点                | 类别      | 业务角色                            |
| ------------------- | --------- | ----------------------------------- |
| `invoiceAddCheck`   | QUERY     | 添加发票前预检                      |
| `invoiceAdd`        | BUSINESS  | 添加发票(请求体是 list[dict])      |

### 6.9 收款核销阶段(`finance/receiveWriteoff`,3 个端点)

| 端点                | 类别      | 业务角色                                          |
| ------------------- | --------- | ------------------------------------------------- |
| `orderFeePage`      | QUERY     | 订单费用分页查询(可核销的子单)                   |
| `writeoffBatch`     | BUSINESS  | 批量核销(费用 ↔ 发票匹配)                        |
| `writeoffPage`      | QUERY     | 核销分页查询(核销记录列表)                       |

### 6.10 端点之间的"调用图"(在 binding 之外的部分)

fin 服务的完整业务流(从 wire 视角):

```
委托单分页 / 新增
    ↓
订单新增(承接委托单)
    ↓
订单订舱
    ↓
订单确认账户
    ↓
实际金额确认 → 订舱金额修改 → 实际金额锁定提交
    ↓
(任何步骤都可能触发) 改票审核申请
    ↓
审核分页 → 审核详情 → 执行审核
    ↓
收款账户编辑 → 收款确认列表 → 确认收款
    ↓
批量收票申请 → checkStep1 → checkStep2 → 批量编辑
    ↓
添加发票预检 → 添加发票
    ↓
订单费用分页 → 批量核销 → 核销分页
```

31 个端点里,只有 5 个 binding 是 **机器能理解的"自动数据流"**,其余 26 个的依赖关系 **靠调用方手动维护**。这是当前设计的边界 — Plate 不假设"AI skill 能从 path 名字反推完整调用图"。

---

## 7. 设计哲学与决策记录

### 7.1 单轨化(PR-C 的核心决策)

`endpoints.py` 文件 docstring 写道:

> 本文件将 `Plate.fin` 从"models.py + PATH_MODELS 双轨"切到"endpoints.py + 31 个 EndpointSpec 单轨"。

**双轨历史问题**:
- 旧的 `PATH_MODELS = {method, path: RequestClass}` 字典是 **显式注册表**,新增端点必须两步:加 Request 类 + 在字典里加映射,容易漏。
- spec 之间没有"哪些是 BUSINESS" / "哪些会改库" / "哪些有 binding"的元信息。
- mock 框架要把 path → spec 时,要做 dict lookup + type check,慢且容易出错。

**单轨化收益**:
- 新增端点只需要"加一个模块级常量" + "在 endpoints.py 里 import 它一次",**没有第二步**
- `registry.collect("fin")` 用 `dir()` 拉常量,所有 31 个 spec 都有 `category` / `mutates_state` / `summary` / `tags` / `bindings` 的元信息
- mock 框架拿到 spec 后用 `isinstance(spec, EndpointSpec)` + `spec.method + spec.path` 唯一标识,无歧义

### 7.2 字段保真 vs 业务校验的边界

`models.py` 的 docstring 明确:

> 注意:模型只描述"形状",不做任何业务校验。

**为什么不做业务校验?**

- 后端真在生产里跑,字段是"宽松的"(200+ 字段、类型乱跳),如果你在客户端严格校验,会有 30% 的请求"明明后端能收,你却不让发"
- 业务校验应该由后端做(client-side validation 在 API 测试里反而是反模式)
- Pydantic 的形状校验已经足够强:`extra="forbid"` 在 `_Base` 上早报错;复杂校验(例如"金额必须 ≥ 0")在 Pydantic 上写 `field_validator` 是反模式(易脆、易和后端漂移)

### 7.3 `category` 与 `mutates_state` 的"为什么"再展开

`category` 是 **AI skill 决策用**(决定"我能不能主动 call 它"):
- `BUSINESS` 端点会改库 → AI 不能在"主动探测"阶段调(否则污染数据)
- `QUERY` 端点不写库 → AI 可以放心 call
- `TOOL` 端点纯计算/辅助 → AI 可以放心 call

`mutates_state` 是 **CT 框架决策用**(决定"主动 mock 探测要不要跳过它"):
- `True` 端点 = 跳过(防止 mock 时意外触发后端副作用)
- `False` 端点 = 主动 call(用 mock response 验证 spec 本身能跑通)

两个字段冗余吗?**不冗余**:
- `category` 是业务语义(给人/AI 看)
- `mutates_state` 是技术语义(给 mock/CT 看)
- 一个端点可以是 `category=QUERY` 但 `mutates_state=True`(有 `check` 类端点是这种,但本服务没出现)

### 7.4 `tags` 的"小词表"约定

31 个 spec 的 tags 全部从以下小词表里挑(粗体是高频词):

- **order** / **order-fee** / **finance** / **audit** / **invoice** / **invoice-batch** / **writeoff** / **receive-account**
- **query** / **detail** / **check** / **book** / **lock** / **sub-order** / **entrust**
- **write**(标记"会写库"语义)

**为什么不写"audit_execute" 这种长词?** tags 是 **业务过滤维度**,应该正交、可枚举。3–4 个短词比一个长词更能组合出"audit + write" / "finance + query" 这样的查询。

### 7.5 为什么 `_Base` 用 `forbid`、其它数据类大多用 `ignore`?

`_Base` 的 `extra="forbid"` 是 **基础契约护栏**:
- `CommonResponseEnvelope`、`OrderDetailRequest` 这种"高频/小字段"类用 forbid
- `_ApplyPageItem` 这种"40 字段 / ES 文档全字段"用 ignore
- `PermissiveRequest` 用 ignore

原则:**字段越少,要求越严**;字段越多,容忍度越高。这与 Pydantic 社区的"用 forbid 严格化"做法相反 — 我们的工程经验是 **100+ 字段的 forbid 模型几乎肯定会和后端真实 wire 漂移**,导致 mock 永远报错。

### 7.6 wire 路径大小写不规则的"为什么"保留

`/api/Finance/ReceiveInvoiceBatch/...` 这条路径上 `Finance` 和 `ReceiveInvoiceBatch` 首字母大写,而其他 8 个组都是小写。后端 Gin 路由表里就这样写,Plate 严守"契约 = 实际 wire"原则:

- 改它 → mock 拿到的 path 与真实路由不匹配 → 真实 mock call 会 404
- 留它 → 一处小不一致,代价是 mock 必须字面匹配

权衡之下,选择"字面保留" + "在 endpoints.py 注释里钉一下,提醒未来同学别动"。

---

## 8. 典型使用示例

### 8.1 通过 registry 查 spec(最常见用法)

```python
from Plate import registry

# 1. 拉式收集 fin 服务(第一次访问 fin 时才会 import + collect)
spec = registry.resolve("fin", "POST", "/api/order/order/orderDetail")

# 2. 拿到 spec 后,做入参校验
req = spec.request.model_validate({"order_id": "ord_123"})

# 3. 拿到响应 envelope(所有 200 都用它)
assert spec.responses[200] is not None

# 4. 拿到响应 data 形状(只对 8 个端点有效)
if spec.response_data_models:
    data_cls = spec.response_data_models[200]
    data = data_cls.model_validate(...)
```

### 8.2 直接按名 import spec(用于静态分析 / 配置文件)

```python
from Plate.fin import orderDetail, auditExecute, invoiceAdd

# 在 YAML / JSON 测试用例里直接 spec 名
test_case = {
    "spec": orderDetail,
    "request": {"order_id": "ord_123"},
    "mock_response": {...},
}
```

### 8.3 通过 manifest 校验完整性

```python
from Plate.manifest import PlateManifest
from Plate import registry

registry.warm("fin")  # 强制加载 fin
manifest = PlateManifest.from_services(["fin"])
checksum = manifest.compute_checksum()
print(f"fin 服务的 31 个 spec 的 SHA256 = {checksum}")

# 在 CI 里把这个 checksum 钉到 git,如果下次发版有变化(新增/删除/修改端点),CI 会爆
```

### 8.4 用 binding 做"自动数据流"

```python
from Plate import registry
from Plate.binding import FieldBinding

# 假设 mock 框架要执行"applyPage → applyDetail"两步
apply_page_spec = registry.resolve("fin", "POST", "/api/Finance/ReceiveInvoiceBatch/applyPage")
apply_detail_spec = registry.resolve("fin", "POST", "/api/Finance/ReceiveInvoiceBatch/applyDetail")

# 第一步:调用 applyPage,得到一堆 apply_id
page_resp = apply_page_spec.request.model_validate({...})  # mock 框架内部,真实响应 data[].receive_invoice_apply_id

# 第二步:从 page_resp 自动抽出 apply_id,喂给 applyDetail.request
binding = apply_detail_spec.bindings[0]
# binding.from_path = ("data", "receive_invoice_apply_id")
# binding.to_path = ("receive_invoice_apply_id",)
# mock 框架按 binding 自动从 page_resp.data[0].receive_invoice_apply_id → detail_req.receive_invoice_apply_id
detail_req = apply_detail_spec.request.model_validate({
    "receive_invoice_apply_id": page_resp.data[0]["receive_invoice_apply_id"]
})
```

### 8.5 通过 api_doc 渲染 Markdown 文档

```bash
# 渲染 fin 服务的所有端点为 Markdown
python -m Plate.api_doc render fin --output docs/fin-api.md
```

(详见 [../api_doc/README.md](../api_doc/README.md))

---

## 9. 不变量总结

下面这些是 `Plate.fin` 模块在运行时的硬性不变量(违反任意一个会被 `EndpointSpec.__post_init__` 或 `_Base` 校验抛错):

| #   | 不变量                                                                              | 守护位置                          |
| --- | ----------------------------------------------------------------------------------- | --------------------------------- |
| 1   | 31 个 spec 的 `method` + `path` 在 fin 服务内全局唯一                               | `EndpointSpec.__post_init__` + `registry._check_no_duplicate_paths_locked` |
| 2   | `request` 必须是 `_Base` 子类(`extra="forbid"` 严格护栏生效)                       | `EndpointSpec.__post_init__` 的 `_assert_safe_model` |
| 3   | `responses` 的 value 必须是 `_Base` 子类                                            | 同上                              |
| 4   | `response_data_models` 的 value 必须是 `_Base` 子类                                | 同上                              |
| 5   | `category` ∈ {BUSINESS, QUERY, TOOL}                                                | `EndpointCategory` 枚举           |
| 6   | `mutates_state` ∈ {True, False}                                                     | 显式 bool                         |
| 7   | `summary` ≤ 120 字符                                                                | 由 L1 端点定义,无强校验(信任人工) |
| 8   | `tags` 是 0–N 个英文小写短词                                                        | 无强校验                          |
| 9   | 任何字段名等于 Python 关键字(如 `del`)时,用下划线后缀并在 validator 里翻译        | `_AuditExt._accept_del_alias`     |
| 10  | 私有类以下划线开头,不出现在 `__all__` 里                                            | 命名约定                          |
| 11  | `PermissiveRequest` 共享给 `orderEntrustOrderAdd` / `orderAdd` / `orderBook`        | `=` 赋值语义(模块级别名)          |
| 12  | `InvoiceAddRequest` 接受 list 输入,内部 wrap 成 `{"_root": list}`                  | `InvoiceAddRequest._wrap_list`    |
| 13  | L2 注释 key 是 `path` 字符串(不是 spec 名字)                                       | `dannotations._DOCS`              |
| 14  | `dannotations.get_doc(path)` 对未注释的 path 返回 `None`,不抛错                    | `dannotations.get_doc`            |

---

## 10. 设计权衡与未来工作

### 10.1 当前权衡

| 决策                                         | 收益                                   | 代价                                       |
| -------------------------------------------- | -------------------------------------- | ------------------------------------------ |
| PermissiveRequest 共享给 3 个端点            | 减少模型维护成本                       | 失去精确字段校验(mock 时漏检)              |
| 多数数据类用 `extra="ignore"`                | mock 时不报"未知 key"                  | 抓不到"后端偷偷加了字段"这种回归          |
| 8 个端点有 `response_data_models`,其余 23 个没有 | 减少 model 数量                    | 消费方拿不到精确 data 形状                |
| `Finance/ReceiveInvoiceBatch` 路径大写不规则 保留 | 不破坏 wire                          | 阅读一致性差                              |
| L2 注释层暂为空壳                            | 渐进补,不强求 PR 完成                 | 文档生成器对未注释的端点渲染空 summary    |
| 不在 spec 里写"调用图"                        | spec 极简,自包含                     | AI skill 必须自己推理完整业务流            |

### 10.2 未来工作(预留,不在本 PR 范围)

1. **dannotations 补全**:按 applyPage → auditPage → orderDetail 三个高频端点优先
2. **response_data_models 扩展**:对 23 个未填的端点,在抓更多 wire 样本后补充
3. **PermissiveRequest 拆分**:当 orderAdd / orderBook 抓到的字段稳定下来后,逐步替换为精确模型
4. **L1/L2 对称性 CI 校验**:有 spec 无 doc 警告,有 doc 无 spec 报错
5. **跨服务 binding 扩展**:目前 5 个 binding 都在 fin 服务内;未来如果 home/audit 和 finance/receiveAccount 之间出现"上游 ID 喂下游",binding 会跨服务

### 10.3 与整体 Plate 哲学的一致性

| 哲学原则(见 [../overview.md](../overview.md)) | fin 模块怎么落地                                              |
| -------------------------------------------- | ------------------------------------------------------------- |
| 零侵入(不污染后端代码)                       | fin 包是独立 Python 文件,后端 Gin 代码不需要改                |
| L1/L2 物理分离                                | `endpoints.py` 是 L1,`dannotations/` 是 L2                    |
| 懒加载(拉式收集)                             | `registry.collect("fin")` 在第一次 `resolve("fin", ...)` 时才 import |
| 线程安全                                       | `registry` 内部 `threading.Lock` 守护,fin 端点本身无状态      |
| 字节级可重现                                 | `manifest.compute_checksum` 对 31 个 spec 算 SHA256           |
| 契约保真                                      | `_SAFE_CONFIG` + `extra="forbid"` 严格护栏                    |
| 声明式 + 命令式混合                           | 端点用声明式(spec),数据流用声明式(binding),运行时用命令式(import) |
| 业务标注(category / mutates_state)            | PR-B 引入,在 31 个 spec 上 100% 覆盖                          |

---

> **完结提示**:这份文档覆盖了 `Plate/fin/` 包的全部代码(2026-07-03 commit `e0be7bf` 后的状态)。当 `models.py` 或 `endpoints.py` 新增/修改端点时,本文件的 §3、§4、§6 表格需要同步更新。建议在 `Plate/fin/` 变更的 PR 模板里挂一条"更新 docs/fin/README.md" 的提醒。
