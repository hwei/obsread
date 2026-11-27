"""Resolve references and extract original source ranges from Markdown tokens."""

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .errors import ObsreadError

BLOCK_ID = re.compile(r"(?<!\S)\^([A-Za-z0-9-]+)[ \t]*$")
INLINE_IDS = re.compile(r"(?<!\S)\^([A-Za-z0-9-]+)[ \t]*$", re.MULTILINE)
LIST_TYPES = {"bullet_list_open", "ordered_list_open"}


@dataclass
class Reference:
    note: str
    fragment: str | None


def parse_reference(value: str) -> Reference:
    value = value.strip()
    if not value.startswith("[[") or not value.endswith("]]"):
        raise ObsreadError("Expected a quoted Wikilink, for example '[[Note#^block-id]]'.")
    inner = value[2:-2].split("|", 1)[0]
    if any(c in inner for c in "\r\n\x00") or "[[" in inner or "]]" in inner:
        raise ObsreadError("Invalid Wikilink")
    note, separator, fragment = inner.partition("#")
    if not note:
        raise ObsreadError("A source note is required; [[#fragment]] is not supported.")
    if separator and not fragment:
        raise ObsreadError("The heading or block ID must not be empty.")
    if fragment.startswith("^") and not re.fullmatch(r"\^[A-Za-z0-9-]+", fragment):
        raise ObsreadError("Block IDs must contain only letters, digits and hyphens.")
    return Reference(note, fragment if separator else None)


def _is_link(path: Path) -> bool:
    # lstat attributes also detect junctions on Python 3.10/3.11, before is_junction existed.
    return path.is_symlink() or bool(
        getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _io_error(error: OSError) -> None:
    raise error


def find_note(vault: Path, note: str) -> Path:
    # Check Windows drives and UNC paths even when running on Unix.
    if PureWindowsPath(note).drive or note.startswith(("/", "\\")):
        raise ObsreadError("The note path must be relative to the vault.")
    parts = note.replace("\\", "/").split("/")
    if any(not p or p in {".", ".."} or p.startswith(".") for p in parts):
        raise ObsreadError("Empty, hidden, and parent path components are not allowed.")
    parts[-1] += "" if parts[-1].endswith(".md") else ".md"
    matches = []
    if len(parts) > 1:
        current = vault
        for index, part in enumerate(parts):
            # Explicit comparison enforces the same case-sensitive policy on Windows and Unix.
            candidate = next((p for p in current.iterdir() if p.name == part), None)
            if candidate is None:
                raise ObsreadError(f"Note not found: {'/'.join(parts)}", 3)
            if index < len(parts) - 1 and _is_link(candidate):
                raise ObsreadError("Linked directories are not supported.")
            current = candidate
            if index < len(parts) - 1 and not current.is_dir():
                raise ObsreadError(f"Note not found: {'/'.join(parts)}", 3)
        if current.is_file():
            matches.append(current)
    else:
        for root, directories, filenames in os.walk(vault, followlinks=False, onerror=_io_error):
            directories[:] = sorted(
                d for d in directories if not d.startswith(".") and not _is_link(Path(root) / d)
            )
            if parts[0] in filenames:
                matches.append(Path(root) / parts[0])
    if not matches:
        raise ObsreadError(f"Note not found: {note}", 3)
    for path in matches:
        if not path.resolve().is_relative_to(vault.resolve()):
            raise ObsreadError(f"Note resolves outside the vault: {path.relative_to(vault)}")
    if len(matches) > 1:
        candidates = "\n".join(f"  {p.relative_to(vault).as_posix()}" for p in sorted(matches))
        raise ObsreadError(f"Ambiguous note {note!r}; use a vault-relative path:\n{candidates}", 4)
    return matches[0]


@dataclass(eq=False)
class Node:
    token: Token
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)

    @property
    def span(self) -> tuple[int, int]:
        assert self.token.map is not None
        return self.token.map[0], self.token.map[1]

    def ancestors(self):
        current = self.parent
        while current is not None:
            yield current
            current = current.parent


