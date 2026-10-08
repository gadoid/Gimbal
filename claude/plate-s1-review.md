# feat/plate-s1 实现评审

> **当前状态（2026-10-08，HEAD 0cebec1）：建议合入 main。**
> 范围：基线 8281802 → 0cebec1，跨 S1-0、A1、A2、B、C、D、E 各批次，加上八轮评审收口。
> 对照：仓库内 `claude/plate-design.md`，修订十三补二。
> 方法：
> - 每轮分 3–4 路核对，每条结论都有复现脚本，或已经定位到代码行；
> - 三侧测试都在干净 checkout 上重跑；
> - CI 在干净副本里逐步模拟；
> - 第五轮起另请一位没参与过前几轮的独立评审员，做整体代码评审。
>
> 本文第 1–7 节反映当前状态；附录保留各轮评审原文，作为历史记录。附录里的「合入判断」「必修」等结论只代表当时那一轮，已经被第 1 节取代。

## 1. 结论

**S1 已满足合入条件，建议合入 main。**

- **阻塞项清零**：第一轮发现的一接即坏、hash 口径、发布闸门三组问题，以及后来发现的路径穿越、迁移备份纪律，都已修复并有测试守护。
- **未完成的部分都已显式降级**：S1 承诺范围里没做的内容（快照与 ref、新 dim、单块回写、路径可配置、批次 C 深度、批次 E 执行闭环），都已在设计里登记到 S1.5，没有被悄悄丢掉。
- **两路复核员的独立结论都是「可以合入」**，其中一位没参与过前几轮。

第一轮的结论是「内核扎实，集成面没有闭合；『S1 全部落地』的说法不成立，暂不建议合入」。当时的判断针对 078f3d8：真实服务器上所有 `/api` 请求都失败、前端没有适配、发布闸门四项必检有三项没有强制执行、CI 缺失。这些问题在之后七轮里逐项收口。「全部落地」的说法已由设计修订十至十三修正为「S1 交付 + S1.5 显式降级清单」。

## 2. 交付状态（对照设计第 11 节）

| 批次 | 已交付 | 降级到 S1.5 |
|---|---|---|
| S1-0 清理 | A1–A6 文档归档与修订；B1–B5 代码清理；B3 删除的接口已在设计里记录（三个接口退役，引用方迁移） | A7 服务画像文档 P2/P3 表述；B6 路线图登记 |
| A1 方言内核 | M2（binding 判别联合、N1、删除 version/updated_at 等）；解析器和渲染器（规范形、往返幂等，155 个文件由 CI 守门）；内容寻址 hash（排除缺省值、dict 键排序）；shape_hash（剔除嵌套说明字段，保留 default/example）；YAML 1.2 core（零新依赖，重复键直接报错，空值读成 null）；149 个接口等价迁移 | 质量尾项（见第 4 节） |
| A2 加载器与平台腿 | 统一加载器，旧 Python 栈删净；轻列表和 `/full` 的新形状；前端适配 binding；适配中心改为一道 shape_hash 门；存量戳迁移，冷启动重落基线时先做字段比对，不吞真实变更 | 快照化、原子重载、`ref` 多版本与 `/convert` 钉住、G5 快照带 commit 标识、reload 触达运行中的服务、`plate_client` 按快照让缓存失效 |
| B 发布与校验 | 发布闸门四项必检全部强制：机械检查、C 类、闭包、签发；内容寻址的全局对象池，原子写入并校验内容；release 号防并发重号；引用闭包传递；N3 common 子集冻结、common 不能单独发版；空发版拒绝且不占号；F1–F4、T1–T6、S1–S3、C1–C3；check 和 release 共用同一个引擎（`collect_system_tree` + `validate_system_tree`） | manifest 记录 shape_hash、call 投影内容寻址、G7 字段级 diff、release 号数值排序与本地月份、correction 引用台账 |
| C 框架自描述 | http 协议自描述和契约测试；P4 单向依赖守卫（AST 扫描，静态写法的 import 都能拦住） | 订阅、参数登记、报告、计划、调试的字段级对拍；框架 dim 全局挂载；恒真测试重写 |
| D CLI 与 CI | `plate` 独立入口，8 个命令；editable 和 wheel 安装（wheel 需要设 `PLATE_REPO_ROOT`）；CI 包括三个系统的 check、方言纪律测试、三侧测试、wheel 冒烟 | `diff --base working/main`、`check --stdin` 补 T/S2、G1 的 HTTP 入口、Agent 编写 skill、N4 单块回写 |
| E 自举切片 | platform「管理员管理成员」：PRD、用户故事、词典、4 个接口的 capability；管道走通到「编写 → 评审 → 入库 → 编排」 | 从故事派生 Scenario 并执行、step 分支表达力验证（第 9 项）、DELETE 接口的 cap 归位、caps_without_define 收敛 |

## 3. 当前质量

**测试**

| 范围 | 结果 |
|---|---|
| plate | 605，0 skip |
| 执行器 | 615（unit + integration） |
| 平台后端 | 782 + 2 skip（需 `PYTHONPATH=src`） |
| 前端 vitest | 1138 |
| vue-tsc | 0 错 |

**CI 模拟**（干净副本，不装 asyncpg）：各步全部通过，前端 job 本轮没有模拟。

**数据稳定性**：从包上移到最后一轮的所有重构，都没有改动对象 hash 和 call 投影（platform 146 个对象、fin 23 个对象，逐轮对比）。

**安全**：
- 动作路由和 loader 两侧都已封住路径穿越，包括 URL 编码、符号链接、大小写和 Unicode 变体；
- 没有 eval、pickle、subprocess，YAML 严格加载；
- 对象动作会校验归属。

**独立评审员对整体代码质量的看法**：
- **优点**：模块边界清楚；构件按内容寻址并原子写入；错误信封统一；测试快且覆盖广。
- **短板**：遍历系统树的代码已经收敛成一份，但 CLI 的 term search 和 review 仍各有一处独立遍历；注册表注册失败时不回滚（S1.5 做原子重载时一并处理）；失败模式和恶意输入的测试仍然偏少。

## 4. 遗留项与建议的处理方式

**合入时**：在真实环境确认 `plate_artifacts/*/releases/` 里没有以前留下的、缺 manifest 的空目录，有就手工删掉。

**S1.5a，建议合入后马上做（1–2 天，都是小改，直接影响接下来写内容的质量和 CI 的可靠性）**：
- `plate check --all`，CI 改成检查所有系统目录（防止不合规的目录名通过 CI 却在服务里悄悄消失）；
- 会悄悄放过错误内容的校验口子：`responses` 为空仍能通过、列表块不继承 service、YAML 合并键被静默当成字面量、复合键抛裸 TypeError、S4 缺失、T5 不比较别名和他人 label、T3/T6 对 common 目标误阻塞；
- F3 finding 补上行号；
- 测试收紧：diff 测试补断言、恢复 `sys.path`、P8 嵌套测试改成真正能失败的写法；迁移脚本退出时关闭数据库连接。

**建议尽早做一次的验证**：step 能否表达分支（第 9 项）。它是结构风险：用户故事写多以后再改 M2，存量就要跟着迁移（P8）。在批量写故事之前，先用一条真实带分支的结算流程走一遍。

**按触发点做**

| S1.5 项 | 触发点 |
|---|---|
| 快照、ref、`/convert` 钉住、路径和构件目录可配置 | 平台开始基于 release 编排和执行时（第 12 节第 11 项） |
| G7 字段级 diff、manifest 记录 shape_hash、call 投影内容寻址 | 做用例变更插件时（task 4.3） |
| term/statement/deliverable dim、doc/paths/references、G1 的 HTTP 入口、Agent 编写 skill | 服务画像接 P2/P3 时，或者 Agent 线启动时 |
| 批次 C 字段级对拍、框架 dim 全局挂载 | schema 反转时（真相源从 gimbal 切到 plate） |
| 批次 E 从故事派生 Scenario 并执行 | 分支验证通过之后 |
| N4 单块回写、`review <词条 id>` 的粒度 | 评审量上来，或者开始做评审界面时 |
| 平台侧尾项：hash 显示截断、空戳、`_ep_key_map`、`baselinedNow` 展示 | 跟着平台集成执行器新能力的工作一起做 |

主线建议回到「平台集成执行器新能力」，plate 侧只按上表的触发点推进。

## 5. 已拍板的决策（评审期间）

| 决策 | 内容 |
|---|---|
| 接口实例的形态（8z） | 统一用 md：md 是定义形态，加载后的 pydantic 对象是内存形态，Python 只承载 M2 |
| hash 口径 | 规范序列化排除缺省值，dict 键一律排序；shape_hash = binding + 声明树，递归剔除 description/ui_kind，保留 default/example；对象 hash 不通过 HTTP 暴露 |
| YAML | 解析按 YAML 1.2 core（自定义 resolver，零新依赖）；重复键直接报错；渲染时对歧义标量强制双引号 |
| C 类口径 | C1 = 全部来源的 cap 集合交集为空才报（三份文档环形分歧也会报）；C3 = 同一 (attr, from) 的去向集合交集为空才报；C2 维持全等 |
| correction_log | 从 manifest 中删除，引用台账随 C 闸门成熟后在 S1.5 回填 |
| 无变化再发版 | 允许：照常生成新号，hash 相同，diff 为 0 |
| 空发版与 common | 0 个对象的发版拒绝，且不占号；common 不能单独发版 |
| 凭据（N4） | 仓库是私网，维持现状；**仓库若要转为公开，必须先轮换远端 PG 口令** |

## 6. 评审期间对线上数据的操作（风险记录）

