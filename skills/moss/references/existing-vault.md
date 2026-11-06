# Adopt an existing vault

This is the default onboarding route when the user already has notes. Keep the
same vault path. Do not ask them to start over, copy personal data into the skill,
or apply the author's domains. `setup` remains for empty vaults only.

## Understand and plan

Locate the actual vault and read its rules, home, representative project notes,
and metadata conventions. Ask only for missing vault location or essential goals.
Use `scripts/migrate.py audit --vault <absolute-path> --plan <external-plan.json>`.
It inventories every file and proposes filenames from H1 headings (or strips a
long trailing hash). Suggestions are not a semantic classification algorithm.

Review and edit `moves` in the JSON plan. Each entry has `from`, `to`, and `reason`.
Use moves for both renaming and folder organization. Keep useful existing folders;
derive categories from the user's actual work, not a prescribed count. Set the
plan's `profile` using the personalization schema. Resolve collisions with a short
meaningful qualifier, not a random ID. Remove unwanted suggestions.

Title rules:
- Concepts: `Clear concept name.md`; projects: `Project name.md`.
- Dated records: `Specific outcome — YYYY-MM-DD.md`, only with an evidenced date.
- Retain meaningful dates, version numbers, course codes and technical identifiers.
- Remove machine IDs/hash suffixes from filenames, preserving identifiers in content.
- Keep good existing titles. Do not give every note a numeric prefix or a date.
- Filename suggestions do not rewrite H1 or YAML `title`. Inspect these separately;
  change human titles only within the requested scope, preserving existing aliases,
  heading links and source/review dates. Do not interpret a frontmatter `title` as
  a universal schema or reserialize arbitrary YAML with a partial parser.

Duplicate groups are candidates only. Preserve history and source material; do
not merge or delete based solely on matching topics or file hashes. Explain real
cross-project relationships in canonical knowledge notes. Navigation lists should
not manufacture semantic edges to every log.

## Prepare and inspect

Run `python <skill>/scripts/migrate.py prepare --plan <plan> --output <new-external-dir>`.
This leaves the source untouched and builds a complete preview vault and report.
It rewrites standard wiki links/embeds, simple Markdown links/reference definitions
and Canvas file/text references. Relative attachment paths follow moved notes.
Code spans and fenced examples are preserved. Attachments are copied as bytes.
Ambiguous links, conflicting filenames, stale inventory and template collisions stop
the operation. Resolve the cause in the plan and use a fresh output directory.

Review every rename/move and `report.json`, including unresolved baseline links.
Check `manual_reference_review`: these are old literal paths remaining in metadata,
examples or plugin state. If any remain, activation requires `--references-reviewed`
after the agent actually checks them. This is an evidence check, not a request for
additional permission. Repair live references before re-preparing; preserved examples
can remain. Do not pass the flag merely to get past an error.
Manually inspect plugin queries, Bases filters, JSON workspace/bookmarks, external
incoming links, title properties and heading/block anchors. Unsupported Markdown
syntax must be fixed through a reviewed agent edit before activation, not silently
declared supported. The helper is a conservative file transformation, not a full
Obsidian parser. Preserve existing `.obsidian` settings; apply graph colors later
only where the user's settings allow it. A conflicting `Home.md`, `System/` file
or template name must be explicitly relocated in the plan; never overwrite it.

Do not edit the preview after preparation: activation checks every file hash.
If additional source edits are needed, back up and perform those authorized edits,
then regenerate the inventory/plan/preview. Stop after two failures with the same
cause; retain artifacts and report the specific blocker.

## Activate and continue

Close Obsidian and pause other writers/sync for the short activation. Present the
concrete change summary; proceed within the user's authorization for reorganization.
Run `python <skill>/scripts/migrate.py activate --output <prepared-dir> --config <new-config>`.
The helper verifies both source and preview hashes, retains the entire original as
a sibling backup, and replaces the vault at the original path. A failed directory
replacement attempts to restore the original immediately. Read `activation.json`
for paths if later configuration writing fails. Do not delete backups automatically.
For manual rollback, stop writers, retain the current vault separately, then put the
original backup back at its original path; do not overwrite newer user edits.

Run `moss.py --config <config> setup --vault <same-vault> --instructions <AGENTS.md>`
only when standing integration is wanted, followed by `doctor`. Reconcile a competing
memory workflow instead of enabling two writers. Register actual source projects,
link relevant existing notes from their new project hubs, and configure user-chosen
areas/colors. Existing notes are not fabricated task records. Explain the home,
project lookup and how future records reuse existing knowledge. Inspect the rendered
vault where available; distinguish file verification from GUI verification.

Report changed titles/folders, preservation checks, unresolved references, backup
location, and actual integration status. Never claim all historical facts were verified.
