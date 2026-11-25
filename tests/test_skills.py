from pathlib import Path

import pytest

from obsread import skills
from obsread.cli import main
from obsread.errors import ObsreadError


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    return tmp_path


@pytest.mark.parametrize(
    "agent,relative",
    [
        ("codex", ".agents/skills/obsread"),
        ("pi", ".pi/agent/skills/obsread"),
        ("antigravity", ".gemini/config/skills/obsread"),
    ],
)
def test_user_install_and_idempotency(home, agent, relative):
    expected = home / relative
    assert not expected.exists()
    assert skills.install_skill(agent) == expected
    source = (expected / "SKILL.md").read_text(encoding="utf-8")
    assert "name: obsread" in source
    assert ("disable-model-invocation: true" in source) == (agent == "pi")
    assert "allow_implicit_invocation: false" in (expected / "agents/openai.yaml").read_text(
        encoding="utf-8"
    )
    written = (expected / "SKILL.md").stat().st_mtime_ns
    assert skills.install_skill(agent) == expected
    assert (expected / "SKILL.md").stat().st_mtime_ns == written
    assert not list(home.rglob("AGENTS.md"))


def test_pi_config_directory_override(home, monkeypatch):
    custom = home / "custom-pi"
    monkeypatch.setenv("PI_CODING_AGENT_DIR", str(custom))
    assert skills.install_skill("pi") == custom / "skills/obsread"


def test_conflict_checked_before_any_writes_and_force_preserves_extra_files(home):
    destination = skills.skill_destination("codex")
    destination.mkdir(parents=True)
    custom = destination / "SKILL.md"
    custom.write_text("local instructions", encoding="utf-8")
    extra = destination / "my-notes.md"
    extra.write_text("personal notes", encoding="utf-8")
    with pytest.raises(ObsreadError, match="--force"):
        skills.install_skill("codex")
    assert custom.read_text(encoding="utf-8") == "local instructions"
    assert not (destination / "agents").exists()
    skills.install_skill("codex", force=True)
    assert "name: obsread" in custom.read_text(encoding="utf-8")
    assert extra.read_text(encoding="utf-8") == "personal notes"


def test_skill_cli_does_not_require_a_vault_or_create_path_on_inspection(home, capsys):
    assert main(["skill", "path", "pi"]) == 0
    assert str(home / ".pi/agent/skills/obsread") in capsys.readouterr().out
    assert not (home / ".pi").exists()
    assert main(["skill", "install", "pi"]) == 0
    captured = capsys.readouterr()
    assert "/skill:obsread" in captured.out
    assert captured.err == ""
