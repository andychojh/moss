---
name: moss
description: Set up and use local Obsidian project memory for Codex. Retrieve relevant dated lessons at project starts and save evidence-linked decisions, failures and checks at meaningful milestones. Includes an empty vault, setup, standing instructions and verification.
---

# Moss

Small notes. Long memory.

Use this for substantive project memory, not casual chat or a transcript of every turn.
Follow the user's project rules and read-only/no-memory requests. A draft is not
verified truth; preserve source dates, uncertainty and human review status.

## First use

The skill is self-contained. Python 3.10+ is required; no pip packages or Obsidian
community plugins are needed. Locate `scripts/moss.py` relative to this file.
Configuration lives outside the skill in `~/.moss/config.json` (override with
`MOSS_CONFIG` or the global `--config` option before the subcommand).

When the user asks to set up Moss, choose their requested **new/empty** vault or
default to `~/Documents/Moss`. For requested standing integration, use the user's
Codex home `AGENTS.md` (`CODEX_HOME`, otherwise `~/.codex`). Run:

```text
python <skill>/scripts/moss.py setup --vault <absolute-vault> --instructions <absolute-AGENTS.md>
python <skill>/scripts/moss.py doctor
```

Setup edits only its marked instruction block, backs up changed preexisting
instructions, and refuses a nonempty unmanaged vault or a competing memory block.
Do not merge an existing personal vault, alter other AI configurations, or install
Python/Obsidian without the user's scope covering it. If they only want explicit
invocation, omit `--instructions`. Installation alone does not run setup.

Read [the setup guide](references/setup.md) for relocation, failure recovery and
what doctor does and does not verify. After setup, tell the user to open the folder
as a vault in Obsidian and start with `Home.md`. If Obsidian Bases is unavailable,
project notes and records remain readable as Markdown.

## Start or resume a project

1. Identify the actual source project root, not a temporary cwd. Run `start
   --project <absolute-root>`. It is read-only. If several projects share a root,
   select the correct `--key`. An unregistered descendant does not inherit its
   parent's project identity.
2. For a new project, register a meaningful title/key and one domain using
   `register --project <root> --key <key> --title <title> --domain <domain>`.
   Domains: Research, Development, Competitions, Learning, Admissions, Investing,
   Creative, Operations, Unsorted. Infer the domain when clear; use Unsorted when
   genuinely unresolved. Do not duplicate an existing project.
3. Read the hub, relevant records and their original evidence. Recent records are
   pointers, not a relevance search or a verified current-state summary. Search
   targeted titles/symptoms instead of loading the entire vault.

## Record a milestone or stop

Prepare UTF-8 JSON following [record.example.json](references/record.example.json).
Keep a stable `task_id` for a logical task. Include useful new decisions, failures,
checks actually run, limits, source paths and reuse conditions. Record conflicts
and proposed replacements explicitly in decisions; do not silently overwrite
verified conclusions. Never include secrets or unrelated private content.

Run `record --project <root> --key <key> --input <json-path>`. Identical input is a
no-op; changed content creates a readable, linked revision. The old body stays
intact and only its `record_current` flag changes. Report the returned path and
actual result. Do not claim a write succeeded if the tool failed. On a failure,
retain the input and diagnose; stop after two failures from the same cause or a
failed fallback, stating what is needed next.

## Grow useful knowledge

Read `System/Rules.md` in the configured vault. Keep general principles in one
`Knowledge/` note with evidence, scope and exceptions. Projects link to it with a
reason and retain their own conditions/results. Search before adding another
canonical note. Promote or revise knowledge only within the user's authorized
scope; never set `reviewed` just because an AI test passed. The writer does not
automatically infer conceptual links or rewrite project status summaries.

## Boundaries

For a visual Korean walkthrough, open [the interactive field guide](references/guide.ko.html)
locally in a browser. Its synthetic demonstrations do not read or write vault data.

Moss writes local files; it is not a background watcher, cloud sync, guaranteed
automatic invocation, or access to another AI's memory. The agent must actually
invoke the workflow. Existing sessions may need an explicit `$moss` request or
restart. Source folders must be accessible. Cross-device sync and public sharing
are separate user choices. Keep private vaults and machine config out of releases.