def _parse(source: str) -> tuple[list[Node], int | None]:
    lines = source.splitlines(keepends=True)
    frontmatter_end: int | None = None
    # Frontmatter is metadata, not a paragraph containing Obsidian blocks.
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None)
        if end is None:
            raise ObsreadError("Unclosed YAML frontmatter", 5)
        frontmatter_end = end
        lines[: end + 1] = ["\n"] * (end + 1)
    nodes: list[Node] = []
    stack: list[Node] = []
    for token in MarkdownIt("commonmark").enable("table").parse("".join(lines)):
        if token.nesting == -1:
            stack.pop()
            continue
        node = Node(token, stack[-1] if stack else None)
        if node.parent:
            node.parent.children.append(node)
        nodes.append(node)
        if token.nesting == 1:
            stack.append(node)
    return nodes, frontmatter_end


def _trim(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _dedent(lines: list[str]) -> str:
    # Expand only indentation; tabs within text/code remain unchanged.
    expanded = []
    for line in lines:
        prefix = re.match(r"[ \t]*", line).group()
        expanded.append(prefix.expandtabs(4) + line[len(prefix) :])
    indent = min((len(s) - len(s.lstrip(" ")) for s in expanded if s.strip()), default=0)
    return "\n".join(s[indent:] if s.strip() else "" for s in _trim(expanded)) + "\n"


def _own_lines(node: Node, lines: list[str]) -> list[str]:
    start, end = node.span
    excluded = set()
    for child in node.children:
        if child.token.type in LIST_TYPES:
            a, b = child.span
            excluded.update(range(a, b))
    return _trim([lines[i] for i in range(start, end) if i not in excluded])


def _text_ids(content: str) -> list[tuple[str, int]]:
    """Locate line-end IDs outside escapes and inline code.

    Inline token maps cover paragraphs, not individual spans. Recording this
    rule's source offsets also handles multiline code spans without guessing rows.
    """
    if not INLINE_IDS.search(content):
        return []
    found = []

    def track(state, silent):
        match = INLINE_IDS.match(state.src, state.pos)
        if match is None:
            return False
        if not silent:
            found.append((match[1], content.count("\n", 0, match.start())))
            state.push("text", "", 0).content = match[0]
        state.pos = match.end()
        return True

    parser = MarkdownIt("commonmark")
    parser.inline.ruler.before("text", "obsread_id", track)
    parser.parseInline(content)
    return found


def _is_closing_fence(line: str, markup: str) -> bool:
    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3 or not stripped.startswith(markup):
        return False
    rest = stripped[len(markup) :]
    return not rest.rstrip(" \t").lstrip(markup[0])


def _is_unclosed_fence(node: Node, lines: list[str]) -> bool:
    if node.token.type != "fence" or node.token.map is None:
        return False
    start, end = node.span
    return end == len(lines) and (
        end - start <= 1 or not _is_closing_fence(lines[end - 1], node.token.markup)
    )


def _diagnose_missing_block_id(
    lines: list[str],
    nodes: list[Node],
    frontmatter_end: int | None,
    block_id: str,
) -> str:
    raw_rows = [
        i for i, line in enumerate(lines) if (m := BLOCK_ID.search(line)) and m[1] == block_id
    ]
    if not raw_rows:
        return f"Block not found: ^{block_id}"
    row = raw_rows[0]
    line_no = row + 1
    if frontmatter_end is not None and row <= frontmatter_end:
        return (
            f"Block not found: ^{block_id} "
            f"(found on line {line_no} inside YAML frontmatter; "
            "frontmatter does not supply block IDs)"
        )
    for node in nodes:
        if node.token.type not in {"fence", "code_block", "html_block"} or node.token.map is None:
            continue
        start, end = node.span
        if not (start <= row < end):
            continue
        start_line = start + 1
        if node.token.type == "fence":
            if _is_unclosed_fence(node, lines):
                return (
                    f"Block not found: ^{block_id} "
                    f"(found on line {line_no} inside an unclosed fenced code block starting at "
                    f"line {start_line}; check for a missing closing fence or broken list-item "
                    "indentation above it)"
                )
            return (
                f"Block not found: ^{block_id} "
                f"(found on line {line_no} inside a fenced code block starting at line "
                f"{start_line}; code blocks do not supply block IDs)"
            )
        kind = "an indented code block" if node.token.type == "code_block" else "an HTML block"
        return (
            f"Block not found: ^{block_id} "
            f"(found on line {line_no} inside {kind} starting at line {start_line}; "
            "it does not supply block IDs)"
        )
    return (
        f"Block not found: ^{block_id} "
        f"(found on line {line_no} inside inline code or escaped text; "
        "it does not supply a block ID)"
    )


def extract(source: str, fragment: str | None, parents: bool = False) -> str:
    source = source.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if fragment is None:
        if parents:
            raise ObsreadError("--parents requires a list block reference.")
        return source if not source or source.endswith("\n") else source + "\n"
    lines = source.splitlines()
    nodes, frontmatter_end = _parse(source)
    if not fragment.startswith("^"):
        if parents:
            raise ObsreadError("--parents requires a list block reference.")
        headings = [n for n in nodes if n.token.type == "heading_open" and n.parent is None]
        matched = []
        for heading in headings:
            inline = heading.children[0].token
            visible = "".join(
                t.content
                for t in inline.children or []
                if t.type in {"text", "code_inline", "image"}
            )
            if fragment in {inline.content, visible}:
                matched.append(heading)
        if not matched:
            unclosed = next((n for n in nodes if _is_unclosed_fence(n, lines)), None)
            if unclosed and any(
                fragment in lines[i] for i in range(unclosed.span[0] + 1, unclosed.span[1])
            ):
                raise ObsreadError(
                    f"Heading not found: {fragment} "
                    f"(note: an unclosed fenced code block starts at line {unclosed.span[0] + 1}; "
                    "check for a missing closing fence or broken list-item indentation)",
                    3,
                )
            raise ObsreadError(f"Heading not found: {fragment}", 3)
        if len(matched) != 1:
            raise ObsreadError(f"Ambiguous heading: {fragment}", 4)
        target = matched[0]
        end = next(
            (
                h.span[0]
                for h in headings
                if h.span[0] > target.span[0] and h.token.tag <= target.token.tag
            ),
            len(lines),
        )
        return "\n".join(_trim(lines[target.span[0] : end])) + "\n"

    block_id = fragment[1:]
    matched = []
    for node in nodes:
        if node.token.type != "inline" or not node.token.children:
            continue
        for found_id, offset in _text_ids(node.token.content):
            if found_id != block_id:
                continue
            mapped = (
                node if node.token.map else next((a for a in node.ancestors() if a.token.map), None)
            )
            if mapped is None:
                raise ObsreadError("The block has no reliable source range.", 5)
            row = mapped.span[0] + offset
            raw_match = BLOCK_ID.search(lines[row])
            if raw_match and raw_match[1] == block_id:
                matched.append((node, row, raw_match))
    if not matched:
        raise ObsreadError(_diagnose_missing_block_id(lines, nodes, frontmatter_end, block_id), 3)
    if len(matched) != 1:
        raise ObsreadError(f"Ambiguous block ID: ^{block_id}", 4)
    inline, row, match = matched[0]
    ancestors = list(inline.ancestors())
    if inline.parent.token.type != "paragraph_open" or any(
        a.token.type in {"blockquote_open", "table_open"} for a in ancestors
    ):
        raise ObsreadError("This block structure is not supported (quote, table, or heading).", 5)
    if inline.token.content.strip() == fragment:
        raise ObsreadError("Standalone block IDs are not supported in this version.", 5)
    item = next((n for n in ancestors if n.token.type == "list_item_open"), None)
    if item is None and row != inline.span[1] - 1:
        raise ObsreadError("A paragraph ID must be at the end of its last line.", 5)
    target = item or inline.parent
    if parents and item is None:
        raise ObsreadError("--parents requires a list block reference.")
    lines[row] = lines[row][: match.start()].rstrip(" \t")
    output = []
    if parents:
        chain = [n for n in target.ancestors() if n.token.type == "list_item_open"]
        for ancestor in reversed(chain):
            output.extend(_own_lines(ancestor, lines))
    output.extend(lines[target.span[0] : target.span[1]])
    return _dedent(output)


def read_reference(
    vault: Path,
    reference: str,
    *,
    parents: bool = False,
    max_lines: int = 500,
    max_bytes: int = 65536,
) -> str:
    ref = parse_reference(reference)
    path = find_note(vault, ref.note)
    try:
        source = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise ObsreadError(f"Note is not valid UTF-8: {path}", 5) from exc
    output = extract(source, ref.fragment, parents)
    line_count, byte_count = len(output.splitlines()), len(output.encode("utf-8"))
    if line_count > max_lines or byte_count > max_bytes:
        raise ObsreadError(
            f"Output exceeds limits: {line_count} lines, {byte_count} UTF-8 bytes "
            f"(limits: {max_lines}, {max_bytes}). "
            "Increase --max-lines or --max-bytes explicitly.",
            6,
        )
    return output
