# Backend Business-Logic Review (gimbal-platform)

| Field | Value |
| --- | --- |
| Scope | V3 composer routers / services / models (scenarios, runs, executions, data_sets, carry, adaptations, endpoint/strategy/generator catalogs, constants, helper) |
| Path | `D:/Gimbal/Gimbal/src/gimbal-platform/backend/app` |
| Stack confirmed | FastAPI 0.115+ / SQLAlchemy 2.x (async) / Pydantic v2 / SQLite (`sqlite+aiosqlite:///./data/app.db`) / asyncio Task (no APScheduler in dispatch path) |
| Review time | 2026-09-02 |
| Reviewer | AI 评审 (sub-agent, code-grounded) |

---

## 评审范围(已读)

- Routers: `scenarios.py`(20290 字节), `runs.py`, `executions.py`, `data_sets.py`, `carry.py`, `adaptations.py`, `endpoint_catalog.py`, `strategy_catalog.py`, `constants.py`, `generator_catalog.py`
- Shared helpers: `_codes.py`, `_error_mapping.py`, `_name_checks.py`, `_ownership.py`
- Services: `run_dispatcher.py`(56721 字节), `run_materialize.py`, `scenario_store.py`, `adaptation_service.py`, `adaptation_ops.py`, `gimbal_launcher.py`, `plate_client.py`, `marks_store.py`, `data_set_store.py`, `carry_store.py`, `carry_injection.py`, `auth_ref_scan.py`, `execution_store.py`
- Schemas: `scenario_composer.py`, `execution.py`, `adaptations.py`, `carry.py`
- Models: 全部 13 个 `composer_scenario / composer_data_set / execution / auth_session / constant_entry / scenario_endpoint_ref / catalog_version / adaptation_batch / adaptation_op / adaptation_snapshot / carry_binding / user` 等
- Core: `core/db.py`, `core/deps.py`, `core/config.py`, `main.py`

---

## 一、问题清单(按严重度排序)

### P0 — Critical

#### P0-1  SQLite 未启用 WAL,并发写会序列化 + 长事务锁
- **位置**: `backend/app/core/db.py:16-22` 与 `core/config.py:32`
- **证据**:
  ```python
  # core/db.py
  engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
  SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
  # 无 PRAGMA journal_mode=WAL;无 busy_timeout
  ```
  ```python
  # core/config.py
  DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"
  ```
- **问题**: `run_dispatcher._fanout` 在一个 execution 内最多并行 200 个行 task(`parallel` 上限),每个 task 通过 `_bump_counters` 走原子 UPDATE;`reconcile_stale_executions` / `open_batch` / `_apply_scenario_op` 也会同时持有 AsyncSession。SQLite 默认 rollback journal 模式同一时刻只允许一个写者,所有 UPDATE 串行化;`SQLITE_BUSY` 默认无限等待,实际无 `connect_args={"timeout": 30}` 等保护。
- **影响**: 大量并发派发时 dispatch 主线程被 DB 写阻塞,执行链路尾延迟;`SQLITE_BUSY` 抛出后 `_bump_counters` 走 try-twice-then-log 路径,counter 漂移(P8 已有 counterDrift 兜底,但根因未除)。
- **修复**: `db.py` 中显式 `connect_args={"check_same_thread": False, "timeout": 30}` 并在引擎启动后通过 `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=30000; PRAGMA foreign_keys=ON`(aiosqlite 用 `event.listens_for(engine.sync_engine, "connect")` 钩子)。

#### P0-2  case.json 明文凭证残留面大于 `DELETE /executions/{id}`
- **位置**: `backend/app/services/run_dispatcher.py:1145-1148, 1178-1191`;`backend/app/services/execution_store.py:29-41`;`backend/app/models/execution.py:38`
- **证据**:
  ```python
  # run_dispatcher.py
  def _write_case_file(case_dir, scenario_dict):
      case_path.write_text(json.dumps(scenario_dict, ensure_ascii=False, indent=2, default=str), ...)
  def purge_case_dir(run_id):
      shutil.rmtree(_run_dir(run_id), ignore_errors=True)
  ```
  ```python
  # execution_store.py
  async def delete_execution(session, ex):
      run_id = (ex.config_json or {}).get("runId")
      await session.delete(ex); await session.commit()
      if run_id: run_dispatcher.purge_case_dir(str(run_id))
  ```
  ```python
  # execution.py Execution.scenario_id — String(128), no FK
  scenario_id: Mapped[str] = mapped_column(String(128), index=True)
  ```
- **问题**: 场景被删除时,`scenario_store.delete` 只 `sa_delete(ComposerDataSet)` + `db.delete(row)`,不级联 Execution;Execution 的 `scenario_id` 列根本没有 FK 约束,孤儿执行会留下。孤儿执行虽然 `owner_id` 有 FK(用户删除会级联),但 case.json 仍含明文凭证(`_write_case_file`)。即便通过 `DELETE /api/executions/{id}` 触发 `purge_case_dir`,如果用户被删除走级联(`User` -> `Execution`),`execution_store.delete_execution` 是手工逐单调用而非 SQLAlchemy cascade,case 案卷不会自动清。
- **影响**: 含明文凭证(`run_dispatcher._apply_users` 注入的 username/password/token) 的 case.json 在 `DATA_DIR/runs/cases/<runId>/case.json` 永久留盘,违反 P2 注释承诺("删除执行必须连带清理")。
- **修复**: 1) 在 `Execution.scenario_id` 加 `ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE")` + 给 `users.id` 的 ondelete cascade 配套触发 purge_case_dir;2) `User` 删除入口加 `await run_dispatcher.purge_case_dir_by_owner(owner_id)`;3) 启动期 `sweep_stale_case_dirs` 已存在但仅按 mtime,与删除路径解耦 — 增 owner 级 sweep。