- **远端 PG 适配戳**：149 个戳已按最终的 shape_hash 口径落好基线，二次 dry-run 结果一致，可重复执行。
- **存量用例迁移（09c1779）**：6 个场景共 176 处旧伪路径改成了 `$.call.*`。**当时的两份备份都是迁移后的状态**（首版脚本的 bug），回滚只能尽力而为：映射是多对一的，迁移前本来就写了 `$.call.*` 的地方无法区分。脚本现在已改为深拷贝、先备份、单事务、默认只演练不写入。

## 7. 过程观察

- **前三轮的主要问题，是验证方式测不到真实环境**：HTTP 走进程内测试客户端，CLI 直接调函数，有几处修复靠手工构造条件的测试通过，提交信息里也有几处说法和实测不符。
- **补上了三道机制**：真实 uvicorn 冒烟、在干净副本里模拟 CI、独立评审员。第四轮起，「声称已修」与实测基本一致。
- **建议保留到后续批次的做法**：每个声称的修复都要有一条在真实路径上能失败的测试；合入前做一次独立的整体评审。

---

# 附录：各轮评审原文（历史记录，结论仅代表当时那一轮）

## 第一轮评审（2026-10-08，HEAD 078f3d8）

> 范围：基线 8281802 → 078f3d8，共 9 个提交（S1-0、A1、A2、A2 平台腿、B、C、D、E）。
> 对照：仓库内 `claude/plate-design.md`（修订九，实现方所依据的版本）。
> 方法：分四路逐批核对，每条结论都有复现脚本，或已在代码里定位到行；三侧测试都在干净 checkout 上重跑过。

### 结论

**内核扎实，集成面没有闭合。「S1 全部落地」的说法不成立，暂不建议合入 main。**

做得好的部分：
- 方言 M2 与设计逐字段一致。
- 规范序列化（`exclude_defaults`）、对象 hash、往返幂等、149 个接口的等价迁移都已完成。
- 统一加载器上线，旧栈已删净。
- release 内容寻址冻结：去重和只追加两条性质都成立。
- 适配中心的两道假门已坍缩为一道 shape_hash 比较。

存在的问题：
- 有两处一接真实服务就会坏。
- 发布闸门四项必检里有三项没有强制执行。
- 7.1 的快照 / ref 模型、7.2 的新 dim、CI 基本没做。

三侧测试全绿（plate 554 / 执行器 615 / 平台 765+2 环境失败），但掩盖了这些问题，原因有三：
- HTTP 测试走进程内 TestClient，测不到真实服务器上的行为。
- CLI 测试直接调 `main()`，测不到安装后的入口。
- 前端没有测试。

### P0：合入前必修（多数是小改）

#### 一接即坏

| # | 问题 | 证据 / 复现 | 改法 |
|---|---|---|---|
| 1 | G5 中间件改写响应体后沿用旧 `content-length` | `http/app.py:80-101`；TestClient 下声明 263 字节、实际 317 字节。真实 uvicorn 下抛 `Too much data for declared Content-Length`，curl 收到 0 字节。**平台对 plate 的所有调用都会失败** | 重建 Response 时丢掉 content-length（或改用 JSONResponse），补一条真实服务器冒烟测试 |
| 2 | 前端未适配 `/full` 的 `api→binding` | 前端零改动。`CaseComposerCanvas.vue:2028-2030` 从目录加步骤得到 `GET ''`；`CaseComposerCatalog.vue:114-122` 显示空 method/path 和 `vundefined`；`types/plate.ts:215-220` 仍是 `api/version/updated_at` | 改这三个文件读 `binding` |
| 3 | 全局 system 动作路由取错参数名，回落到 fin | `routes_grammar.py:789/819/850` 取的是 `path_params["system"]`，但该路由的参数叫 `id`。已复现：`POST /api/system/platform/action/gaps` 返回 fin 的 23 个接口。**换成 `release` 会冻结 fin** | 读 `id`，删掉 `or "fin"` |
| 4 | `plate` 入口安装后不可用 | hatch 只打包 `src/gimbal`，安装后报 `ModuleNotFoundError: gimbal_plate` | 补 `[tool.hatch.build] packages` |
| 5 | 9b3075e 把说明行写到了 `twin_generator/cli.py` 文件头 | `SyntaxError: invalid character '⚠'`（B1 要求工具保留可用） | 改为 docstring 内注释 |
| 6 | 存量适配戳未迁移，首次上线触发 pending 风暴 | 模拟 126 个 `1.0.0` + 25 个 `1.1.0` 的旧戳：`catalog_diff` 把 149 个全部判为 pending，字段级 ops 全为 0，需要人工开 149 次批次；另有 2 个去重接口成为 `missing_on_plate` | 非 hex 戳按「首见基线」静默重落；或在 A2 落 8m 的 alembic |

#### hash 口径必须在第一次落戳 / 发版之前修

shape_hash 会写进平台的 `catalog_versions`。上线后再改口径，就是第二场适配风暴。

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| 7 | shape_hash 的 binding 段没有排除缺省值，违反修订九第①条 | `canonical.py:51` 用 `binding.model_dump(mode="json")`，导致 `headers:{}`、`timeout_seconds:30.0` 进入投影。复现：给 HttpBinding 加一个带缺省值的字段，所有接口的 shape_hash 都会变 | 补 `exclude_defaults=True`，并把 P8 测试扩展到嵌套模型和 shape_hash |
| 8 | dict 键按文件序，同一对象有多个 hash | `responses` / `headers` 换个书写顺序，content_hash 就变；shape_hash 对 responses 排了序，但对 headers 没排 | 规范形里对 dict 键统一排序（renderer 同步） |
| 9 | 用的是 YAML 1.1（PyYAML），设计要求 YAML 1.2 | `enum: [01, 07, 08]` 解析成 `[1, 7, '08']`，`on/off` 解析成布尔值，`12:30` 解析成 750；渲染出的 `'1e3'` / `'08'` 不加引号，按 1.2 读回会变成数字。存量 164 个块恰好未受影响 | 推荐：继承 PyYAML 的 `CSafeLoader`，换成 YAML 1.2 core schema 的隐式类型（解析由 C 完成，语义按 1.2），渲染时对歧义标量强制加引号。实测 164 个块用纯 Python 解析约 0.86 秒，C 加载器约 0.11 秒；ruamel 的保真模式是纯 Python 实现，会比现在更慢，不推荐 |
| 10 | YAML 重复键静默取后值 | `name: n` 后面再写 `name: OTHER`，结果为 `OTHER`；N5 的合并冲突残留正好会触发这种情况 | 解析时检测到重复键即报错 |
| 11 | 声明内的说明性字段是否参与 shape_hash，口径未定 | 目前声明内 `description` / `example` / `default` / `ui_kind` 的改动都会改变 shape_hash；设计里写的是「声明树」，没有说明是否剔除嵌套的说明性字段 | **需要你拍板**：`example` / `default` 影响用例取值，可以保留；`description` / `ui_kind` 建议剔除 |

#### 发布闸门的强制项

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| 12 | 签发人可以为空 | `signed_by=""` 是缺省值且从不校验（CLI / HTTP / 函数三处都是），测试 r2 本身就没有签发人 | 必填，空值拒绝 |
| 13 | C 类不一致不阻塞，`correction_log` 记的是 finding 而不是矫正引用 | `release.py:194` 只看 blocking。复现：存在 C1 不一致时照样发出 `2026.10.1` | 先修第 14 条的语义，再接入阻塞；否则修完会变成发布不了 |
| 14 | C1 / C3 语义错误 | C1 不区分来源，同一文件里也会触发；C3 对同一 attr 的任意两个 transition 都报；spec 枚举键的 `attr:` 前缀与 transition 的 `value:` 键永远对不上 | 按 7 节定义重写，补正反例测试 |
| 15 | 引用闭包只查块→词条一跳；common 未冻结进 manifest | 复现：reviewed 词条 refers 一个 draft 词条能发版；parent 是 draft 也能发版；common 下的 draft 词条一律被视为已冻结；manifest 里没有 common 对象（违反 N3），离线消费方无法解析 | 闭包沿 refers / parent / replaced_by 传递；common 对象随 manifest 冻结 |
| 16 | 构件写入不原子，release_id 生成有竞争 | 截断的对象文件会因「已存在」被后续 release 复用；8 个并发进程产出了重复 id，有一份 manifest 被覆盖 | 写临时文件再 rename，复用前校验 hash；对 releases 目录加锁或用 `O_EXCL` |

### P1：S1 承诺范围内未完成（建议本分支补齐，或在设计里显式降级）

| 设计项 | 现状 |
|---|---|
| 7.1：按系统分区的不可变快照、原子重载、失败保留旧快照 | 仍是单个可变全局 registry，靠 `reset()` 后重新 load。复现：一个坏文件导致半加载（148/149）。F3 冲突时 `by_id` 先写入再检查，冲突后会留下残留 |
| 7.1 / 8.3：`ref` 参数，缺省取最新 release，否则取 working；`/convert` 的 run 级钉住 | 完全没有。`?ref=xxx` 被静默忽略 |
| G5：快照标识为 `<系统>@working:<commit>` | 写死成常量 `"working"`；错误信封里没有这个字段 |
| reload 触达运行中的服务 | `plate reload` 只在 CLI 进程内建一个 registry 然后丢弃；服务端没有 reload 接口 |
| 批次 D：CI，包括入库闸门和 N3 common 重校验 | 没有 `.github/`；pre-commit 里也没有 `plate check` |
| 7.2：新增 dim `term` / `statement` / `deliverable`，动作 `doc` / `paths` / `references` / `diff` | 只有 `type`，其余全部 404 或返回 unknown action；9.1 能力接线（画像 P2 / P3）因此无处可接 |
| 入库闸门与发布闸门同一引擎 | `check` 不带 common，导致 T1 重名检查缺失、引用 common 时误报 S2 / T2；F3 和交付物 id 唯一性只在 release 里查；方言错误直接抛 traceback（`plate new` 生成的骨架也会触发）；`--stdin` 只做单文件校验 |
| `diff --json`（G7，适配中心依赖） | 只能比两个 release 的对象级增删改；`--base working` / `--base main` 会崩溃；release 按字符串排序，`.10` 会排在 `.9` 前面 |
| N5 / N4：`review --set` 只改目标块 | 整个文件重新渲染（加空行、改键序）；传入词条 id 会把整个块的 10 个词条都翻回 draft；Block 没有记录结束行，单块回写缺少基础 |
| 批次 C：框架自描述 | 只有手写的 http 描述符；订阅、参数登记、报告、计划、调试五项只做了存在性断言；漂移守卫只比对键名（executor 删字段或收紧约束、改 auth 枚举都测不出）；`test_v3_no_reverse_import` 在 pyproject、文档、代码注释里都被引用，但**从未存在过** |
| 路径可配置 | CLI 和 HTTP 的 check / gaps / release 都写死了 `parents[N]/systems`，忽略 `PLATE_SYSTEMS_PATH`；构件输出目录不可配 |

