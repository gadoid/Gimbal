#!/usr/bin/env bash
# P0-01:统一验证入口 —— 干净克隆上一条命令跑完全部测试,作为所有 Goal 的合并门。
#
# 用法:
#   bash scripts/verify_all.sh              # 全部四步(gimbal+plate / 平台后端 / 平台前端 / 自举)
#   bash scripts/verify_all.sh gimbal       # 只跑指定步(可多选:gimbal backend frontend bootstrap)
#
# 任一步失败 → 退出码非零;末尾输出各部分通过/失败计数汇总。
# 平台后端用真实依赖(gimbal 引擎可用时连真引擎;缺引擎的环境按既有
# skipif 守卫降级,不算失败)。前端需要 node/npm(vitest)。自举须从其
# 自身目录跑(根目录跑 gimbal_bootstrap 包不可导入,且 tests/ 目录名与
# 根 tests 撞);其实测对账门(test_contract_reconcile_live)依赖运行中
# 服务与干净数据,属深度验证,不入合并门(文件内已有 GIMBAL_SB_USERNAME
# 跳过守卫)。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

STEPS=("${@:-}")
if [ ${#STEPS[@]} -eq 0 ] || [ -z "${STEPS[0]}" ]; then
  STEPS=(gimbal backend frontend bootstrap)
fi

declare -a LABELS=()
declare -a RCS=()
declare -a SUMMARIES=()

run_step() {
  local label="$1"; shift
  echo ""
  echo "==================== [$label] ===================="
  local out rc
  out="$(mktemp)"
  "$@" >"$out" 2>&1 </dev/null
  rc=$?
  RCS+=("$rc")
  LABELS+=("$label")
  # 末 3 行(计数行通常在最后)
  tail -n 3 "$out"
  # 计数行取末个非空行 —— vitest --silent 末尾是空行,裸 tail -n 1 取到空
  SUMMARIES+=("$(grep -v '^[[:space:]]*$' "$out" | tail -n 1 | cut -c1-100)")
  rm -f "$out"
}

for step in "${STEPS[@]}"; do
  case "$step" in
    gimbal)
      run_step "gimbal+plate pytest" bash -c "cd '$ROOT' && python -m pytest tests/ -q"
      ;;
    backend)
      run_step "platform backend pytest" bash -c "cd '$ROOT/src/gimbal-platform/backend' && python -m pytest tests/ -q"
      ;;
    frontend)
      run_step "platform frontend vitest" bash -c "cd '$ROOT/src/gimbal-platform/frontend' && npx vitest run --silent"
      ;;
    bootstrap)
      run_step "bootstrap pytest" bash -c "cd '$ROOT/src/gimbal-bootstrap' && python -m pytest tests/ -q --ignore=tests/test_contract_reconcile_live.py"
      ;;
    *)
      echo "未知步骤: $step(合法: gimbal backend frontend bootstrap)" >&2
      exit 64
      ;;
  esac
done

echo ""
echo "==================== 汇总 ===================="
failed=0
for i in "${!LABELS[@]}"; do
  if [ "${RCS[$i]}" -eq 0 ]; then
    printf '  %-28s PASS  %s\n' "${LABELS[$i]}" "${SUMMARIES[$i]}"
  else
    printf '  %-28s FAIL(rc=%s)  %s\n' "${LABELS[$i]}" "${RCS[$i]}" "${SUMMARIES[$i]}"
    failed=$((failed + 1))
  fi
done

if [ "$failed" -gt 0 ]; then
  echo "结果: $failed 个步骤失败"
  exit 1
fi
echo "结果: 全部通过"
exit 0