#### P0-3  scenario_store.update / copy 无 SELECT FOR UPDATE,runSchemes 透传逻辑在并发 PUT 下会丢
- **位置**: `backend/app/services/scenario_store.py:107-148, 138-145`
- **证据**:
  ```python
  # update
  row = await _get_row(db, scenario_id)         # 无 with_for_update
  ...
  stored_orch = ((row.payload or {}).get("orchestration") or {})
  orch_data = draft.orchestration.model_dump(by_alias=True, mode="json")
  orch_data["runSchemes"] = stored_orch.get("runSchemes") or []   # 透传保留
  row.payload = ScenarioDraft(...).model_dump(...)
  ```
- **问题**: 两个客户端(编辑器多 tab / 多人协作)同时 PUT 同一 scenario,均先读到 `runSchemes = [...]`,再各自整体替换 row.payload。如果 PUT A 在 PUT B 之后 commit,B 的 commit 覆盖 A 的全部更新,runSchemes 的最新值不会进入下一次读(下次读的就是 B 覆盖后的)。场景同步到 endpoint_ref_index 同样在 A/B 间覆盖 — 索引与最终 payload 不一致。
- **影响**: 编辑器两个 tab 并发保存时丢失方案、丢失步骤重排,endpoint_ref_index 倒排与 definition 漂移;影响"窄端点专管键"承诺(spec §3.2)。
- **修复**: `update` 走乐观并发:加 `version` 列(`Integer, default=0`),`update` 时 `where(id==X, version==read_version)` 失败则抛 409 conflict 提示前端重读;或事务内 `await db.execute(select(...).with_for_update())` 但 SQLite 不真支持行锁,故首选乐观锁。

#### P0-4  run_dispatcher 全局信号量 `_global_launch_sem` 跨所有 execution 共享 8 槽
- **位置**: `backend/app/services/run_dispatcher.py:160-178, 689-698`;`backend/app/core/config.py:51`
- **证据**:
  ```python
  _launch_sems: dict[int, asyncio.Semaphore] = {}
  def _global_launch_sem():
      loop_id = id(asyncio.get_running_loop())
      sem = _launch_sems.get(loop_id)
      if sem is None:
          sem = asyncio.Semaphore(max(1, settings.MAX_CONCURRENT_LAUNCHES))   # 8
  ```
- **问题**: 设计意图是限流防止万级子进程,但**8 是全局共享**:一个 200 行的长尾执行长时间占 8 槽,其他小执行全部饿死;`parallel` 字段(per-execution, 上限 200)对外显示并发度但实际被全局闸二次限制,UI 显示"parallel=64"但实际等 8。`PLATE_BREAKER_THRESHOLD=3` 仅熔断 plate 调用,不影响 launcher 槽位。
- **影响**: 平台整体吞吐被钉死在 8 个并发子进程(per-event-loop);多用户共享一个平台实例时延迟公平性差;SLA 难预估。
- **修复**: 把全局闸改为 owner-级 quota(`Semaphore(2)`/owner,planner 设 per-user 上限);或加入调度器(优先级队列);至少文档化"parallel 字段是请求意图,实际并发受全局闸约束",前端文案对齐。

---

### P1 — High

#### P1-1  `list_scenarios` 全表扫描 + Python filter,无分页
- **位置**: `backend/app/services/scenario_store.py:295-312`;`backend/app/routers/scenarios.py:240-257`
- **证据**:
  ```python
  # scenario_store.list_rows
  stmt = select(ComposerScenario).order_by(ComposerScenario.updated_at.desc())
  rows = (await db.execute(stmt)).scalars().all()
  return [r for r in rows if _passes_filters(...)]
  ```
- **问题**: 每次 list 全量加载所有 scenario 行,在内存里跑 `_passes_filters`(meta 重建 + q 子串扫 + system/module/priority 比对)。`q` 扫 4 字段 × N 行,无 LIMIT/OFFSET。
- **影响**: 1k 行以下尚可;5k+ 场景时 P99 延迟 >1s;前端无分页协议,只能靠滚动加载,无法稳定实现。
- **修复**: 把 filter 下推到 SQL(`meta` 是 JSON,可在 SQLite 用 `json_extract` 或 PG `->>`;SQLite JSON 函数: `WHERE json_extract(payload, '$.definition.meta.module') = :module`),加 `limit/offset` 参数(对齐 `executions.list_executions` 的 limit/offset 风格)。

