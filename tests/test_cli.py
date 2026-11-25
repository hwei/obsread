import json
import os
import subprocess
import sys

import pytest

from obsread import config
from obsread.cli import main
from obsread.errors import ObsreadError


@pytest.fixture
def setup(tmp_path, monkeypatch):
    vault = tmp_path / "中文 vault"
    vault.mkdir()
    (vault / "Note.md").write_text("- target ^id\n  - child\n- sibling\n", encoding="utf-8")
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config/config.json")
    monkeypatch.delenv("OBSREAD_VAULT", raising=False)
    return vault


def test_config_set_persists_absolute_path(setup, capsys, monkeypatch, tmp_path):
    assert main(["config", "set", "vault", str(setup)]) == 0
    capsys.readouterr()
    monkeypatch.chdir(tmp_path)
    assert main(["[[Note#^id]]"]) == 0
    captured = capsys.readouterr()
    assert captured.out == "- target\n  - child\n"
    assert captured.err == ""
    assert main(["config", "show"]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["config"]["vault"] == str(setup.resolve())


def test_precedence_and_broken_config_override(setup, monkeypatch, tmp_path):
    missing = str(tmp_path / "missing")
    config.set_vault(str(setup))
    monkeypatch.setenv("OBSREAD_VAULT", missing)
    assert config.resolve_vault(str(setup)) == setup.resolve()
    with pytest.raises(ObsreadError):
        config.resolve_vault()
    monkeypatch.setenv("OBSREAD_VAULT", str(setup))
    config.config_path().write_text("bad json", encoding="utf-8")
    assert config.resolve_vault() == setup.resolve()


@pytest.mark.parametrize("value", ["[]", '{"vault": 7}', '{"vault": ""}', "{bad"])
def test_invalid_config_errors_are_clean(setup, capsys, value):
    config.config_path().parent.mkdir()
    config.config_path().write_text(value, encoding="utf-8")
    assert main(["[[Note]]"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "configuration" in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "args,code",
    [
        (["[[Missing]]"], 3),
        (["[[Note#^missing]]"], 3),
        (["[[Note#^id]]", "--max-lines", "1"], 6),
        (["[[Note]]", "--parents"], 2),
    ],
)
def test_failure_stdout_is_empty(setup, capsys, args, code):
    assert main(["--vault", str(setup), *args]) == code
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("obsread: ")


def test_missing_config_and_io_failure(setup, capsys, monkeypatch):
    assert main(["[[Note]]"]) == 2
    assert "config set vault" in capsys.readouterr().err

    def denied(*args):
        raise PermissionError("denied")

    monkeypatch.setattr(config, "load_config", denied)
    assert main(["[[Note]]"]) == 7
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "denied" in captured.err


@pytest.mark.parametrize("value", ["0", "-1", "abc"])
def test_invalid_limit(setup, capsys, value):
    with pytest.raises(SystemExit) as error:
        main(["--vault", str(setup), "[[Note]]", "--max-lines", value])
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "positive integer" in captured.err


def test_real_cli_utf8_pipes_and_exit_codes(setup):
    (setup / "中文.md").write_text("- 中文内容 ^id\n  - 子项\n", encoding="utf-8")
    env = {**os.environ, "OBSREAD_VAULT": str(setup), "PYTHONIOENCODING": "ascii"}
    result = subprocess.run(
        [sys.executable, "-m", "obsread", "[[中文#^id]]"], capture_output=True, env=env
    )
    assert result.returncode == 0
    assert result.stdout.decode("utf-8") == "- 中文内容\n  - 子项\n"
    assert result.stderr == b""
    failed = subprocess.run(
        [sys.executable, "-m", "obsread", "[[中文#^missing]]"], capture_output=True, env=env
    )
    assert failed.returncode == 3
    assert failed.stdout == b""
    assert b"Traceback" not in failed.stderr
