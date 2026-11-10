# authz M2a/M2b 评审第五轮必修项修复(2026-11-10)

对照:`m2a-m2b-completion-review-r5-2026-11-10.md`(5 项必修 = 2 项本轮新增 + 3 项第三轮遗留)。
分支 `feat/plate-s1`,修后提交见 git log。评审§四 4.1–4.4 已于同日拍板(见文末「裁定与后续」;4.3 按值掩码当场实现)。

## 修复清单

### 2.1 platformize / transfer 令牌越区(本轮新增)

`routers/integration.py`:`POST /tasks/{id}/platformize` 与 `POST /tasks/{id}/transfer` 在令牌路径
(个人 ∨ 项目)一律 404 —— 人工治理动作不开放给机器身份(项目令牌映射负责人的完整用户权限,
修前可越区平台化他人公共模板 / 转移负责人本人的公共维护权)。会话路径行为不变。
测试:`test_authz_r5_review_fixes.py::TestPlatformizeTransferTokenDenied`(个人令牌 + 项目令牌
两个端点都 404;Admin+ 会话 platformize / transfer 照旧 200)。

### 2.2 项目凭证「改地址再拨测」明文出口 + Admin+ 口径矛盾(本轮新增)

`routers/project_credentials.py`:

- **改 `url` 须同时重录 `password`**(422 `url_change_requires_password`)—— 拨测/执行把解密凭据
  发往 `a.url`,单改地址 = 把存量密码重定向到任意收集端;同值 url 不算改动。个人凭证面(本人单判)
  不受影响。
- **管理门 `_manage_gate` 去掉 Admin+ 旁路**(本地实现:项目管理员 ∨ 404 / 成员 403),与选用门
  `can_use_project_credentials` 同口径 —— 收掉「Admin+ 不能用却能改址拨测」的自相矛盾;列表读面
  同步收口(Admin+ 非成员 404,不再给用户名视图)。模块头「没有任何明文出口」的自述更正为
  「明文唯一出口 = 拨测(发往凭证自身登录地址,改址须重录密码)」。
- 前端 `ProjectCredentialsPanel.vue`:编辑态改地址出提示、未录密码前置拦截(不发请求);
  `ProjectCredentialsPanel.url.test.ts` 2 例。
- 测试:`TestProjectCredentialUrlPasswordAndGate`(422 / 同值放行 / url+密码 200;Admin+ 非成员
  读-建-改-测全 404;成员视图不变)。

### r3二.1 项目成员数据集:丢敏感列 + 列不出同事(第三次复现)

- **成员可列同事的数据集**:`GET /api/data-sets` 可见集 = 本人属主场景 ∪ 我所在项目的项目区场景
  (`scenario_store.project_member_scenario_ids`,新增);同事的预览/单读剥敏感列口径不变
  (`owned_ids` 传属主集)。非成员仍不可见。
- **非属主保存不再丢敏感列**:`data_set_store.update` 增 `viewer_id` —— 非属主提交是脱敏视图,
  按**行位**把存量敏感列值并回(`scenario_store.merge_sensitive_columns`,新增);存量值权威
  (提交里的同键猜测值不覆盖 —— 读者本看不到真值);新增行无敏感值可并,保持提交形态。属主保存
  原样。Q3 账号列(`@slot.*`)不是敏感列,不受并回影响。
- 测试:`TestDataSetMemberListingAndSensitiveKeep`(成员列表 1 条且预览无 password;整表保存后
  属主读回 secret1/secret2 在、猜测值不生效、普通列更新;属主保存原样)。

### r3二.2 carry 项目层非成员可读(第三次复现)

`routers/carry.py::_resolve_scope`:`scope=project` 的**读面**补成员校验(非成员 404 —— 此前
`write=False` 完全不设门,`GET /carry/bindings/{svc}?scope=project&projectId=` 与
`GET /carry/defaults?scope=project` 都能带出项目层值)。Admin+ 写旁路照旧(漂移同门);成员任一
角色可读(与 `/carry/bindings` 可见层并集同口径)。
测试:`TestCarryProjectReadGate`;`test_authz_s40_carry_scope.py` 既有断言全数保持。

### r3二.3 导出不守区规则(第三次复现)+ S7.5 记录更正

`routers/scenarios.py::_materialized_executable` 增 `project_id` 透传 `prepare_exec` ——
`GET /scenarios/{id}/export` 按**场景所在区**适用原 5(与执行链同口径):项目/公共区场景导出
内置凭证(`config.users`)当空、直连地址(`config.services`)不生效,**属主本人也一样**(区规则
不看人);私有区属主导出仍带本人明文(Q3 裁定不变)。preview-plate 草稿路径不涉及(草稿无区)。
- 测试:`TestExportZoneRules`(私有区带 users+direct baseUrl;项目区两者皆空)。
- **S7.5 实施记录更正**(`authz-m2a-s7-detail-2026-11-09.md`):原文「项目 / 公共区不带内置
  凭证(原 5)」当时不实 —— 导出链漏传 `project_id`,属主导出项目场景仍带明文;本批已修。