#### P1-2  `_next_dataset_id` 是 read-then-write 竞态
- **位置**: `backend/app/services/data_set_store.py:233-251`
- **证据**:
  ```python
  async def _next_dataset_id(db):
      res = await db.execute(select(ComposerDataSet.dataset_id))
      used = {int(m.group(1)) for (did,) in res.all() if m := _NNN_RE.match(did or "")}
      n = 1
      while n in used: n += 1
      return f"ds-{n:03d}" if n <= 999 else f"ds-{n}"
  ```
- **问题**: 两个请求并发 create dataset 时都读到 `used = {1,...,7}`,都返回 `ds-008`,后 commit 的拿 IntegrityError。代码确实 catch IntegrityError 并判 `_is_dataset_id_collision` → 409,但调用方要重试,目前不重试,直接返回 409 给用户。
- **影响**: 用户手动重试成本低;但自动化脚本/copy_scenario 内部循环 create 时碰到一次就放弃。
- **修复**: 改用循环重试(限 5 次)或 `MAX(dataset_id)+1` SQL(对 NNN 格式:`SELECT MAX(CAST(SUBSTR(dataset_id,4) AS INTEGER)) FROM composer_data_sets WHERE dataset_id LIKE 'ds-%'`)。

#### P1-3  `get_scenario_draft` 对历史空 system/meta 行的可读性
- **位置**: `backend/app/routers/scenarios.py:425-442`
- **证据**:
  ```python
  @router.get("/{scenario_id}/draft", response_model=ScenarioDraft)
  ...
  payload = row.payload or {}
  try:
      return ScenarioDraft.model_validate(payload)
  except Exception as e:
      raise HTTPException(status_code=500, detail="draft_corrupt: 存储的 ScenarioDraft 与 schema 不一致")
  ```
- **问题**: `ScenarioMeta._validate_system` 拒绝空 `system: []`;`_meta_from_row`(读 shape 路径)会兜底填 `["default"]`,但 `get_scenario_draft` 直接 `model_validate(payload)`,不走兜底。SQLite CURRENT_TIMESTAMP 之外若历史 row 的 `meta.system=[]` 漏底,这条端点 500。
- **影响**: 数据迁移期(scenario 字段从 V1 升到 V3)极易踩雷;前端"导出场景"按钮一键 500,影响数据导出可信度。
- **修复**: 用 `ScenarioDraft.model_validate(_normalize_legacy(payload))`,与 `_meta_from_row` 同一修复路径;或先 SchemaMeta 校验失败时回退到 `_meta_from_row` 的修复版再二次 validate。

#### P1-4  `_finalize_execution` 在 `_bump_counters` 失败的极端窗口下可能误判终态
- **位置**: `backend/app/services/run_dispatcher.py:959-998`
- **证据**:
  ```python
  async def _finalize_execution(db_factory, execution_id, *, status=None):
      ...
      ex = await session.get(Execution, execution_id)
      if ex is not None:
          final_status = status or (STATUS_FAILED if ex.failed else STATUS_DONE)
          ...
          if (final_status != STATUS_CANCELED and ex.passed + ex.failed != ex.total_runs):
              ... cfg["counterDrift"] = True; ex.config_json = cfg
  ```
- **问题**: `ex.passed` / `ex.failed` 由 `_bump_counters` 在多行 task 上原子 UPDATE 累加,但 `expire_on_commit=False` 意味着同一 session 内的 UPDATE 不刷新 ORM 缓存;`_finalize_execution` 是新 session `session.get(Execution, ...)`,值是最新值 — OK。但当某行 `_bump_counters` 两次重试都失败(JSONL 已记 counter_bump_failed),此行的 passed/failed 不在 ex 上,`passed+failed < total_runs` 触发 `counterDrift` 标记。**counterDrift 是探测信号,但 Execution 仍标 `done`/`failed`,UI 不感知"还有未结算的行"**。
- **影响**: 监控面不准;运维需要扫 JSONL 才能发现真计数。
- **修复**: 让 `counterDrift=True` 的 execution 显式标 `status="failed"` + 加 `note="counter_drift: 详见 JSONL"`,或新增 Execution 字段 `pending_counters`;最小代价 — 让 `Execution` schema 暴露 `counterDrift`,read 侧前端红条。

#### P1-5  scenario_endpoint_ref 没有 FK + cascade,孤儿行可能累积
- **位置**: `backend/app/models/scenario_endpoint_ref.py:1-25`;`backend/app/services/scenario_store.py:169-188`
- **证据**:
  ```python
  # scenario_endpoint_ref — 无 ForeignKey
  scenario_id: Mapped[str] = mapped_column(String(128), primary_key=True)
  ```
  ```python
  # scenario_store.delete — 显式 drop_scenario 后删数据集
  await endpoint_ref_index.drop_scenario(db, scenario_id)
  await db.execute(sa_delete(ComposerDataSet).where(...))
  await db.delete(row)
  ```
- **问题**: 倒排表无 FK → 应用层 `endpoint_ref_index.drop_scenario` 失败(异常/未实现)时,孤儿 ref 永久留存。`adaptation_service.impact`(`where(ScenarioEndpointRef.endpoint_id == endpoint_id)`)会扫到孤儿行,UI 显示"受影响的鬼场景"然后 404。
- **影响**: 数据完整性漂移;catalog_version.carry_drift 报表里 `orphaned` 误算。
- **修复**: 加 `ForeignKey("composer_scenarios.scenario_id", ondelete="CASCADE")` 到 `scenario_endpoint_ref.scenario_id`;PG 迁移时连同 `composer_data_sets` 已有 cascade 一并存在。

