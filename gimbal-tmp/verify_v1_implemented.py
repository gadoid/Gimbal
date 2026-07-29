"""V1 文档声明 vs 实际代码对照表 (修正版)"""
from pydantic import BaseModel, ValidationError
from gimbal_plate.schema.endpoint.endpoint import EndpointSpec, ApiSpec
from gimbal_plate.schema.endpoint.io_spec import IOFieldBinding, RequestSpec, ResponseSpec
from gimbal_plate.schema.endpoint.metadata import EndpointMetadata


class DummyM(BaseModel):
    x: int = 1


def expect_reject(label, fn):
    try:
        out = fn()
        print(f"NO_REJECT | {label} | result={out!r}")
    except ValidationError as e:
        first = str(e).splitlines()[1] if len(str(e).splitlines()) > 1 else str(e)
        print(f"REJECT_OK  | {label} | err={first[:140]}")
    except Exception as e:
        print(f"ERROR      | {label} | {type(e).__name__}: {e}")


def expect_accept(label, fn):
    try:
        out = fn()
        print(f"ACCEPT_OK  | {label}")
    except ValidationError as e:
        first = str(e).splitlines()[1] if len(str(e).splitlines()) > 1 else str(e)
        print(f"REJECT_UNEXPECTED | {label} | err={first[:140]}")
    except Exception as e:
        print(f"ERROR      | {label} | {type(e).__name__}: {e}")


# 公共基线 dict — 通过 spread 更新字段
def make_ep(**overrides):
    base = dict(
        id="a.b",
        system="s",
        service="sv",
        name="n",
        api=ApiSpec(service="sv", method="GET", path="/x"),
        responses={200: ResponseSpec(status=200)},
    )
    base.update(overrides)
    return base


print("=== §2 EndpointSpec ===")
expect_reject("id='' (V1 §2.2)", lambda: EndpointSpec(**make_ep(id="")))
expect_reject("id='BadID' 大写 (V1 §2.2)", lambda: EndpointSpec(**make_ep(id="BadID")))
expect_reject("system='' (V1 §2.2)", lambda: EndpointSpec(**make_ep(system="")))
expect_reject("service='' (V1 §2.2)", lambda: EndpointSpec(**make_ep(service="")))
expect_reject(
    "service != api.service (V1 §2.2)",
    lambda: EndpointSpec(**make_ep(service="sv1", api=ApiSpec(service="sv2", method="GET", path="/x"))),
)
expect_reject("name='' (V1 §2.2)", lambda: EndpointSpec(**make_ep(name="")))
expect_reject(
    "api 缺失 (V1 §2.2)",
    lambda: EndpointSpec(**{k: v for k, v in make_ep().items() if k != "api"}),
)
expect_reject(
    "200 缺失 (V1 §2.2)",
    lambda: EndpointSpec(**make_ep(responses={400: ResponseSpec(status=400)})),
)
expect_reject(
    "extra='unknown' (V1 §2.3)",
    lambda: EndpointSpec(**make_ep(unknown_field="nope")),
)
ep = EndpointSpec(**make_ep())
print(f"ACCEPT_OK  | updated_at 自动填充 (V1 §2.3) | {ep.updated_at is not None}")

print()
print("=== §3 ApiSpec ===")
expect_reject("service='' (V1 §3)", lambda: ApiSpec(service="", method="GET", path="/x"))
expect_reject("path 不以 / 开头 (V1 §3)", lambda: ApiSpec(service="s", method="GET", path="x"))
expect_reject("timeout=0 (V1 §3)", lambda: ApiSpec(service="s", method="GET", path="/x", timeout_seconds=0))
expect_reject("timeout=601 (V1 §3)", lambda: ApiSpec(service="s", method="GET", path="/x", timeout_seconds=601))
expect_reject("method='INVALID' (V1 §3)", lambda: ApiSpec(service="s", method="INVALID", path="/x"))

print()
print("=== §4.1 RequestSpec ===")
expect_accept("body_type='none' 全空 (合法基线)", lambda: RequestSpec(body_type="none"))
expect_reject(
    "body_type='none' 但 model 非空 (V1 §4.1)",
    lambda: RequestSpec(body_type="none", model=DummyM),
)
expect_reject(
    "body_type='none' 但 schema 非空 (V1 §4.1, alias)",
    lambda: RequestSpec(body_type="none", **{"schema": {"a": 1}}),
)
expect_reject(
    "body_type='json' 但 model/schema 都空 (V1 §4.1 第二条)",
    lambda: RequestSpec(body_type="json"),
)

print()
print("=== §4.2 ResponseSpec ===")
expect_reject("status=99 (V1 §4.2)", lambda: ResponseSpec(status=99))
expect_reject("status=600 (V1 §4.2)", lambda: ResponseSpec(status=600))
expect_reject(
    "assertable_fields 路径不在 fields (V1 §4.2)",
    lambda: ResponseSpec(
        status=200,
        fields=[IOFieldBinding(name="a", path="a")],
        assertable_fields=["does.not.exist"],
    ),
)

print()
print("=== §4.3 IOFieldBinding ===")
expect_reject("name='' path='' (V1 §4.3)", lambda: IOFieldBinding(name="", path=""))
expect_reject(
    "enum=['a','b'] default='z' (V1 §4.3)",
    lambda: IOFieldBinding(name="s", path="s", enum=["a", "b"], default="z"),
)
f = IOFieldBinding(name="x", path="x")
print(f"ACCEPT_OK  | source_kind 默认值 (V1 §4.3) | {f.source_kind}")
expect_reject(
    "source_kind='bogus' (V1 §4.3)",
    lambda: IOFieldBinding(name="x", path="x", source_kind="bogus"),
)

print()
print("=== §5 EndpointMetadata ===")
for p in [1, 2, 3, None]:
    expect_accept(f"priority={p} (V1 §5 合法)", lambda p=p: EndpointMetadata(priority=p))
for p in [0, 4, 5]:
    expect_reject(f"priority={p} (V1 §5 非法)", lambda p=p: EndpointMetadata(priority=p))
m = EndpointMetadata(tags=["a", "b", "a"])
print(f"ACCEPT_OK  | tags 去重 (V1 §5) | {m.tags}")
m = EndpointMetadata()
print(f"ACCEPT_OK  | failed_criteria 默认 (V1 §5) | {m.failed_criteria}")
expect_accept(
    "failed_criteria 多项 (V1 §5)",
    lambda: EndpointMetadata(failed_criteria=["code=400", "code=403"]),
)

print()
print("=== §6 描述层 ===")
try:
    from gimbal_plate.case.exporter import EndpointCaseExporter
    print("ACCEPT_OK  | EndpointCaseExporter 可导入")
except Exception as e:
    print(f"ERROR      | {type(e).__name__}: {e}")