## 裁定与后续(评审§四,2026-11-10 拍板)

### 4.1 exclusive 同账号约束 → **移入 M3**

原方案 P5 第二行(同一执行内不同槽位不得落同一账号,仅对声明 `session_policy: exclusive`
的系统检查)从未实现、声明位也不存在 —— 正式改挂 **M3**(含:声明位小迁移、派发/预检逐行
与全图口径检查、Q3 suite 编排对行级账号列的支持〔现为 409 `dataset_binding_unsupported`〕)。
M2 需求清单就此收口,不再悬空。

### 4.2 M6–M8 → **全部按已实施推荐确认**

- M6 项目令牌管理门 = 项目管理员 ∨ Admin+(与项目凭证门**有意不同口径**:令牌非机密、
  无导出面,Admin+ 保留应急吊销;凭证是机密,r5-2.2 后门更窄);
- M7 账号列按**绑定名**引用;M8 个人池下账号列**生效**(执行人个人池同名解析)。
- 均无代码变动;m2b-detail §四裁定表已改「已裁定」。

### 4.3 项目凭证间接可读 → **按值掩码,本批实现**(引擎侧)

裁定:立即做按值掩码,不等 M3。实现(`src/gimbal`):

- **登记册** `protocols/secrets.py`(新):进程内累积的秘密值集(阈值 ≥6 字符,过短不登记
  —— 测试短串会把证据面掩成马赛克;泄漏方向只上调不下调)。
- **登记点**:`AuthRegistry.set`(users 定义输入的 password/refresh_token/静态 token;
  username/url 不是秘密不入册)+ `AuthSession.apply_token`(认证/刷新后的运行期访问
  令牌 —— 成员「提取登录响应里的 token」这条路也堵上)。
- **证据出口**(键名脱敏先做、值掩后做;**原值面绝不过这里** —— scratch/断言/提取仍按
  真值求值,见 `CallResult.to_scratch` 契约):
  - `CallResult.to_evidence`(事件/归档/报告统一证据面;先掩后截,截断不会把值切成
    可见两半);
  - `project_step_completed` 投影(extracts 值 / assertions expected·actual·message /
    error_brief);
  - `Engine._detail_row`(run.finished 随终线发平台的 details 行:error 串 / outputs)。
- dict 的**键**一并掩(秘密值也可能被放进键名);空册零开销直通(无凭证场景不产生拷贝)。
- CLI 每案一进程;suite / 平台内嵌多场景同进程值集跨场景累积 —— 旧值被多掩是安全方向
  噪声,不是泄漏。
- 测试:`tests/unit/test_value_masking_secrets.py` 7 例(登记阈值/形状、registry+apply_token
  入册、to_evidence 普通键名也掩、投影 extracts/assertions/error_brief、details 行、空册
  行为不变)。
- 平台侧**零改动**:派发本就把凭证物化进 case 的 `config.users`,掩码是引擎证据面行为;
  平台持久化的 events/rows 全部来自引擎投影,天然继承。

### 4.4 第三轮三.1–三.3 → **按推荐**

- 三.1 项目区数据集敏感列:**保持**(成员读脱敏 + 非属主保存按行位并回存量值,即本批
  r3二.1 修复后的形态);
- 三.2 原 5 落库面:列 **M3** 小切片 —— 进项目/公共区(新建带 projectId / 提升 / 发布)
  即剥 `config.users` 与 `config.services` 存储 + 一次性清洗存量行(与发布副本
  strip="always" 同口径,「共享区不落明文」闭环);
- 三.3 公共模板指纹按属主个人池:**保持**(换绑改变实际执行凭证,暂停-重新确认是知情
  机制而非缺陷;属主侧规范「少折腾换绑」)。

## 门禁

- 后端全量(必修项后):`1971 passed / 3 skipped`(1965 + r5 新增 6)。
- 前端:vitest 1350(新增 2)/ vue-tsc 0 / eslint 0 / build ✓。
- 4.3 引擎按值掩码追加:root 套件 `1433 passed / 3 skipped`(新增 7);后端全量复跑
  `1970 passed / 3 skipped + 2 errors` —— 两个执行链测试(test_debug_console /
  test_execution_refactor)为已知全量 teardown 串扰类(前序泄漏的后台任务打到已删
  schema;单独跑、两文件同跑 18/18 均绿;受害者逐次不同,评审分块跑 0 error),非本批
  引擎改动所致。