#### P1-6  `run_dispatcher` 重新登录/冷启动后 `_shutting_down` 状态机的潜在副作用
- **位置**: `backend/app/services/run_dispatcher.py:106-157, 351-356, 449-481`
- **证据**:
  ```python
  _in_flight: set[asyncio.Task] = set()
  _shutting_down: bool = False
  ...
  async def drain_in_flight_dispatches():
      global _shutting_down
      _shutting_down = True
      ...
  def reset_shutdown_state(): global _shutting_down; _shutting_down = False
  ```
- **问题**: `lifespan` 在 startup 调 `reset_shutdown_state` 清掉标志,但**`_cancel_requested` 与 `_tasks_by_execution` 没 reset**(只有 `reset_cancel_state()` 测试用)。生产 server 重启时 `_cancel_requested` 仍含上次进程的 eid;若新进程复用了同一 execution.id(autoincrement,SQLite 一般不会,但 PG 序列恢复有概率),会误判"取消"在边界,行不计数。
- **影响**: 极小概率触发但难调试;任务取消语义被旧进程的脏状态污染。
- **修复**: `reset_cancel_state()` 在 `lifespan` startup 也调一次(测试同款),或将所有模块级全局归一收敛到一个 `reset_all_module_state()` 在 lifespan startup 调用。

#### P1-7  `ConstantEntry` 创建不互斥 literal/generator,schema 层没拦
- **位置**: `backend/app/routers/constants.py:84-109`;`backend/app/schemas/constants.py`(`is_literal_primitive`)
- **证据**:
  ```python
  @router.post("", response_model=ConstantEntryOut, status_code=...)
  async def create_constant(payload: ConstantEntryCreateIn, user, session):
      entry = ConstantEntry(
          owner_id=user.id, name=payload.name, ...,
          entry_kind=payload.entry_kind,
          value=payload.value,
          spec=payload.spec,
      )
      session.add(entry); await session.commit()
  ```
- **问题**: `payload` 可能同时带 `value` 和 `spec`;DB 接受两者并存。PATCH 的 `_validate_patch` 才校验互斥,但 create 路径只把字段写入,不强制"literal → 禁 spec"/"generator → 禁 value"。前端生成式表单 bug 会创建非法条目。
- **影响**: 引擎 preprocess 拿到混合条目,可能用 generator 求值时又用 literal value,行为未定义(spec 仅说"两类互斥")。
- **修复**: `create_constant` 内做与 `_validate_patch` 同款校验:`entry_kind == "literal" → value 必填 & spec 必 None`;`generator` 反之。

#### P1-8  `run_dispatcher._fanout` 入口的 `_cancel_requested.discard(execution_id)` 与 `cancel_execution` 端点的 race
- **位置**: `backend/app/services/run_dispatcher.py:515-519`;`backend/app/routers/executions.py:157-181`
- **证据**:
  ```python
  # run_dispatcher._fanout 起点
  _cancel_requested.discard(execution_id)   # 防御性出清
  ```
  ```python
  # routers/executions.py cancel_execution
  run_dispatcher.request_cancel(ex.id)   # 加入集合
  if not run_dispatcher.has_live_fanout(ex.id):
      # 无在飞 fanout → 立即终态化
      ex.status = STATUS_CANCELED; ex.finished_at = utcnow(); await session.commit()
  ```
- **问题**: 时序1:客户端 cancel → `request_cancel(eid)` 入集合 → `_fanout` 启动前 `discard(eid)` 清掉 → 后续行边界检查 `if eid in _cancel_requested` 永远 False,运行到完不被取消。时序2:`_fanout` 已跑过 discard 行后才接 cancel,正常。**`discard` 把 cancel 状态"防御性"清了,但 cancel 端点的"立即终态化"路径(无在飞)与 `_fanout` 启动之间存在 TOCTOU**:两 request 间隔毫秒级但概率非零。
- **影响**: 用户点取消后 run 仍跑完,行全数计入 passed/failed,与设计意图"P4 协作式取消"违背。
- **修复**: 用 `asyncio.Event`/`Future` 替代裸 set;或在 `dispatch_run` 内(创建 execution 之前)登记 `request_cancel`,`_fanout` 内不再无条件 `discard`;最稳妥是把"cancel 请求已存在"当成"拒绝 spawn fanout"(直接终态化)。

#### P1-9  gimbal_launcher 路径与子进程管理的潜在 OSError 漏点
- **位置**: `backend/app/services/gimbal_launcher.py:184-256`
- **证据**:
  ```python
  try:
      proc = await asyncio.create_subprocess_exec(*argv, ...)
  except OSError as e:
      return LaunchResult(launch_status="error", error=f"spawn failed: ...", argv=argv)
  ...
  log_fh = engine_log_path.open("w", encoding="utf-8", newline="") if engine_log_path else None
  ```
