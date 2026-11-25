import argparse
import json
import sys
from importlib.metadata import version

from .config import config_path, load_config, resolve_vault, set_vault
from .errors import ObsreadError
from .reader import read_reference
from .skills import AGENTS, INVOCATIONS, install_skill, skill_destination


def positive_int(value: str) -> int:
    try:
        number = int(value)
        if number > 0:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("must be a positive integer")


def _config(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="obsread config")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("show", help="Show the user config file and saved values")
    setter = commands.add_parser("set", help="Save a default vault")
    setter.add_argument("key", choices=["vault"])
    setter.add_argument("value")
    args = parser.parse_args(argv)
    if args.command == "show":
        print(json.dumps({"path": str(config_path()), "config": load_config()}, ensure_ascii=False))
    else:
        path = set_vault(args.value)
        print(f"Saved default vault in {path}")
    return 0


def _skill(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="obsread skill")
    commands = parser.add_subparsers(dest="command", required=True)
    installer = commands.add_parser("install", help="Install the bundled skill for an agent")
    installer.add_argument("agent", choices=AGENTS)
    installer.add_argument("--force", action="store_true", help="Replace differing bundled files")
    path = commands.add_parser("path", help="Show the agent's user skill destination")
    path.add_argument("agent", choices=AGENTS)
    args = parser.parse_args(argv)
    if args.command == "path":
        print(skill_destination(args.agent))
    else:
        destination = install_skill(args.agent, force=args.force)
        print(f"Installed obsread skill for {args.agent}: {destination}")
        print(f"Invoke with {INVOCATIONS[args.agent]} followed by your request and Wikilink.")
        print("Reload skills or start a new agent session to pick up the installation.")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Console entry points use UTF-8 even when the Windows console code page differs.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", newline="\n")
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] == "config":
            return _config(argv[1:])
        if argv and argv[0] == "skill":
            return _skill(argv[1:])
        parser = argparse.ArgumentParser(
            description="Read a precise Obsidian Wikilink from local Markdown.",
            epilog=(
                "Set a default vault: obsread config set vault PATH. "
                "Agent integration: obsread skill install {codex,pi,antigravity}. "
                "Inspect a skill destination: obsread skill path AGENT."
            ),
        )
        parser.add_argument("reference", help="Quoted [[Note]], [[Note#Heading]], or [[Note#^id]]")
        parser.add_argument("--vault", help="Override the configured vault")
        parser.add_argument("--parents", action="store_true", help="Include list ancestors")
        parser.add_argument("--max-lines", type=positive_int, default=500)
        parser.add_argument("--max-bytes", type=positive_int, default=65536)
        parser.add_argument("--version", action="version", version=f"obsread {version('obsread')}")
        args = parser.parse_args(argv)
        output = read_reference(
            resolve_vault(args.vault),
            args.reference,
            parents=args.parents,
            max_lines=args.max_lines,
            max_bytes=args.max_bytes,
        )
        sys.stdout.write(output)
        return 0
    except ObsreadError as exc:
        print(f"obsread: {exc}", file=sys.stderr)
        return exc.code
    except OSError as exc:
        print(f"obsread: {exc}", file=sys.stderr)
        return 7


if __name__ == "__main__":
    raise SystemExit(main())
