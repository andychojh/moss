# Setup & recovery

The repository contains an installable skill at `skills/moss`. Install that whole
folder, not just `SKILL.md`. The bundled template contains no project records.

## One guided setup

Ask Codex: “Install $moss, ask what work I want to remember and help me choose
useful categories (or none). Create a new vault at [absolute path], enable project
memory in my Codex instructions, and verify the installation.” Codex resolves
its installed script location and runs setup and doctor. No API key is needed.
Using Codex itself remains subject to your usual account and service terms.

For manual setup, replace `<skill>` with the installed directory. Use `python3`
instead of `python` where appropriate. Paths with spaces must be quoted.

```sh
python <skill>/scripts/moss.py setup --vault /absolute/path/Moss --instructions /absolute/path/AGENTS.md
python <skill>/scripts/moss.py doctor
```

On Windows, use absolute drive paths, for example `D:\Notes\Moss`.
Setup creates a fresh vault, saves an external machine config, and adds only the
Moss block to the explicitly selected `AGENTS.md`. Previous instruction text is
backed up under the config directory's `backups/` before a change. Repeating setup
preserves notes, graph settings and instructions outside that block. Setup cannot
merge an existing unmanaged vault. Choose a fresh folder instead.

Open that folder using Obsidian's “Open folder as vault”. Enable the bundled core
Bases, Canvas and Graph features if your installation has them disabled. No
community plugin is installed. New project notes are found by the domain tables;
new logs appear in their project's table. The global graph hides logs/navigation
so a growing log does not become a giant hub.

New vaults have no preset subject areas. See [personalization](personalization.md)
to set labels and colors, add categories later, or retain a v0.1 vault safely.

## What is checked

`doctor` checks ownership, expected entry points, registered hubs/views, project
routing, one current revision per task, Canvas file targets/edge endpoints and
standing instructions. Generated Bases are JSON (valid YAML); keep their format
when editing files directly. Doctor does not prove factual accuracy, search every
link or validate UI rendering. It never repairs or deletes notes on its own.

## Move or uninstall

Back up the vault and config first. On a new machine, install the skill, copy the
vault, and run setup with a **new machine config** (`--config` before `setup`). A
config already bound to another vault is deliberately not redirected. Update
source roots in `System/projects.json` after reviewing the mapping; historical
source paths remain dated evidence. Then run doctor. Cross-OS relocation has not
been established by a Windows-only local run; see CI for tested platforms.

To stop standing invocation, remove only the `MOSS:BEGIN` through `MOSS:END` block
from your Codex instructions. You can then uninstall the skill. Keep the vault;
it is plain files and is never removed by Moss. Other Codex settings are unrelated.

If a run is interrupted, keep the record input JSON. A writer lock is a directory
at `System/.write-lock`; only remove it after confirming no writer is running.
Then retry the exact input. Successfully written revisions are detected and their
current flags repaired on retry. Setup stages a fresh vault before moving it into
place. A completed vault with an interrupted config write can be reattached by
repeating the same setup command. Inspect errors before retrying.

One machine's lock does not coordinate two independently synced copies. Avoid
concurrent writes through cloud-sync folders; resolve conflicts before resuming.
