-- 钉死会话时区为 UTC（PG迁移方案 §2.1）：任何漏网的 naive datetime
-- 一律按 UTC 渲染，不再随宿主本地时区（+8h）漂移。
-- 注意：docker init 脚本只在卷首次初始化时执行；对既有卷需手工执行一次
-- 同名语句（见 docs: src/gimbal-platform/docs/runbook-pg.md）。
ALTER DATABASE gimbal SET timezone TO 'UTC';
