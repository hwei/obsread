Install the CLI from PyPI, choose your vault, and install the skill for your agent:

```sh
uv tool install obsread
obsread config set vault '/absolute/path/to/your/vault'
obsread skill install codex
```

Use `pi` or `antigravity` instead of `codex` if needed. Skills are bundled with the
CLI; no repository checkout or `AGENTS.md` edits are required.

Invoke explicitly with `$obsread` in Codex, `/skill:obsread` in Pi, or `/obsread`
in Antigravity CLI, followed by your request and a quoted Obsidian Wikilink such
as `[[Note#^block-id]]`. In a shell command, quote the Wikilink; inside the agent's
prompt, use the reference directly. Reload skills or start a new session after
installation.

To install directly from this GitHub Release wheel instead of PyPI:

```sh
uv tool install '{{WHEEL_URL}}'
```

Upgrading? Run `uv tool upgrade obsread` (or `uv tool install --reinstall '{{WHEEL_URL}}'`),
then re-run `obsread skill install AGENT` for each agent you use. Review differing
local skill files before using `--force`.

For manual skill installation, download `obsread-skill.zip` below. See the README
for configuration, supported structures, and each agent's invocation policy.
