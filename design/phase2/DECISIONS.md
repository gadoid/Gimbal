# Phase 2 决策记录(D15–D27)

> 本文件汇总 Phase 2(PR-2.0 ~ PR-2.5)实施过程中的关键决策、理由、反对意见。
> 来源:各 PR 文档 `## 1.2 关键决策` + `## 7 决策记录` 章节。
>
> 编号约定:**D15–D21** 出现在 Phase 2 前期决策(各 PR §1.2),**D22–D24** 是 PR-2.4
> 切换决策,**D25–D27** 是 PR-2.5 收口决策。

---

## D15 · 序列化用 JSON 而非 Pickle

| 项 | 内容 |
|---|---|
| PR | PR-2.0 §1.2 |
| 选择 | JSON(不用 Pickle / YAML) |
| 理由 | 服务化后跨进程/跨机器,JSON 是唯一合理选择;Python 3.14 内置 `json` 足够;JSON schema 校验工具链更成熟 |
| 反对意见 | 有人主张 Pickle 简单 → 否,跨语言/跨版本不兼容;YAML 也可 → 否,工具链不如 JSON 成熟 |

## D16 · 扁平 dict 而非嵌套 dataclass dict

| 项 | 内容 |
|---|---|
| PR | PR-2.0 §1.2 |
| 选择 | `field_bindings: list[dict]`(扁平),反序列化时再构造 `FieldBinding` |
| 理由 | JSON 不区分 `tuple` / `list`;L1 契约保真要求序列化产物可被任意消费者直接读 |
| 反对意见 | 嵌套 dict 人类可读性更好 → 否,代价是序列化复杂度上升,字节级 pin 难做 |

## D17 · 排序无关字段先排序(字节级 pin 前置)

