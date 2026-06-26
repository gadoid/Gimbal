# GIMBAL Capture Filter Strategy Reference

Load this when configuring or debugging the **capture whitelist** — deciding
which requests `gimbal capture` records and which it drops. `gimbal capture` is
the mitmproxy-based traffic recorder; this file documents the v0.4 YAML strategy
format consumed by `gimbal/capture/loader.py`, not how to turn a capture into a
scenario (that is `gimbal-traffic-to-scenario`).

All paths below are **relative to the GIMBAL repo root**. Pointers reference
symbols (classes/functions), not line numbers, so they survive edits — `grep`
the symbol if you need the exact site.

## File location & lookup order

`loader.py` resolves the strategy file via `_default_search_paths`, in order:

1. `./.gimbal/filters.yaml` — in-project, **recommended for team sharing**
2. `./filters.yaml` — project root
3. `~/.gimbal/filters.yaml` — personal, cross-project
4. `$GIMBAL_FILTERS` — env var pointing at any path

`--filter-file <path>` overrides all of the above (highest priority, skips
auto-search). With `--strict-files-only`, a missing file is a hard error
(no fallback to auto-search).

## YAML structure

```yaml
mode: include              # root mode; unmatched request → default exclude
default_profile: smoke     # used when --filter-profile is omitted

profiles:
  smoke:
    description: smoke capture — core order/query endpoints only
    rules:
      - path: /api/order               # prefix + method whitelist
        methods: [GET, POST]
      - path_glob: "/api/v*/order/**"  # fnmatch-style glob
      - path_glob: "/api/payment/*"
      - path_regex: "^/api/(user|account)/[0-9]+/?$"
```

