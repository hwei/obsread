"""Install bundled instructions into an explicitly selected agent's user directory."""

import os
from importlib import resources
from pathlib import Path

from .errors import ObsreadError

AGENTS = ("codex", "pi", "antigravity")
INVOCATIONS = {"codex": "$obsread", "pi": "/skill:obsread", "antigravity": "/obsread"}


def skill_destination(agent: str) -> Path:
    home = Path.home()
    if agent == "codex":
        return home / ".agents/skills/obsread"
    if agent == "pi":
        return Path(os.environ.get("PI_CODING_AGENT_DIR") or home / ".pi/agent") / "skills/obsread"
    if agent == "antigravity":
        return home / ".gemini/config/skills/obsread"
    raise ObsreadError(f"Unknown agent: {agent}")


def bundled_files(agent: str) -> dict[str, bytes]:
    root = resources.files("obsread").joinpath("_skill")
    if not root.joinpath("SKILL.md").is_file():
        # Editable checkouts retain the canonical skill outside the Python package.
        root = Path(__file__).resolve().parents[2] / "skills/obsread"
    if not root.joinpath("SKILL.md").is_file():
        raise ObsreadError("Bundled skill is missing; reinstall obsread.", 7)
    content = root.joinpath("SKILL.md").read_text(encoding="utf-8")
    if agent == "pi":
        # Pi's explicit-only switch lives in SKILL.md rather than Codex's metadata.
        content = content.replace("---\n", "---\ndisable-model-invocation: true\n", 1)
    return {
        "SKILL.md": content.encode("utf-8"),
        "agents/openai.yaml": root.joinpath("agents").joinpath("openai.yaml").read_bytes(),
    }


def install_skill(agent: str, *, force: bool = False) -> Path:
    destination = skill_destination(agent)
    files = bundled_files(agent)
    if destination.exists() and not destination.is_dir():
        raise ObsreadError(f"Skill destination is not a directory: {destination}")
    metadata = destination / "agents"
    if metadata.exists() and not metadata.is_dir():
        raise ObsreadError(f"Skill metadata destination is not a directory: {metadata}")
    # Check all conflicts before writing anything. Extra user files are left alone.
    for name, content in files.items():
        target = destination / name
        if target.exists():
            if not target.is_file():
                raise ObsreadError(f"Skill destination is not a file: {target}")
            if target.read_bytes() != content and not force:
                raise ObsreadError(
                    f"Existing skill differs: {target}. "
                    "Review local changes, then use --force to replace the bundled files."
                )
    for name, content in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != content:
            target.write_bytes(content)
    return destination
