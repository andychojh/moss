---
{
  "type": "guide",
  "wiki_layer": "system",
  "graph_role": "navigation"
}
---

# A small field guide

1. Open [[Home]] and pick a project, optionally through one of your areas.
2. Read relevant records and follow their source evidence.
3. Resume work in the actual project folder.
4. Ask Codex to record useful decisions, failures and checks with `$moss`.
5. Reuse principles through Knowledge notes, with links explaining why they apply.

The project table defaults to **Latest per task**. Choose **All revisions** to see
how a decision changed. The writer creates logs and basic hubs; it does not rewrite
the prose in an existing hub or synthesize all cross-project knowledge by itself.

## Colors
You choose domain names and colors. [[System/Areas]] is the current legend;
[[System/Domain Map.canvas]] is generated from your profile. A color means a
category, not importance or confidence. There is no fixed category list.
Use `configure --profile` through Codex to add areas or change labels and colors.
IDs are stable routing keys; relabeling does not move project files or records.

## Graph and map
The global graph hides navigation, logs, system files and templates. New records
therefore appear in project tables without flooding the global graph. To inspect
logs, replace the graph search with `path:"Records"`, or a specific project path.
Use a note's local graph to inspect nearby relationships. The Canvas is a visual
entry point; its arrows describe the memory lifecycle, not project dependencies.

## Local, on purpose
Moss writes Markdown to this vault. It needs no community plugin, API key or
background service. Codex must invoke the skill; installing it does not capture
all chats. File access, model behavior and project instructions still apply.
Sync to another machine and sharing are separate choices. Run `doctor` after
setup or relocation; it checks structure, not factual correctness.
