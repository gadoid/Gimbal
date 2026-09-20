"""服务画像响应模型(服务画像方案 §5.3)— P1:热力网格 + 接口级线索板。

显式 Field(alias=...) 对齐前端 camelCase,风格同 schemas/adaptations.py。
槽①(req)P1 恒 None:plate `reference` dim 是 P2,方案 §2.4 挂起清单。
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_CAMEL = ConfigDict(populate_by_name=True)

Quadrant = Literal["requirement", "data", "test", "topology"]


class GridSignals(BaseModel):
    """四格状态条(§2.3)。位置固定:①需求 ②用例 ③最近执行 ④适配告警。"""

    model_config = _CAMEL

    # 槽①需求关联:P1 无数据源(reference dim 是 P2),恒 None 占位
    req: str | None = None
    cases: bool = False
    # 'pass' | 'fail' | None(从未执行 / 仅有 canceled / 进行中且无完成态)
    last_run: str | None = Field(default=None, alias="lastRun")
    alarm: bool = False


class GridEndpoint(BaseModel):
    model_config = _CAMEL

    id: str
    method: str = ""
    path: str = ""
    name: str = ""
    signals: GridSignals = Field(default_factory=GridSignals)
    case_count: int = Field(default=0, alias="caseCount")
    last_run_at: str | None = Field(default=None, alias="lastRunAt")


class GridStats(BaseModel):
    """顶部统计条(§2.1)。`noRequirement` 随 P2 reference dim 再加。"""

    model_config = _CAMEL

    total: int = 0
    no_cases: int = Field(default=0, alias="noCases")
    has_alarm: int = Field(default=0, alias="hasAlarm")
    never_run: int = Field(default=0, alias="neverRun")


class ServiceGrid(BaseModel):
    model_config = _CAMEL

    service: str
    endpoints: list[GridEndpoint] = Field(default_factory=list)
    stats: GridStats = Field(default_factory=GridStats)
    # False = plate 轻量列表不可达,endpoints 为空,页面降级横幅(§2.4)
    plate_reachable: bool = Field(alias="plateReachable")


# ─── 接口级线索板(方案 §3;P1:测试象限完整,其余象限占位)────────
class BoardSubject(BaseModel):
    model_config = _CAMEL

    id: str
    method: str = ""
    path: str = ""
    name: str = ""
    version: str = ""
    field_count: int = Field(default=0, alias="fieldCount")
    # True = /full 与轻量列表均不可得,主体只有裸 id(方案 §5.3 两档降级之后)
    degraded: bool = False


class BoardNode(BaseModel):
    model_config = _CAMEL

    id: str
    kind: Literal[
        "endpoint", "table", "topology", "reference",
        "scenario", "execution", "adaptation", "card",
    ]
    quadrant: Quadrant | None = None
    label: str
    meta: dict[str, Any] = Field(default_factory=dict)


class BoardEdge(BaseModel):
    model_config = _CAMEL

    from_: str = Field(alias="from")
    to: str
    kind: Literal["contains", "refs", "affects", "ran", "annotates"]


class BoardTrail(BaseModel):
    model_config = _CAMEL

    kind: Literal["risk"]
    path: list[str]


class BoardResponse(BaseModel):
    model_config = _CAMEL

    subject: BoardSubject
    nodes: list[BoardNode] = Field(default_factory=list)
    edges: list[BoardEdge] = Field(default_factory=list)
    trails: list[BoardTrail] = Field(default_factory=list)
    # 象限就绪态:P1 = test ok + 其余 unavailable;P2/P3 逐个点亮
    quadrants: dict[str, str] = Field(default_factory=dict)


# ─── 自建卡(方案 §3.3)──────────────────────────────────────────
class CardCreate(BaseModel):
    model_config = _CAMEL

    subject_id: str = Field(min_length=1, alias="subjectId")
    body: str = Field(min_length=1)
    quadrant: Quadrant
    annotates_node_id: str | None = Field(
        default=None, alias="annotatesNodeId"
    )


class CardPatch(BaseModel):
    model_config = _CAMEL

    body: str | None = None
    quadrant: Quadrant | None = None
    # 哨兵语义在 service 层:显式传 null = 清空注解,缺省 = 不动
    annotates_node_id: str | None = Field(default=None, alias="annotatesNodeId")


class CardOut(BaseModel):
    model_config = _CAMEL

    id: int
    subject_kind: str = Field(alias="subjectKind")
    subject_id: str = Field(alias="subjectId")
    body: str
    is_root: bool = Field(default=False, alias="isRoot")
    quadrant: Quadrant
    annotates_node_id: str | None = Field(default=None, alias="annotatesNodeId")
    author_id: int = Field(alias="authorId")
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
