import os
import subprocess
from pathlib import Path

import pytest

from obsread.errors import ObsreadError
from obsread.reader import extract, find_note, parse_reference, read_reference

TREE = """- 游戏开发
  - 资源管理系统
  - UI 系统
    - 热更新设计 ^ui-hot-reload
      - UI 应当是独立的声明式资源
      - 支持服务器动态下发
      - 支持 A/B 测试
    - 其他 UI 设计
  - 战斗系统
"""
SUBTREE = """- 热更新设计
  - UI 应当是独立的声明式资源
  - 支持服务器动态下发
  - 支持 A/B 测试
"""


def assert_error(code, function, *args, **kwargs):
    with pytest.raises(ObsreadError) as error:
        function(*args, **kwargs)
    assert error.value.code == code


def test_design_subtree_and_parents():
    assert extract(TREE, "^ui-hot-reload") == SUBTREE
    assert extract(TREE, "^ui-hot-reload", parents=True) == (
        "- 游戏开发\n  - UI 系统\n" + "".join("    " + s + "\n" for s in SUBTREE.splitlines())
    )


@pytest.mark.parametrize("marker", ["-", "*", "+", "1.", "12)", "- [ ]", "- [x]"])
def test_leaf_and_list_marker(marker):
    assert extract(f"{marker} target ^id\n\n{marker} sibling\n", "^id") == f"{marker} target\n"


def test_multiline_loose_item_and_nested_code():
    source = """- parent
  - target ^id
    continuation

    second paragraph

    ```python
    print('keep ^fake')
    ```

    - child ^child

  - sibling

outside
"""
    assert extract(source, "^id") == (
        "- target\n  continuation\n\n  second paragraph\n\n"
        "  ```python\n  print('keep ^fake')\n  ```\n\n  - child ^child\n"
    )
    assert_error(3, extract, source, "^fake")


def test_lazy_continuation_and_following_paragraph_boundary():
    assert extract("- target ^id\nlazy continuation\n\noutside\n", "^id") == (
        "- target\nlazy continuation\n"
    )
    assert extract("- target\nlazy continuation ^id\n\noutside\n", "^id") == (
        "- target\nlazy continuation\n"
    )


def test_paragraph_and_unicode_line_endings():
    assert extract("\ufefffirst\r\nsecond ^id\r\n\r\nother\r\n", "^id") == "first\nsecond\n"


def test_tabs_are_interpreted_by_parser_and_internal_tabs_preserved():
    assert extract("- parent\n\t- target ^id\n\t  - child\n\t- sibling\n", "^id") == (
        "- target\n  - child\n"
    )
    assert extract("- a\tb ^id\n", "^id") == "- a\tb\n"


def test_mixed_indentation():
    assert extract("- parent\n \t- target ^id\n \t  - child\n \t- sibling\n", "^id") == (
        "- target\n  - child\n"
    )


def test_parent_own_content_not_other_subtrees():
    source = """- parent
  continuation

  second paragraph

  - before
    - hidden
  - target ^id
    - kept
  - after
"""
    assert extract(source, "^id", True) == (
        "- parent\n  continuation\n\n  second paragraph\n  - target\n    - kept\n"
    )


@pytest.mark.parametrize(
    "source",
    [
        "```md\n- fake ^id\n```\n",
        "    fake ^id\n",
        "`literal ^id`\n",
        "literal \\^id\n",
        "<!--\nfake ^id\n-->\n",
        "---\nproperty: fake ^id\n---\nbody\n",
    ],
)
def test_fake_ids_are_not_blocks(source):
    assert_error(3, extract, source, "^id")


@pytest.mark.parametrize(
    "source",
    [
        "paragraph\n\n^id\n",
        "> paragraph ^id\n",
        "- item\n  > quoted ^id\n",
        "# heading ^id\n",
        "| Column |\n| --- |\n| cell ^id |\n",
        "| Column |\n| --- |\ncell ^id\n",
    ],
)
def test_unsupported_blocks_never_fall_back(source):
    # A table cell ending in a pipe is not an Obsidian line-end ID.
    code = 3 if source.endswith("|\n") else 5
    assert_error(code, extract, source, "^id")


def test_duplicate_id_and_code_decoy():
    assert_error(4, extract, "a ^id\n\nb ^id\n", "^id")
    assert extract("```\nfake ^id\n```\n\na ^id\n", "^id") == "a\n"


def test_multiline_inline_code_cannot_supply_id_or_shift_real_id():
    source = "- `code\n  fake ^id\n  more` real ^id\n  - child\n"
    assert extract(source, "^id") == "- `code\n  fake ^id\n  more` real\n  - child\n"
    assert_error(3, extract, "- `code\n  fake ^id\n  more`\n", "^id")


def test_nonterminal_paragraph_id_is_rejected():
    assert_error(5, extract, "first ^id\nsecond\n", "^id")


def test_heading_section_and_nested_heading():
    source = "# Before\nno\n## Target\ntext\n### Child\nchild\n## Next\nhidden\n"
    assert extract(source, "Target") == "## Target\ntext\n### Child\nchild\n"
    assert extract("Title\n===\ntext\n\nOther\n===\nhidden\n", "Title") == "Title\n===\ntext\n"
    assert extract("# **Formatted** heading\nbody\n", "Formatted heading") == (
        "# **Formatted** heading\nbody\n"
    )


def test_quote_and_code_headings_do_not_end_section():
    source = "## Target\n> # Quote\n\n```md\n# Code\n```\n\n## Next\n"
    assert extract(source, "Target") == "## Target\n> # Quote\n\n```md\n# Code\n```\n"


