# Troubleshooting

Quick triage map for "I ran gimbal and got exit code N". Match the exit
code first, then walk the **first** fix that matches.

## Exit 0 but nothing ran

You almost certainly passed `--allow-empty`, or your pattern matched
zero scenarios and the `--yes` prompt was suppressed (non-TTY).

- Re-run with `-o json` and inspect `result.total`.
- Re-run *without* `--allow-empty` to confirm; expect exit 5 instead.
- Check `gimbal asset list <namespace>` to verify the ref really exists.

## Exit 1 — tests failed

The scenario/suite ran end-to-end but at least one assertion failed.

1. Re-run with `--log-level debug` to see HTTP request/response bodies.
2. Re-run with `--output json` to machine-parse which step failed.
3. If the failure is mid-chain, isolate: `--step-from N --step-to N`
   (only on `run scenario`; for `run launch`, edit the YAML).
4. For an interactive pause, add `--breakpoint=<step>` to drop into the
   debugger at that step.
5. Check `--reporter html` and open the report — it usually points at
   the failing assertion in one click.

Common root causes (in order of frequency):

- **Wrong env** — `--env=staging` but `config.users.<u>.token` was set
  for dev. Try `--env=prod` to confirm.
- **Stale var-file** — `--var-file` overrides scenario `config.vars`.
  Delete the override or pass `--var` explicitly.
- **Time-sensitive assertions** — token TTL, OTP, idempotency keys.
  Replace with `${var.<name>}` and inject fresh values per run.

## Exit 2 — usage / validation

The CLI rejected your input. Read stderr carefully; pydantic errors name
the exact field.

| Stderr pattern | Fix |
|---|---|
| `invalid ref 'foo-bar'` | Refs are `ns/name:tag`. Use `/` and `:`, not `-`. |
| `--var-file root must be a mapping` | The YAML root is a list/scalar; wrap in a map. |
| `Scenario validation failed for ...` | A required field is missing — see `references/scenario-skeleton.md`. |
| `--step-from 不能大于 --step-to` | Swap the bounds. |
| `--parallel foo` | Use integer or `auto`. |
| `--auth=token needs --token-file` | Provide both, or use `--auth=none`. |

If `--dry-run` exits 2 but `run launch` (without `--dry-run`) appears to
work, that's a false positive — `--dry-run` parses with
`Scenario.model_validate`; the live path may have already failed before
reaching validation. Re-check with `--log-level debug`.

## Exit 3 — asset not found / engine exception

Two distinct causes share the code:

1. **Asset not found.** Registry ref doesn't exist.
   - `gimbal asset list <ns>` to confirm.
   - `gimbal asset inspect <ref>` to see metadata.
   - Check `--registry` — is the agent looking at the right root?
2. **`Engine.run()` raised.** Look at the traceback.
   - `gimbal self-check` first; if it also fails with non-zero, bootstrap is broken (exit 4 territory).
   - `--log-level debug` to capture the full stack.
   - Look for "AssetMaterializer" / "RefBase" — that means a `${ref.*}`
     placeholder couldn't be resolved. Either the registry is empty or
     the ref is misspelled.

## Exit 4 — bootstrap failure

The framework itself couldn't come up. Almost never recoverable by the
agent; surface to the user.

1. `gimbal self-check` to confirm.
2. If self-check is also 4, the install is broken — re-install.
3. Check `--log-level debug` for the offending plugin/extension.
4. Try `--config gimbal.yaml` with a known-good config (or no config)
   to rule out config corruption.

## Exit 5 — no match

Pattern matched zero scenarios. Either broaden the pattern or pass
`--allow-empty` if "no work today" is a valid outcome.

```bash
gimbal run scenario "demo/*" --yes           # interactive prompt if TTY
gimbal run scenario "demo/*" --yes --allow-empty  # always silent
```

## Common runtime errors that aren't exit codes

These surface as stderr text but gimbal still exits 0 — they're logged,
not raised:

| Symptom | Likely cause |
|---|---|
| `[preprocessor] ${var.foo} resolved to None` | `foo` not in `config.vars` and not in `--var`/`--var-file` |
| `AssetMaterializer: ref customs/declare not found` | push the asset first, or fix the ref spelling |
| `Service '<name>' not in config.services` | add it to `config.services` in the YAML |
| `hook ... not registered` | a plugin failed to activate; check `gimbal self-check` |
| `Reporter ... raised during finalize` | reporter bug; report still written, just incomplete |

## When in doubt

Run the canonical sanity loop:

```bash
gimbal --version                          # is it installed at all?
gimbal self-check                         # is the framework infra OK?
gimbal asset list                         # is the registry readable?
gimbal run launch <file> --dry-run        # does the YAML parse?
gimbal run launch <file> -o json          # does the full pipeline work?
```

Each step has a clear pass/fail; once you find the first non-zero exit,
the corresponding step above tells you what to try next.