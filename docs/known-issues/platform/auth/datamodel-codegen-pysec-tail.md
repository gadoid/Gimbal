# datamodel-code-generator 0.28.5 的 PYSEC 尾巴（M2 生成器钉死,升级待排期）

> **模块**：dev 工具链（根 `pyproject.toml` dev 组 `datamodel-code-generator==0.28.5`
> × `scripts/gen_m2.py` × plate-ci pip-audit 门）
> **状态**：未修复（P2 待排期 —— 升级是独立轮,见「重开条件」）
> **来源**：2026-11-24 auth 加固批 pip-audit OSV 面首跑(21 条 advisory/3 包,
> 同批已处置:certifi PYSEC-2026-4320、opentelemetry-api CVE-2026-126360
> 两个运行时补丁位随 lock 重生提钉 —— 本条只登记剩量)

---

## 0. 事实

- `datamodel-code-generator==0.28.5` 被根 pyproject dev 组**精确钉死**;
  消费方是 `scripts/gen_m2.py`(「附录 A 定稿」参数面,生成 m2 的
  py/ts/dbgcmd 三侧构件)。
- pip-audit(OSV)报 9 条 PYSEC:2026-3555 / 3557 / 3558 / 3560 / 3561 /
  3563 / 3564 / 3565 / 3566,修复版本 0.60.2 ~ 0.64.0(**跨大版本**)。

## 1. 为什么是 P2 而不是 P1

- **dev-only 工具**:生成 M2 模型代码的开发期工具,不进生产部署
  (部署装的是 lock 里的运行时面 + editable 本仓包;生成物已入库);
- advisory 面是**代码生成工具自身**(输入是仓内自有 M2 schema,不是
  不可信输入);生产运行时零暴露;
- 但 0.28 → 0.64 会**改生成物形状**(参数语义大版本间有迁移),同提交
  要重生全部生成物并过 M2 漂移守卫 + M2 兼容性守卫,是独立工程轮,
  不适合搭车小改。

## 2. CI 门在位口径

plate-ci 的 pip-audit 门对这 9 个 ID 显式 `--ignore-vuln`(注释指回本条)；
其余 advisory 命中即红。**新 PYSEC 落到 datamodel-code-generator 不会被
门拦** —— 依赖本条的重开信号(下)人工巡检,或待升级轮整体消掉。

## 3. 重开条件(触发即回本条开升级工单)

1. M2 下一轮演进(生成物本来要动)——顺带升级 0.28 → 最新 + 重生全量
   生成物 + 双守卫绿,9 条 PYSEC 与 ignore 白名单整体消掉;
2. 上游 advisory 升级为「生成不可信输入」类(工具链暴露面扩大);
3. 生产部署形态变化导致 dev 工具进部署面(目前无此形态)。
