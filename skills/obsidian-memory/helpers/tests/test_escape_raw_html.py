"""Tests for escape_raw_html / escape_raw_html_tree (Obsidian raw-tag guard).

Origin: 2026-06-11 — a bare <noscript> in a session-log field made Obsidian's
reading view stop rendering markdown for the rest of the note.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from session_end import escape_raw_html, escape_raw_html_tree


def test_bare_tag_gets_backticked():
    assert escape_raw_html("falsified <noscript> handling") == "falsified `<noscript>` handling"


def test_closing_and_selfclosing_tags():
    assert escape_raw_html("a </div> b <br/> c") == "a `</div>` b `<br/>` c"


def test_tag_with_attributes():
    assert escape_raw_html('x <details class="more"> y') == 'x `<details class="more">` y'


def test_placeholder_path_tag():
    assert escape_raw_html(".claude/rules/<area>.md") == ".claude/rules/`<area>`.md"


def test_already_backticked_untouched():
    s = "use `<noscript>` carefully"
    assert escape_raw_html(s) == s


def test_inside_inline_code_span_untouched():
    s = "run `cat <file> | grep x` now"
    assert escape_raw_html(s) == s


def test_fenced_block_untouched():
    s = "before <b>\n```html\n<div class=\"x\"><noscript>hi</noscript></div>\n```\nafter <i>"
    out = escape_raw_html(s)
    assert "`<b>`" in out and "`<i>`" in out
    assert '<div class="x"><noscript>hi</noscript></div>' in out  # fence verbatim


def test_not_a_tag_left_alone():
    s = "5 < 6 and a -> b and x<3"
    assert escape_raw_html(s) == s


def test_tree_walks_nested_structures():
    raw = {"summary": "hit <noscript>", "streams": [{"title": "t", "body": "see </main>"}], "n": 3}
    out = escape_raw_html_tree(raw)
    assert out["summary"] == "hit `<noscript>`"
    assert out["streams"][0]["body"] == "see `</main>`"
    assert out["n"] == 3


def test_idempotent():
    once = escape_raw_html("x <noscript> y")
    assert escape_raw_html(once) == once