### P2：质量项（可以跟在后面修）

- **方言解析**：
  - 片段 `text` 会越过标题吞到下一个块之前（`parser.py:146`），而 `text` 参与 hash。
  - `responses` 为空时也能通过（`models.py:193`），状态码 `000` / `999` 合法。
  - frontmatter 的 `service` 继承没有实现（`models.py:237` 的注释声称已实现）。
  - 报错行号永远指向围栏起始行。
  - 4 个反引号包裹的示例里的 `gimbal:` 块会被当成真实块解析。
  - BOM 会让 frontmatter 失效；CRLF 输入渲染后换行符混杂。
- **校验**：
  - S1 的槽位约束是全局一张表，没有按 kind 区分：rule 带 cap、step 带未知槽位、outcome 既无 outcome 也无 target，都能通过。
  - S4 未实现。
  - T5 不比较「别名 vs 他人 label」。
  - T3 / T6 的目标在 common 时会误阻塞。
  - 多数 finding 没有文件:行号。
- **gaps**：
  - `outcome_keys_without_statement` 拼出来的 `outcome:<status>` 不是合法的词条 id；只要存在任意一条 outcome 片段，计数就归零。
  - F4 只支持下限阈值，「without」类指标无法设门槛。
  - `placeholder` 恒为空。
- **manifest**：
  - 缺 F4 checklist。
  - call 投影没有做内容寻址。
  - `_call_projection` 和 `export/gimbal.py:_render_call` 是两份实现（P3 双真源风险）。
  - `types_version` 写死为 1。
  - 对象文件存的不是规范形。
  - statement 的 `kind` 字段覆盖了对象类型字段。
- **平台腿**：
  - from/to 展示只有 `catalog_diff` 截取了 8 位，批次详情、画像节点、动态流仍显示 64 位全长。
  - plate 未返回 shape_hash 时，`open_batch` 会落一个空戳，导致永久 pending。
  - `plate_client` 没有按快照失效缓存。
  - 画像 subject 的 version 槽位填的是 hash 前缀，不是快照标识。
  - 残留死代码 `_semver_gt` / `_parse_dt`。
- **批次 E**：
  - `branch_on` 只是个标记，没有分支目标，也没有路径展开，所以第 9 项（step 能否表达分支）**实际上没有验证**。
  - 没有从 story 派生 Scenario，也没有跑执行。
  - DELETE 接口挂的是 `cap:user.disable`。
  - `caps_without_define=4` 没有收敛。
  - 「词条反查」测试是自己拼字符串，没有调用 plate。
- **测试与环境**：
  - 两处测试会写进真实仓库：`test_cli_d` 写 `systems/fin/`，HTTP release 测试写 `plate_artifacts/`。
  - 代码用了 `typing.override`（需要 3.12），但 `.python-version` 是 3.11。
  - 提交信息里说的「平台 7 个 WIP 失败」在干净 checkout 上只有 2 个，都是环境原因。
- **S1-0**：
  - A7（服务画像文档的 P2 / P3 表述）没有做。
  - B6 没有记入路线图。
  - B3 删掉了 `order_dispatch` 接口，而不是改成显式 id 关联，违反「清理不改变对外行为」。

### 建议的修复顺序

1. **P0 一次性修完**：分三组——一接即坏 6 项、hash 口径 5 项、发布闸门 5 项。每组配一条「真实进程」测试：uvicorn 子进程冒烟、`pip install -e` 后跑 `plate --help`、前端目录加步骤的 e2e 或类型检查。
2. **P1 二选一**：
   - (a) 在本分支补齐快照 / ref / reload、CI、新 dim、统一 check 引擎；
   - (b) 在设计第 11 节把这些显式移到 S1.5，同时把合入条件改成「P0 清零 + 降级说明」。
   - 无论选哪个，CI 和统一 check 引擎都建议放进本分支，因为它们是入库闸门成立的前提。
3. **P2 跟随修复**；其中第 9 项分支表达力建议在 E 切片里补上分支目标和路径展开，真正验证一次。

---

## 第二轮复核（2026-10-08，HEAD 2049abd）

> 范围：078f3d8 之后的 7 个提交（3d7333e、77c16eb、99953b6、9f99b6c，以及平台执行详情的 19b6eae、e63ddc1、2049abd）。
> 对照：仓库 `claude/plate-design.md` 修订十。修订十显式降级到 S1.5 的项按「决定延后」处理，不计为缺陷。合入条件按修订十：P0 清零 + S1.5 清单。
> 方法：四路复核员重跑第一轮的全部复现脚本，再补新场景。下面标为「已复现」的条目我又独立验证过一遍。

### 结论

**修复率高，修好的部分质量也不错，但还没达到修订十自己定的合入条件。**

- **已真正生效的修复**：一接即坏的 6 项（前端目录列表除外）、hash 口径（dict 键排序、binding 排除缺省值）、YAML 重复键、发布闸门的签发人必填 / 原子写入 / release_id 防并发，以及 BOM/CRLF、statement 吞段、frontmatter 继承。三侧测试和基线持平：plate 557 / 执行器 615 / 平台 765+2（环境原因）/ 前端 1133，vue-tsc 0 错。
- **老问题还在**：有几处「声称已修」的修复靠手工构造条件的测试通过，真实路径上并没有生效。提交信息仍然偏乐观，例如「四项必检全部强制」「种子 reviewed 词条的边同样遍历」「统一 check」，这三条都和实测不符。

### 第三轮必修（多数是小改）

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| R1 | **C 类闸门实际永远不会触发** | 已复现。C1–C3 按 `getattr(st, "_source")` 区分来源，但生产代码里没有任何地方设置 `_source`，所有片段都落进同一个 `<unknown>` 来源，所以永远不会报。`test_c1` 是手工设置了 `_source` 才通过的，而且它用的 rule 带 cap 槽位，这个写法已经被新的 S1 规则拒掉了。复现：两个 PRD 把同一个 outcome 挂到不同 cap 上，照样能发版 | 解析器在 statement 上记下来源文件（或者把来源显式传给 C 检查）；补一条跨两个真实文件的 release 级测试 |
| R2 | **全局 release 路由会把整个 `systems/` 当成一个系统来冻结** | 已复现。`routes_grammar.py:868` 取不到系统名时得到 `""`，于是对 `systems/` 本身跑发布闸门。gaps 和 check 这次都加了 400 守卫，release 漏了。现在只是因为 `common/system.md` 过不了 F2 才没真的冻结出去 | 和 gaps/check 一样，没有系统名直接返回 400 |
| R3 | **155 个 md 里有 154 个不再是规范形** | 已复现。渲染器强制双引号以后，原来的单引号标量（`'200'`、时间字符串）都会改成双引号；含 `": "` 的字符串也会被多加引号。第一次 `plate review` 或任何回写，都会把整个文件改一遍 | 单独一个提交把 `systems/` 全量重新渲染一次；CI 加一道 `render(parse(x)) == x` 检查 |
| R4 | 引用闭包的起点没有包含全部 reviewed 词条 | 遍历只从「被 reviewed 块引用的词条」出发。一个 reviewed 词条如果没被任何块引用，它自己 refers 到 draft 词条、或父节点是 draft，照样能发版（第一轮的两个复现依旧成立） | 以所有 reviewed 词条为起点做闭包遍历 |
| R5 | **CI 按现在的写法会一直是红的**，而且漏掉了 common | 执行器测试那一步在收集阶段就报错（`test_launcher_dual_read.py` 依赖平台后端，需要 `cryptography`，但 `.[dev]` 没装）。common 自身的词条从来不检查：坏 id、孤儿父节点、悬空 refers 都能通过。`common/system.md` 本身也过不了 F2 | 补装依赖，或者把这一步拆到平台 job 里；CI 加上 `plate check common`，并给 common 的 F2 定一个口径（比如 common 豁免 system 块） |
| R6 | **存量戳迁移脚本有风险** | ① 默认 `--db` 是写死了账号密码的 PG 连接串，进了仓库；② 不管戳是不是已经过期，一律用当前真源覆盖，一个本该 pending 的真实变更会被抹掉；③ 没有 dry-run；④ 代码里仍然没有冷启动重落基线，没跑过脚本的环境照样 149 个全部 pending | 去掉默认连接串，改成必填参数或读环境变量（**如果仓库是公开的，这组凭据要轮换**）；加 `--dry-run`；只覆盖非 hex 格式的旧戳；`catalog_diff` 遇到非 hex 戳按首见基线处理 |
| R7 | 前端目录列表行没改完 | `CaseComposerCatalog.vue:443-446` 还在映射 `e.api` / `e.version`。按路径搜索永远搜不到；`/full` 没返回时表头不显示 method/path；`/full` 失败时加出来的步骤是 `GET ''`。列表行是 `any` 类型，所以 vue-tsc 发现不了 | 列表行改读平铺的 `method` / `path` |
| R8 | `children` 里的说明字段还会影响 shape_hash | `_decl_shape` 只处理了顶层声明，嵌套 `children` 里的 `description` 改了照样触发 pending（`fin.order.order_add` 上复现）。`systems/` 里有 46 个文件用到 `children` | 递归剔除。注意：PG 里的戳已经按现在的口径迁移过了，口径修正后要再跑一次迁移（脚本本身支持重跑） |
| R9 | 2049abd 引入的回归：兜底轮询停不下来 | SSE 收到 404（执行已删除）时 `detail` 被置为 null，兜底定时器因此每 3 秒拉一次 404，直到页面卸载。重连次数用完后也是一样，而页面横幅这时写的是「已停止刷新」。另外 `_refreshOnce` 不检查代际号，上一个执行的迟到响应可能覆盖当前的 detail | 404 或重连次数用完时视为终态，停止轮询；`_refreshOnce` 也加代际比对 |
| R10 | HTTP check 和 CLI check 结论不一样 | CLI 已经带上 common，HTTP 没有：引用 common 词条时 HTTP 会误报 S2 阻塞，也不跑 `validate_tree_ids` | HTTP 调用 CLI 用的同一个函数 |
| R11 | 并行执行时引擎日志回退会拿错文件 | 第二个及以后的 worker 写的是 `server-engine-N.log`，回退逻辑却固定返回第一个 worker 的 `server-engine.log`，用户看到的是别的 worker 的日志 | 按 case 所属的 worker 去找；找不到就返回 404，不要回退 |

