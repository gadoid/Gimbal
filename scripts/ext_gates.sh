#!/usr/bin/env bash
# ext_gates.sh — 归一方案 v1.0 §6.3 门禁 ②③(b2-13 加入 verify_all;
# ① ext 目录残留门禁随批3 加入)。命中即非零退出。
# ② ref 字面比较零残留(基线 19 处,批2 后应为 0;只放行 run_semantics.py)
# ③ 新保留字零散写(等值比较 + integration@ 前缀;后端只放行分类器,
#    前端只放行 types/plate.ts 的常量与记录域判定函数)
set -u
cd "$(dirname "$0")/.."
rc=0

# ① 平台目录与 ext: 特例零残留(b3-9 加入)。豁免按**文件路径**锚定
#    (b2.6/评审 F8:原按整行内容豁免,adr 会误配 address、已删/已退役
#    会放过任意带注释行)—— 均为记录退役面的历史文档/审计映射:
#    auditText 审计文案、audit.py 历史动作词表、runbook-pg 迁移史、
#    docs/adr 退役日志、概念地图已退役条目;dist 是构建产物不扫。
hits=$(grep -rInE "ExternalEndpoint|external_endpoint|external-endpoints|ext_svc|_strip_ext_anchors|_external_schema_warnings|starts[wW]ith\(['\"]ext:" \
  src docs --exclude-dir=alembic --exclude-dir=node_modules \
  --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude-dir=dist \
  --exclude-dir="*.egg-info" \
  | grep -vE "^src/gimbal-platform/frontend/src/components/admin/(__tests__/)?auditText(\.test)?\.ts:|^src/gimbal-platform/backend/app/services/audit\.py:|^src/gimbal-platform/docs/runbook-pg\.md:|^docs/adr/|^docs/概念地图\.md:" \
  | grep -v "\.dump$" || true)
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
