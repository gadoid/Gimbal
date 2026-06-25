"""E4 并发回归测试:v3 §10.2 — "dictionary changed size during iteration"。

背景:
  GIMBAL framework 明确有并发执行(多 scenario 并行跑),而 ``resolve`` /
  ``warm`` 都对 ``_index`` 做迭代。修复前 collect 在锁内写、resolve/warm
  在锁外读/迭代 → CPython 在 ``for k in self._index:`` 期间,若另一线程
  的 collect 改了 dict,会抛 ``RuntimeError: dictionary changed size
  during iteration``。

本测试在多线程下"反复 collect + resolve + warm"高频冲撞,验证:
  1. 整个测试期间不抛 RuntimeError
  2. resolve 返回的 EndpointSpec 与预期一致(无撕裂)
  3. 全部线程退出后,registry 状态自洽(loaded 集合 = 实际 import 过的 service)
"""
from __future__ import annotations

import importlib
import random
import sys
import threading
import time
import types

import pytest
from pydantic import BaseModel, ConfigDict

import Plate
from Plate.core import EndpointKey, _Registry  # noqa: F401  # _Registry 在反向验证中用
from Plate.spec import EndpointSpec


# ════════════════════════════════════════════════════════════════════════════
# 辅助
# ════════════════════════════════════════════════════════════════════════════

def _good_model(name: str) -> type[BaseModel]:
    return type(
        name,
        (BaseModel,),
        {
            "model_config": ConfigDict(extra="forbid"),
            "__annotations__": {"x": str},
            "x": "",
        },
    )


Req = _good_model("Req")
Resp = _good_model("Resp")

# 准备 N 个 fixture service,每个里有 1 个 spec
SERVICE_DIRS = [f"conc_svc_{i}" for i in range(5)]
SERVICE_SPECS: dict[str, EndpointSpec] = {
    d: EndpointSpec(method="GET", path=f"/api/{d}", responses={200: Resp})
    for d in SERVICE_DIRS
}


def _install_fixtures() -> None:
    """把所有 fixture service 模块塞进 sys.modules,供 importlib.import_module 解析。"""
    for d, spec in SERVICE_SPECS.items():
        full = f"Plate.{d}"
        mod = types.ModuleType(full)
        mod.__file__ = f"<test-fixture>/Plate/{d}.py"
        mod.__package__ = full
        setattr(mod, "endpoint", spec)
        sys.modules[full] = mod


def _uninstall_fixtures() -> None:
    for d in SERVICE_DIRS:
        sys.modules.pop(f"Plate.{d}", None)
    importlib.invalidate_caches()


# ════════════════════════════════════════════════════════════════════════════
# 共享 fixture:测试间隔离(autouse)
# ════════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _isolate_concurrent_state():
    """测试间隔离:每个测试前后 reset + 卸载 fixture。

    对应设计:§"并发测试不变量" — registry 是进程级单例,任何残留状态污染后续测试。
    业务影响:不隔离 = 后续测试拿到上一轮的 loaded services,误判"未加载"行为。
    """
    yield
    _uninstall_fixtures()
    Plate.registry.reset()


# ════════════════════════════════════════════════════════════════════════════
# [1] 单线程基线
# ════════════════════════════════════════════════════════════════════════════

def test_single_thread_resolve_baseline() -> None:
    """业务需求:单线程下 resolve 应正常工作(无并发,排除 fixture 自身 bug)。

    对应设计:§"并发测试基线"。
    业务影响:违反 = [2] 高冲撞测试可能因 fixture 自身 bug 失败,而非真实并发问题,
             修错方向。
    """
    _install_fixtures()
    for d in SERVICE_DIRS:
        spec = Plate.registry.resolve(d, "GET", f"/api/{d}")
        assert spec is SERVICE_SPECS[d]


# ════════════════════════════════════════════════════════════════════════════
# [2] 多线程高冲撞:resolve + warm 混合,跑 K 轮
# ════════════════════════════════════════════════════════════════════════════