### 修订十降级清单里漏掉的项（既没修，也没写进 S1.5）

按修订十的合入条件，这些项要么修掉，要么补进 S1.5 清单，否则就是被悄悄丢掉了：

1. **P4 单向依赖守卫测试 `test_v3_no_reverse_import`**：设计、pyproject、`protocols.py` 里都在引用它，但这个测试从来没有存在过。补起来很便宜（扫描 `gimbal_plate` 里有没有 `import gimbal`），建议直接补，不要降级。
2. **批次 C**：S1.5 只写了「字段级对拍」。框架 dim 的全局挂载没写；`hasattr(__file__)` 那几条恒真测试、binding 枚举漂移测不出来，也都没写。
3. **批次 D 的 Agent 编写 skill**：没交付，也没写进清单。
4. **manifest**：没有 shape_hash（修订九要求的），call 投影没有 hash，`_call_projection` 仍然和 `_render_call` 是两份实现。
5. **diff**：release 号按字符串排序（第 10 个以后会取错最新版本）；release 号的月份用的是 UTC，青岛时间每月头几个小时会算到上个月；只写了 `--base working/main`，两个 release 之间的字段级差异（G7）没写。
6. **`check --stdin`** 不跑 T 类和 S2 规则；S2 的 finding 没有文件:行号。
7. **G1 的 `full_schema`** 没有 HTTP 入口。
8. **批次 E**：没有从用户故事派生 Scenario，也没有执行；第 9 项（step 能否表达分支）仍然没验证，但路线图 P4 的验收描述还写着全链走通。内容层面：DELETE 接口挂的还是 `cap:user.disable`，`caps_without_define` 仍是 4。
9. **A7**（服务画像文档）、**B6**（记入路线图）、**B3**（删掉的接口只在提交信息里算白名单，设计没有修订）。
10. **`review <词条 id>`** 会把整个词条列表块都改掉。S1.5 的「N4 单块回写」管的是重写整个文件，不覆盖这个「目标粒度」问题。
11. **`responses` 为空仍能通过校验**；YAML 合并键（`<<:`）现在解析会报错；复合键（`? [a, b]`）抛出的是裸 TypeError。
12. **G4 结构化锚点**，以及 `plate_client` 按快照让缓存失效（9.1）。
13. **`correction_log`**：现在只有在没有 finding 时才能发版，所以已发布 manifest 里这一项永远是空的，而 §8.1 要求的是记录矫正变更的引用。**需要你决定**：改成记引用，还是正式删掉这个字段。
14. **S1 期间的一个行为要写清楚**：已经可以通过 `POST system/action/release` 发版，但 `ref` 延后了，平台会一直读 working。§8.3 说的「编排和执行钉住 release」在 S1 期间不成立，S1.5 清单里应该明确写出来。
15. **测试仍然往仓库里写东西**：`test_release_http_action_writes_manifest` patch 错了模块，仓库的 `plate_artifacts/fin/releases` 里已经有 2026.10.1–10.4 四个版本；`test_cli_d` 会写到 `systems/fin/` 下。

### 需要你拍板的

- **YAML 解析端的口径。** 修订十定的是继续用 1.1，只在渲染时强制加引号，理由是 ruamel 要新增依赖。但解析端仍然会悄悄改值：手写的 `enum: [01, 08]` 会读成 `[1, '08']`，`on` 读成 True，`12:30` 读成 750，而且没有任何警告。另外 `'0o10'` 渲染时也没加引号。有一个不新增依赖的办法：在 PyYAML 上自定义 resolver，换成 1.2 core 的隐式类型规则，大约 30 行，还能用 C 加载器提速。如果维持 1.1，至少应该对这几类歧义标量给出 F 级告警。
- **`correction_log` 的去留**，见上面第 13 条。

### 设计文档

- **§7.2 前后矛盾**：正文仍写着 `/full` 带 `content_hash`，但修订九第②条明确说对象 hash 不通过 HTTP 暴露（代码按后者实现）。§7.2 应该改掉。
- **§7.1 与修订十不一致**：正文写的还是「键序按 M2 定义序」，修订十已经改成 dict 键一律排序。

---

## 第三轮复核（2026-10-08，HEAD 0e1307b）

> 范围：2049abd 之后的 3 个提交（5ebadd1、fda9abd、0e1307b）。
> 对照：仓库设计修订十一（含 S1.5 补遗）。
> 方法：四路复核员重跑全部复现脚本，在干净副本里模拟 CI。标「已复现」的条目我又独立验证过一遍。

### 结论

**R1–R11 中 9 项修复、2 项部分修复，降级清单基本补齐。合入前还差 4 个小修。**

三侧测试与基线持平：plate 564 / 执行器 615（需手动补一个依赖）/ 平台后端 766 + 2 个环境失败 / 前端 1136，vue-tsc 0 错。测试不再往仓库里写东西（已对比测试前后的 mtime）。

### R1–R11 逐项

| # | 结论 | 说明 |
|---|---|---|
| R1 C 类闸门 | ✅ | 两个 PRD 的冲突会阻塞发版；同文件内的冲突正确忽略；C2、C3 在真实冲突下都会触发。真实树上 0 finding，platform 和 fin 都能发版 |
| R2 全局 release 路由 | ✅ | 全局路由下 release / gaps / check 都返回 400，按系统的路由正常 |
| R3 规范形 | ✅ | 155 个文件全部满足 `render(parse(x)) == x`，`test_canonical_tree` 守门。全部对象的 object_hash 和 2049abd 一致，说明重渲染没有改动数据 |
| R4 引用闭包 | ✅ | 第一轮的两个复现现在都会阻塞 |
| R5 CI | ⚠️ 仍会是红的 | `cryptography` 已补，但执行器测试在收集阶段又缺 `pydantic-settings`。手动装上后 615 个全过。common 已进入检查循环 |
| R6 戳迁移脚本 | ⚠️ | 已改好的部分：去掉了凭据、有 dry-run、只读、可安全重跑、过期的 hex 戳会保留并报告。见下面 N3、N4 |
| R7 前端目录行 | ✅ | 改读平铺的 method / path，按路径搜索能命中；`/full` 失败时用轻列表兜底，不再产出 `GET ''` |
| R8 嵌套 children 的说明字段 | ✅ | 45 个接口的 shape_hash 因此变化，PG 里的戳已按新口径重迁 |
| R9 兜底轮询 | ⚠️ | 404 死循环已修，迟到响应的竞争已修。见下面 N5 |
| R10 HTTP check 与 CLI check 一致 | ✅ | 共享 `validate_system_tree`，引用 common 的场景下两边结论相同 |
| R11 并行 worker 的引擎日志 | ❌ | 没改，`executions.py:480` 仍固定返回 `server-engine.log` |

YAML 解析改为 1.2 core（自定义 resolver，没有新增依赖）：`on` / `12:30` / 日期都不再被悄悄改值；60 个刁钻字符串在 1.1、1.2 和严格加载器下都能原样读回。`correction_log` 已按决定删除。`test_v3_no_reverse_import` 现在会真正扫描，变异测试中静态 import 都能被拦下，只有 `importlib` 动态导入能绕过。

### 本轮新发现