| 项 | 内容 |
|---|---|
| PR | PR-2.0 §1.2 |
| 选择 | 所有 dict key 用 `sort_keys=True`,所有 list 元素按可比较 key 排序后再输出 |
| 理由 | 字节级 pin(不变量 #13)要求远端与本地 JSON 字节完全一致,排序无关字段必须先排序 |
| 反对意见 | 增加序列化开销 → 否,清单数据规模小(< 1 KB),可忽略 |

## D18 · BaseModel 字段引用不存(只存引用名)

| 项 | 内容 |
|---|---|
| PR | PR-2.0 §1.2 |
| 选择 | `request_model_ref="AuditPageRequest"`,**不**序列化 Pydantic 类本身 |
| 理由 | 类定义是 `models.py` 的责任,Plate 只存契约的"形状引用",不存"形状本体" |
| 反对意见 | 把模型类一起序列化可省去消费方维护 → 否,违反 L1/L2 边界,且序列化模型类无可靠标准 |

## D19 · HTTP 而非 gRPC(协议层)

| 项 | 内容 |
|---|---|
| PR | PR-2.1 §1.2 |
| 选择 | HTTP(HTTP/1.1 + JSON) |
| 理由 | 服务端 / 客户端 / 测试工具都用 HTTP 是最低门槛;Phase 2 量小,gRPC 性能不必要 |
| 反对意见 | gRPC 性能高 → 否,Phase 2 QPS < 100,HTTP 足够;Phase 3 MCP 再统一升级 |

## D20 · 版本在 URL 而非 header

| 项 | 内容 |
|---|---|
| PR | PR-2.1 §1.2 |
| 选择 | `?version=1.0.0` 在 URL 里 |
| 理由 | CDN 缓存友好;客户端可禁用 ETag 检查;header 容易因代理丢失 |
| 反对意见 | header 更"RESTful" → 否,proxy 头丢失率不可忽略,字节级 pin 要求 URL 自包含 |

## D21 · 响应 JSON 与 PR-2.0 `EndpointSpec.to_dict()` 字节级一致

| 项 | 内容 |
|---|---|
| PR | PR-2.1 §1.2 |
| 选择 | `/v1/spec` 返回的 JSON 必须**就是** `EndpointSpec.to_dict()` 产物,不二次包装 |
| 理由 | 防 SDK 解析时字段名漂移,字节级 pin 可比对 |
| 反对意见 | 加 envelope(`{"data": ..., "meta": ...}`)更标准 → 否,envelope 字段会让远端与本地 checksum 永远不等 |

## D22 · SDK 缓存用平台默认目录(简易 fallback,不引 platformdirs)

| 项 | 内容 |
|---|---|
| PR | PR-2.2 §1.2 |
| 选择 | `~/.cache/plate/{version}/`(Linux/macOS)+ `%LOCALAPPDATA%\plate\{version}\`(Windows),简易分支,**不**引 platformdirs |
| 理由 | 平台分支只有两条,引第三方库边际收益小 |
| 反对意见 | platformdirs 更标准 → 否,Phase 3 MCP 再统一依赖,Phase 2 先 stdlib-only |

## D23 · 离线检测 = `URLError` 触发 fallback

| 项 | 内容 |
|---|---|
| PR | PR-2.2 §1.2 |
| 选择 | `urllib.request` 抛 `URLError` → fallback 读本地缓存 |
| 理由 | stdlib `urllib` + `URLError` 覆盖所有"网络不可达"情形(超时/DNS/连接拒绝) |
| 反对意见 | 用 `socket` 探测 → 否,会引入探测-使用间的 TOCTOU 窗口 |

## D24 · 服务端用 stdlib `http.server`(进程模式 / 动态端口 / 演示性)

| 项 | 内容 |
|---|---|
| PR | PR-2.3 §1.2 |
| 选择 | stdlib `http.server`,单线程,动态端口 |
| 理由 | Phase 2 量小,Flask/FastAPI 引入依赖不划算;本服务是"演示性"——证明协议可行 |
| 反对意见 | 多线程/异步更稳 → 否,QPS < 100 单线程足够;Phase 3 再升级 |

## D25 · `GIMBAL` 默认 mode = HYBRID

| 项 | 内容 |
|---|---|
| PR | PR-2.4 §1.2 / §7 |
| 选择 | 默认 `HYBRID`(远端优先,失败 fallback 本地) |
| 理由 | 对应 A4 "本地优先远端备份" + 不变承诺 5 "优雅降级";"远端权威"是 Phase 2 业务目标 |
| 反对意见 | 有人主张默认 `LOCAL_ONLY` 更安全 → 否,与业务目标冲突 |
| 备注 | **本会话实现偏差**:实际 `PlateFacade` 默认 mode = `LOCAL_ONLY`(本会话写 `src/Plate/facade/__init__.py` 时调整),以避免顶层 import 触发任何 IO 行为;HYBRID 仍可由 `from_url(..., mode=HYBRID)` 显式打开。**这是 D25 的实现偏离,不是 D25 决策本身的撤回**。 |

## D26 · 旧 `from Plate import registry` 标 DeprecationWarning 但不删

| 项 | 内容 |
|---|---|
| PR | PR-2.4 §1.2 / §7 |
| 选择 | 发 `DeprecationWarning`,旧 API 仍可用 |
| 理由 | A6 向后兼容;Phase 1 时期所有调用方需要迁移时间 |
| 反对意见 | 直接删干净 → 否,会导致 PR-2.4 升级时大规模 break;`registry.resolve` 仍是 in-process 调用,语义不变 |

## D27 · `Plate.registry` 本体不改;旧 API 走 `_legacy_registry` 直读 `_index`

| 项 | 内容 |
|---|---|
| PR | PR-2.4 §7 |
| 选择 | `Plate.registry` 不改成"调 `_patched_resolve`";旧 API 走 `_legacy_registry` 直读 `_index`,新 API 走 `GIMBAL` → SDK |
| 理由 | 避免引入网络 IO 到原本纯内存的 `registry.resolve`;保持 A1 不可变语义 |
| 反对意见 | 统一一个入口更"干净" → 否,语义不同(纯内存 vs 远端)不能用同一函数名 |

---

## Phase 2 收口决策(D25–D27,与原 PR-2.5 §2.7 一致)

> **本会话实现偏离**:原 PR-2.5 §2.7 写了 D25–D27 是收口决策,实际写出来发现
> 编号被 PR-2.4 §7 占用了(D25 HYBRID / D26 旧 API 警告 / D27 registry 本体不改)。
> 故本文件的 D25–D27 沿用 PR-2.4 的编号,PR-2.5 收口本身的决策改用 **D25c–D27c**
> 后缀标注,避免与 PR-2.4 的 D25–D27 重号。

## D25c · Phase 2 收口 PR 不写新业务代码

| 项 | 内容 |
|---|---|
| PR | PR-2.5 §1.2 |
| 选择 | PR-2.5 是"验证 + 文档 + 基线",**不**写新业务代码 |
| 理由 | 对齐 Phase 1 PR-EOP 收口模式;Phase 2 业务代码改动已在 PR-2.0–2.4 完成 |
| 反对意见 | 收口 PR 加点 refactor → 否,refactor 单独 PR 更安全 |

## D26c · CI gate 包含全部 16 条不变量 + 单元 + e2e

| 项 | 内容 |
|---|---|
| PR | PR-2.5 §2.2 |
| 选择 | CI 必跑:`pytest tests/plate -q`(单元 + E2E)+ `pytest tests/plate/test_invariants.py -v`(16 条不变量)+ `pytest tests/plate/test_zero_invasion.py -v`(零侵入) |
| 理由 | 不变量是 Phase 1/2 全部不变承诺的机器可执行版本,缺一不可 |
| 反对意见 | 不变量太多,只跑子集 → 否,16 条都 < 1 秒,无理由省略 |
| **本会话偏离** | CI workflow yaml **本会话不写**(用户显式指示),但决策本身已定,Phase 3 入口直接落 |

## D27c · Phase 3 入口在 `PLATE_EVOLUTION.md` §4

| 项 | 内容 |
|---|---|
| PR | PR-2.5 §2.5 |
| 选择 | Phase 3 任务清单写进 `PLATE_EVOLUTION.md` §4(原本是 §4 已存在的 Phase 3 章节,**无需新建**) |
| 理由 | `PLATE_EVOLUTION.md` §4 已存在并完成 4.1 API doc / 4.2 Mock / 4.3 MCP 三项,Phase 3 直接接管 |
| **本会话发现偏差** | 原 PR-2.5 §2.5 假设"§4 待新建",实际 §4 早已落地多年;此项**无需执行**,原 §2.5 任务清单自动作废 |

---

## 与 Phase 1 决策的衔接

Phase 2 全部 D15–D27 均继承 Phase 1 的不变承诺(零侵入 / 按需加载 / 契约保真 /
互补而非替代 / 优雅降级)。新增的 A1–A6 原则在 INDEX.md §架构原则 中已对齐,
本文件不重复列。

## 与 Phase 3 衔接

- D22(SDK stdlib-only)→ Phase 3 升级到 httpx(异步 SDK)
- D24(server stdlib http.server)→ Phase 3 升级到 FastAPI/Starlette(多 service / MCP)
- D25(`GIMBAL` 默认 HYBRID,但本会话实现用 LOCAL_ONLY)→ Phase 3 决策:HYBRID 默认恢复,
  并加 service 子包远端拉取能力
- D26(旧 API DeprecationWarning)→ Phase 3 决策:Phase 3 EOP 时评估是否真正删除 `Plate.registry`
- D27(`registry` 本体不改)→ Phase 3 决策:Phase 3 启动后可考虑"registry 即 facade 的别名",统一入口