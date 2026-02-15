"""Tests for mcp_server/apple_docs.py — pure functions and tool registration."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from mcp_server.apple_docs import (
    _chunk_markdown,
    _parse_search_results,
    _read_section,
    _slugify,
    register_apple_docs_tools,
)


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_heading(self):
        assert _slugify("NavigationStack") == "navigationstack"

    def test_heading_with_spaces(self):
        # Spaces are dropped by _slugify (not converted to dashes)
        assert _slugify("Navigation Stack Overview") == "navigationstackoverview"

    def test_heading_with_special_chars(self):
        # Non-alnum, non-slash/hyphen/underscore chars are dropped
        assert _slugify("@Observable macro") == "observablemacro"

    def test_preserves_hyphens_and_underscores(self):
        assert _slugify("some-thing_else") == "some-thing-else"

    def test_collapses_double_dashes(self):
        assert _slugify("a -- b") == "a-b"

    def test_strips_leading_trailing_dashes(self):
        assert _slugify("-hello-") == "hello"

    def test_empty_string_returns_section(self):
        assert _slugify("") == "section"

    def test_all_special_chars(self):
        assert _slugify("!!!") == "section"

    def test_slash_becomes_dash(self):
        assert _slugify("documentation/swiftui") == "documentation-swiftui"


# ---------------------------------------------------------------------------
# _parse_search_results
# ---------------------------------------------------------------------------


class TestParseSearchResults:
    def test_normal_output(self):
        output = textwrap.dedent("""\
            SwiftUI: NavigationStack — docs/apple/swiftui.md#navigationstack
            Foundation: Observable — docs/apple/foundation.md#observable
        """)
        results = _parse_search_results(output)
        assert len(results) == 2
        assert results[0] == {
            "title": "SwiftUI",
            "heading": "NavigationStack",
            "path": "docs/apple/swiftui.md",
            "anchor": "navigationstack",
        }
        assert results[1]["title"] == "Foundation"
        assert results[1]["anchor"] == "observable"

    def test_skips_docindex_info_lines(self):
        output = "[docindex] Loaded 142 entries\nSwiftUI: View — docs/swiftui.md#view"
        results = _parse_search_results(output)
        assert len(results) == 1
        assert results[0]["heading"] == "View"

    def test_no_anchor(self):
        output = "SwiftUI: Overview — docs/apple/swiftui.md"
        results = _parse_search_results(output)
        assert len(results) == 1
        assert results[0]["anchor"] == ""
        assert results[0]["path"] == "docs/apple/swiftui.md"

    def test_empty_output(self):
        assert _parse_search_results("") == []
        assert _parse_search_results("\n\n") == []

    def test_malformed_lines_skipped(self):
        output = "no separator here\nSwiftUI: View — docs/swiftui.md#view\nalso bad"
        results = _parse_search_results(output)
        assert len(results) == 1

    def test_no_heading_colon(self):
        # "TitleOnly — path#anchor" — no ": " separator in the label
        output = "TitleOnly — docs/foo.md#bar"
        results = _parse_search_results(output)
        assert len(results) == 1
        assert results[0]["title"] == "TitleOnly"
        assert results[0]["heading"] == ""


# ---------------------------------------------------------------------------
# _read_section
# ---------------------------------------------------------------------------


class TestReadSection:
    def _write_md(self, tmp_path: Path, content: str) -> Path:
        f = tmp_path / "doc.md"
        f.write_text(textwrap.dedent(content))
        return f

    def test_reads_section_by_anchor_tag(self, tmp_path):
        md = self._write_md(tmp_path, """\
            # Top
            Preamble

            <a id="nav-stack">
            ## NavigationStack
            Content about navigation.
            More content.

            ## Other Section
            Other stuff.
        """)
        section = _read_section(md, "nav-stack")
        assert section is not None
        assert "NavigationStack" in section
        assert "Content about navigation" in section
        assert "Other Section" not in section

    def test_reads_section_by_slug(self, tmp_path):
        md = self._write_md(tmp_path, """\
            ## NavigationStack
            Stack content here.

            ## TabView
            Tab content here.
        """)
        section = _read_section(md, "navigationstack")
        assert section is not None
        assert "Stack content here" in section
        assert "TabView" not in section

    def test_returns_none_for_missing_anchor(self, tmp_path):
        md = self._write_md(tmp_path, "## Foo\nbar\n")
        assert _read_section(md, "nonexistent") is None

    def test_returns_none_for_missing_file(self, tmp_path):
        assert _read_section(tmp_path / "nope.md", "any") is None

    def test_last_section_reads_to_eof(self, tmp_path):
        md = self._write_md(tmp_path, """\
            ## Only Section
            All the content.
            More content.
        """)
        # _slugify("Only Section") → "onlysection" (spaces dropped)
        section = _read_section(md, "onlysection")
        assert section is not None
        assert "All the content" in section
        assert "More content" in section

    def test_respects_heading_level(self, tmp_path):
        md = self._write_md(tmp_path, """\
            ## Parent
            Parent text.
            ### Child
            Child text.
            ## Sibling
            Sibling text.
        """)
        section = _read_section(md, "parent")
        assert section is not None
        assert "Parent text" in section
        assert "Child text" in section  # child (###) is deeper, included
        assert "Sibling text" not in section  # same level (##), excluded


# ---------------------------------------------------------------------------
# _chunk_markdown
# ---------------------------------------------------------------------------


class TestChunkMarkdown:
    def test_basic_chunking(self):
        text = "## Intro\nSome text.\n## Details\nMore text."
        chunks = _chunk_markdown(text, "swiftui")
        assert len(chunks) == 2
        assert chunks[0]["title"] == "swiftui/Intro"
        assert chunks[0]["label"] == "apple-docs"
        assert "Some text" in chunks[0]["text"]
        assert chunks[1]["title"] == "swiftui/Details"

    def test_preamble_before_first_heading(self):
        text = "Preamble line.\n## First\nContent."
        chunks = _chunk_markdown(text, "foundation")
        assert len(chunks) == 2
        assert chunks[0]["title"] == "foundation/preamble"
        assert "Preamble line" in chunks[0]["text"]

    def test_empty_text(self):
        assert _chunk_markdown("", "x") == []

    def test_no_headings(self):
        text = "Just some text without headings."
        chunks = _chunk_markdown(text, "misc")
        assert len(chunks) == 1
        assert chunks[0]["title"] == "misc/preamble"

    def test_heading_only(self):
        text = "## Empty Section"
        chunks = _chunk_markdown(text, "test")
        assert len(chunks) == 1
        assert chunks[0]["title"] == "test/Empty Section"


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registers_four_tools(self):
        from mcp.server.fastmcp import FastMCP
        mcp = FastMCP("test")
        register_apple_docs_tools(mcp)

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {"rlm_apple_search", "rlm_apple_export", "rlm_apple_read", "rlm_context7_ingest"}
        assert expected.issubset(tool_names), f"Missing: {expected - tool_names}"