| # | 级别 | 问题 | 改法 |
|---|---|---|---|
| N1 | **合入前修** | **YAML 空值被读成 `''` 而不是 `null`**（已复现：`a:` / `b: ` / `- ` 得到 `{'a': '', 'b': '', 'd': ['']}`）。自定义 null resolver 没有登记空串这个首字符。后果：手写时留空的字段变成空串，进入规范形和 hash；`refers:` 或 `replaced_by:` 留空会变成指向 `''`；`request:` 留空会报一条让人看不懂的校验错误。代码注释说「空值仍为 null」，与实际不符 | null resolver 的首字符列表补上 `''`，再加一条测试 |
| N2 | **合入前修** | CI 执行器那一步缺 `pydantic-settings` | 补进 `.[dev]` |
| N3 | **合入前修** | **冷启动重落基线会吞掉真实变更。** `catalog_diff` 和迁移脚本遇到 semver 旧戳时，直接以当前 plate 形状作为基线。如果旧 `spec_json` 里有一个后来被删掉的字段（本该产生一个 removeField 待适配），重落后这个字段就消失了，也没有任何报告。唯一的信号是 `baselinedNow` 计数，前端没有展示 | 重落之前先跑一次 `diff_field_specs(旧 spec_json, 当前 full)`，ops 不为空就保留为待适配或报异常；只有 ops 为空才静默重落 |
| N4 | 处理 | **凭据仍留在 git 历史里。** `gimbal:gimbal@127.0.0.1:15432` 在 77c16eb、08b9841、6884acb 中都能找到，HEAD 的 `compose.pg.yml`、ETL json 等文件里也有。提交信息和 runbook 里还写了内网 IP `192.168.22.106`。只删 HEAD 里的这一处没有实际意义 | 仓库如果是公开的：远端 PG 不要使用这组口令（或者轮换），本地开发用的口令和远端分开。是否清理历史由你决定 |
| N5 | 建议修 | **e63ddc1 加的保险被撤掉了。** 现在 SSE 重连次数用完时，兜底定时器也一起停。可兜底存在的意义恰恰就是 SSE 长期不通的场景（例如经过会缓冲的代理），这种情况下状态又会卡在 running。另外，上一个执行迟到的 404 没有做代际比对，可能把当前执行的轮询停掉 | 重连次数用完只停 SSE，兜底继续拉取，横幅改成「实时推送已断开，按 3 秒刷新」；404 分支也加代际比对 |
| N6 | 建议修 | 迁移脚本会把 e6a9f4c 到 77c16eb 之间平台代码写下的戳（binding 带缺省值、键未排序）误报为「真源已变」 | 在报告里注明这种可能；或者再补一种旧口径识别 |
| N7 | 待定 | **C3 可能误报。** 一份文档只描述了状态机的一部分（a→b），另一份描述了完整链（a→b→c），这时 C3 会阻塞。C1 的「集合一致」按设计字面就是子集也算不一致，文档多了以后会频繁触发 | **需要你拍板**：C1 / C3 是比较「全等」还是「不冲突」（子集允许，矛盾才报） |
| N8 | 小 | `.gitattributes` 写的是 `systems/** text eol=lf`，以后往 `systems/` 放截图或 PDF 会被当成文本改写换行符，文件会损坏 | 收窄为 `systems/**/*.md text eol=lf` |

### 没修、也没写进 S1.5 的剩余项

| 项 | 现状 |
|---|---|
| F3 在 check 阶段不完整 | 修订十一说共享引擎包含「树级 F3」，但跨文件的重复 statement id、重复 endpoint id 在 check 时是 0 finding，要到发版才拦。入库闸门因此漏掉 F3 |
| 非 editable 安装 | `pip install .` 以后运行 `plate` 仍然报 `ModuleNotFoundError`；CI 用的是 `-e`，所以发现不了 |
| B3 删掉的接口 | 仍然只记在提交信息里，设计 §11 的 B3 没有更新 |
| 批次 C 的恒真测试 | `hasattr(__file__)` 那几条没有点名写进 S1.5 |
| P4 验收措辞 | 设计第 679 行、路线图第 340 行仍写着「编写 → 评审 → 入库 → 编排 → 执行 → 过闸门」全链走通，但派生 Scenario 和执行已经列进 S1.5，验收条件实际上没有满足 |
| 校验与工具的零散项 | `load_types` 的路径少回退一级（在仓库外运行时，所有文件都报 F1）；`PlateRelease` shim 必然失败；S4 缺失；T5 不比较别名和他人的 label；T3 / T6 对 common 里的目标误阻塞；YAML 合并键 / 复合键；标题切分不识别代码块；`responses` 为空仍能通过；列表块不继承 service；P8 嵌套测试仍是恒真的；平台侧 hash 显示截断、`open_batch` 可能落空戳、`_ep_key_map` |

建议的处理：前 5 项要么修掉，要么写进 S1.5；最后一行可以整体作为 S1.5 的「质量尾项」登记一条，不必逐个修。

### 合入判断

修完 N1、N2、N3，再把上表前 5 项修掉或登记进 S1.5，就满足修订十一的合入条件。N4 的凭据和 N7 的 C 类语义需要你决定，不阻塞合入。

---

## 第四轮复核（2026-10-08，HEAD 9ca0267）

> 范围：0e1307b 之后的 2 个提交——09c1779（执行器：退役旧 scratch 伪路径，并迁移存量用例）、9ca0267（第三轮收口，`gimbal_plate` 上移为 `src/` 下的同级包）。

### 结论

**第三轮的必修项全部修好，CI 在干净副本里逐步模拟全部通过。阻塞合入的只剩 1 处两行改动。**

测试结果（`PYTHONPATH=src`，与 editable 安装或 CI 一致）：

| 范围 | 结果 |
|---|---|
| plate | 591 |
| 执行器 unit | 601（排除 `test_defect_fixes.py`：它请求外部 URL，属环境项） |
| 执行器 compiler + integration | 108 |
| 平台后端 | 782（另 2 skip） |
| 前端 vitest | 1138 |
| vue-tsc | 0 错 |

之前几轮记的「后端 765 通过 + 2 失败」，原因是我们的环境没把 `src` 放进路径，后端测试其实没有回归。

### 第三轮项逐项

| 项 | 结论 |
|---|---|
| N1 空值读成 `''` | ✅ `a:`、`- `、`{k: }` 都读成 null，显式写的 `''` 仍是空串；新增的 `test_yaml_core_schema` 有实际意义 |
| N2 CI 依赖 | ✅ CI 全部步骤通过：editable 安装、common/fin/platform 三个系统的 check、方言纪律 59、plate 591、执行器 615、非 editable 冒烟 |
| N3 冷启动吞掉变更 | ✅ semver 戳上真实的 removeField 会保留为待适配。没有形状缓存的戳仍会静默重落（没有可比对的东西，可以接受），`baselinedNow` 前端仍不展示 |
| N5 兜底轮询 | ✅ 重连用尽只停 SSE，兜底继续拉；三处 404 都做了代际比对；卸载时无泄漏。小瑕疵：兜底拉到终态停下后，横幅仍显示「按 3 秒轮询」 |
| N6 迁移脚本误报中间态戳 | 未单独处理（影响小） |
| N7 C1/C3 口径 | ✅ 已定为「不冲突」：子集或互补都放行，真实矛盾仍会阻塞。真实系统树上 0 finding，platform 和 fin 都能发版 |
| N8 `.gitattributes` | ✅ 已收窄到 `systems/**/*.md` |
| R11 并行 worker 的引擎日志 | ✅ 只有一个 worker 时回退，多个 worker 返回 404，不会再给出别的 worker 的日志 |
| F3 入库闸门 | ✅ CLI 能拦住跨文件重复的接口 id、路由键、片段 id；finding 里的行号仍是 0 |
| B3 记录、P4 措辞 | ✅ 设计和路线图都已改；P4 现在明确写「管道走通，不含执行」 |
| 批次 C 恒真测试 | 已写进 S1.5，测试本身没改 |

hash 稳定性：所有对象的 object_hash 和 shape_hash 都与 0e1307b 一致，155 个文件仍是规范形，包上移没有影响数据。

### 本轮新发现

| # | 级别 | 问题 | 改法 |
|---|---|---|---|
| M1 | **合入前修** | `validation.py:98` 和 `release.py:366` 用 `parents[2]` 求仓库根，包上移后这一级是 `src/`（上移前就已经少算一级，这次改动没修到）。已复现：工作目录不在仓库根时，`load_types()` 静默返回 0 个模板，导致 `/api/type` 为空、校验不带模板。用 `run_plate.py` 从它自己的目录启动 plate 就会中招。CI 从仓库根运行，有工作目录兜底，所以测不出来 | 两处改成 `parents[3]`；模板一个都没加载到时报错，不要静默；`PlateRelease` shim（解析到 `src/systems/fin`、不传签发人，必然失败）修掉或删掉 |
| M2 | 修文档或补实现 | **非 editable 安装后只有 `plate --help` 能用。** 仓库根是从包所在位置推出来的，wheel 安装后指向 venv，`check`/`gaps` 在任何目录下都报「未知系统」，`PLATE_SYSTEMS_PATH` 也不生效。修订十二写的是「wheel 下双入口均可用」，CI 冒烟只跑了 `--help`，所以发现不了 | 二选一：修订十二改成「wheel 安装仅入口可用；数据目录随 S1.5 的路径可配置一起解决」；或者现在就让 CLI 认 `PLATE_SYSTEMS_PATH` 或 `--root`，冒烟改跑 `plate check` |
| M3 | 待定 | C1 判的是「所有来源的交集为空」，不是「任意两份文档没有交集」。三份文档两两有交集、但三者没有共同值时会阻塞，比如 {del,demote}、{demote,login}、{login,del} | **需要你拍板**，结论在 §7 补一句即可 |
| M4 | 小 | 包上移留下的旧路径：6 处测试或工具仍往 `sys.path` 加 `src/gimbal-plate`（`test_plate_gimbal_contract.py`、`test_run_injection.py`、gimbal-bootstrap 的 3 个测试、`ab_dispatch_dump.py`）。现在只是因为 editable 安装让包可导入才能通过；不把 `src` 放进路径时，后端测试在收集阶段就会中断。`gimbal_bootstrap/case_builder.py`、`contract_gen_py.py` 指向的路径早已不存在（非主线工具） | 统一删掉这些 `sys.path` 修补，依赖 editable 安装或 `PYTHONPATH=src` |
| M5 | 记录 | 执行器 09c1779 的存量迁移靠一个没提交的驱动脚本完成，提交信息里提到的备份 `legacy-path-migration-backup.json` 也不在仓库里；仓库内的 `migrate_legacy_case.py` 只能处理文件。迁移逻辑本身可重复执行。另外，没迁移的旧引用现在会在编译期报 `INPUT_UNSATISFIED`，不再拖到运行时每步都失败，这个行为变化是合理的 | 把驱动脚本和备份的存放位置写进 runbook，方便回滚和追溯 |

