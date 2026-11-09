"""authz M2a S6:别名瘦身 + serviceBindings 收窄(存量清洗)。

固定顺序(全部在本迁移事务内):

① ``service_aliases.slot = coalesce(slot, credential_alias)``(S3 起两列
   同步;防御漏同步行)。
② 无默认环境、但存在「没挂环境的别名地址」→ 建一个默认环境(D2 兜底
   不断:否则这些地址删列后无处可落,没人显式选环境的执行会丢地址)。
③ 别名地址回落部署表(按 (基础服务, 环境) 聚合,一致才落):
   * 没挂环境的别名 → 默认环境;**别名地址胜**(DO UPDATE)——「没人
     显式选环境」路径此前是别名地址优先,保持逐字节不变;
   * 挂环境的别名 → 其环境;部署表已有行**不覆盖**(DO NOTHING)——
     显式选环境路径此前就是部署表优先;
   * 同键地址不一致 → 不落(进报告)。
④ 方案 payload 清洗:``serviceBindings`` 各条目剥 ``url`` / ``authAlias``
   (S6 线上形态 = 服务键 → {alias}),空条目删除;逐方案记录丢弃内容。
   被剥的绑定 url 按基础服务聚合**补缺**落默认环境部署表(该键尚无部署
   行、各方案地址一致才落)—— 如平台保活探针方案钉的本机地址,不补会
   让依赖它的执行直接丢地址;冲突 / 已有行不落(进报告)。
⑤ 报告与通知:``audit_logs`` 一行(action ``migration.alias_slimming``,
   detail = 冲突组 / 地址被部署表取代的别名 / 别名环境选择器 / 个人别名
   共享化 / 方案清洗清单);方案属主各一条通知(列出受影响方案与丢弃
   字段);Admin+ 一条汇总通知(指向部署地址页)。
⑥ 删四列:``base_url`` / ``environment_id``(FK)/ ``owner_user_id``
   (FK + 索引)/ ``credential_alias``。

fresh 链守卫:baseline 按当前模型建表(四列已不存在)→ 各步内省后空转。
downgrade:回加四列(可空);``credential_alias = slot``;``base_url`` 从
默认环境部署表按基础服务回填;方案清洗与个人别名属主不可逆(报告留档)。
"""
import json

from alembic import op
import sqlalchemy as sa

revision = "0047_alias_slimming"
down_revision = "0046_carry_scope"
branch_labels = None
depends_on = None

_RETIRED = ("url", "authAlias", "auth_alias")


def _has_column(bind, table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(bind).get_columns(table)}


def _default_env_id(bind):
    return bind.execute(sa.text(
        "SELECT id FROM environments WHERE is_default")).scalar()


def _ensure_default_env(bind) -> "int | None":
    """②:有无环境的别名地址却没有默认环境 → 建一个(名字避让重名)。"""
    env_id = _default_env_id(bind)
    if env_id is not None:
        return env_id
    need = bind.execute(sa.text(
        "SELECT 1 FROM service_aliases "
        "WHERE base_url IS NOT NULL AND base_url <> '' "
        "AND environment_id IS NULL LIMIT 1")).scalar()
    if not need:
        return None
    names = set(bind.execute(sa.text(
        "SELECT name FROM environments")).scalars().all())
    name, n = "默认环境", 2
    while name in names:
        name, n = f"默认环境-{n}", n + 1
    return bind.execute(sa.text(
        "INSERT INTO environments "
        "(name, description, lines, is_default, created_at, updated_at) "
        "VALUES (:n, :d, CAST('{}' AS jsonb), true, now(), now()) "
        "RETURNING id"),
        {"n": name, "d": "authz M2a S6 迁移建立:承接未挂环境的别名地址"}
    ).scalar()


