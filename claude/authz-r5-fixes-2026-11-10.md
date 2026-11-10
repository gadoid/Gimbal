# authz M2a/M2b 评审第五轮必修项修复(2026-11-10)

对照:`m2a-m2b-completion-review-r5-2026-11-10.md`(5 项必修 = 2 项本轮新增 + 3 项第三轮遗留)。
分支 `feat/plate-s1`,修后提交见 git log。**裁定项(评审§四 4.1–4.4)不在本批**,待拍板。

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

## 不在本批(评审§四,待拍板)

- 4.1 exclusive 同账号约束(实现 or 移入 M3);
- 4.2 M6–M8 裁定确认;
- 4.3 项目凭证按键名脱敏的残余风险(按值掩码 or 公告披露);
- 4.4 第三轮三.1–三.3(项目区敏感列策略 / 原 5 待确认 / 公共模板指纹按属主个人池)。
- 覆盖缺口:exclusive 未建模;Q3 suite 编排仍 409 `dataset_binding_unsupported`。

## 门禁

后端全量:`1965 + 6(r5 新增)= 1971 passed / 3 skipped`(test_execution_refactor 已知 teardown
死锁单跑即过,与既往口径一致);前端 vitest 1350(新增 2)/ vue-tsc 0 / eslint 0 / build ✓。
