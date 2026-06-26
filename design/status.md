PR-2.3 阶段总结与下一步实现计划
一、PR-2.3 现状总结
1.1 已完成(代码与测试)
模块	状态	备注
src/Plate/server/response.py	✅ 落地	json_response / error_response,用 sort_keys=True, separators=(",",":") 保证字节级稳定
src/Plate/server/router.py	✅ 落地	{name} 与 {name:path} 占位符 → 正则;Route dataclass;register_handlers + match_route API
src/Plate/server/init.py	⚠️ 落地但含 DEBUG	7 个 handler + PlateRequestHandler + PlateServer;含 _collect_specs_for_service 辅助函数;仍残留 DEBUG print
tests/plate/test_server.py	✅ 31 单元测试	孤立运行 31/31 通过
tests/plate/test_server_e2e.py	✅ 8 E2E 测试	孤立运行 8/8 通过
tests/plate/test_invariants.py	✅ 新增不变量 #12	test_invariant_server_protocol_byte_equal + allowlist 更新
tests/plate/test_zero_invasion.py	✅ allowlist 更新	列入 server / router / response
1.2 已知问题(阻塞 5 个测试)
5 个测试在孤立运行时通过,在全量套件中失败:
失败测试	现象
TestServerManifest::test_manifest_default	len(body["services"]["fin"]) == 0 (期望 31)
TestServerSpec::test_spec_service_fin	len(body["specs"]) == 0
TestServerSpec::test_spec_endpoint_existing	ENDPOINT_NOT_FOUND
TestE2EByteEqual::test_e2e_spec_endpoint_byte_equal_to_local	空 spec 列表
TestE2EServerStandalone::test_e2e_multi_endpoint_consistency	空 spec 列表
已通过 debug 锁定的事实:
Plate.fin 模块的 vars().values() 确实有 31 个 EndpointSpec 实例
类身份核对正确:from Plate.spec import EndpointSpec is from Plate.core import EndpointSpec 为 True
registry.collect("fin") 返回 _loaded={"fin"} 但 _index={}
触发器:test_invariant_top_level_does_not_load_service_subpackages 先运行,卸载了 Plate.*,导致后续 server 线程里 _index 与 sys.modules 状态错位
1.3 架构一致性核对
原则	兑现度
零侵入(server 不修改 registry 状态)	✅ handler 仅 collect + resolve,从不 register
按需加载	⚠️ 取决于 registry 行为,全量套件下退化
契约保真(byte-equal)	✅ json.dumps(sort_keys=True, separators=(",",":")) + compute_checksum 走 sort_keys=True
互补而非替代	✅ 服务端是只读视图
优雅降级	✅ 错误码 + available_* 提示
A1 版本优先	✅ DEFAULT_VERSION=1.0.0,SUPPORTED_VERSIONS=(1.0.0,),未传 version → 400
A2 不可变序列化	✅ to_dict() 不变
A3 冷热分层	✅ /v1/spec/* 与 /v1/doc/* 分离
A4 本地优先远端备份	⚠️ 远端(本 PR)已通,本地优先路径在 PR-2.4(SDK)实现
A5 协议先于实现	✅ PR-2.1 协议先行,本 PR 严格响应
A6 向后兼容	🟡 单版本下不显式需要,PR-2.4+ 升版时再验证
1.4 设计偏差
偏差	设计	实际	影响
部署方式	subprocess.Popen 起外部进程	pytest fixture 同进程起线程(daemon HTTPServer)	E2E 仍可拉,只是非"真子进程"
数据采集	走 registry.collect + _index	调试中发现不可靠,新增 _collect_specs_for_service 直采旁路	短期可解,长期应修复 registry
端点路由	设计文档示例 /v1/spec/{service}/{method}/{path:path}	✅ 一致	OK
/healthz	必须	✅ handle_healthz 已实现	OK
Update Todos

梳理 PR-2.3 现状与架构一致性

诊断 5 个测试失败的根因与候选修复方案

起草 PR-2.3 阶段总结(已完成/未完成/设计偏差)

起草下一步实现计划(P0/P1/P2 分级)
二、下一步实现计划(P0 / P1 / P2 分级)
P0 — 阻塞 PR-2.3 收口(必须先做,否则 5 个测试不绿)
P0-1:定位 registry.collect 与 sys.modules 状态错位的根因
任务:读 src/Plate/registry.py 的 collect() 与 _collect_locked(),重点看它如何检测"新 spec":
是否捕获了首次 import 时的 sys.modules 状态作为基准?
是否依赖 inspect.getsourcefile / 模块属性扫描?
register_endpoint_spec 装饰器在何时往 sys.modules 注入类?
判定标准:
如果根因是"装饰器在 sys.modules 里留下了 detached 引用" → 修装饰器(最干净)
如果根因是"collect 内部对 __subclasses__ 之类的全局视图依赖" → 在 collect 开头显式 importlib.import_module("Plate." + svc) 并 vars() 扫一遍
预计 1–2 小时
P0-2:三选一修复方案
方案	描述	优点	缺点	推荐度
A. 修根因	修 registry.collect 使其对 sys.modules 状态重置鲁棒	一次性治好,服务未来多进程/多线程都受益	风险面大,需回归全套	⭐⭐⭐
B. server 端用旁路	已在 __init__.py 加好 _collect_specs_for_service,只差替换 registry.collect 调用	改动小,不动 registry	registry 本身的脆弱性仍存在,Phase 3 还会撞	⭐⭐
C. eager collect	在 PlateServer.__init__ 主线程里先 for svc in SUPPORTED_SERVICES: registry.collect(svc),再起 HTTP 线程	一行修复,避竞态	治标,registry 错位仍可能在 fixture teardown 后复现	⭐
建议:先 A(根因),A 失败回退 C。不要选 B——B 把"server 不依赖 registry 状态" 变成隐性约束,违反 A5 协议先于实现的"数据源 = 本地 registry"。
P0-3:清除 DEBUG print
[src/Plate/server/__init__.py:111-155](src/Plate/server/__init__.py#L111-L155) 的 print(...file=sys.stderr) 块,以及任何 import sys 仅为 DEBUG 而引入的位置。一并移除并跑 ruff / black。
P0-4:全量套件验证
pytest tests/plate -q,期望 426/426 通过(原 386 + 新增 40 server 测试)。
P1 — PR-2.4 准备(GIMBAL SDK 切换 + 向后兼容)
P1-1:写 PR-2.4 设计文档
放到 design/phase2/PR-2.4.md,骨架:
# PR-2.4: GIMBAL 切换 + 向后兼容

## 1. 业务动机
  - Phase 1 SDK 只能查本地 registry
  - Phase 2 后必须能切"远端优先 / 本地兜底 / 远端失败回退本地"
## 2. 三态切换矩阵
  | mode        | 读路径                       | 适用场景     |
  | local-only  | Plate.registry               | dev/单测    |
  | remote-first| HTTP server → 本地 cache     | ci/staging  |
  | local-fallback| HTTP server,失败 → 本地     | prod        |
## 3. 兼容矩阵
  - v1.0.0 server ↔ v1.0.0 client
  - v1.0.0 server ↔ v1.1.0 client(协议向前兼容)
  - 旧 client(无 server 认知) → 走 local-only
## 4. 代码入口
  - GIMBAL.from_url(url) / GIMBAL.from_local() 工厂
  - sdk/__init__.py 暴露新 API,旧 API 走 deprecation warning
## 5. 验收
  - 字节级 pin:同一份 contract,远端 vs 本地 checksum 一致
  - 失败注入:server 500 → 降级到本地,功能不退化
  - 旧调用代码可继续工作(warning 而非 error)
预计半天
P1-2:实现 PR-2.4 骨架(在 P0 收口后)
src/Plate/sdk/__init__.py: PlateClient 类,3 个 mode
tests/plate/test_sdk_switch.py: mode 切换 + 降级 + 字节 pin
预计 1–1.5 天
P2 — PR-2.5 收尾(Phase 2 收口 + 基线 + 文档同步)
P2-1:写 PR-2.5 设计文档
design/phase2/PR-2.5.md:
Phase 2 全景回顾(PR-2.0 → 2.5)
5 不变承诺 + 6 新增原则兑现度审计
测试基线(目标 ≥ 480)
文档同步清单(PLATE_DESIGN.md §7 §8, README.md 增 PR-2.x 章节)
Phase 3 入口(MCP / 多进程 / 异步)预留
P2-2:Phase 2 收口 PR
合并 PR-2.3 / PR-2.4
更新基线到 design/phase2/BASELINE.md
给 GIMBAL_MAIN 打 tag(如 phase-2-eop)
三、关键风险与提醒
风险	触发条件	缓解
registry.collect 跨线程不可重入	当前已观测	优先 P0-1 根因修复;否则 P0-2C 缓兵之计
PR-2.4 切换 mode 时 checksum 漂移	远端与本地 to_dict 顺序差异	已在 PR-2.0 强约束 sort_keys=True,套件需再覆盖一次
多版本上线后旧 server 协议破坏	升 1.1.0 时改 checksum 字段语义	PR-2.4 兼容性矩阵必须先写测试
server 单线程 QPS 瓶颈	未来 > 100 QPS	Phase 3 切 ThreadingHTTPServer 或 aiohttp
四、立即可执行的下一步(给下次会话的开局指令)
打开 src/Plate/registry.py,通读 collect / _collect_locked / register_endpoint_spec
复现最小化失败 fixture:加载 → 卸载 Plate.* → 重新加载 → 调 collect,观察 _index
据此选定 P0-2 方案(A / C),落地修复
删 DEBUG → 全量 pytest tests/plate -q → 426/426 绿
切到 P1-1:写 PR-2.4 设计文档
当前会话总结(给你存档):
PR-2.3 设计完成 + 代码基本完成 + 测试基本完成,5 个测试因 registry 状态错位失败(P0 级)
32 个新测试在孤立场景下全绿,意味着业务逻辑正确,问题在测试间状态污染而非产品缺陷
下一步是定位 registry.collect 的鲁棒性问题(P0-1),修复后即可收口 PR-2.3