def _reland_addresses(bind, default_env) -> dict:
    """③:别名地址按 (基础服务, 环境) 聚合回落部署表,返回报告片段。"""
    rows = bind.execute(sa.text(
        "SELECT alias_name, base_service, base_url, environment_id "
        "FROM service_aliases "
        "WHERE base_url IS NOT NULL AND base_url <> ''")).all()
    groups: dict[tuple[str, int, bool], dict[str, str]] = {}
    selectors: list[dict] = []
    for alias, base, url, env in rows:
        if env is not None:
            groups.setdefault((base, env, False), {})[alias] = url
            if env != default_env:
                selectors.append({"alias": alias, "baseService": base,
                                  "envId": env})
        elif default_env is not None:
            groups.setdefault((base, default_env, True), {})[alias] = url
    conflicts: list[dict] = []
    for (base, env, alias_wins), by_alias in sorted(groups.items()):
        urls = set(by_alias.values())
        if len(urls) > 1:
            conflicts.append({"baseService": base, "envId": env,
                              "aliases": dict(sorted(by_alias.items()))})
            continue
        url = urls.pop()
        bind.execute(sa.text(
            "INSERT INTO deployments "
            "(base_service, env_id, base_url, created_at, updated_at) "
            "VALUES (:b, :e, :u, now(), now()) "
            "ON CONFLICT (base_service, env_id) DO "
            + ("UPDATE SET base_url = EXCLUDED.base_url, updated_at = now()"
               if alias_wins else "NOTHING")),
            {"b": base, "e": env, "u": url})
    # 地址被部署表取代(最终部署地址 ≠ 别名自带地址)的别名
    final = {(b, e): u for b, e, u in bind.execute(sa.text(
        "SELECT base_service, env_id, base_url FROM deployments")).all()}
    superseded = []
    for alias, base, url, env in rows:
        eid = env if env is not None else default_env
        got = final.get((base, eid)) if eid is not None else None
        if got != url:
            superseded.append({"alias": alias, "baseService": base,
                               "envId": eid, "aliasUrl": url,
                               "deploymentUrl": got})
    return {"conflicts": conflicts, "superseded": superseded,
            "envSelectors": selectors}


def _cleanse_schemes(bind) -> list[dict]:
    """④:方案 payload 剥退役字段,返回逐方案清单(含属主)。"""
    rows = bind.execute(sa.text(
        "SELECT r.id, r.scheme_id, r.scenario_id, r.name, r.payload, "
        "       s.owner_id, s.name AS scenario_name "
        "FROM composer_run_schemes r "
        "LEFT JOIN composer_scenarios s ON s.scenario_id = r.scenario_id"
    )).mappings().all()
    report: list[dict] = []
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            continue
        sb = payload.get("serviceBindings")
        if not isinstance(sb, dict) or not sb:
            continue
        kept: dict[str, dict] = {}
        dropped: dict[str, dict] = {}
        for svc, b in sb.items():
            if not isinstance(b, dict):
                dropped[svc] = {"value": b}
                continue
            gone = {k: b[k] for k in _RETIRED if k in b}
            if gone:
                dropped[svc] = gone
            alias = b.get("alias")
            if isinstance(alias, str) and alias.strip():
                kept[svc] = {"alias": alias.strip()}
        if not dropped:
            continue
        payload = {**payload, "serviceBindings": kept}
        bind.execute(sa.text(
            "UPDATE composer_run_schemes SET payload = CAST(:p AS jsonb) "
            "WHERE id = :id"), {"p": json.dumps(payload, ensure_ascii=False),
                                "id": r["id"]})
        report.append({"schemeId": r["scheme_id"],
                       "schemeName": r["name"],
                       "scenarioId": r["scenario_id"],
                       "scenarioName": r["scenario_name"],
                       "ownerId": r["owner_id"], "dropped": dropped})
    return report