- **问题**: `engine_log_path.open("w", ...)` 没有 try/except — `case_dir` 已 `mkdir(parents=True, exist_ok=True)` 但路径非文件而是目录、磁盘满、权限拒绝都会抛 `OSError`,污染 `_row` 的 except 链记为 `dispatcher_error`(而非 `launch_error`),且 `log_fh` 此时未定义 — 后续 `if log_fh: log_fh.flush(); log_fh.close()` 在异常路径下会 NameError。
- **影响**: 一次性把整行的 status/case 文件落盘路径都打飞,运维难定位是磁盘满还是权限还是 spawn 失败。
- **修复**: 把 `engine_log_path.open` 包 try/except,失败转 `launch_status="error"`(在 spawn 之前返回),与 spawn 失败一致语义。

#### P1-10  carry drift / service fields 调用 plate 串行 N 次 /full,无并发也无缓存
- **位置**: `backend/app/services/carry_store.py:60-101`;`backend/app/services/adaptation_service.py:60-78`
- **证据**:
  ```python
  for item in items:
      try:
          full = await _plate_full_endpoint(item["id"])   # 逐端点串行 HTTP
      ...
  ```
- **问题**: drift 报告与 `service_fields` 路由对 plate 每个 endpoint 拉一次 `/full`,N 个端点 = N 次串行 HTTP,延迟叠加,plate 端连接池未复用(每次走 plate_client 单例 OK,但并发数为 1)。
- **影响**: 一次 drift 报告几十秒级别,运维使用时延过差,降低 `catalog/diff` 主动巡检意愿。
- **修复**: `asyncio.gather` + `asyncio.Semaphore(4)` 限制并发,带超时(plate 默认 30s)。

---

### P2 — Medium

#### P2-1  `execution_rows` 全量日 JSONL glob + 全文解析
- **位置**: `backend/app/services/run_dispatcher.py:245-277`
- **证据**:
  ```python
  for path in sorted((settings.DATA_DIR / "runs").glob("*.jsonl")):
      with path.open(...) as fh:
          for line in fh: ...
  ```
- **问题**: 每次 GET `/executions/{id}/rows` 对历史执行必须扫全部日 JSONL,过滤出该 execution 的所有行。30 天执行历史 = 30 次 open + 全行 JSON parse + 字典构造。
- **影响**: 活跃执行走内存 registry(快);历史执行随天数线性恶化。
- **修复**: 在每个 JSONL 行级索引 — 加 `runs/execution_index.jsonl`(`{executionId: [runId, lastRowAt]}`)或直接在主 JSONL 加 `executionId` 子索引文件 `runs/by-execution/<id>.jsonl`(写时 fanout 双写,读时直读)。

#### P2-2  `list_batches` N+1
- **位置**: `backend/app/services/adaptation_service.py:873-878, 375-402`
- **证据**:
  ```python
  async def list_batches(db):
      batches = (await db.execute(select(AdaptationBatch).order_by(...))).scalars().all()
      return [await _batch_detail(db, b.batch_id) for b in batches]   # 每批 3+ 次查询
  ```
- **问题**: `_batch_detail` 每个 batch 查 ops + snapshots + 累 opCounts。N 批次 = N 次 ops + N 次 snapshots 查询(可批但当前未批)。
- **影响**: 管理员查看所有批次时,N 大时延。
- **修复**: `WHERE batch_id IN (selected_ids)` 一次拉 ops/snapshots,Python 端 groupby。

#### P2-3  `impact` 兜底逻辑走全表 `composer_scenarios`
- **位置**: `backend/app/services/adaptation_service.py:239-247`
- **证据**:
  ```python
  scen_rows = (await db.execute(
      select(ComposerScenario).order_by(ComposerScenario.scenario_id)
  )).scalars().all()
  ```
- **问题**: 当 `field_name is None`(只传 endpointId)时,必须扫全表找锚点 step。1k+ 场景线性扫。
- **修复**: 同 P1-1,推到 SQL(JSON 提取或 anchor_step_indexes 已扫 endpoint_ref_index,可在 endpoint_ref_index 里建 endpoint_id 索引;line 17 已经 `ix_ser_endpoint` 命中但只能拿到 (scenario_id, step_index),仍需 `anchor_step_indexes` 解析 payload 找没索引的 step)。

#### P2-4  Plate client 共享单例 + `set_client_for_tests` 无锁
- **位置**: `backend/app/services/plate_client.py:65-83`
- **证据**:
  ```python
  _client: httpx.AsyncClient | None = None
  def get_client():
      global _client
      if _client is None:
          _client = httpx.AsyncClient(...)
      return _client
  def set_client_for_tests(client):
      global _client
      _client = client
  ```
- **问题**: 生产代码一般不会在请求中调 `set_client_for_tests`,但 FastAPI 测试 + lifespan 共享进程时,fixture 切换 client 与请求中的 get_client 可能竞态(单线程 asyncio 不致命,但 fixture 重入)。
- **修复**: 用 contextvar 或 per-event-loop 缓存(同 `_global_launch_sem` 的 pattern)。