def test_heading_errors():
    assert_error(4, extract, "# Same\na\n## Same\nb\n", "Same")
    assert_error(3, extract, "body\n", "missing")
    assert_error(2, extract, "# Heading\n", "Heading", parents=True)
    assert_error(2, extract, "body ^id\n", "^id", parents=True)
    assert_error(5, extract, "---\nunclosed\n", "^id")


def test_whole_note_and_links_preserved():
    assert extract("[[Other]]\n![[Image]]", None) == "[[Other]]\n![[Image]]\n"
    assert extract("", None) == ""
    assert_error(2, extract, "body", None, parents=True)
    assert extract("- [[Other]] ^id\n  - child ^child\n", "^id") == (
        "- [[Other]]\n  - child ^child\n"
    )


def test_reference_alias_and_extension():
    ref = parse_reference("[[目录/中文 Note.md#^id|别名]]")
    assert (ref.note, ref.fragment) == ("目录/中文 Note.md", "^id")
    assert parse_reference("[[Note]]").fragment is None


@pytest.mark.parametrize(
    "reference", ["Note", "[[#^id]]", "[[Note#]]", "[[Note#^]]", "[[Note#^has space]]", "[[N\nx]]"]
)
def test_bad_reference(reference):
    assert_error(2, parse_reference, reference)


def write(vault: Path, name: str, source: str = "text ^id\n") -> Path:
    path = vault / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_duplicate_filenames_and_relative_path(tmp_path):
    write(tmp_path, "A/Note.md")
    write(tmp_path, "B/Note.md")
    assert_error(4, read_reference, tmp_path, "[[Note#^id]]")
    assert read_reference(tmp_path, "[[A/Note#^id]]") == "text\n"
    assert_error(3, read_reference, tmp_path, "[[A/note#^id]]")
    assert_error(3, read_reference, tmp_path, "[[missing]]")


@pytest.mark.parametrize(
    "name", ["../Note", "/Note", "C:/Note", "C:Note", "A/../Note", ".git/Note"]
)
def test_path_escape(tmp_path, name):
    assert_error(2, find_note, tmp_path, name)


def test_hidden_directories_and_exact_case(tmp_path):
    write(tmp_path, ".obsidian/Note.md")
    write(tmp_path, "A/Note.md")
    assert read_reference(tmp_path, "[[Note#^id]]") == "text\n"
    assert_error(3, find_note, tmp_path, "note")
    assert_error(3, find_note, tmp_path, "a/Note")


def test_symlinks_and_real_path_boundaries(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = write(tmp_path, "outside/Note.md")
    try:
        (vault / "Outside.md").symlink_to(outside)
        (vault / "Linked").symlink_to(outside.parent, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit creating symlinks")
    assert_error(2, find_note, vault, "Outside")
    assert_error(3, find_note, vault, "Note")
    assert_error(2, find_note, vault, "Linked/Note")


def test_limits_apply_to_output_not_file(tmp_path):
    write(tmp_path, "Note.md", "noise\n\n" * 1000 + "- small ^id\n")
    assert read_reference(tmp_path, "[[Note#^id]]", max_lines=1, max_bytes=8) == "- small\n"
    assert_error(6, read_reference, tmp_path, "[[Note]]")
    assert_error(6, read_reference, tmp_path, "[[Note#^id]]", max_bytes=7)
    write(tmp_path, "中文.md", "中文 ^id\n")
    assert_error(6, read_reference, tmp_path, "[[中文#^id]]", max_bytes=6)


@pytest.mark.skipif(os.name != "nt", reason="Windows junctions")
def test_windows_junctions_are_not_traversed(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    outside = write(tmp_path, "outside/Note.md")
    junction = vault / "Linked"
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside.parent)],
        capture_output=True,
    )
    assert result.returncode == 0
    assert_error(3, find_note, vault, "Note")
    assert_error(2, find_note, vault, "Linked/Note")
    assert outside.exists()


def test_bom_crlf_and_invalid_utf8(tmp_path):
    (tmp_path / "Note.md").write_bytes(b"\xef\xbb\xbfline ^id\r\n\r\nother\r\n")
    assert read_reference(tmp_path, "[[Note.md#^id]]") == "line\n"
    (tmp_path / "Bad.md").write_bytes(b"\xff")
    assert_error(5, read_reference, tmp_path, "[[Bad]]")


def test_missing_block_diagnostics_for_unclosed_fence_and_code():
    broken_list_fence = "- ```\n  body\n\nhttps://example.com\n  ```\n- target ^id\n## Heading\n"
    with pytest.raises(ObsreadError) as err:
        extract(broken_list_fence, "^id")
    assert err.value.code == 3
    assert "line 6" in str(err.value)
    assert "unclosed fenced code block starting at line 5" in str(err.value)

    with pytest.raises(ObsreadError) as heading_err:
        extract(broken_list_fence, "Heading")
    assert heading_err.value.code == 3
    assert "unclosed fenced code block starts at line 5" in str(heading_err.value)

    with pytest.raises(ObsreadError) as closed_err:
        extract("```md\n- fake ^id\n```\n", "^id")
    assert closed_err.value.code == 3
    assert "fenced code block starting at line 1" in str(closed_err.value)
    assert "unclosed" not in str(closed_err.value)

    with pytest.raises(ObsreadError) as fm_err:
        extract("---\nprop: ^id\n---\nbody\n", "^id")
    assert fm_err.value.code == 3
    assert "line 2 inside YAML frontmatter" in str(fm_err.value)

    with pytest.raises(ObsreadError) as inline_err:
        extract("`code ^id\nmore`\n", "^id")
    assert inline_err.value.code == 3
    assert "line 1 inside inline code or escaped text" in str(inline_err.value)