def _land_scheme_urls(bind, schemes: list[dict], default_env) -> dict:
    """④b:被剥的方案绑定 url → 默认环境部署表(仅补缺,一致才落)。"""
    if default_env is None:
        return {"landed": [], "skipped": []}
    base_of = dict(bind.execute(sa.text(
        "SELECT alias_name, base_service FROM service_aliases")).all())
    by_base: dict[str, set[str]] = {}
    for item in schemes:
        for svc, gone in item["dropped"].items():
            url = gone.get("url") if isinstance(gone, dict) else None
            if isinstance(url, str) and url.strip():
                by_base.setdefault(base_of.get(svc, svc), set()).add(
                    url.strip())
    existing = set(bind.execute(sa.text(
        "SELECT base_service FROM deployments WHERE env_id = :e"),
        {"e": default_env}).scalars().all())
    landed, skipped = [], []
    for base, urls in sorted(by_base.items()):
        if base in existing or len(urls) > 1:
            skipped.append({"baseService": base, "urls": sorted(urls),
                            "reason": ("exists" if base in existing
                                       else "conflict")})
            continue
        url = urls.pop()
        bind.execute(sa.text(
            "INSERT INTO deployments "
            "(base_service, env_id, base_url, created_at, updated_at) "
            "VALUES (:b, :e, :u, now(), now())"),
            {"b": base, "e": default_env, "u": url})
        landed.append({"baseService": base, "envId": default_env,
                       "url": url})
    return {"landed": landed, "skipped": skipped}


def _notify(bind, user_id: int, title: str, body: str, link: str,
            payload: dict) -> None:
    bind.execute(sa.text(
        "INSERT INTO notifications "
        "(user_id, type, title, body, link, payload, created_at) "
        "VALUES (:u, 'announcement', :t, :b, :l, CAST(:p AS jsonb), now())"),
        {"u": user_id, "t": title[:255], "b": body, "l": link,
         "p": json.dumps(payload, ensure_ascii=False)})


_LEGACY_COLS = (("base_url", sa.String(512)),
                ("environment_id", sa.Integer()),
                ("owner_user_id", sa.Integer()),
                ("credential_alias", sa.String(64)))


