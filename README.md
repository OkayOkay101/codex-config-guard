# Codex Config Guard

English | [ไทย](README.th.md)

Automatic syntax checking and recovery for the Codex `config.toml` on Windows — works without opening Codex.
The target file is `%CODEX_HOME%\config.toml` when that variable is set, otherwise `%USERPROFILE%\.codex\config.toml`.

## Quick install

Requires Windows 10/11 and [Python 3.11+](https://www.python.org/downloads/windows/) (tick *Add python.exe to PATH* during setup).

1. Download: click **Code → Download ZIP** on GitHub and extract it to a permanent location, e.g. `Documents\Codex Config Guard`
   (or `git clone https://github.com/OkayOkay101/codex-config-guard.git`).
2. Double-click **`Install.cmd`** — it validates your current config, takes the first backup and registers a Task Scheduler task that runs at every logon (no administrator rights needed).
3. Double-click **`Status.cmd`** to confirm it is running.

> Do not move the folder after installing; if you do, run `Install.cmd` again.
> Your current config must be valid TOML, otherwise the task is not registered.

## Usage

| Shortcut | PowerShell (from the tool folder) | Purpose |
|---|---|---|
| `Status.cmd` | `.\Guard.ps1 status` | Check the live file, backup count and heartbeat |
| — | `.\Guard.ps1 check` | Syntax check only |
| Drop a file on `Apply-Draft.cmd` | `.\Guard.ps1 apply C:\path\draft.toml` | Validate a draft, back up, then replace atomically |
| `Restore.cmd` | `.\Guard.ps1 restore` | Restore the latest verified backup |

`apply` preserves bytes, comments and line endings; the draft must be a different file from the live config. `restore` does not roll back when the current file already matches the latest backup.

The watcher runs under `pythonw` (no console window), polls every 2 seconds and waits for the file to be stable for at least 3 seconds before backing up or restoring.

## Windows paths in TOML

```toml
command = 'C:\Program Files\nodejs\node.exe'   # literal string, no escaping
```

With double quotes you must escape backslashes (`\\`). Schema-aware editors can use this line in a draft:

```toml
#:schema https://developers.openai.com/codex/config-schema.json
```

## Stored data and security

- `state/backups/` — last 20 verified copies with SHA-256 metadata
- `state/quarantine/` — invalid files kept before recovery; never auto-deleted
- `state/events.jsonl` — UTC time, event type, hashes and error position; **no config content**; rotated above 2 MB
- `state/` is restricted to the installing user, SYSTEM and Administrators because backups may contain API keys or tokens
- `state/`, `work/` and `runtime.json` are git-ignored — **never share or commit `state/`**
- No network access; model names, permission policies and MCP settings are never changed

## Managing / uninstalling

```powershell
Get-ScheduledTaskInfo -TaskName 'Codex Config Guard'
Stop-ScheduledTask    -TaskName 'Codex Config Guard'
Start-ScheduledTask   -TaskName 'Codex Config Guard'
Unregister-ScheduledTask -TaskName 'Codex Config Guard' -Confirm:$false   # uninstall
```

Keep `state/backups/` before deleting the folder if you may need old copies.

## Limitations

- Syntactically valid TOML may still contain values Codex does not support.
- When another program writes the config directly, there is a short window before recovery in which Codex could read a broken file. Use `apply` to validate before touching the live file.
- If every backup is invalid, no default is written. The watcher only runs while the user is logged on.
- Notifications are tray balloons that Windows may hide; `status` and the log are always available.

## Recommended companion: Codex Sidebar Repair

If your problem is **projects or chat grouping missing from the Codex desktop sidebar** (while the data is still in the database), try
[Swih/codex-sidebar-repair](https://github.com/Swih/codex-sidebar-repair) — an unofficial Windows recovery utility (MIT License).

- Node.js 24+, no dependencies, no administrator rights.
- `node repair-sidebar.cjs` previews without changing files; apply with `--apply` after fully quitting Codex.
- Relies on internal state formats that may change between versions.

Config Guard protects the settings file; Sidebar Repair restores sidebar state — they complement each other.

## More docs

- [Architecture](docs/ARCHITECTURE.md) · [สถาปัตยกรรม (ไทย)](docs/ARCHITECTURE.th.md)
- Codex config reference: https://learn.chatgpt.com/docs/config-file/config-reference

## Tests

```powershell
python -m unittest discover -v
```

Tests use mock files under `work/` and never touch the real config.

## License

[MIT No Attribution (MIT-0)](LICENSE) — use, modify and redistribute freely, commercially or not, without keeping the copyright notice.