### 仍未修、也未登记的（建议一次性写进 S1.5 的「质量尾项」）

- **校验规则**：S4 缺失；T5 不比较别名和他人的 label；T3/T6 对 common 里的目标误阻塞。
- **YAML 边界情况**：合并键 `<<` 在 system/defaults 块里静默变成字面量键；复合键抛出的是裸 TypeError；代码块里以 `#` 开头的行仍被当成标题切分。
- **模型与测试**：`responses` 为空仍能通过；列表块不继承 service；P8 嵌套测试仍然恒真；`test_yaml_core_schema` 建议补一条断言，确认显式 `''` 读出来仍是空串。
- **平台侧**：hash 显示截断不一致；`open_batch` 可能落空戳；`_ep_key_map`；`baselinedNow` 没有界面展示。

### 合入判断

改完 M1（两行，加上模板为空时报错），并把 M2 的文档措辞改准，就满足修订十二的合入条件。M3 需要你拍板；M4、M5 和上面的尾项可以合入后再处理，或者统一登记进 S1.5。

---

## 第五轮评审（2026-10-08，HEAD b895377）：增量复核 + 独立全量评审

> 范围：
> - 增量部分：91ab393、b895377，复核 M1–M5。
> - 全量部分：另请一位没参与过前几轮的复核员，对 `gimbal_plate` 的现状做整体代码评审，不看 diff，S1.5 已登记的项不计。
>
> 测试：plate 593 / 执行器 601 + 108 / 平台后端 782 / 前端 1138，vue-tsc 0 错。CI 在干净副本里逐步模拟全部通过，包括 wheel + `PLATE_REPO_ROOT` 冒烟。测试不再往仓库里写东西。

### 增量：M1–M5

| 项 | 结论 |
|---|---|
| M1 路径深度 | ✅ 两处已改为 `parents[3]`；工作目录在 /tmp 时能加载 9 个模板；模板为空时抛 RuntimeError，没有误伤 tmp 树测试和 HTTP 启动；shim 已删，没有残留引用 |
| M2 wheel 安装 | ✅ 设了 `PLATE_REPO_ROOT` 后，check / gaps / release / diff / term search 都能用。小问题：不设时报的是裸 traceback，没提示要设这个变量 |
| M3 C1 口径 | ⚠️ §7 已写明「全部来源交集为空」，但新加的测试用的是三个单元素集合，两两本来就不相交，按两两口径也会报，所以没钉住这个决定。应换成环形用例 {del,demote}/{demote,login}/{login,del}（复核员手动探针确认，现行实现对环形会阻塞） |
| M4 旧路径 | ✅ 清干净了。后端测试不加 `src`、不装包也能完成收集 |
| M5 迁移驱动入库 | ❌ 见下面 B2 |
| 质量尾项登记 | ✅ S4/T5/T3/T6、YAML 边界、空 responses、列表块继承、P8 恒真测试、平台侧四项，都写进了 S1.5 |

### 新发现：阻塞项

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| B1 | **全局动作路由的系统名可被请求体控制，存在路径穿越和任意位置写入** | 三个 system 动作取系统名用的是 `path_params.get("system") or body.get("_system")`（`routes_grammar.py:791/824/850`），全局路由 `POST /api/system/action/{name}` 不做任何校验。已复现：`check` 传 `{"_system":"../tests/plate"}` 返回 200；`release` 传指向任意目录的 `_system`，会把 manifest 写进 `plate_artifacts/<任意名>/`；末段是 `..` 时 manifest 会写到构件池外面。另外，`{"_system":"nonexist"}` 的 check 返回 **200 ok:true**，调用方会拿到假绿。plate 不做认证，靠内网边界，但这仍然是可写文件系统的入口 | 系统名只从路径参数取，删掉 `_system`；先校验 `reg.has_system()` 和名字格式 `^[a-z0-9_-]+$`，再确认 `resolve()` 后的路径仍在 systems 根目录下；系统不存在返回 404 |
| B2 | **PG 迁移脚本的备份存的是迁移后的数据** | `backup[sid] = d` 只保存了引用，紧接着 `d["definition"] = out` 原地修改，备份里实际是新路径（假连接模拟确认）。备份文件在全部更新完成后才写；没有事务，中途失败会留下迁移了一半的表；重跑会覆盖上一份备份；备份文件也没进 `.gitignore`。**09c1779 那次远端迁移如果走的是同一段逻辑，当时的备份很可能也不能用来回滚**（`order_dispatch-rebind-backup.json` 同理，需要确认） | 备份做深拷贝，并在任何更新之前落盘；所有更新放进一个 `conn.transaction()`；默认 dry-run；`*-backup.json` 加进 `.gitignore`。**另外请人工核对一下现有备份文件里存的是旧路径还是新路径** |

### 新发现：主要问题

| # | 问题 | 证据 | 改法 |
|---|---|---|---|
| J1 | **release 的检查比 check 弱** | `release_system` 自己组装系统树，不调用 `validate_tree_ids`，也不做路由键 F3。已复现：路由键重复时 check 会阻塞，release 却照常冻结。修订十二说「check 与 release 同口径」，实际只单向成立 | release 内部直接调用 `validate_system_tree`，只保留发布闸门特有的步骤 |
| J2 | **服务端有三套找数据根目录的机制** | CLI 用 `PLATE_REPO_ROOT`；loader 用 `PLATE_SYSTEMS_PATH`；HTTP 动作和 `load_types` 两个都不认。后果：服务设了 `PLATE_SYSTEMS_PATH` 时，接口查询读的是 A 树，HTTP release 冻结的却是 B 树；wheel 部署下 HTTP `gaps` 会**静默返回 `endpoints_total: 0`**，`/api/type` 和 check 返回 500。设计把「路径可配置」放在 S1.5，但它现在的风险是**冻结错内容**，不只是好不好用 | 至少把「HTTP 动作和 `load_types` 都用 loader 的根目录」提到本分支做；gaps 遇到 0 个接口时报错 |
| J3 | **不校验接口的 `system` 字段和所在目录是否一致** | `systems/fin/` 下写 `system: platform` 的接口，`check fin` 能通过；release 把它冻结进 fin 的 manifest，loader 却把它注册到 platform 下 | `validate_system_tree` 加一条阻塞规则；loader 加断言 |
| J4 | `field-defaults` 对没有请求体的接口返回 500 | `field_defaults.py:97` 直接访问 `endpoint.request.declarations`，没判断 request 是否为空；其他调用点都判断了。在 `fin.account.query_balance` 上复现 | 加空值判断 |
| J5 | CLI 和 HTTP 报内容错误的方式不一致 | CLI check 把 DialectError 转成 F0 时靠拆分报错字符串（Windows 的 `C:` 路径会拆错，明明 `e.source`/`e.line` 都有）；HTTP check 直接 500，并在消息里带出绝对路径；`plate gaps`/`release` 打的是裸 traceback | 在 `validate_system_tree` 里统一捕获，用 `e.source`/`e.line` 生成 F0 |

### 新发现：次要问题

- **注册表没有回滚**：路由键重复抛错之前，`by_id`/`by_service`/`by_tag` 已经写入，占位服务也已创建（S1.5 做原子重载时会升为主要问题）。
- **release 的文件和输入处理**：
  - manifest 用普通写入，不是临时文件 + rename；
  - 目录里混入 `2026.10.x` 这类名字时，release_id 生成会抛 ValueError；
  - 0 个对象也能发版，common 也能单独发版（违反 N3）；
  - `checklist` 传入非字典时返回 500。
- **系统作用域的对象动作不校验归属**：`/api/systems/platform/endpoint/fin.…/action/*` 会直接作用在 fin 的接口上。
- **`export/gimbal.py` 的 `_interpolate`**：只处理顶层值，而且会把数字转成字符串（`'${count}'` 变成 `'5'`），嵌套值不处理。
- **同一段遍历系统树的代码有 5 份**（routes_grammar、validation、release、cli、loader），J1 就是这些副本之间的分歧造成的。
- **测试缺口**：
  - 没有覆盖 `_system` 注入、release 与 check 的一致性、loader 的失败模式、CLI 的 diff/release/reload；
  - `test_export_dispatch.py:144` 断言的是 `hasattr(typing, "get_args")`，测的其实是标准库，属于恒真测试，S1.5 没有登记；
  - bootstrap 测试捕获的是所有 ImportError，`gimbal_plate` 自身真的导入失败时也会被静默跳过，建议收窄到 `gimbal_plate.systems.*`；
  - 后端有 4 个 contract 测试在执行器 CLI 不可用时报失败，应该改成跳过。
- **性能**：目前没问题（149 个接口 `/full` 约 45ms）。shape_hash 每次请求都重算，中间件会重新序列化每个响应体，到 700 个接口时 `/full` 估计约 250ms，等快照落地后一起缓存即可。
- **其他**：前端横幅靠匹配「按 3 秒」这段文字来清除，改文案就会失效；迁移脚本的 docstring 里写了内网 IP。

### 整体代码质量（独立评审员的结论）

- **优点**：模块边界清楚（dialect / validation / release / http）；YAML 严格加载，没有 `eval`/`pickle`/`subprocess`；构件按内容寻址、原子写入，release_id 用独占方式创建；错误信封统一；注释能追溯到设计；593 个测试运行很快。
- **短板**：「同一引擎」只是口头约定，没有在结构上强制，遍历系统树的代码复制了 5 份，而且已经出现分歧；HTTP 动作信任请求体和包所在的目录位置；CLI 与 HTTP 的错误处理不一致；注册表失败时不回滚；测试覆盖了正常路径，但很少测失败模式和恶意输入。

