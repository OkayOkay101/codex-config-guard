# Codex Config Guard architecture

## Components

| File | Role |
|---|---|
| `guard.py` | Core: TOML validation (`tomllib`), backup, restore, watcher (`watch`) and CLI |
| `Guard.ps1` | Runs `guard.py` with the Python recorded in `runtime.json` |
| `Install.ps1` / `Install.cmd` | Writes `runtime.json` and registers the *Codex Config Guard* scheduled task |
| `Verify-Installation.ps1` | Restarts the task and checks for a fresh heartbeat and a valid config |
| `Notify.ps1` | Tray balloon on recovery or errors |
| `Status.cmd` / `Restore.cmd` / `Apply-Draft.cmd` | Double-click shortcuts |
| `test_guard.py` | Unit tests on mock files in `work/` |

## Flow

```
config.toml changes ──► wait until stable ≥ 3 s ──► validate (tomllib)
                                              ├─ valid ─► back up to state/backups (+ SHA-256)
                                              └─ invalid ─► move broken file to state/quarantine
                                                          ─► re-check hash ─► atomic replace with latest verified backup
```

- **Atomic write**: write a temp file in the same folder, `os.replace`, then read back and verify the hash.
- **Locks**: `state/operation.lock` serialises tool commands; `state/watch.lock` prevents duplicate watchers.
- **Privacy**: logs never contain config content or parser messages (they may include secrets).
- **Errors**: `ConfigError` (invalid TOML), `ConflictError` (file changed mid-operation), `NoBackupError` (no usable backup — never writes defaults).

## Fixed target

`TARGET` in `guard.py` is resolved from `CODEX_HOME` (if set) or `~/.codex`, plus `config.toml`. The CLI deliberately has no override,
to avoid accidentally overwriting another file (tests pass a mock target via `Guard(target=...)`).
