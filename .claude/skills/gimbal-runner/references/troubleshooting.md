# Troubleshooting (launch path)

Quick triage for "I ran `gimbal run launch` and got exit code N".
Match the exit code first, then walk the **first** fix that matches.

## The canonical sanity loop

```bash
gimbal --version                          # is it installed at all?
gimbal run launch <file> --dry-run        # does the YAML parse?
gimbal run launch <file> -o json          # does the full pipeline work?
```

Stop at the first non-zero exit; the sections below tell you what to do
next. (`self-check` and `asset list` from the design docs are **not
implemented** — never insert them into this loop.)

## Exit 1 — tests failed

The scenario ran end-to-end but at least one assertion failed.

1. Re-run with `--log-level debug` to see HTTP request/response bodies.
2. Re-run with `-o json` to machine-parse which step failed.
3. **To isolate a mid-chain step** (there is no `--step-from` /
   `--breakpoint` on launch):
   - copy the YAML to a temp file,
   - delete (or comment out) the steps *after* the failing one,
   - for steps *before* it that only produce context vars, replace the
     dependency with a `--var` injection (e.g. skip the login step and
     pass `--var session_token=...` directly),
   - re-run the temp file. Never edit the user's original in place.
4. `--reporter html` and open the report — it usually points at the
   failing assertion in one click.

Common root causes (in order of frequency):

- **Wrong env** — `--env=staging` but the token in `config.users` was
  set for dev. Confirm which env the credentials belong to.
- **Stale --var-file** — remember the priority: CLI `--var` →
  `config.vars` → `--var-file`. Pass `--var` explicitly to override.
- **Time-sensitive assertions** — token TTL, OTP, idempotency keys.
  Replace hardcoded values with `${var.<name>}` and inject fresh ones
  per run.

## Exit 2 — usage / validation

The CLI rejected the input. Read stderr carefully; pydantic errors name
the exact field. **First check: did you invoke an unimplemented
subcommand?** `run scenario`, `run suite`, `run match`, `run server`,
`asset *`, and `self-check` all fail this way on the current build —
that's not an argument problem, stop and tell the user the feature
doesn't exist yet.

| Stderr pattern | Fix |
|---|---|
| unknown command / no such subcommand | Unimplemented feature — see above. Do not retry with different args. |
| `Scenario validation failed for ...` | Required field missing — see `scenario-skeleton.md`. |
| `--var-file root must be a mapping` | The YAML root is a list/scalar; wrap it in a map. |
| `--inline` + `SOURCE` both given | They're mutually exclusive; pick one. |
| stdin read refused | `SOURCE="-"` needs a pipe, not a TTY. |

If `--dry-run` exits 2 but a full `run launch` appears to work, that's
a false positive — `--dry-run` uses `Scenario.model_validate`; the live
path may have failed before reaching validation. Re-check with
`--log-level debug`.

## Exit 3 — engine exception

On this build there is no asset registry, so exit 3 means
**`Engine.run()` raised**. Do not "re-list assets and retry" — there
are no assets.

1. `--log-level debug` to capture the full stack; read the traceback.
2. `AssetMaterializer` / `RefBase` in the trace → the scenario contains
   a `${ref.*}` placeholder, which depends on the unimplemented
   registry. Tell the user that scenario can't run on this build.
3. Otherwise it's a framework bug — capture the trace and surface it.

## Exit 4 — bootstrap failure

The framework itself couldn't come up. Not recoverable by the agent.

1. `--log-level debug` for the offending plugin/extension.
2. Try `--config` pointing at a known-good `gimbal.yaml` (or no config)
   to rule out config corruption.
3. If it persists, the install is broken — surface to the user;
   suggest reinstalling from the working tree.

## Exit 124 / 127 (wrapper `scripts/gimbal_cli.py` only)

- `127` — gimbal binary not found. Try `python -m gimbal` from the
  source tree, or set `GIMBAL_BIN`. If neither exists, ask the user
  where the GIMBAL working tree is.
- `124` — subprocess timeout. Raise `--timeout` or investigate a hung
  HTTP call with `--log-level debug`.

## Runtime errors that don't change the exit code

These surface in stderr but gimbal still exits 0 — logged, not raised.
**Never conclude success from exit 0 alone; skim stderr.**

| Symptom | Likely cause |
|---|---|
| `[preprocessor] ${var.foo} resolved to None` | `foo` not in `config.vars` and not injected via `--var`/`--var-file` |
| `Service '<name>' not in config.services` | add it to `config.services` in the YAML |
| `hook ... not registered` | a plugin failed to activate; check `-P` flags and the bootstrap log |
| `Reporter ... raised during finalize` | reporter bug; report written but incomplete |
