# 执行链重构 — `gimbal run launch {case-path}` 子进程化设计

> 日期:2026-08-24
> 状态:已实施
> 范围:Gimbal-platform 后端执行触发链路(POST /api/runs → 逐行执行)。
> 前置:V3 场景容器化(`payload = {definition, orchestration}`,08-13)、
> Case 层解散(08-20)、数据集资产域 P1+P2(稀疏行/行 0 基线虚行/转置编辑器,08-21~23)。

## 1. 背景

V3 当前执行链(a6d0974,#4 运行最小链路):

```
POST /api/runs → dispatch_run → _fanout(每 数据集行 × 重复次数):
  _compose_scenario(definition, row)      # 行键 → config.vars
  → plate /convert                        # 校验 + 剥平台视图字段
  → _inject_exec_users / _inject_prefix_vars
  → gimbal HTTP POST /run (:8766)         # gimbal run server
```

问题:

1. **执行调用形态偏离原始设计**。PLATFORM_REQUIREMENTS §3 的执行触发契约是
   `subprocess.run([GIMBAL_BIN, "run", "launch", <abs_path>])`;#4 把它换成了
   常驻 HTTP 服务,平台侧多了一个必须在线的引擎进程依赖(gimbal run server),
   且 `.env` 里预留的 `GIMBAL_BIN`(Spec-1 定义、注明"不消费")一直空转。
2. **场景结构变了**。`ComposerScenario.payload` 已是 `{definition, orchestration}`
   容器;执行链必须只吃 `definition`(orchestration 是平台侧投影,绝不外发)。
   该点在现链路已处理,本次重构保持并显式化。
3. **数据集实现变了**。新数据集编辑器(转置表格/CSV/行 0 基线虚行)把**所有行值
   字符串化**(`DataSetEditor.toApiRow` 的 `String(v)`,null→`""`),行是稀疏覆盖
   (缺键=继承基线,`""`=显式空覆盖,基线行不落库)。旧 dispatcher 假设"行值 JSON
   类型原样保留",直接合入会把整型变量覆盖成字符串,破坏
   `Assertion{expected: 0}` 这类强类型断言。
4. feature-gaps.md §二挂起的执行链相关项(僵尸派发对账等)等本重构落地后再做。

## 2. 目标

- 平台侧执行调用统一为 **`gimbal run launch {case-path}` 子进程**,退役平台侧
  gimbal HTTP client(引擎侧 `gimbal run server` 保留为引擎能力,不动)。
- 触发执行落盘的 **scenario.json 是 gimbal 可执行的数据驱动用例**:引擎不原生
  支持数据集(schema 无 datasets/rows 字段),数据驱动由平台侧逐行展开——
  每行合成一个完整 scenario(行数据注入 `config.vars`),一个 case 文件一次
  launch。这是"数据集的数据注入过程"的落点。
- 保留原有执行能力:数据集多选/稀疏行语义、D12 基线执行(空数据集=隐式空行)、
  执行用认证多选(owner 级解密 + override/merge/append 合并策略 + append 冲突
  预检 409 + injectCredentials=false)、stepTo(0-based 含端点)、nRuns、parallel、
  prefix 提单号前缀、env 记录、Execution 计数器/终态、JSONL 运行日志、
  "平台侧故障不炸 201 语义"。
- API 契约不变:`POST /api/runs` 请求/响应体、Execution 读侧 config_json 键
  全部保持,前端零改动。

## 3. 新执行链

```
POST /api/runs (RunRequest — 不变)
  → dispatch_run:校验(env/数据集归属/stepTo 越界/append 冲突)+ Execution 行 — 不变
  → _fanout 后台任务,per (dataset × row × repeat):
      1. _compose_scenario(definition, row)
         # 行键 → config.vars;行值按基线类型还原(str→int/float/bool)
      2. plate /convert(consumer="gimbal")           # 不变:校验+剥平台视图字段
      3. _inject_exec_users(merge_policy)             # 不变:明文只进 run 副本
         _inject_prefix_vars(prefix)
      4. 落盘 case 文件:DATA_DIR/runs/cases/<runId>/<stem>/case.json   # 新
      5. gimbal_launcher.launch(case_path, step_to, report_dir)    # 新:子进程
           argv = [<GIMBAL_BIN | python -m gimbal>, run, launch, <case>,
                  -o, json, --report-dir, <case_dir>/reports(, --step-to N)]
      6. stdout JSON {exit_code,total,passed,failed,skipped} → 行计数   # 新
  → JSONL / Execution 计数增量 / 终态(failed>0 → failed)— 不变
```

### 3.1 数据注入的顺序与隐私边界

顺序保持 convert 前置:明文凭证(prefix/exec auths)只注入 convert 产物并落盘
run 副本,**不流经 plate** 校验/日志。case 文件含明文 users——与 V1 临时 yaml
同语义(E3:临时 yaml users 注入而来),文件落在平台 DATA_DIR 权限域内。

### 3.2 行值类型还原(新)

`_compose_scenario` 合入行键时,若基线(场景级 `config.vars` 同名键)是
int/float/bool 而行值是 str,则尝试按基线类型还原(`"2"`→2、`"true"`→true、
`"1.5"`→1.5);还原失败(int("abc"))保留原字符串。基线是 str/生成式 dict/不存在
时原样合入。这恢复了旧编辑器"int 还是 int"的语义,同时兼容新编辑器/CSV 的
全字符串存储与三态单元格(空串仍显式覆盖为 `""`)。

### 3.3 case 文件与报告

- 目录:`DATA_DIR/runs/cases/<runId>/<stem>/case.json`,stem =
  `case-{seq:03d}-{baseline|<datasetId>}-r{rowIdx}-n{rep}`(每 case 独立
  子目录,引擎报告落同目录下 `reports/`)。
  与 JSONL(`DATA_DIR/runs/<date>.jsonl`)同域,构成执行审计面(什么数据真的
  打给了引擎);JSONL 行新增 `casePath`/`reportDir` 字段。
- `--report-dir <case_dir>/reports`:引擎原生报告逐 case 隔离,并发 fan-out
  不互踩;文件保留供后续报告聚合(feature-gaps §二)。

## 4. gimbal_launcher(新服务,替换 gimbal_client)

`app/services/gimbal_launcher.py`:

- `launch(case_path, *, step_to=None, report_dir=None, cwd=None, timeout=None)
  -> LaunchResult`
- `LaunchResult{launch_status, exit_code, total, passed, failed, skipped,
  error, stdout, argv}` — `launch_status ∈ ok|timeout|error`;`stdout` 为
  原文(诊断用),计数来自 `-o json` 解析,解析失败退化为仅退出码(计数 0,
  `error` 带 stderr 尾行)。`run_result` property 输出 JSONL `runResult`
  字段形状(与旧 HTTP RunResponse 对齐)。
- 进程:`asyncio.create_subprocess_exec`(stdout/stderr PIPE;子进程
  `PYTHONIOENCODING=utf-8`;Windows 下 `CREATE_NO_WINDOW`)。超时
  `GIMBAL_TIMEOUT_SEC`(默认 300s)到点 kill + communicate 收尸,返回
  `launch_status="timeout"`。
- 退出码语义(引擎 exit_codes.py):0=passed;1=failed(测试失败);
  2=校验拒绝;3/4/5=引擎侧错误。launcher 不吞退出码,全部如实上报。
- 可执行文件:`settings.GIMBAL_BIN`(现由 .env 提供
  `D:\Gimbal\Scripts\gimbal.exe`);空值回退 `[sys.executable, "-m", "gimbal"]`
  (同 venv 部署时最稳)。
- 测试缝:`_base_argv()`(可 monkeypatch 成 `[sys.executable, "-c", ...]` 假
  命令)+ `launch()` 本身可被 dispatcher 级测试整体替换(继承原
  `gimbal_client.run` 的 mock 模式)。
- Typed errors 不再需要:子进程不会"不可达"——spawn 失败(OSError)与超时都
  归一为 `LaunchResult.launch_status`,由调用方(run_dispatcher)映射为
  `launch_error`/`launch_timeout` 状态行。

### 4.1 状态口径(JSONL / 计数)

| 场景 | status | 计数 |
|---|---|---|
| exit_code==0 | `passed` | passed+1 |
| exit_code==1(测试失败) | `failed` | failed+1 |
| exit_code==2(引擎校验拒绝) | `gimbal_rejected` | failed+1 |
| exit_code>=3 / spawn OSError | `launch_error` | failed+1 |
| 超时 kill | `launch_timeout` | failed+1 |
| plate 挂/拒 | `plate_unavailable`/`plate_rejected` | failed+1(不变) |

(旧口径的 `gimbal_unavailable` 随 HTTP client 退役;`gimbal_rejected` 语义
保留——引擎 422 与 CLI exit 2 同源,均为 scenario 校验失败。)

## 5. 退役清单

- `app/services/gimbal_client.py` 删除;`main.py` lifespan 的
  `gimbal_client.aclose()` 移除;`GIMBAL_BASE_URL` 设置项删除
  (`GIMBAL_TIMEOUT_SEC` 由 launcher 复用为子进程超时)。
- 受影响测试的 mock 点从 `gimbal_client.run` 迁到 `gimbal_launcher.launch`
  (test_run_baseline / test_run_m1_capabilities / test_scenario_visibility_and_copy /
  test_scenario_composer_plate_integration)。

## 6. 明确不做(本轮)

- env 的 `--env` 透传:平台 envId(dev-local/test-env-A/B)与引擎
  `conf/environments/{dev,prod}.yaml` 名字空间不一致,现链路 env 本就只记录
  不注入;保持现状,待环境模型统一后再接。
- 僵尸派发对账、报告聚合 UI(feature-gaps §二,仍挂起)。
- RunDialog 的 auths 选择器(前端缺口,与本次后端重构解耦)。
- 引擎侧 `gimbal run server` 保留,不删(引擎能力,非平台依赖)。

## 7. 验证

- 新增 `tests/test_gimbal_launcher.py`:
  - argv 组装(GIMBAL_BIN 直传/回退 `-m gimbal`/step-to/report-dir);
  - stdout JSON 解析(干净/带噪声回退/不可用返回 None);
  - 假命令子进程往返(monkeypatch `_base_argv` → `python -c` 打 JSON,
    含"stdout 无 JSON 退化为仅退出码+stderr 尾行"/超时 kill/spawn 失败);
  - **真 CLI E2E ×2**:真 `gimbal run launch`(GIMBAL_BIN exe)+ 测试内
    http.server 单步 GET /ping + `$.response_status` 断言——eq 200 →
    exit 0/passed 1;eq 500(必失败)→ exit 1/failed 1。引擎不可用的
    环境(无 GIMBAL_BIN 且 gimbal 不可导入)自动 skip。
- 受影响测试迁移后全量 `python -m pytest tests -q` 通过(211 passed,
  含 2 条真 CLI E2E)。

## 8. 实施发现(E2E 验证时确认的引擎契约)

1. **断言必须显式声明 `phase` 才会被执行 —— 已修(引擎侧按 kind 落默认)**。
   引擎 `StrategyDispatcher.dispatch_phase` 按 `s.phase == phase` 严格过滤
   (src/gimbal/strategy/dispatcher.py:158),`StrategyBase.phase` 缺省
   `None`——没有 `phase: "verifying"` 的 assertion **静默不执行**(step
   无条件通过);Composer 前端产出的策略恰好都不写 phase,平台执行
   "全绿"是假象。修复:引擎 schema 按 kind 落默认
   (src/gimbal/schema/strategy.py:Assertion→VERIFYING /
   Extract→AFTER_REQUEST / Assign→BEFORE_REQUEST),显式声明仍可覆盖;
   所有输入源(平台/手写 YAML/CSV)受益。E2E 里失败断言用例不再写
   phase,作为默认值的回归哨兵(eq 500 若断言未执行会假绿 exit 0)。
2. **子进程 stdio 强制 UTF-8**(已修在 launcher):引擎 JSON 报告
   `ensure_ascii=False` 且错误信息含中文,Windows 管道缺省走 locale
   码页(GBK);launcher 传 `PYTHONIOENCODING=utf-8` 保证
   `decode("utf-8")` 不乱码。
3. **选中"0 行数据集"导致执行 0/0/0 秒完结**(已修,回归自线上
   sc-test-5nhvaloj6 / ds-005):新编辑器行 0 基线虚行不落库,只有
   基线的数据集 `rows=[]`;旧逻辑仅对"未选数据集"回退隐式空行,
   选了 0 行数据集则 entries 为空 → Execution total/passed/failed
   全 0、5µs 内 done。修:选中的 0 行数据集同样回退一个隐式空
   覆盖行(`rows or [{}]`),与 D12 同语义(线上验证见
   test_selected_dataset_with_zero_rows_runs_baseline_once)。
4. **编排场景 `config.services` 恒空 —— 已修(dispatcher 物化)**:Composer
   只在 step.api.view_hints 存 endpoint_id,`config.services={}`;plate
   /convert 不做 services 物化(且 plate 端点模型本就无 host 概念,
   service = 业务域)→ 引擎侧 URL 解析必失败。修复:dispatch 侧
   `_inject_services`(run_dispatcher.py)在 post-convert 注入——steps
   引用而未映射的服务名填入选定环境 RunEnv.baseUrl;authored 映射
   不覆盖、baseUrl 为空不注入(不造假 URL)。部署主机从此只属于
   环境模型(envs.yaml / data/envs.yaml 覆盖)。
5. **run 路径漏补 plate 必填 meta 默认 —— 已修(归一化收敛)**:
   preview/export 路由(`_draft_to_full_scenario_dict`)一直在发送前
   补 plate 必填默认(`meta.requirementRef: []` 等,UI 不采集),
   但该归一化**不落库**(导出文件里的 requirementRef 是导出时补的),
   run 执行链读存量场景直接发 plate /convert → 全行
   `plate_rejected: meta.requirementRef Field required`(线上
   sc-test-5nhvaloj6,4/4 行)。测试没抓到是因为 PlateMock 直通
   不校验,而 `make_draft` 的 meta 恰好不带这些字段。修复:归一化
   抽成 `plate_client.fill_plate_defaults`(plate 契约归属模块),
   preview 路由与 `_compose_scenario` 共用同一份默认
   (test_run_baseline.test_run_fills_plate_required_meta_defaults
   断言发往 plate 的 payload 已补默认)。
