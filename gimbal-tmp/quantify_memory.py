"""量化 fin 系统的 EndpointSpec 在内存中的真实占用。"""
import sys
import tracemalloc
from gimbal_plate.systems.fin.endpoint import ALL_ENDPOINTS

tracemalloc.start()


def deep_size(obj, _seen=None):
    """递归计算 Python 对象的内存占用(包含嵌套)。"""
    if _seen is None:
        _seen = set()
    oid = id(obj)
    if oid in _seen:
        return 0
    _seen.add(oid)
    size = sys.getsizeof(obj)
    if hasattr(obj, "__dict__"):
        size += deep_size(obj.__dict__, _seen)
    if isinstance(obj, dict):
        size += sum(deep_size(k, _seen) + deep_size(v, _seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set)):
        size += sum(deep_size(i, _seen) for i in obj)
    elif isinstance(obj, str):
        size += obj.__sizeof__()
    return size


endpoint_sizes = []
print("=== fin 系统 18 个 EndpointSpec 量化 ===")
print(f"{'id':<45} {'字段数':>6} {'sizeof(KB)':>10}")
print("-" * 70)

total_fields = 0
for ep in ALL_ENDPOINTS:
    field_count = 0
    if ep.request is not None:
        field_count += len(ep.request.fields)
    for status in ep.responses.values():
        field_count += len(status.fields)
    total_fields += field_count

    size_kb = deep_size(ep) / 1024
    endpoint_sizes.append(size_kb)
    print(f"{ep.id:<45} {field_count:>6} {size_kb:>10.1f}")

print("-" * 70)
total_kb = sum(endpoint_sizes)
print(f"总字段数:    {total_fields}")
print(f"endpoint 数:  {len(ALL_ENDPOINTS)}")
print(f"总内存占用:  {total_kb:.1f} KB ({total_kb/1024:.2f} MB)")
print(f"平均每个:    {total_kb/len(ALL_ENDPOINTS):.1f} KB")
print()

print("=== 不同规模下的内存推算 ===")
sizes = [10, 100, 555, 1000]
factors = [10, 100, 555, 1000]
for f in factors:
    proj_kb = total_kb * f
    proj_mb = proj_kb / 1024
    print(f"{f}x ({f*18} endpoint):  {proj_mb:.1f} MB")

print()
print("=== tracemalloc 实际测量 ===")
current, peak = tracemalloc.get_traced_memory()
print(f"当前分配:    {current/1024:.1f} KB")
print(f"峰值分配:    {peak/1024:.1f} KB")
tracemalloc.stop()