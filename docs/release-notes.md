Install the CLI, choose your vault, and install the skill for your agent:

```sh
uv tool install '{{WHEEL_URL}}'
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

PyPI publishing is not enabled yet. Packages are available from this GitHub Release.
For a different version, use its wheel download URL.

Upgrading? Run `uv tool install --reinstall '<new release wheel URL>'`, then re-run
`obsread skill install AGENT` for each agent you use. Review differing local skill
files before using `--force`.

For manual skill installation, download `obsread-skill.zip` below. See the README
for configuration, supported structures, and each agent's invocation policy.
