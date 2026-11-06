# Your work, your categories

Moss has a common memory process, not a fixed subject taxonomy. New vaults have
no preset domains. Start uncategorized, or choose categories during onboarding.
The packaged examples are synthetic and opt-in; they are never installed by default.

## A short onboarding conversation

Ask only for missing context: what work needs continuity, the language the user
uses, and whether broad areas help retrieval. Use their actual project boundaries.
Suggest a few areas with a reason for each, then use their choices. For example,
a studio might choose client work and original work; another person might prefer
no areas. Neither is a universal default. Never scan unrelated private folders
to invent a personality profile. Adjust note detail and milestone frequency to
the user's needs; retain dates, evidence, uncertainty and non-destructive history.

## Profile format

```json
{
  "domains": [
    {"id": "client-work", "label": "고객 작업", "color": "#4879C4"},
    {"id": "originals", "label": "Original work", "color": "#35A38B"}
  ]
}
```

`id` is a stable folder/property key: 1–48 ASCII letters, digits or hyphens,
starting with a letter. IDs are case-sensitive but case-only duplicates are
rejected for portability. `Shared` and Windows device names are reserved.
`Unsorted` is the canonical fallback ID. `label` is a readable Unicode name;
`color` is a six-digit hex color. There is no eight-category limit. An empty
`{"domains": []}` is valid. Save this as UTF-8 JSON outside private source files.

```sh
python <skill>/scripts/moss.py setup --vault <absolute-new-vault> --profile <profile.json>
python <skill>/scripts/moss.py domains
python <skill>/scripts/moss.py configure --profile <profile.json>
python <skill>/scripts/moss.py doctor
```

`configure` merges the listed IDs. It adds new categories and updates labels and
colors; omitted categories remain. Existing project paths and record bodies never
move. Areas, Bases, a category table, a Canvas and graph color groups are generated
from the profile. `Home` links to `System/Areas` and `System/Domain Map.canvas`.
The category Canvas is navigation, not a claim that all projects are related.
Conceptual links still need evidence and an explanation.

Generated files are updated only if their last generated content remains intact.
If you edited one, configuration stops before overwriting it. Reconcile the edit
with Codex; do not delete it to silence the check. Other graph preferences and
unrelated color groups are preserved. Domain registry snapshots are backed up in
`System/Backups`. After an interrupted update, retry the exact same profile;
doctor reports the pending update. Do not hand-edit its journal.

## Existing v0.1 users

Replace only the installed skill folder; keep the vault and external config.
Run `domains` to inspect the inferred existing categories, then `configure` with
your additions/label/color changes (or an empty profile to import the existing
taxonomy). Run doctor. Existing records, routes, area prose, Home content and
the user's original Canvas remain intact. A link to the new category navigation
is added if absent. Legacy area headings may retain their original text; the
new category table uses your chosen labels. No migration runs on installation.

Changing IDs, moving existing projects, merging or deleting areas is a separate
reviewed migration. This version deliberately does not silently relocate notes
or delete the old eight areas from an existing vault. For a new clean start,
create a separate empty vault with a separate machine config.