#### P2-5  `fill_plate_defaults` 就地修改入参 dict
- **位置**: `backend/app/services/plate_client.py:86-115`
- **证据**:
  ```python
  def fill_plate_defaults(payload, *, owner=""):
      payload.setdefault("kind", "scenario")
      meta = payload.setdefault("meta", {})
      if not meta.get("createTime"):
          meta["createTime"] = _now_iso()
      meta.setdefault("requirementRef", [])
      if owner and not meta.get("owner"):
          meta["owner"] = owner
      payload.setdefault("scenarioId", meta.get("scenarioId", ""))
      return payload
  ```
- **问题**: `setdefault` 是就地改。`scenarios.py:_draft_to_full_scenario_dict`(`payload = {k: v for k, v in draft.definition.items()}`)构造新 dict 但内层 meta 仍是引用,plate 拒绝(4xx) 时外层 payload 已被添加 `kind/requirementRef/owner` 等;**前端拿到的 `body.definition` 不可逆地被污染**(次轮请求会带 kind 等冗余字段)。
- **影响**: 表单反复编辑保存时把 "scenario" kind / requirementRef=[] 反复提交,虽然无害但语义混淆;`scenarioId` 顶层字段一旦填入,前端不会清除。
- **修复**: 内部走 `copy.deepcopy(payload)`,函数签名明确"返回新对象"。

#### P2-6  `endpoint_id` 在代理 URL 中未做 URL encode
- **位置**: `backend/app/routers/endpoint_catalog.py:45, 47`;`backend/app/routers/strategy_catalog.py:88`;`backend/app/services/adaptation_service.py:64`
- **证据**:
  ```python
  resp = await client.get(f"/api/endpoint/{endpoint_id}/full")
  ```
- **问题**: `endpoint_id:path` 允许含 `/`,但若含 `?` / `#` / ` ` 等保留字符,f-string 直接拼会破坏 URL。
- **修复**: `httpx.URL(path=f"/api/endpoint/{endpoint_id}/full")` 让 httpx 自行编码。

#### P2-7  `_resolve_exec_auths` 全量读 owner 凭证到内存
- **位置**: `backend/app/services/run_dispatcher.py:1069-1128`
- **证据**:
  ```python
  rows = (await session.execute(
      select(DBAuthSession).where(
          DBAuthSession.owner_id == owner_id, DBAuthSession.alias.in_(aliases),
      )
  )).scalars().all()
  for a in rows:
      runtime = RuntimeAuthSession(... fernet_decrypt(a.username_enc) ...)
      resolved.append(ResolvedAuth.from_runtime(runtime, alias=a.alias))
  ```
- **问题**: `ResolvedAuth` 在内存持有 username/password 明文,从 `_fanout` 入口到最后一个 `_row()` 完成才释放。30 行 × 300s timeout = 明文凭证在堆中停留数分钟;同时如果 owner 凭证很多(几百个 alias),`IN` 子句扩大。
- **影响**: 内存攻击面 + 调试器/转储泄露风险。攻击面有限但与"明文不过 DB"承诺不一致 — 实际是"明文不过 DB 但在内存中随意停留"。
- **修复**: 把 `_resolve_exec_auths` 改为"按行即时解密"(`_row` 入口传 alias 列表,内部 Lazy decrypt);或让 `_apply_users` 接受一个"解密回调"避免清单常驻。

#### P2-8  `stars.json` 文件 store 与 DB 不一致的可能
- **位置**: `backend/app/services/marks_store.py:1-122`;`backend/app/routers/scenarios.py:262-272`
- **证据**:
  ```python
  @router.post("/{scenario_id}/star", status_code=204)
  async def star_scenario(user, db, scenario_id, body):
      row = await _load_row(db, scenario_id)
      _require_reader(user, row)
      stars.set_mark(user.id, scenario_id, body.starred)
  ```
- **问题**: stars 是 JSON 文件,scenario 创建/删除走 DB,二者无强一致性:`set_visibility` / `delete` 不动 stars(OK,star 跟着 scenario 走,但场景被 hard delete 后 stars 残留),`scenario_store.delete` 调 `stars.remove_item(scenario_id)`(OK),但**JSON 文件没参与 DB 事务**:DB commit 失败而 stars 已更新会反向;stars 文件丢失/损坏而 DB 行还在场景里 → `scenario.to_read_shape` 返回 `starred=False` 用户视角丢失。
- **影响**: 启动期从 JSON 重建失败仅 warning(`marks_store.py:88`),stars 表整个丢失不可察觉。
- **修复**: 迁移 stars 到 `star_marks(owner_id, scenario_id, created_at)` DB 表,加入唯一索引;或写入改 DB 触发器 + JSON 镜像。

#### P2-9  carry preview 与 dispatch 的 alias 注入顺序不一致
- **位置**: `backend/app/routers/scenarios.py:159`;`backend/app/services/run_dispatcher.py:417`
- **证据**:
  ```python
  # scenarios.py preview-plate
  aliases = sorted(set([*scanned, *bound]))
  ```
  ```python
  # run_dispatcher.py dispatch_run
  auth_aliases = list(dict.fromkeys([*scanned, *bound]))
  ```
- **问题**: preview 排序后去重,dispatch 保序去重。同一请求的 preview 与 dispatch 注入顺序不同,引擎 preprocess 若依赖顺序会出差异(目前不算路径,但 spec §7 写"导出 = 执行"应字符字面一致)。
- **修复**: 一处统一为 `dict.fromkeys([*scanned, *bound])`,另一处同步。