def upgrade() -> None:
    bind = op.get_bind()
    present = {c for c, _ in _LEGACY_COLS
               if _has_column(bind, "service_aliases", c)}
    if not present:
        return   # fresh 链(baseline 已是瘦身后形状)
    # fresh 链半形态(0006 补回了 base_url,其余三列不存在):补齐为可空
    # 空列,下面的回填逻辑统一按存量形态走、末尾一并删除
    for col, typ in _LEGACY_COLS:
        if col not in present:
            op.add_column("service_aliases",
                          sa.Column(col, typ, nullable=True))

    # ①
    bind.execute(sa.text(
        "UPDATE service_aliases SET slot = credential_alias "
        "WHERE slot IS NULL AND credential_alias IS NOT NULL"))
    # ② ③
    default_env = _ensure_default_env(bind)
    addr = _reland_addresses(bind, default_env)
    personal = [{"alias": a, "ownerId": o} for a, o in bind.execute(sa.text(
        "SELECT alias_name, owner_user_id FROM service_aliases "
        "WHERE owner_user_id IS NOT NULL ORDER BY alias_name")).all()]
    # ④ + ④b
    schemes = _cleanse_schemes(bind)
    scheme_urls = _land_scheme_urls(bind, schemes, default_env)

    # ⑤ 报告 + 通知
    report = {**addr, "personalAliasesShared": personal,
              "schemeUrlsLanded": scheme_urls["landed"],
              "schemeUrlsSkipped": scheme_urls["skipped"],
              "schemesCleansed": schemes, "defaultEnvId": default_env}
    bind.execute(sa.text(
        "INSERT INTO audit_logs "
        "(actor_id, actor_name, action, resource_type, resource_id, "
        " detail, created_at) "
        "VALUES (NULL, 'migration', 'migration.alias_slimming', "
        "'migration', '0047_alias_slimming', CAST(:d AS jsonb), now())"),
        {"d": json.dumps(report, ensure_ascii=False)})
    by_owner: dict[int, list[dict]] = {}
    for item in schemes:
        if item["ownerId"] is not None:
            by_owner.setdefault(int(item["ownerId"]), []).append(item)
    for owner, items in by_owner.items():
        lines = [f"「{i['scenarioName'] or i['scenarioId']}」方案"
                 f"「{i['schemeName']}」:"
                 + "、".join(f"{svc}({'/'.join(sorted(d))})"
                            for svc, d in i["dropped"].items())
                 for i in items]
        _notify(bind, owner,
                f"运行方案的服务绑定已清理({len(items)} 个方案)",
                "服务绑定不再保存手填 URL 与凭证别名:地址由所选环境的部署"
                "地址给出,凭证由「我的凭证」里的槽位绑定给出。以下方案的"
                "对应字段已移除:\n" + "\n".join(lines),
                "/auths", {"migration": "0047_alias_slimming",
                           "schemes": items})
    if any((addr["conflicts"], addr["superseded"], addr["envSelectors"],
            personal, schemes)):
        admins = bind.execute(sa.text(
            "SELECT id FROM users WHERE role IN ('super_admin', 'admin') "
            "AND NOT is_system")).scalars().all()
        summary = (f"地址冲突未落部署表 {len(addr['conflicts'])} 组;"
                   f"地址被部署表取代的别名 {len(addr['superseded'])} 个;"
                   f"别名环境选择器失效 {len(addr['envSelectors'])} 个;"
                   f"个人别名转共享 {len(personal)} 个;"
                   f"方案绑定清洗 {len(schemes)} 个。"
                   "详情见审计日志 migration.alias_slimming。")
        for uid in admins:
            _notify(bind, uid, "别名瘦身迁移报告(authz M2a S6)", summary,
                    "/admin/deployments",
                    {"migration": "0047_alias_slimming",
                     "conflicts": addr["conflicts"]})

    # ⑥ 删四列(先放开延迟约束:同事务内 UPDATE 留下的待触发事件挡 ALTER)
    bind.execute(sa.text("SET CONSTRAINTS ALL IMMEDIATE"))
    for fk in sa.inspect(bind).get_foreign_keys("service_aliases"):
        if set(fk["constrained_columns"]) & {"environment_id", "owner_user_id"}:
            op.drop_constraint(fk["name"], "service_aliases",
                               type_="foreignkey")
    for ix in sa.inspect(bind).get_indexes("service_aliases"):
        if set(ix["column_names"]) & {"owner_user_id", "environment_id"}:
            op.drop_index(ix["name"], table_name="service_aliases")
    for col in ("base_url", "environment_id", "owner_user_id",
                "credential_alias"):
        if _has_column(bind, "service_aliases", col):
            op.drop_column("service_aliases", col)


def downgrade() -> None:
    bind = op.get_bind()
    if not _has_column(bind, "service_aliases", "base_url"):
        op.add_column("service_aliases", sa.Column(
            "base_url", sa.String(512), nullable=True))
    if not _has_column(bind, "service_aliases", "environment_id"):
        op.add_column("service_aliases", sa.Column(
            "environment_id", sa.Integer(),
            sa.ForeignKey("environments.id"), nullable=True))
    if not _has_column(bind, "service_aliases", "credential_alias"):
        op.add_column("service_aliases", sa.Column(
            "credential_alias", sa.String(64), nullable=True))
    if not _has_column(bind, "service_aliases", "owner_user_id"):
        op.add_column("service_aliases", sa.Column(
            "owner_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="NO ACTION",
                          deferrable=True, initially="DEFERRED"),
            nullable=True))
        op.create_index("ix_service_aliases_owner_user_id",
                        "service_aliases", ["owner_user_id"])
    bind.execute(sa.text(
        "UPDATE service_aliases SET credential_alias = slot"))
    bind.execute(sa.text("""
        UPDATE service_aliases a SET base_url = d.base_url
        FROM deployments d, environments e
        WHERE e.is_default AND d.env_id = e.id
          AND d.base_service = a.base_service
    """))
