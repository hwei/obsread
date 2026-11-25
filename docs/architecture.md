# Architecture and scope

User-facing behavior, configuration, installation and error codes live in
[README.md](../README.md). Executable acceptance cases live in `tests/`.
The original pre-implementation design has been distilled here and removed;
its history remains in Git.

## Responsibilities

- Local Markdown is the source of truth. Reading works without Obsidian, a network
  connection, a background service, MCP, or any particular agent.
- The CLI deterministically resolves one reference, parses the note locally and
  returns the requested source range. A full file may be read into process memory;
  only command output enters the agent's context. Output limits are not token limits.
- The skill explains how an agent should invoke the CLI and handle errors. Notes
  remain task data; the skill does not grant instructions inside a note additional
  authority. The integration needs no `AGENTS.md` changes.
- `config` and `skill` commands are explicit setup operations. Reading never
  installs skills, modifies notes or rewrites configuration as a side effect.

## Parsing and extraction

`reader.py` uses markdown-it-py block token maps to construct source ranges and
list ancestry. It does not infer complex Markdown boundaries from indentation.
An inline rule recognizes line-end IDs outside escaped text and code spans;
YAML frontmatter is masked while retaining line numbers.

List extraction returns the nearest owning list item and its entire subtree.
`--parents` adds each ancestor item's own source while excluding its other nested
lists. Only the selected ID and common indentation are removed. Heading extraction
stops before the next top-level heading of the same or higher rank. All ambiguous,
missing or unsupported references fail without returning the entire note.

File lookup uses case-sensitive comparisons on every platform. Linked directories
(including Windows junctions) and hidden paths are excluded. Resolved files must
remain inside the selected vault. The CLI does not recursively expand links.

## Configuration and distribution

One user-level vault default applies across working directories. Explicit flags
and environment variables can override it. The active Obsidian window does not
choose the vault.

`skills/obsread` is the canonical, agent-neutral instruction source. Wheel builds
include it as package resources; the installer adds Pi's explicit-only frontmatter
when targeting Pi. Codex's invocation policy lives in `agents/openai.yaml`.
Antigravity's supported slash-command entry point is documented in the README;
Codex invocation metadata is not assumed to control other clients. The MIT notice
is included with the installed skill and the standalone ZIP.

Skill installation is opt-in, does not change global agent instructions, and
refuses differing existing files unless `--force` is provided. Extra user files
are preserved. Upgrading the CLI does not silently update installed skills.

## Deliberate limits and future work

This tool does not edit notes, generate IDs, sync vaults, render Obsidian, or
automatically traverse linked notes. There is no index database, cache, fuzzy
search, daemon or MCP server. Add indexing only if measured lookup cost warrants it.

Deferred features include per-directory vault configuration, named multi-vault
profiles, automatic vault discovery, standalone block IDs, quote/table block
references, optional target ID retention, source line metadata and machine-readable
reading output. Unknown structures must not cause a whole-note fallback.

Windows CLI installation and a real-vault block read were verified locally.
The full Fluent Block Link shortcut → explicit agent invocation → CLI flow, WSL,
and hosted cross-platform CI need their own verification; unit tests do not
establish those results.