### 合入判断

**B1、B2 必须先修。** B1 改动很小；B2 除了改脚本，还要人工确认现有备份能不能用。

建议同一轮一起修：
- J1：release 改为直接调用 `validate_system_tree`。这样把 5 份遍历代码收成 1 份，J1、J5 就从根上解决了。
- J2：至少让 HTTP 动作和 `load_types` 使用 loader 的根目录，并给 gaps 加 0 接口保护。
- J3、J4：都是几行的改动。

其余次要问题可以登记进 S1.5。

---

## 第六轮复核（2026-10-08，HEAD 528766b）

> 范围：f383b2e（N4 拍板：仓库为私网，凭据维持现状）、528766b（第五轮收口：B1/B2 + J1–J5）。
> 方法：第五轮的独立评审员重跑自己的复现脚本，并加大 B1 的攻击面；另两路复核员在干净副本里模拟 CI，并对比 release 与 check 的阻塞结果。

### 结论

**B1、J3、J4 已修好，B2 的脚本逻辑也修对了，release 和 check 的阻塞集合已经一致；但新加的测试让 CI 变红了，需要再修一个小点才能合入。**

测试结果：
- plate：597 通过（排除新测试文件）；装上 asyncpg 后 599 通过。
- 执行器 615，平台后端 782，前端 1138，vue-tsc 0 错。
- 全部对象 hash、call 投影与 b895377 一致，重构没有让 hash 漂移。

### 逐项

| 项 | 结论 | 说明 |
|---|---|---|
| B1 路径穿越 | ✅ | 请求体里的 `_system` 被忽略，全局路由返回 400。`%2e%2e`、`..%2F`、`fin%2F..%2Fplatform`、`.`、`FIN`、`fïn` 都返回 404；systems 下指向外部的符号链接，在动作路由上也返回 404 |
| B2 迁移脚本 | ✅ 逻辑正确，⚠ 文档说法不成立 | 默认 dry-run；备份是旧态，在第一条 UPDATE 之前落盘；全部更新在一个事务里，中途出错整体回滚。但还有两处缺口：已有备份会被直接覆盖（有历史备份的机器上再跑 `--write` 会把它冲掉），备份前 `setdefault("kind")` 已经改过数据。另外 docstring 写「原态可确定性重建」**不成立**：映射是多对一的，迁移前就写了 `$.call.response.*` 的场景反推时会被错改回旧路径，也没有反向脚本。应改成「尽力而为的回滚，没有真正的变更前备份」 |
| J1 只有一个装配点 | ✅ 主路径 | release 现在是 `collect_system_tree` → `validate_system_tree` → 闸门自身的步骤。构造了 5 棵测试树，check 和 release 的阻塞码完全一致。另有 3 处独立遍历：CLI 的 term search、CLI 的 review、loader 的 J3 检查 |
| J2 同一个数据根 | ⚠ | 设了 `PLATE_SYSTEMS_PATH` 后，查询、check、gaps、release 都读同一棵树。**新发现**：`types.yaml` 的来源不统一。release 读的是 systems 根旁边的 `types/`，check、gaps 和 CLI 先找工作目录、再找包所在位置。已复现：同一棵树 check 通过、release 被阻塞；反过来的情况也能复现。构件目录仍然写在包所在仓库下（已列入 S1.5） |
| J3 system 字段与目录一致 | ✅ | check 报 F3，loader 启动时直接失败 |
| J4 field-defaults | ✅ | 无请求体的接口返回空列表 |
| J5 方言错误统一 | ⚠ | check 报 F0 并带正确行号。但 release 遇到方言错误时只返回一条消息、没有 report，HTTP 422 里也没有 findings 列表；`plate gaps` 和 `term search` 仍会打印裸 traceback |
| M3 环形测试 | ✅ | 换成多元素的环形用例后，按两两口径实现会失败，确实把「全部来源交集为空」这个口径钉住了 |

### 新发现

| # | 级别 | 问题 | 改法 |
|---|---|---|---|
| X1 | **合入前修** | **CI 变红**：新增的 `test_migrate_pg_driver.py` 会加载迁移脚本，脚本顶层 `import asyncpg`，而 `.[dev]` 里没有 asyncpg，于是整个 `pytest tests/plate` 在收集阶段中断 | 脚本改为在 `main()` 里导入 asyncpg，测试里加 `pytest.importorskip("asyncpg")`；或者把 asyncpg 加进 dev 依赖 |
| X2 | 建议修 | 同一棵树上 check 和 release 读的 `types.yaml` 可能不是同一份（见 J2） | 从解析出的数据根算一次 types 路径，传给两边 |
| X3 | 建议修 | **common 仍能单独发版**，0 个对象也能发版（违反 N3）。上一轮的次要问题里提过，没修，也没写进 S1.5 | release 拒绝 `common`，拒绝 0 个对象的发版 |
| X4 | 小 | 按系统路由的对象动作不检查归属：`/api/systems/platform/endpoint/fin.…/action/field-defaults` 返回 200，同一个 URL 的 GET 详情却返回 404 | 在这里复用 GET 详情的归属检查 |
| X5 | 小 | loader 跟随符号链接时不做包含性检查，指向外部的树会被加载出来并对外提供查询（此时动作路由返回 404，前后不一致）；动作只接受 `^[a-z][a-z0-9_-]*$`，loader 却接受任意目录名 | loader 加上同样的 resolve 包含性检查和名字规则 |
| X6 | 小 | 迁移脚本会覆盖已有备份；docstring 里「可确定性重建」的说法需要更正（见 B2） | 备份文件名带时间戳，或者文件已存在就拒绝运行；改写 docstring |

### 合入判断

修完 X1（几行）就满足修订十三的合入条件。X2、X3 建议同一轮修掉，都是几行的事。X4–X6 可以登记进 S1.5。

---

## 第七轮复核（2026-10-08，HEAD 6ab713d）

> 范围：6ab713d（第六轮收口：X1–X6，加上 J5 的残留）。
> 方法：在干净副本里模拟 CI，并且**不装 asyncpg**；重跑全部对抗用例；由独立评审员对这次的 diff 做最后一遍检查。

### 结论

**只差一处 release 的检查顺序（R1，我也独立确认过）。修完就可以合入。**

- **CI**：在不装 asyncpg 的干净副本里逐步模拟，每一步都通过。plate 598 + 1 skip、方言纪律 60、执行器 615、wheel 冒烟通过；三个系统的 check 都通过。
- **数据稳定**：platform 146 个对象、fin 23 个对象发版到临时目录，hash 和 call 投影都与之前一致。
- **两条闸门口径一致**：6 棵测试树上 check 与 release 的阻塞码完全相同，包括方言错误那棵（两边都报 F0）。

### 逐项

| 项 | 结论 |
|---|---|
| X1 CI 收集 | ✅ 没有 asyncpg 时驱动测试显示为 skip，不再报错；装上后 3 条测试都过 |
| X2 types 同源 | ✅ 本地 types 更宽松、更严格、缺失三种情况下，check 和 release 结论都一样 |
| X3 common 与空发版 | ✅ common 单独发版会被拒（CLI 退出码 1，HTTP 422）；全部是 reviewed 内容的首次发版正常；全是 draft 的发版被拒。**但见 R1** |
| X4 对象动作归属 | ✅ 用别的系统的接口返回 404，本系统的接口照常 200 |
| X5 loader 名字规则与符号链接 | ✅ 生效了，但跳过时**不留任何日志**，见 R4 |
| X6 迁移备份 | ✅ docstring 已更正为「尽力而为」。备份防覆盖基本起不到作用，见 R2 |
| J5 残留 | ✅ 发版遇到方言错误时 422 里带 F0 findings；`plate gaps` 和 `term search` 输出友好报错（`error: 文件:行`），退出码 2 |
| B1 回归 | ✅ 各种穿越写法仍返回 404 |

### 新发现

| # | 级别 | 问题 | 改法 |
|---|---|---|---|
| R1 | **合入前修** | **空发版虽然被拒，release 号却被占掉了。** `if not freeze_list` 这个检查在 `manifest_dir.mkdir()` 之后（`release.py:263-282`）。被拒两次之后，目录下会留下两个空的 `releases/2026.10.1`、`2026.10.2`，下一次真正的发版只能从 10.3 开始编号。而 `plate diff` 遇到没有 manifest 的目录会崩溃。这正是 X3 声称要防止的情况 | 先算出 `freeze_list` 并做空检查，再进入 mkdir 循环；补一条回归测试，断言被拒时没有创建任何目录 |
| R2 | 小 | 迁移备份防覆盖基本不会触发：文件名带的是秒级时间戳，只有两次运行落在同一秒内才会撞名；而且先 `exists()` 再写之间存在竞争。对应的测试要靠两次运行落在同一秒，会时过时不过 | 改用 `open(path, "x")` 独占创建；测试改为直接构造冲突 |
| R3 | 小 | 驱动测试已经把假 asyncpg 注入了 `sys.modules`，`importorskip("asyncpg")` 其实不需要，反而让这些测试在 CI 里永远被跳过 | 删掉 importorskip |
| R4 | 小 | loader 跳过非法名字或逃出根目录的符号链接时，直接 `continue`，不打日志，check 也不报。像 `fin.v2` 这样的目录能通过 CI 的 check，服务里却悄悄不出现 | 每次跳过都 `logging.warning`；check 对不合法的目录名报 finding |
| R5 | 登记 | 设了 `PLATE_SYSTEMS_PATH` 时，构件仍写在包所在仓库的 `plate_artifacts` 下，副本树发出的版本会和真实仓库的 fin 共用一个编号序列 | 在 S1.5「构件目录可配置」这一条里写明这个现象 |
| — | 待定 | 内容没有任何变化时再次发版，仍然会生成一个新的 release 号（hash 全部相同）。设计里没有规定这种情况 | **需要你拍板**：允许（符合只追加原则）、拒绝，还是只给告警 |

