#!/usr/bin/env bash
# ext_gates.sh — 归一方案 v1.0 §6.3 门禁 ②③(b2-13 加入 verify_all;
# ① ext 目录残留门禁随批3 加入)。命中即非零退出。
# ② ref 字面比较零残留(基线 19 处,批2 后应为 0;只放行 run_semantics.py)
# ③ 新保留字零散写(等值比较 + integration@ 前缀;后端只放行分类器,
#    前端只放行 types/plate.ts 的常量与记录域判定函数)
set -u
cd "$(dirname "$0")/.."
rc=0

# ① 平台目录与 ext: 特例零残留(b3-9 加入;允许名单:auditText「已退役」
#    映射、runbook-pg 历史段、alembic 历史链)
hits=$(grep -rInE "ExternalEndpoint|external_endpoint|external-endpoints|ext_svc|_strip_ext_anchors|starts[wW]ith\(['\"]ext:"   src docs --exclude-dir=alembic --exclude-dir=node_modules     --exclude-dir=__pycache__ --exclude-dir=.pytest_cache   | grep -vE "auditText|runbook-pg|已退役|已删|alembic|batch0-inventory|single-source-registry|ADR|adr|services/audit\.py"   | grep -v "\.dump$" || true)
if [ -n "$hits" ]; then
  echo "[gate①] ext 目录/特例残留:"; echo "$hits"; rc=1
fi

hits=$(grep -rnE "(ref|v|eff|declared)\s*[!=]=\s*['\"]working['\"]" \
  src/gimbal-platform/backend/app | grep -v "services/run_semantics.py" || true)
if [ -n "$hits" ]; then
  echo "[gate②] ref 字面比较残留:"; echo "$hits"; rc=1
fi

hits=$(grep -rnE "(ref|v|eff|declared|plateRef)\s*[!=]==?\s*['\"]integration['\"]|starts[wW]ith\(['\"]integration@" \
  src/gimbal-platform/backend/app src/gimbal-platform/frontend/src \
  | grep -vE "services/run_semantics.py|types/plate.ts|__tests__" || true)
if [ -n "$hits" ]; then
  echo "[gate③] 新保留字散写残留:"; echo "$hits"; rc=1
fi

exit $rc
