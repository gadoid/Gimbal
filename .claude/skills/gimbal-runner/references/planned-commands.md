# Planned commands — ⚠️ NONE OF THESE EXIST YET

> **Agent rule: never construct or execute any command on this page.**
> This is the design spec for GIMBAL's target CLI surface, preserved so
> you can (a) explain the roadmap when the user asks, and (b) recognize
> that a request maps to a *future* feature rather than to a flag you
> haven't found. When a feature ships, its section moves out of this
> file and into `commands.md` / SKILL.md.
>
> Attempting these today returns exit 2 (unknown command). That is not
> an argument error — do not loop on fixing the args.

## Target mental model

```
gimbal
├── run
│   ├── suite     <SUITE_ID>...        by ID, namespace wildcards
│   ├── scenario  <SCENARIO_ID>...     by ID, namespace wildcards
│   ├── match     <PATTERN>...         glob/selector against local files
│   ├── server                          long-running HTTP/gRPC/WS service
│   └── launch    [SOURCE]             ✅ IMPLEMENTED — see commands.md
├── asset                               Docker-like local registry
│   ├── push, pull, list, inspect, remove, tag, gc
└── self-check                          framework infra smoke test
```

Design intent: `run` goes through `bootstrap()` → `Engine.run()`;
`asset` is a fast path building an `AssetStore` directly (no event bus,
no plugins); `self-check` is an integration test.

## run scenario / run suite (planned)

Run assets pushed to the registry, by `ns/name:tag` ref with namespace
wildcards. Key planned flags: `--step-from/--step-to/--breakpoint`
(step-level debugging — the feature launch lacks), `--source
{auto,local,remote}`, `--tag`, `--include-scenario/--exclude-scenario`
(suite only), `--order {sequential,parallel,as-given}`,
`--continue-on-error`, `--retry`, `--timeout`.

Design landmine to preserve: multi-match confirmation prompts are
**skipped on non-TTY and the run proceeds** — agents must pass `-y`
explicitly for intent, `--allow-empty` if zero matches is acceptable,
and must not read exit 0 + `--allow-empty` as "something ran".

## run match (planned)

Glob/selector execution over local files, no registry:
`--path/--include/--exclude`, `--changed-only --changed-since=REF`
(git-aware), `--last-failed`, `--collect-only`, `--shuffle --seed`.
Exit 5 (`EXIT_NO_MATCH`) belongs to this feature.

*Current workaround (with user consent): loop `run launch` over a file
glob in the shell.*

## run server (planned)

Long-running service: `--host/--port/--unix-socket`,
`--workers/--max-concurrent/--queue-size`, `--mode
{http,grpc,websocket}`, `--auth {none,token,mtls}` + `--token-file`,
`--allow-origin`, `--register-to/--heartbeat-interval`,
`--health-port/--metrics-port`, `--graceful-timeout`, `--pidfile`.

When this ships, the skill must gain an agent recipe for lifecycle
management: background start with PID capture, health-port probe to
confirm readiness, and cooperative SIGINT semantics (first Ctrl-C ends
the current task, second forces exit).

## asset family (planned)

Docker-like refs `ns/name:tag`. `push -f FILE -k
{suite,scenario,data,blob}`, `pull -o FILE`, `list [ns] -o json`,
`inspect`, `remove -y`, `tag SRC DST [--overwrite]`, `gc -y`.

When this ships, add agent guardrails: `remove`, `gc`, and
`--overwrite` are destructive and confirmation prompts are skipped on
non-TTY — the agent must get explicit user approval and show
`list`/`inspect` output for what will be affected before executing.

## self-check (planned)

No-arg framework infra smoke test (bootstrap + event bus + hook
registry). Once shipped, it becomes step 2 of the sanity loop in
`troubleshooting.md`.

## Suite file skeleton (planned, cannot be executed yet)

```yaml
kind: suite
suite:
  - kind: scenario        # each item is a FULL scenario document —
    scenarioId: sc-...    # every field from scenario-skeleton.md,
    meta: ...             # not a placeholder
    config: ...
    resource: {}
    steps: [...]
```