#### P2-10  `runs.py` 把 scenario 预加载给 dispatch_run 但仍重新解析步骤与 datasets
- **位置**: `backend/app/routers/runs.py:54-75`;`backend/app/services/run_dispatcher.py:357-388`
- **证据**:
  ```python
  scen = await scenario_store.get_row(db, body.scenario_id)
  ensure_owner(user, scen.owner_id, ...)
  return await run_dispatcher.dispatch_run(db, user_id=user.id, req=body,
                                           preloaded_scenario=scen)
  ```
  ```python
  # dispatch_run 中
  steps = steps_from_payload(scen.payload)   # 重新解析
  for ds_id in req.data_set_ids:
      ds = await _find_dataset_by_id(db, ds_id)   # N 次查询
  ```
- **问题**: 预加载只省 1 次 scenario 查询;datasets 仍 N 次。`req.data_set_ids` 可能 50 个,加 DB 往返。
- **修复**: 同步预加载 datasets:`datasets = await data_set_store.list_for_scenario(db, scen.scenario_id)`,在 dispatch_run 里 dict 查。

#### P2-11  cancel_execution 的 status 更新无原子保护
- **位置**: `backend/app/routers/executions.py:157-181`
- **证据**:
  ```python
  run_dispatcher.request_cancel(ex.id)
  if not run_dispatcher.has_live_fanout(ex.id):
      ex.status = STATUS_CANCELED; ex.finished_at = utcnow()
      await session.commit(); await session.refresh(ex)
  ```
- **问题**: 无 live fanout 的判断是基于模块级 `_tasks_by_execution` 字典;同时 dispatcher 内 `_fanout` 已退出但 done-callback 尚未触发 pop 时,`has_live_fanout` 仍 True → router 不立刻 finalize,等下一次 cancel 或下次 list 才看到 canceled。极端竞态:dispatcher 已 finalize 为 done,router 端把它改 canceled(覆盖最终态)。
- **影响**: 罕见但会出现"执行已完成却显示 canceled"。
- **修复**: 把 finalize 幂等化:`update Execution set status=CANCELED where id=? and status in (QUEUED, RUNNING)`,DB 层兜底。

#### P2-12  `ServiceBinding.url` 与 `AuthSession.url` 缺 URL 格式校验
- **位置**: `backend/app/schemas/scenario_composer.py:186-191`;`backend/app/models/auth_session.py:31`
- **证据**:
  ```python
  class ServiceBinding(BaseModel):
      auth_alias: str | None = Field(default=None, alias="authAlias", max_length=128)
      url: str | None = Field(default=None, alias="url", max_length=512)
  ```
- **问题**: `url` 接受任意 512 字符字符串(含 `javascript:`, `file:`, 空字符串等)。run-time 注入到 `Config.services[svc]` 后被引擎消费,可能引发不期望的网络请求或 SSRF(虽然面向内网)。
- **影响**: 内网测试平台 SSRF 风险较低但非零;运维/二方包升级可能让"任何 URL"被更广消费。
- **修复**: ServiceBinding 加 `field_validator("url")` 用 `pydantic.HttpUrl` 限定 http/https,允许为空(None)。

#### P2-13  `data_set_store.create` 对 unique 冲突的判别容错但可能误吞 NOT NULL 错
- **位置**: `backend/app/services/data_set_store.py:82-91`
- **证据**:
  ```python
  except IntegrityError as e:
      await db.rollback()
      if _is_dataset_id_collision(e):
          raise ValueError(f"dataset_id_exists: {dataset_id}") from e
      raise
  ```
- **问题**: `_is_dataset_id_collision` 用 `if "dataset_id" not in msg: return False` + 黑名单 `("NOT NULL", "FOREIGN KEY", "CHECK constraint")`。如果 NOT NULL 错的消息里恰好出现 "dataset_id"(例如"NOT NULL constraint failed: composer_data_sets.dataset_id")会被误判为 collision,因为 NOT NULL 才会被黑名单 — 实际 OK。但**未来若 schema 加新 NOT NULL 字段,消息形态可能绕过黑名单**,且当前 `_next_dataset_id` 100% 保证 `dataset_id` 非空,基本不可能出现 NOT NULL on dataset_id,但仍属于"防御深度不足"。
- **修复**: 用 SQLite `PRAGMA table_info(composer_data_sets)` 主动检查 NOT NULL 列列表,在 catch 里按列名 whitelist 判别。

#### P2-14  main.py router 注册顺序敏感且注释 "MUST be last" 容易踩坑
- **位置**: `backend/app/main.py:114-128`
- **证据**:
  ```python
  app.include_router(runs.router, prefix="/api")
  app.include_router(data_sets.router, prefix="/api")
  app.include_router(data_sets.create_router, prefix="/api")  # before scenarios
  ...
  app.include_router(scenarios.router, prefix="/api")  # MUST be last
  ```
