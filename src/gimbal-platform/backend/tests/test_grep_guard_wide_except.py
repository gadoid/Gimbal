"""grep 守卫(C6 余域清扫):宽捕获降级必须可见。

不变式(CONTRIBUTING 铁律 5 + wiring-quality-audit §4.1):``except
Exception`` 旁路必须三行内可见降级 —— 补 ``logger.warning`` 或显式
``raise``(原因进响应/收口结果的按判例入白名单)。与 owner_compare /
role_literals 守卫同构的双断言:白名单之外新增即红;白名单条目失效
(修复后忘删 / 计数下降)也红。条目锚定「路径:except 行内容:次数」,
不含行号,无关编辑不挪条目。

文件级豁免(单点判例,仿 owner_compare 的 _ownership/zone 豁免):

* ``run_dispatcher.py`` / ``graph_dispatch.py`` / ``gimbal_server_session.py``
  —— dispatcher 域已扫(2026-11-23,58 处分类:真静默 8 处补 warning、
  刻意静默 9 处保留判例在档),余量按登记册 C6 渐进口径不重复冻结;
* ``plate_client.py`` —— 兜底出口带 reason 载荷回传消费者告警,可见性
  由上游承载(登记册 C6 留观察);
* ``jsonpath.py`` —— 镜像拷贝(backend/gimbal/plate 三处同步约束),
  ``_compare_op`` 比较语义刻意(类型不匹配判 False),不动镜像。

白名单存量分类(2026-11-24 批 B 扫清后冻结):

* 「可见性由载荷/返回值承载」判例:上游错误文本进 HTTPException 载荷
  (catalog 三处)、测速结果四元组(deployments)、收口错误串(integration_
  runner 两处)、投递结果元组(webhook_outbox)、探活结果元组(auth_probe);
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

_APP = Path(__file__).resolve().parents[1] / "app"

# 文件级豁免(判例见模块注释)
_EXEMPT_FILES = {
    "run_dispatcher.py",
    "graph_dispatch.py",
    "gimbal_server_session.py",
    "plate_client.py",
    "jsonpath.py",
}

_EXCEPT_RX = re.compile(r"except (Exception|BaseException)(\s+as \w+)?:")
_LOGGER_RX = re.compile(r"\blogger\.")
_RAISE_RX = re.compile(r"^\s*raise\b", re.MULTILINE)
_WINDOW = 3

# 存量冻结(2026-11-24 批 B 扫清后;分类见模块注释)
_ALLOWLIST: dict[str, int] = {
    # ── 「可见性由载荷/返回值承载」判例(批 B 注释在档)─────────────
    'routers/endpoint_catalog.py:except Exception:': 1,
    'routers/strategy_catalog.py:except Exception:  # noqa: BLE001': 1,
    'routers/generator_catalog.py:except Exception:  # noqa: BLE001': 1,
    'routers/deployments.py:except Exception as e:  # noqa: BLE001 — 测速失败是结果不是 500': 1,
    # 投递结果元组承载(HTTP 状态/异常 repr 进 delivery 记录)
    'services/webhook_outbox.py:except Exception as e:  # noqa: BLE001 — 网络/超时一律走退避': 1,
    # 探活结果元组承载(认证结果原因串进返回值)
    'services/auth_probe.py:except Exception as e:': 1,
    # ── 「原因进收口结果」判例(integration_runner:错误串随 _finish
    #    落库,执行详情/卡片可见;基础兜底 = rollback 后新会话收口)──
    'services/integration_runner.py:except Exception as e:  # noqa: BLE001': 1,
    'services/integration_runner.py:except Exception as e:  # noqa: BLE001 — plate/通道任何故障 = 失败收口': 1,
    'services/integration_runner.py:except Exception as e:  # noqa: BLE001 — 基础设施兜底': 1,
    # 会话层故障:收口本槽(三行外)后 re-raise,显式失败
    'services/integration_runner.py:except Exception:': 1,
    # ── 显式 raise 判例(suite_version:B-1 成员修订 resolve 拒绝 →
    #    SuiteVersionError,注释块在 raise 前;预检不连坐)────────────
    'services/suite_version.py:except Exception as exc:': 1,
    'routers/suites.py:except Exception as e:  # noqa: BLE001 — 预检不因链路故障 500': 1,
    # ── 提示/预览面降级(adaptation_service:plate 不可达 → resolved/
    #    lines 置空,原因面(仍为预览/stale)随响应承载)──────────────
    'services/adaptation_service.py:except Exception:  # noqa: BLE001 — plate 不可达:提示降级': 1,
    'services/adaptation_service.py:except Exception:  # noqa: BLE001': 1,
}


def _scan() -> Counter:
    hits: Counter = Counter()
    for sub in ("routers", "services"):
        for py in sorted((_APP / sub).rglob("*.py")):
            if py.name in _EXEMPT_FILES:
                continue
            lines = py.read_text(encoding="utf-8").splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("#"):
                    continue  # 注释行里的「except Exception」字样不是代码
                if not _EXCEPT_RX.search(line):
                    continue
                window = "\n".join(lines[i + 1:i + 1 + _WINDOW])
                if _LOGGER_RX.search(window) or _RAISE_RX.search(window):
                    continue
                hits[f"{py.relative_to(_APP).as_posix()}:{line.strip()}"] += 1
    return hits


def test_no_new_silent_wide_excepts():
    """增量禁止:白名单之外的宽捕获(三行内无 logger 且不 raise)即失败。"""
    current = _scan()
    unknown = {k: v for k, v in current.items() if v != _ALLOWLIST.get(k)}
    assert not unknown, (
        "宽捕获旁路降级不可见(三行内无 logger 且不 raise)——按「降级必须"
        "可见」补 logger.warning / 显式 raise,或按判例归类白名单:\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(unknown.items())))


def test_allowlist_has_no_stale_entries():
    """白名单不腐化:清扫后忘删(或计数下降)的条目同样失败。"""
    current = _scan()
    stale = {k: v for k, v in _ALLOWLIST.items() if current.get(k, 0) != v}
    assert not stale, (
        "白名单条目已不存在或计数下降(清扫后请同步删除):\n  "
        + "\n  ".join(f"{k}: {v}" for k, v in sorted(stale.items())))
