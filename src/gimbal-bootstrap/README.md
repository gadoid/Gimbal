# gimbal-bootstrap

用 gimbal-platform 测 gimbal-platform。平台侧的用例编排，不改平台 schema。

## 三个部分

| 部件 | 位置 | 干什么 |
|---|---|---|
| 契约生成器 | `gimbal_bootstrap/contract_gen.py` | 拉平台自己的 `/openapi.json`，转成 plate 的 `EndpointSpec`，落成 `endpoints.json` |
| 契约登记 | `src/gimbal-plate/gimbal_plate/systems/platform/` | 加载 `endpoints.json`，通过 plate 现有的 registry 注册 115 条 platform 端点 |
| 用例编排 | `gimbal_bootstrap/orchestrator.py` + `cases/*.yaml` | 以普通用户身份走平台公开 HTTP，跑黄金链路与每域烟雾，用完清理 |

平台代码改动只有一处：`app/routers/auth.py` 补了一行 `ChangePasswordIn` 的 import
（文件有 `from __future__ import annotations`，漏这个 import 会让
`/openapi.json` 整个 500）。除此之外，**被测系统一行未动**。

## 用法

```bash
cd src/gimbal-bootstrap

# 1. 重新生成契约（平台接口有变动时）
python -m gimbal_bootstrap.contract_gen

# 2. 跑全部自举用例
python -m gimbal_bootstrap.orchestrator
```

编排器会**先注册一个专用账号然后停下来**：新注册用户一律是 `member`，而
`/api/users/roster` 这类端点要管理员权限。停住之后到平台里把该账号提权为
管理员，回车继续。

账号名是 `sb_<10位十六进制>`。自举账号口令**不入库** —— 账号是管理员，口令
提交进仓库等于把平台交出去。真值放 gitignore 掉的 `src/gimbal-bootstrap/.env`：

```bash
cp src/gimbal-bootstrap/.env.example src/gimbal-bootstrap/.env
# 编辑 .env 填 GIMBAL_SB_PASSWORD
```

进程环境变量优先于 `.env`：

```bash
export GIMBAL_SB_USERNAME=sb_xxxx
export GIMBAL_SB_PASSWORD=...
python -m gimbal_bootstrap.orchestrator
```

设了 `GIMBAL_SB_USERNAME` 就直接复用该账号，既不注册也不暂停 —— 提权好的
账号存进环境变量，之后每次重跑都省掉这道人工环节。

想跳过暂停（域用例会 403）用 `--no-pause`，只跑黄金链路用
`--cases cases/golden_path.yaml`。

## 漂移检测

```bash
python -m pytest tests/test_contract_drift.py
```

**单向**：契约里登记了、平台却没了的端点算漂移；平台多出来的端点不算 ——
契约是地板，不是天花板。

两层：静态层拿 `/openapi.json` 对账，无副作用无需登录；实测层用提权后的
自举账号真打几个 GET，确认不只是 schema 上有而是真能通，需要
`GIMBAL_SB_USERNAME` 和 `GIMBAL_SB_TOKEN`，没设就跳过。

## 两条要记住的坑

**plate 的 `by_route` 是后写覆盖先写。** 两条端点登记到同一个
`(service, method, path)` 会静默吃掉一条，运行时才炸。生成器在
`check_collisions()` 里直接抛，登记前就炸。

**`orchestration.steps` 必须和 `definition.steps` 严格同序同长。** 少一个，
建场景就被拒。`_new_scenario()` 按 `len(definition["steps"])` 生成。

## 目录

```
gimbal_bootstrap/
  contract_gen.py      OpenAPI → EndpointSpec
  platform_client.py   薄 HTTP 客户端，4xx/5xx 抛 PlatformError
  case_builder.py      用例 YAML → plate Scenario definition
  assertions.py        断言求值器（$.call.response.* 路径）
  orchestrator.py      端到端：注册 → 建资源 → 跑 → 清理
cases/
  golden_path.yaml     T1-T8 全链路
  domains.yaml         每域一条烟雾
tests/                 43 passed, 1 skipped
```