- **问题**: 路由顺序靠人工维护。新增 `/api/scenarios/{scenario_id}/xxx` 子端点时,若忘记放在 scenarios.py 的前缀顺序头部就会被 `/{scenario_id}` 吞掉。当前 scenarios.py 已经把 `/preview-plate`, `/{scenario_id}/star`, `/{scenario_id}/publish`, `/{scenario_id}/unpublish`, `/{scenario_id}/copy`, `/{scenario_id}/run-schemes`, `/{scenario_id}/draft` 都排在 `/{scenario_id}` 之前,但 `runs` router 前缀是 `/runs`(不冲突),`data_sets` 是 `/data-sets`(不冲突),`scenarios` 自身的子路由全部在模块内有序 — 主流程 OK,**但 `create_router`(data_sets.create_router)是单独注册而非在 data_sets 模块内,新人极易添加 router 时打破隐式顺序**(注释明确警告过)。
- **修复**: 给 `create_router` 改名为 `data_sets.nested_router`,挪回 data_sets.py 文件头部;或加自动化测试断言"每条 /scenarios/{id}/xxx 子路径能 resolve 到非 catch-all handler"。

---

## 二、亮点

1. **统一的 owner/auth 收紧**:`_ownership.ensure_owner` + `can_read_scenario` 单一权威,`scenarios` / `data_sets` / `runs` 全部走 owner_id(int) 判定,字符串 owner 仅展示。`_require_reader` 把"无权读"统一为 404 而非 403,避免存在性泄漏,设计扎实。
2. **run dispatcher 的 cancel 协作式状态机**(P4):`_cancel_requested` 集合 + `_tasks_by_execution` 索引 + 行边界检查 + `cancel_execution` 端点的"无 fanout 立即终态化"分支,思路正确且文档化充分。
3. **重启僵尸收敛**(P3):`reconcile_stale_executions` 启动期把 queued/running 标 failed + reconciled 标记,显式区分用户视角的"未开始"和"已死"。
4. **熔断器**:`PLATE_BREAKER_THRESHOLD=3` + `plate_state["consecutive_unavailable"]` 防止 plate 宕机时逐行 30s 超时堆叠,设计周到。
5. **carry 注入链**:预览与执行共用 `materialize_run_copy` 纯函数 + `build_carry_context` 同源,spec §7 黄金等价保障做实。
6. **rollback 乐观冲突**:`_rollback_*` 三类实体的乐观比对 + 不盲写 + 冲突报告,避免"批次外修改"被覆盖。
7. **scenario_endpoint_ref 派生层**:scenario 创建/更新同事务维护倒排,补 `rebuild` 兜底,可重建性显式。
8. **error_mapping helpers**:`key_error_404` / `not_found_404` / `value_error_http` 把 9+4 处的 copy-paste 收敛到一张 code→status 表。
9. **fail-closed 写穿预防**:`fill_plate_defaults` / `_resolve_exec_auths` 明文不入 DB 的承诺有代码注释 + 物理验证。
10. **CORS 设计干净**:JWT 走 Authorization header,`allow_credentials=False` + 非通配 origins,无 cookie 模式踩雷面。

---

## 三、总评

**整体业务实现质量**:中等偏上,核心链路(run dispatch + carry 注入 + 适配批次 + scenario CRUD)业务规则与状态机已具备雏形,错误码与所有权收紧统一度较高,设计意图通过注释和测试(隐含)有清晰外化。**短板集中在三个工程地基**:
1. **SQLite 未做生产配置**(无 WAL / busy_timeout)— 任何并发派发都会被卡;
2. **跨进程一致性的边角路径**未完全收敛(case 凭证残留、runSchemes 透传 TOCTOU、stars.json 旁路 DB);
3. **扩展性的 N+1 / 全表扫描**在数据量过 1k 行时已可见。

### 建议优先做的 3 项工作

1. **SQLite WAL + busy_timeout 配齐**(`P0-1`)— 单点改动但解锁后续所有并发性能优化(否则加索引也无意义,写仍串行)。
2. **案例案卷残留闭环**(`P0-2`)— 给 `Execution.scenario_id` 加 FK cascade + 用户删除入口的 `purge_case_dir_by_owner`,让 case.json 明文凭证真正不外溢。
3. **乐观锁 + 反向索引重建**(`P0-3` + `P1-5`)— scenario 加 `version` 列做 OCC、`scenario_endpoint_ref` 加 FK cascade,从根上消除"双 tab 编辑丢方案"与"孤儿倒排行"两类暗病。

---

## 附录:评审依据代码索引

| 关注点 | 关键文件 |
| --- | --- |
| 路由与所有权 | `app/routers/scenarios.py`, `runs.py`, `executions.py`, `data_sets.py`, `carry.py`, `adaptations.py`, `routers/_ownership.py`, `routers/_error_mapping.py` |
| 业务状态机 | `app/services/run_dispatcher.py` (cancel/drain/breaker/memo), `app/services/adaptation_service.py` (batch lifecycle) |
| 子进程 | `app/services/gimbal_launcher.py` |
| 凭证与执行 | `app/services/run_materialize.py` (物化纯函数), `app/services/carry_injection.py`, `app/services/auth_ref_scan.py` |
| 持久化 | `app/core/db.py` (SQLite engine), `app/models/*`, `app/services/scenario_store.py`, `data_set_store.py`, `carry_store.py`, `marks_store.py` |
| 配置与生命周期 | `app/core/config.py`, `app/main.py` (lifespan/router order) |
