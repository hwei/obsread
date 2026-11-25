# obsread

Read an Obsidian Wikilink from local Markdown and return only the requested note,
heading section, or block subtree. Obsidian does not need to be running.

Python 3.10+ is required. The project is under local development; a public package
and release have not been published yet.

## Install and configure

From a checkout, install an isolated command with [uv](https://docs.astral.sh/uv/):

```sh
uv tool install .
obsread config set vault '/absolute/path/to/your/vault'
obsread config show
```

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

## Explicit Codex skill

Copy `skills/obsread` into the user skill directory. In PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME/.agents/skills" | Out-Null
Copy-Item -Recurse ./skills/obsread "$HOME/.agents/skills/obsread"
```

On macOS/Linux:

```sh
mkdir -p ~/.agents/skills
cp -R skills/obsread ~/.agents/skills/obsread
```

If it is already installed, update that existing folder rather than nesting a
second copy inside it. In Codex, invoke it explicitly:

```text
$obsread 请分析 [[2026-11-25#^ui-hot-reload]] 中的设计。
```

The skill disables implicit invocation in its Codex metadata. No `AGENTS.md`
changes are required. The CLI must be on the agent's PATH and the configured
vault must be accessible. Other agents can use the same CLI; skill installation
and explicit invocation syntax depend on that agent.

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

## Releases

Before the first public release, choose a license, create the GitHub repository,
confirm the PyPI project name, and configure a PyPI Trusted Publisher for this
repository's `release.yml` workflow and `pypi` environment. Source publication
and package publication are separate setup steps.

Update `project.version` in `pyproject.toml` and refresh `uv.lock`, commit, then
push a matching tag such as `v0.1.0`. The release workflow:

1. Runs the CI checks.
2. Verifies the tag matches the package version and builds the wheel and sdist.
3. Packages the standalone skill as `obsread-skill.zip` and records SHA-256 hashes.
4. Publishes the Python distributions through PyPI Trusted Publishing.
5. Creates a GitHub Release containing distributions, the skill, and checksums.

After a public PyPI release, installation will be `uv tool install obsread`.
The workflow does not automatically choose versions or publish on every commit.
