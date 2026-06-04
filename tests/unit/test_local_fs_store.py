"""Integration test for gimbal.repository (AssetRef / AssetStore / LocalFsContentStore)."""
import sys
import os
import json
import shutil
import tempfile
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# 在 import 之前先做一次 logging 的最低配置（防 collect 时崩）
import logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

print("=" * 60)
print("ASSET REPOSITORY TEST")
print("=" * 60)


# ── 临时目录 ──
TMP = tempfile.mkdtemp(prefix="gimbal_repo_test_")
print(f"\nUsing temp dir: {TMP}")


def cleanup():
    if os.path.isdir(TMP):
        shutil.rmtree(TMP, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════
# 1. AssetRef 解析
# ════════════════════════════════════════════════════════════════════
print("\n[1] AssetRef.parse() — various forms")
from gimbal.repository import AssetRef
from gimbal.exceptions import InvalidAssetRef

cases = [
    ("library/hello",                       "library", "hello", "latest", None),
    ("hello",                                "library", "hello", "latest", None),
    ("library/hello:v1.0",                   "library", "hello", "v1.0",  None),
    ("hello:v1.0",                           "library", "hello", "v1.0",  None),
    ("my-ns/my-name:v1.0",                  "my-ns",   "my-name","v1.0",  None),
    ("ns/hello@sha256:" + "a" * 64,         "ns",      "hello", "latest", "sha256:" + "a" * 64),
]
for raw, ns, name, tag, digest in cases:
    r = AssetRef.parse(raw)
    assert r.namespace == ns,   f"{raw}: ns={r.namespace} expected={ns}"
    assert r.name == name,      f"{raw}: name={r.name} expected={name}"
    assert r.tag == tag,        f"{raw}: tag={r.tag} expected={tag}"
    assert r.digest == digest,  f"{raw}: digest={r.digest} expected={digest}"
    print(f"  {raw:60s} → {r}")

# 非法名
for bad in ("../escape", "UPPER", "", "ns/hello:bad@tag", "ns/hello@sha256:short"):
    try:
        AssetRef.parse(bad)
    except (InvalidAssetRef, ValueError):
        pass
    else:
        raise AssertionError(f"Expected invalid ref: {bad!r}")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 2. push / pull 简单流程
# ════════════════════════════════════════════════════════════════════
print("\n[2] AssetStore.push / pull — basic flow")
from gimbal.repository import AssetStore, LocalFsContentStore, compute_digest
from gimbal.exceptions import AssetAlreadyExists, AssetNotFound, AssetDigestMismatch

backend = LocalFsContentStore(root=os.path.join(TMP, "store1"))
store = AssetStore(backend=backend)

data = json.dumps({"name": "declare", "version": "1.0"}, ensure_ascii=False).encode("utf-8")
ref = AssetRef.parse("customs/declare:v1.0")

rec = store.push(ref, data, kind="suite", media_type="application/json")
assert rec.digest == compute_digest(data)
assert rec.size == len(data)
assert rec.kind == "suite"
print(f"  pushed: {ref}  digest={rec.digest}  size={rec.size}")

# 再 push 同 ref 不带 overwrite → 报错
try:
    store.push(ref, data, kind="suite")
except AssetAlreadyExists as e:
    print(f"  AssetAlreadyExists (expected): {e}")

# overwrite=True
rec2 = store.push(ref, data, kind="suite", overwrite=True)
assert rec2.digest == rec.digest, "same content should have same digest"
print(f"  re-pushed with overwrite: digest same={rec2.digest == rec.digest}")

# pull
content = store.pull(ref)
assert content.digest == rec.digest
assert content.raw == data
assert content.parsed == {"name": "declare", "version": "1.0"}
print(f"  pulled: parsed={content.parsed}")
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 3. 多 tag 指向同一 digest（内容复用）
# ════════════════════════════════════════════════════════════════════
print("\n[3] Multiple tags → same content (dedup)")
ref_v1 = AssetRef.parse("customs/declare:v1.0")    # 复用 [2] 推上去的
ref_v2 = AssetRef.parse("customs/declare:v2.0")
ref_latest = AssetRef.parse("customs/declare:latest")

store.tag(ref_v1, ref_v2)
store.tag(ref_v1, ref_latest)

# 列出 tag
tags = store.list_tags("customs", "declare")
assert [t.tag for t in tags] == ["latest", "v1.0", "v2.0"], f"got {tags}"
print(f"  tags: {[t.tag for t in tags]}")

# 三个 ref 都能 pull 到相同 content
for r in (ref_v1, ref_v2, ref_latest):
    c = store.pull(r)
    assert c.digest == rec.digest
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 4. 内容寻址：相同内容 → 相同 digest
# ════════════════════════════════════════════════════════════════════
print("\n[4] Content-addressable: same content → same digest")
backend2 = LocalFsContentStore(root=os.path.join(TMP, "store2"))
store2 = AssetStore(backend=backend2)
data2 = b"identical content"
r1 = store2.push(AssetRef.parse("ns/a:v1"), data2)
r2 = store2.push(AssetRef.parse("ns/b:v1"), data2)
assert r1.digest == r2.digest, f"digest differ: {r1.digest} vs {r2.digest}"
print(f"  r1={r1.digest}\n  r2={r2.digest}\n  same={r1.digest == r2.digest}")
# 物理层 blob 只有一份
stats = backend2.stats()
print(f"  blob count: {stats['n_blobs']} (should be 1)")
assert stats['n_blobs'] == 1, f"expected 1 blob, got {stats['n_blobs']}"
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 5. remove + GC
# ════════════════════════════════════════════════════════════════════
print("\n[5] remove + GC")
backend3 = LocalFsContentStore(root=os.path.join(TMP, "store3"))
store3 = AssetStore(backend=backend3)
store3.push(AssetRef.parse("ns/keep:v1"), b"keep")
store3.push(AssetRef.parse("ns/drop:v1"), b"drop-then-gc")

stats_before = backend3.stats()
print(f"  before: blobs={stats_before['n_blobs']} manifests={stats_before['n_manifests']}")
assert stats_before['n_blobs'] == 2

# remove drop
store3.remove(AssetRef.parse("ns/drop:v1"))

# 此时 drop 的 blob 是孤儿（tag 已删）
removed = backend3.gc()
print(f"  gc removed: {removed}")
assert removed == 1, f"expected 1 removed, got {removed}"

stats_after = backend3.stats()
print(f"  after: blobs={stats_after['n_blobs']} manifests={stats_after['n_manifests']}")
assert stats_after['n_blobs'] == 1
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 6. list_assets + find_by_digest
# ════════════════════════════════════════════════════════════════════
print("\n[6] list_assets / find_by_digest")
backend4 = LocalFsContentStore(root=os.path.join(TMP, "store4"))
store4 = AssetStore(backend=backend4)
store4.push(AssetRef.parse("ns1/a:v1"), b"aaa")
store4.push(AssetRef.parse("ns1/a:v2"), b"aaa")  # 同内容不同 tag
store4.push(AssetRef.parse("ns1/b:v1"), b"bbb")
store4.push(AssetRef.parse("ns2/c:v1"), b"ccc")

all_assets = store4.list_assets()
print(f"  total records: {len(all_assets)}")
assert len(all_assets) == 4

ns1_assets = store4.list_assets(namespace="ns1")
print(f"  ns1 records: {len(ns1_assets)}")
assert len(ns1_assets) == 3

# 找 digest
records_for_aaa = backend4.find_by_digest(compute_digest(b"aaa"))
print(f"  records pointing to 'aaa' digest: {len(records_for_aaa)}")
assert len(records_for_aaa) == 2
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 7. AssetResolver（CLI 桥接）
# ════════════════════════════════════════════════════════════════════
print("\n[7] AssetResolver — single + wildcard")
from gimbal.core.asset_resolver import AssetResolver, AssetKind

backend5 = LocalFsContentStore(root=os.path.join(TMP, "store5"))
store5 = AssetStore(backend=backend5)
store5.push(AssetRef.parse("customs/declare:v1.0"),   b'{"k":"declare"}', kind="suite")
store5.push(AssetRef.parse("customs/inspect:v1.0"),   b'{"k":"inspect"}', kind="suite")
store5.push(AssetRef.parse("customs/settle:latest"),  b'{"k":"settle"}',  kind="suite")
store5.push(AssetRef.parse("payment/checkout:v1.0"),  b'{"k":"checkout"}', kind="suite")

resolver = AssetResolver(kind=AssetKind.SUITE, asset_store=store5)

# 单 ref
single = resolver.resolve(["customs/declare:v1.0"])
assert len(single) == 1
assert single[0].ref.namespace == "customs"
assert single[0].content.parsed == {"k": "declare"}
print(f"  single: {single[0].ref}")

# 命名空间通配
all_customs = resolver.resolve(["customs/*:v1.0"])
print(f"  customs/*:v1.0 → {[str(a.ref) for a in all_customs]}")
assert len(all_customs) == 2
assert {a.ref.name for a in all_customs} == {"declare", "inspect"}

# 任意 tag
any_customs = resolver.resolve(["customs/*:latest"])
print(f"  customs/*:latest → {[str(a.ref) for a in any_customs]}")
assert len(any_customs) == 1
assert any_customs[0].ref.name == "settle"

# 完全通配
star = resolver.resolve(["*/*:v1.0"])
print(f"  */*:v1.0 → {[str(a.ref) for a in star]}")
assert len(star) == 3

# 不存在的 ref → 跳过（warn-and-skip）
nonexistent = resolver.resolve(["nonexistent/asset:v1"])
assert len(nonexistent) == 0
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 8. inspect
# ════════════════════════════════════════════════════════════════════
print("\n[8] inspect (no content download)")
backend6 = LocalFsContentStore(root=os.path.join(TMP, "store6"))
store6 = AssetStore(backend=backend6)
ref_x = AssetRef.parse("ns/x:v1")
store6.push(ref_x, b"hello world", media_type="text/plain", metadata={"author": "alice"})
rec = store6.inspect(ref_x)
print(f"  inspected: digest={rec.digest} size={rec.size} media_type={rec.media_type}")
print(f"  metadata: {rec.metadata}")
assert rec.digest == compute_digest(b"hello world")
assert rec.size == 11
assert rec.media_type == "text/plain"
assert rec.metadata == {"author": "alice"}
print("  PASS")


# ════════════════════════════════════════════════════════════════════
# 清理
# ════════════════════════════════════════════════════════════════════
cleanup()
print("\n" + "=" * 60)
print("ALL ASSET REPOSITORY TESTS PASSED")
print("=" * 60)