### 合入判断

两位复核员的结论一致：**修完 R1（几行代码加一条测试）即可合入**，没有其他阻塞项，路径穿越在动作路由和 loader 两边都已封住。R2–R5 登记进 S1.5 的质量尾项即可。

---

## 第七轮优化项清单（2026-10-08，基于 6ab713d，可直接交给 Agent 一次性修改）

> 拍板：**内容没有变化时再次发版，允许。** 照常生成新的 release 号，不告警，不拒绝，符合「只追加」原则。两次发版的对象 hash 完全相同，`plate diff` 会报 0 处变更。这一条写进设计第 8.2 节。
> 原则：不新增模块，只在现有文件里改；每一项都要配测试，验收以测试和下面的复现为准。

### 必修

#### O1 空发版拒绝前不能占用 release 号（R1）

- **位置**：`src/gimbal_plate/release/release.py:259-282`
- **问题**：`if not freeze_list` 这个检查排在 `manifest_dir.mkdir()` 的重试循环之后。发版被拒时，已经建好的空目录不会删掉，release 号也就被占用了。
- **改法**：
  1. 先计算 `freeze_list` 并做空检查，通过后再计算 `release_id`、进入 mkdir 循环。
  2. 防御性修复：`cli.py` 的 `cmd_diff`（约 207-219 行）选择 release 时，跳过没有 `manifest.json` 的目录，并给出一条提示。崩溃中断留下的半成品目录同样适用。
- **测试**：
  - 对全是 draft 的树连续发版两次，断言两次都失败，且 `releases/` 不存在或为空。
  - 之后加入一个 reviewed 块再发版，断言 release 号是 `YYYY.MM.1`。
  - diff 遇到缺 manifest 的目录时不崩溃。
- **附带清理**：如果真实环境的 `plate_artifacts/*/releases/` 里已经有没有 manifest 的空目录，请手工删掉。

### 同轮修（都很小）

#### O2 迁移备份的防覆盖要真正生效（R2）

- **位置**：`scripts/migrate_legacy_case_pg.py:80-85`
- **问题**：秒级时间戳下，「先 `exists()` 再 `write_text`」几乎不可能撞名，而且两步之间有竞争窗口。
- **改法**：用 `open(backup_path, "x", encoding="utf-8")` 独占创建，捕获 `FileExistsError` 后报错退出。时间戳可以保留，用来区分不同批次。
- **测试**：预先创建一个同名文件（用 monkeypatch 把时间戳固定住），断言脚本拒绝运行，而且没有执行任何 UPDATE。不再依赖两次运行碰巧落在同一秒。

#### O3 驱动测试在 CI 里真正跑起来（R3）

- **位置**：`tests/plate/test_migrate_pg_driver.py:19`
- **问题**：测试已经通过 `sys.modules` 注入了假的 asyncpg，`pytest.importorskip("asyncpg")` 是多余的，结果在 CI 里（没装 asyncpg）这些测试永远被跳过。
- **改法**：删掉 importorskip，同步更新第 80-81 行的注释。
- **验收**：在没装 asyncpg 的环境下运行 `pytest tests/plate/test_migrate_pg_driver.py`，3 条测试全部通过，0 个跳过。

#### O4 不合规目录跳过时要留下痕迹，名字规则只保留一处（R4）

- **位置**：`src/gimbal_plate/loader.py:283-297`、`src/gimbal_plate/http/routes_grammar.py:792`、`src/gimbal_plate/cli.py`（check 的入口）
- **问题**：
  - loader 遇到非法名字或逃出根目录的符号链接时直接 `continue`，不留任何日志。
  - `plate check fin.v2` 不走名字规则，所以这种目录能通过 CI 的检查，服务里却悄悄不出现。
  - 同一条正则在 loader 和 routes 里各写了一份。
- **改法**：
  1. 系统名正则只定义一处（例如在 loader 里定义 `SYSTEM_NAME_RE`），routes 和 cli 都从这里引用。
  2. loader 每次跳过时，用 `logging.warning` 写明目录和原因（「名字不合规」或「符号链接逃出根目录」）。
  3. CLI `check` 遇到名字不合规的系统，输出一条阻塞 finding（复用 F1 或 F3 的编码，说明里写「系统目录名不合规，服务不会加载」），退出码非 0。
- **测试**：
  - 用 `fin.v2` 目录跑 check，断言阻塞。
  - loader 加载同一个根目录时，断言有 warning 日志，且这个系统没有被注册。
  - 指向根目录外的符号链接，断言有 warning。

### 文档

#### O5 设计文档补记（仓库里的 `claude/plate-design.md`）

1. **第 8.2 节**：补一句「内容没有变化时再次发版，允许：照常生成新号，对象 hash 相同，diff 为 0」。
2. **S1.5「构件目录可配置」这一条（R5）**，补写一个现象：设了 `PLATE_SYSTEMS_PATH` 时，构件仍然写在包所在仓库的 `plate_artifacts/` 下，副本树和真实仓库的同名系统会共用一个 release 编号序列。解决方案仍按 S1.5 处理。
3. **修订记录**：加一条「修订十三补二」，记下 O1–O4 和上面的拍板。

### 验收（全部满足才算完成）

- CI 在干净副本里逐步模拟全部通过，不装 asyncpg 也要过；`tests/plate` 的跳过数为 0。
- 上面每一项的新测试都通过。
- 真实 fin / platform 发版到临时目录后，对象 hash 和 call 投影与 6ab713d 一致。

---

## 第八轮复核（2026-10-08，HEAD 0cebec1）：建议合入

> 范围：0cebec1（第七轮收口，O1–O5）。
> 方法：在不装 asyncpg 的干净副本里模拟 CI；重跑全部对抗用例；独立评审员对这次的 diff 做最后一遍检查。两路复核员的结论都是**可以合入**。

### 结果

- **CI**：每一步都通过，具体如下（前端 job 本轮没有模拟）：

  | 步骤 | 结果 |
  |---|---|
  | `pip install -e .[dev]` | 通过 |
  | 三个系统的 check | 通过 |
  | 方言纪律测试 | 60 |
  | `tests/plate` | 605，**0 skip** |
  | 执行器测试 | 615 |
  | wheel 冒烟 | 通过 |

- **数据稳定**：platform 146 个对象、fin 23 个对象，hash 和 call 投影都与 6ab713d 完全一致。
- **无回归**：
  - 闭包检查、签发人、release 号并发、损坏对象重写、N3、C1/C2/C3 环形用例，表现都和上一轮一样；
  - 6 棵测试树上 check 和 release 的阻塞码完全一致；
  - common 单独发版会被拒；
  - 各种路径穿越写法都返回 404。

| 项 | 结论 |
|---|---|
| O1 空发版不占号 | ✅ 连续被拒两次，磁盘上什么都不留（构件根目录都没有创建），下一次真正的发版是 `.1`；`plate diff` 会跳过没有 manifest 的目录 |
| O2 备份防覆盖 | ✅ 用 `open(x)` 独占创建，而且在事务开始之前。重名时直接退出，不会执行任何 UPDATE；冲突测试固定了时间，结果稳定。小瑕疵：退出时没有关闭数据库连接 |
| O3 驱动测试真正运行 | ✅ 屏蔽 asyncpg 后 3 条通过、0 skip |
| O4 名字规则单一化 | ✅ 名字规则只在 loader 里定义一处，routes 和 CLI 都引用它，没有循环导入；loader 遇到不合规目录会打 warning；`plate check fin.v2` 阻塞并以退出码 2 退出；根目录内合法的符号链接照常加载 |
| O5 设计补记 | ✅ §8.2 写入了「内容无变化允许发版」；S1.5 补写了副本树共用编号序列的现象 |
| 无变化再发版 | ✅ 照常生成新号，对象 hash 相同，diff 报 0 处变更，和拍板一致 |

### 合入后登记进 S1.5 质量尾项的小项

- `plate check` 不带参数时只检查 fin，没有「检查所有系统」的模式。CI 写的是固定的系统名，所以多出来的 `fin.v2/` 只会在服务启动时打一条 warning，CI 不会失败。建议加 `plate check --all`，遍历每个 systems 根目录下的所有子目录。
- `TestDiffSkipsManifestless` 只断言了退出码，没有断言「`.1 → .3` 配对」和「已跳过」的提示；中间有一行代码的续行写法很怪。
- `test_loader_warns_and_skips` 调用了 `sys.path.insert`，事后没有恢复。
- O2 的退出路径上没有关闭数据库连接。

### S1 合入结论

**feat/plate-s1 满足修订十三补二的合入条件，建议合入 main。** 八轮评审下来的状态：

- **阻塞项清零**：一接即坏、hash 口径、发布闸门、路径穿越、备份纪律都已修好并有测试守护。
- **入库闸门成立**：CI 会跑三个系统的 check、规范形守门，以及三侧测试。
- **延后项登记完整**：快照与 ref、新的 dim、单块回写、路径可配置、批次 C 的深度对拍、批次 E 的执行闭环，以及质量尾项，都已写进 S1.5。

**合入后建议第一件事**：在真实环境确认 `plate_artifacts/` 里没有之前留下的空 release 目录；然后从 S1.5 里按依赖关系挑起点。建议先做「快照 + ref + 路径可配置」，因为编排、执行按 release 钉住版本，以及 9.1 的画像接线，都依赖它。