`includes:` (relative to the main YAML's directory) may pull in shared profiles;
cycles are rejected (`IncludeCycleError`).

## Rule fields

Data model: `Rule` / `Profile` / `StrategyFile` in `gimbal/capture/strategy.py`.

| field        | type         | meaning                                                      |
|--------------|--------------|-------------------------------------------------------------|
| `host`       | string       | exact host (one of the host trio)                           |
| `host_glob`  | string       | fnmatch host                                                |
| `host_regex` | string       | regex host                                                  |
| `path`       | string       | **prefix** match (`/api/order` matches `/api/order/123`)    |
| `path_glob`  | string       | fnmatch (`*` any segment span, `?` one char)                |
| `path_regex` | string       | regex (double-escape backslashes in YAML: `\\d`)            |
| `methods`    | list[string] | HTTP method whitelist; upcased; empty = match all methods   |

## Match semantics

Implemented in `CompiledMatcher.match` (`strategy.py`).

- **Within one rule:** `host` / `path` / `methods` are **AND** — all present
  fields must match.
- **Across rules:** **OR** — any matching rule matches the request.
- **No rule matches:** root `mode: include` → default **exclude** (drop);
  root `mode: exclude` → default **include** (keep).
- Every rule needs **at least one** match field. Unknown fields error out
  (`extra="forbid"`).

### The three `path` forms — know the difference

| form         | behavior                                   | example                                    |
|--------------|--------------------------------------------|--------------------------------------------|
| `path`       | `request.path.startswith(rule.path)`       | `/api/order` **also** matches `/api/orderlist` |
| `path_glob`  | `fnmatch(request.path, rule.path_glob)`    | `/api/v*/order/**` — `*` spans segments     |
| `path_regex` | `re.search(rule.path_regex, request.path)` | `^/api/order/[0-9]+$` — exact               |

**Prefix gotcha:** `path: /api/order` matches `/api/orderlist` too. To match
`/api/order` and its sub-paths only, use `path_regex: "^/api/order(/.*)?$"`.

## Rule patterns by scenario

**Strict prefix + method**

```yaml
- path: /api/order
  methods: [POST, PUT]    # only create/update
- path: /api/user
  methods: [GET]          # only user reads
```

**Multi-version glob**

```yaml
- path_glob: "/api/v*/order/**"   # any v1/v2/v3 order sub-path
- path_glob: "/api/payment/*"     # single segment (no slash)
```

**Regex exact-id match**

```yaml
- path_regex: "^/api/order/[0-9]+$"
  methods: [GET, DELETE]
- path_regex: "^/api/user/profile/?$"
```

**Pin to a host** (omit `host` to match any host)

```yaml
- host: api.example.com
  path_glob: "/api/order/**"
  methods: [POST]
```

## CLI invocation

Auto-search + default profile:

```bash
gimbal capture start --session dev-1
```

Explicit file + profile:

```bash
gimbal capture start --session dev-1 \
  --filter-file ./.gimbal/filters.yaml \
  --filter-profile smoke
```

Legacy CSV prefix append (backward-compat; `--filter` = comma-separated path
prefixes, `--filter-mode` controls include/exclude, default include):

```bash
gimbal capture start --session dev-1 \
  --filter-file ./.gimbal/filters.yaml --filter-profile smoke \
  --filter "/api/debug" --filter-mode include
```

Require the file to exist (no auto-fallback):

```bash
gimbal capture start --session dev-1 --strict-files-only
```

CLI wiring: `gimbal/capture/cli.py` (`start_cmd`).

## Preflight validation — must pass before mitmdump starts

These run in the parent process; failure → **exit code 5**, mitmdump never
launches. Check each before `capture start`:

- YAML parses: `python -c "import yaml; yaml.safe_load(open('./.gimbal/filters.yaml'))"`
- every rule has ≥1 `host`/`path`/`method` field
- every `path_regex` / `host_regex` compiles (`re.compile` doesn't throw)
- the `--filter-profile` name exists under `profiles:`
- `includes:` paths resolve (relative to the main YAML's dir) with no cycle

## Runtime verification — after capture starts

- `gimbal capture list --session dev-1` shows the session as established
- proxy set to `127.0.0.1:8080` in the browser/client
- whitelisted requests land in `$GIMBAL_HOME/captures/active/<sid>.ndjson`
- `gimbal capture show --session dev-1 --tail` shows the expected
  method/path live
- requests **not** on the whitelist do **not** appear in the NDJSON

## Recommended practice (advisory, not a gate)

- Pin complex regexes as unit tests in `tests/test_loader_yaml.py` /
  `tests/test_loader_profile.py` so they don't silently rot.
- Prefer `./.gimbal/filters.yaml` (committed) over personal `~/.gimbal/` files
  for anything the team relies on.

## Troubleshooting

| symptom                          | cause                                              | fix                                                        |
|----------------------------------|----------------------------------------------------|-----------------------------------------------------------|
| `FilterFileNotFound`             | no file on any auto-search path                    | add `--filter-file` or create `./.gimbal/filters.yaml`    |
| `EmptyRulesError`                | profile has `rules: []`                            | add ≥1 rule                                               |
| `RuleCompileError`               | illegal regex                                      | test with `re.compile`; in YAML write `\\d` not `\d`      |
| `ProfileNotFound`                | `--filter-profile` typo                            | check it against the keys under `profiles:`               |
| `IncludeCycleError`              | `includes:` form a loop                            | break the include chain                                   |
| nothing captured                 | `mode: include` + nothing matched → all excluded   | capture a path you know matches; or temp `path_glob: "/**"` to debug |
| everything captured              | rule too broad, or mode inverted                   | re-check the three `path` forms (see table above)         |

## Source pointers (read-only)

| concern                      | location                          |
|------------------------------|-----------------------------------|
| data model (Rule/Profile/StrategyFile) | `gimbal/capture/strategy.py` |
| runtime matcher              | `gimbal/capture/strategy.py` → `CompiledMatcher` |
| loader (search paths, includes, profile select) | `gimbal/capture/loader.py` → `_default_search_paths` |
| legacy CSV filter            | `gimbal/capture/filter.py`        |
| mitmproxy addon → matcher    | `gimbal/capture/proxy.py`         |
| CLI wiring                   | `gimbal/capture/cli.py` → `start_cmd` |
| user manual (filter section) | `USER_MANUAL.md`                  |
| design doc (full semantics)  | `gimbal-design/07-filter-strategy.md` |