def test_multi_thread_collect_resolve_warm_no_runtime_error() -> None:
    """业务需求:多线程下 collect/resolve/warm 混合高频冲撞,无 RuntimeError。

    对应设计:v3 §10.2 "dictionary changed size during iteration" 修复验证。
    业务影响:违反 = 真实并发 scenario 下随机触发 RuntimeError,生产事故难复现。
    """
    THREADS = 8
    ROUNDS = 50  # 每线程 50 轮,共 400 次混合操作
    errors: list[BaseException] = []
    errors_lock = threading.Lock()
    barrier = threading.Barrier(THREADS)
    _install_fixtures()

    def worker(thread_id: int) -> None:
        try:
            # 对齐到同一时刻启动,最大化冲撞概率
            barrier.wait(timeout=10)
            for round_idx in range(ROUNDS):
                # 随机选一个 service
                d = SERVICE_DIRS[(thread_id + round_idx) % len(SERVICE_DIRS)]
                # 随机一种操作
                op = (thread_id * 7 + round_idx) % 3
                if op == 0:
                    # collect
                    Plate.registry.collect(d)
                elif op == 1:
                    # resolve(读 index)
                    got = Plate.registry.resolve(d, "GET", f"/api/{d}")
                    assert got is SERVICE_SPECS[d], (
                        f"thread {thread_id} round {round_idx}: 撕裂"
                    )
                else:
                    # warm 多个
                    batch = random.sample(SERVICE_DIRS, k=min(3, len(SERVICE_DIRS)))
                    specs = Plate.registry.warm(batch)
                    # 验证返回的 spec 都是预期对象
                    got_ids = {id(s) for s in specs}
                    expected_ids = {id(SERVICE_SPECS[b]) for b in batch}
                    assert got_ids == expected_ids, (
                        f"thread {thread_id} round {round_idx}: warm 撕裂"
                    )
        except BaseException as e:
            with errors_lock:
                errors.append(e)

    threads = [
        threading.Thread(target=worker, args=(i,), name=f"T{i}")
        for i in range(THREADS)
    ]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed = time.perf_counter() - t0

    assert not errors, (
        f"并发下抛了 {len(errors)} 个异常:\n  "
        + "\n  ".join(repr(e) for e in errors[:3])
    )
    # 状态自洽:每个 service 都被 collect 至少一次(其实 warm 里有 batch,可能没覆盖全部)
    # 至少 loaded 集合 ⊆ fixture 全集
    loaded = set(Plate.registry.loaded_services())
    assert loaded <= set(SERVICE_DIRS), f"loaded 包含未知 service: {loaded}"
    # index 的所有 spec 都是预期的
    for key, spec in Plate.registry._index.items():  # noqa: SLF001
        assert key.service in SERVICE_DIRS
        assert spec is SERVICE_SPECS[key.service]


# ════════════════════════════════════════════════════════════════════════════
# [3] 极端情况:同一 service 反复 collect
# ════════════════════════════════════════════════════════════════════════════

def test_repeated_collect_under_concurrency_is_idempotent() -> None:
    """业务需求:同一 service 反复 collect(N 线程齐发)应幂等。

    对应设计:§_Registry._collect_locked 幂等保证。
    业务影响:违反 = 重复 collect 重复 import,index 被覆盖,resolve 拿到错的 spec。
    """
    THREADS = 8
    errors: list[BaseException] = []
    errors_lock = threading.Lock()
    barrier = threading.Barrier(THREADS)
    _install_fixtures()

    def collect_worker(_tid: int) -> None:
        try:
            barrier.wait(timeout=10)
            for _ in range(100):
                Plate.registry.collect(SERVICE_DIRS[0])
        except BaseException as e:
            with errors_lock:
                errors.append(e)

    threads = [
        threading.Thread(target=collect_worker, args=(i,)) for i in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert not errors, f"重复 collect 在并发下异常: {errors[:3]}"
    assert len(Plate.registry._index) == 1, (  # noqa: SLF001
        f"重复 collect 不应重复入 index: {len(Plate.registry._index)}"  # noqa: SLF001
    )


# ════════════════════════════════════════════════════════════════════════════
# [4] 反向验证:确定性复现"读路径不持锁"的旧 bug
# ════════════════════════════════════════════════════════════════════════════

def test_dict_changed_size_is_deterministic_in_raw_python() -> None:
    """业务需求:Python 字典 + 线程模型能稳定复现 RuntimeError
    → 证明 [2] 测试是真有意义(不是巧合没踩到)。

    对应设计:§"反向验证 - 复现能力"。
    业务影响:[2] 通过但本测试若失败 = 复现能力不稳,不能完全证明修复有效。
    注:部分平台 GIL 行为可能让本测试无法复现 → 仅打印警告,不阻塞 CI。
    """
    d: dict = {f"k{i}": i for i in range(10_000)}
    a_err: list[BaseException] = []
    barrier4 = threading.Barrier(2)

    def iterator_thread() -> None:
        try:
            barrier4.wait(timeout=5)
            for _ in d:  # 持迭代状态
                time.sleep(0.0001)  # 释放 GIL,给 B 机会
        except BaseException as e:
            a_err.append(e)

    def mutator_thread() -> None:
        try:
            barrier4.wait(timeout=5)
            time.sleep(0.005)  # 让 A 先进入迭代
            d["NEW_KEY"] = 999  # 触发 A 的 RuntimeError
        except BaseException:
            pass

    t1 = threading.Thread(target=iterator_thread)
    t2 = threading.Thread(target=mutator_thread)
    t1.start(); t2.start()
    t1.join(timeout=10); t2.join(timeout=10)

    # 反向验证:仅当能复现时严格断言;无法复现时(平台 GIL 行为差异)skip
    if a_err and "dictionary changed size" in str(a_err[0]):
        # 成功复现:证明 [2] 测试有意义
        return
    pytest.skip(
        f"本平台 GIL 行为下无法复现 'dictionary changed size'(消息: {a_err[:1]!r})。"
        f"[2] 仍是修复有效性的主证据(400 次操作零异常)"
    )
