# obsread

Read an Obsidian Wikilink from local Markdown and return only the requested note,
heading section, or block subtree. Obsidian does not need to be running.

Python 3.10+ is required. Distributed under the [MIT license](LICENSE).
Download packages from [GitHub Releases](https://github.com/hwei/obsread/releases).
PyPI publication is not enabled yet.

## Install and configure

For agent use, complete all three steps: **install the CLI, configure your vault,
and install the skill for your agent**. No `AGENTS.md` changes are needed.

Install the published wheel using [uv](https://docs.astral.sh/uv/):

```sh
uv tool install 'https://github.com/hwei/obsread/releases/download/v0.1.0/obsread-0.1.0-py3-none-any.whl'
obsread config set vault '/absolute/path/to/your/vault'
obsread skill install codex
```

Choose `pi` or `antigravity` instead of `codex` as appropriate; you can install for
multiple agents. For standalone shell use, skip the skill step. The skill is
included in the Python package, so installing it does not require a separate
download or network access. Installing the CLI does not silently install skills.

For another version, use its wheel URL from GitHub Releases. From a source
checkout, use `uv tool install .` instead. To upgrade an existing installation,
run `uv tool install --reinstall '<new release wheel URL>'`, then re-run the skill
installer for each agent you use. Once PyPI publication is enabled, installation
will also be available as `uv tool install obsread`.

Check your saved vault with `obsread config show`.

The default vault is independent of your working directory. Resolution order:
`--vault` > `OBSREAD_VAULT` > the saved user setting. There is no automatic switch
to the active Obsidian window and no per-project vault configuration.

Configuration is JSON at:

- Windows: `%APPDATA%/obsread/config.json`
- macOS: `~/Library/Application Support/obsread/config.json`
- Linux: `$XDG_CONFIG_HOME/obsread/config.json` (default `~/.config/obsread/config.json`)

Configure Windows and WSL separately using paths understood by each environment.
Vault paths are personal configuration and are never included in the public skill.

## Read a reference

```sh
obsread '[[Daily/2026-11-25#^ui-hot-reload]]'
obsread '[[Daily/2026-11-25#^ui-hot-reload]]' --parents
obsread '[[2026-11-25#UI 系统]]'
obsread '[[2026-11-25]]'
obsread --vault '/another/vault' '[[Note#^block-id]]'
```

Quote Wikilinks to protect spaces and shell metacharacters. PowerShell and Bash
support the single quotes shown here; CMD requires double quotes.

Given this note:

```markdown
- 游戏开发
  - UI 系统
    - 热更新设计 ^ui-hot-reload
      - 支持服务器动态下发
      - 支持 A/B 测试
    - 其他 UI 设计
```

Reading `[[Note#^ui-hot-reload]]` returns:

```markdown
- 热更新设计
  - 支持服务器动态下发
  - 支持 A/B 测试
```

`--parents` adds the ancestor list items' own content, excluding their other
subtrees. The target ID is removed; descendant IDs and links are preserved.
Only the common indentation is removed. Internal tabs and Markdown are preserved.

The parser uses CommonMark source ranges, with table recognition to avoid treating
table rows as ordinary paragraphs. Supported references:

- Entire notes (only when explicitly requested with `[[Note]]`).
- Top-level ATX and Setext heading sections, including subordinate headings.
- List-item IDs at the end of a paragraph, including unordered, ordered and task
  lists, multiline items, internal blank lines and nested content.
- Ordinary paragraph IDs at the end of the paragraph.

Standalone ID lines, quote/callout IDs, table IDs and heading IDs are unsupported
and produce errors. Relative fragments such as `[[#^id]]` need a source note and
are rejected. Code, HTML blocks, and YAML frontmatter do not supply block IDs.
This is not a complete implementation of every Obsidian Markdown extension.

Names are case-sensitive on all platforms. A basename is searched recursively;
duplicate names are errors. Include a vault-relative directory to disambiguate.
Hidden paths and linked directories are skipped/rejected; resolved files must
remain inside the vault. No links or embeds are expanded.

Successful reads write only Markdown to stdout. Errors leave stdout empty,
write an explanation to stderr, and return a nonzero status. Config and help
commands have their own informational output.

Output defaults to at most **500 lines and 65,536 UTF-8 bytes**. Exceeding either
limit returns an error, never a truncated result. Increase `--max-lines N` and/or
`--max-bytes N` explicitly when a larger result is needed. These are output limits,
not file-size or token limits; parsing may read the entire source file locally.

| Exit code | Meaning |
| --- | --- |
| 0 | Success |
| 2 | Invalid arguments or configuration |
| 3 | Note, heading, or block not found |
| 4 | Ambiguous note, heading, or block |
| 5 | Unsupported structure, invalid Markdown metadata, or invalid UTF-8 |
| 6 | Output exceeds limits |
| 7 | File IO or permission error |

## Agent skills

Install instructions for the agent you use:

```sh
obsread skill install codex
obsread skill install pi
obsread skill install antigravity
```

| Agent | User skill directory | Explicit invocation |
| --- | --- | --- |
| Codex | `~/.agents/skills/obsread` | `$obsread <request and Wikilink>` |
| Pi | `~/.pi/agent/skills/obsread` | `/skill:obsread <request and Wikilink>` |
| Antigravity CLI | `~/.gemini/config/skills/obsread` | `/obsread <request and Wikilink>` |

Pi honors `PI_CODING_AGENT_DIR` when it is set. Antigravity's directory is shared
with its App. Use `obsread skill path pi` (or another agent name) to inspect the
destination without writing anything.

For example, in Pi:

```text
/skill:obsread 请分析 [[2026-11-25#^ui-hot-reload]] 中的设计。
```

Reload skills after installing: Pi uses `/reload`, Antigravity CLI uses
`/skills reload`; start a new agent session if necessary. Codex detects skill
changes automatically; restart it if the skill does not appear.

Codex metadata disables implicit invocation. The Pi installer adds Pi's
`disable-model-invocation: true` frontmatter. Antigravity exposes skills as slash
commands; do not assume Codex's invocation policy controls Antigravity.

The CLI must be on the agent's PATH and the configured vault must be accessible.
Skill discovery and explicit invocation behavior are described in the official
[Codex](https://developers.openai.com/codex/skills),
[Pi](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md)
and [Antigravity](https://antigravity.google/docs/skills) documentation.

Re-running an install with identical files is harmless. If existing files differ,
the installer refuses to overwrite them. Review local changes, then run, for example,
`obsread skill install pi --force` to replace the bundled files. Extra personal
files in the skill folder are preserved. After upgrading the CLI, re-run the skill
installer for each agent you use; installed skills do not silently update.

For manual installation or another compatible agent, download `obsread-skill.zip`
from a GitHub Release and extract its `obsread` folder into that agent's skill
directory. The canonical source is `skills/obsread`; keep its instructions together
with its metadata. Pi's explicit-only field must be added when installing manually.

## Development

```sh
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build --no-sources
```

Tests use temporary vaults and never write to your real notes. CI runs on
Windows, macOS and Linux with Python 3.10 and 3.14.

See [architecture and scope](docs/architecture.md) for implementation decisions,
responsibility boundaries, and deferred features. Usage lives in this README;
skill behavior lives in `skills/obsread/SKILL.md`; acceptance cases live in tests.

## Releases

GitHub Releases are the current distribution channel. PyPI publishing is opt-in
and is disabled while the repository Actions variable `PUBLISH_PYPI` is unset or
not `true`.

Update `project.version` in `pyproject.toml` and refresh `uv.lock`, commit, then
push a matching tag such as `v0.1.0`. The release workflow:

1. Runs the CI checks.
2. Verifies the tag matches the package version and builds the wheel and sdist.
3. Packages the standalone skill as `obsread-skill.zip` and records SHA-256 hashes.
4. Creates a GitHub Release containing distributions, the skill, checksums, and
   first-use instructions from `docs/release-notes.md`.
5. If `PUBLISH_PYPI=true`, also publishes the Python distributions through PyPI
   Trusted Publishing. GitHub publication does not depend on PyPI credentials.

To enable PyPI later, confirm the project name, configure a Trusted Publisher for
GitHub owner `hwei`, repository `obsread`, workflow `release.yml`, and environment
`pypi`, then set the repository variable:

```sh
gh variable set PUBLISH_PYPI --body true --repo hwei/obsread
```

The next version tag will publish to both destinations. The workflow does not
automatically choose versions or publish on every commit.
