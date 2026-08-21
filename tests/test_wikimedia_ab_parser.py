from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from chronopersona.ab_parser_common import ABParserError
from chronopersona.ab_parser_sample import load_profile_for_plan
from chronopersona.wikimedia_ab_parser import (
    _base36_sha1,
    diff_added_spans_v0,
    parse_wikimedia_fixture,
    sanitize_wikitext_v0,
)


ROOT = Path(__file__).resolve().parents[1]


def _profile():
    return deepcopy(load_profile_for_plan(ROOT))


def _payload() -> bytes:
    return (ROOT / "tests/fixtures/ab-parser-v0/wikimedia.xml").read_bytes()


def _parse(payload: bytes | None = None, profile=None):
    profile = profile or _profile()
    selections = profile["fixture_bundle"]["selections"]
    selected = [
        (key, selections[key])
        for key in profile["fixture_bundle"]["selection_order"]
        if selections[key]["source"] == "wikimedia"
    ]
    return parse_wikimedia_fixture(
        payload or _payload(), profile=profile, selections=selected
    )


def test_wikimedia_fixture_resolves_parent_by_identity_not_xml_order() -> None:
    records, counts = _parse()
    early, late = records
    assert counts == {"pages": 2, "revisions": 6}
    assert early["lineage"] == {
        "parent_revision_id": "1100",
        "child_revision_id": "1101",
        "child_parent_revision_id": "1100",
        "parent_timestamp": "2012-02-01T10:00:00Z",
        "child_timestamp": "2012-02-01T10:00:00Z",
        "history_coverage": "complete-synthetic-page",
        "chronology": "unresolved-equal-time",
    }
    assert early["normalized"]["child_tokens"] == [
        "alpha",
        "stars",
        "form",
        "slowly",
        "a",
        "young",
        "star",
        "shines",
        "brightly",
    ]
    assert early["candidate_spans"] == [
        {
            "child_token_start": 4,
            "child_token_end": 9,
            "tokens": ["a", "young", "star", "shines", "brightly"],
        }
    ]
    assert "current snapshot" not in early["normalized"]["child_text"].casefold()
    assert late["diagnostics"]["import_comment_signal"] == "signal-present"
    assert all(record["authorship_status"] == "unresolved" for record in records)


@pytest.mark.parametrize(
    "old,new",
    [
        (
            'xmlns="http://www.mediawiki.org/xml/export-0.11/"',
            'xmlns="https://www.mediawiki.org/xml/export-0.11/"',
        ),
        ('version="0.11"', 'version="0.10"'),
        ('xml:lang="en"', 'xml:lang="fr"'),
        ("<id>1101</id>", "<id>01101</id>"),
        ("<origin>1101</origin>", "<origin>0</origin>"),
        ('bytes="86"', 'bytes="85"'),
        ('sha1="1t9y6n97w0jryf1e63we424j8dekyyi"', 'sha1="0000000000000000000000000000000"'),
        ('<text xml:space="preserve"', '<text location="remote" xml:space="preserve"'),
    ],
)
def test_wikimedia_exact_schema_and_identity_mutations_fail(old, new) -> None:
    payload = _payload().replace(old.encode(), new.encode(), 1)
    with pytest.raises(ABParserError):
        _parse(payload)


def test_wikimedia_duplicate_scalar_and_revision_order_drift_fail() -> None:
    payload = _payload().replace(b"<ns>0</ns>", b"<ns>0</ns><ns>0</ns>", 1)
    with pytest.raises(ABParserError):
        _parse(payload)
    payload = _payload().replace(
        b"<timestamp>2012-02-01T10:00:00Z</timestamp>\n      <contributor>",
        b"<contributor>",
        1,
    )
    with pytest.raises(ABParserError):
        _parse(payload)


def test_wikimedia_missing_or_cross_page_parent_fails() -> None:
    payload = _payload().replace(b"<parentid>1100</parentid>", b"<parentid>2100</parentid>", 1)
    with pytest.raises(ABParserError):
        _parse(payload)
    payload = _payload().replace(b"<parentid>1100</parentid>", b"", 1)
    with pytest.raises(ABParserError):
        _parse(payload)


def test_wikimedia_equal_time_is_accepted_as_unresolved() -> None:
    payload = _payload().replace(
        b"<timestamp>2012-02-01T10:00:00Z</timestamp>",
        b"<timestamp>2012-02-02T10:00:00Z</timestamp>",
        1,
    )
    # The first replacement is the selected child; make its parent equal too.
    payload = payload.replace(
        b"<timestamp>2012-02-01T10:00:00Z</timestamp>",
        b"<timestamp>2012-02-02T10:00:00Z</timestamp>",
        1,
    )
    records, _counts = _parse(payload)
    assert records[0]["lineage"]["chronology"] == "unresolved-equal-time"
    assert "chronology-unresolved" in records[0]["reasons"]


def test_wikimedia_origin_mismatch_is_a_closed_unresolved_signal() -> None:
    payload = _payload().replace(b"<origin>1101</origin>", b"<origin>1100</origin>", 1)
    records, _counts = _parse(payload)
    assert records[0]["disposition"] == "unresolved"
    assert records[0]["diagnostics"]["origin_matches_child"] is False
    assert "inherited-or-rollback-signal" in records[0]["reasons"]


@pytest.mark.parametrize(
    "payload",
    [
        b"\xef\xbb\xbf" + _payload(),
        _payload().replace(b"<mediawiki", b"<!DOCTYPE x><mediawiki", 1),
        _payload().replace(b"<mediawiki", b"<!ENTITY x 'y'><mediawiki", 1),
        _payload().replace(b"<page>", b"<!-- forged --><page>", 1),
        _payload().replace(b"<title>", b"<?forged x?><title>", 1),
        _payload().replace(b"Alpha stars", b"Alpha\x00stars", 1),
    ],
)
def test_wikimedia_unsafe_xml_envelopes_fail(payload) -> None:
    with pytest.raises(ABParserError):
        _parse(payload)


def test_mediawiki_base36_sha1_fixed_vectors() -> None:
    assert _base36_sha1(b"Baseline prose remains.") == "iy2aeq6rbq3t8q34bbgk8frjczc0txn"
    assert _base36_sha1(b"e\xcc\x81") == "eqwhi7iwo9506nr5uwfjskm4k77zya1"
    assert _base36_sha1(b"pad-95") == "0p1sbnvf6du8edhkkixtoew7gf0yekn"


def test_wikitext_sanitizer_drops_nested_markup_and_keeps_link_labels() -> None:
    contract = _profile()["transformations"]["wikimedia"]
    result = sanitize_wikitext_v0(
        """Base.\n\n{{outer|{{inner}}|{{{parameter}}}}}\n<ref>citation</ref>\n* list\n{|
| table
|}\nLinks: [[File:x.jpg|hidden]] [[Target|visible]] [https://example.invalid label]""",
        contract,
    )
    assert result["text"] == "Base.\n\nLinks: visible label"
    assert result["removed_counts"]["templates"] == 3
    assert result["removed_counts"]["tables"] == 1
    assert result["removed_counts"]["dropped_links"] == 1


def test_wikitext_nested_template_closers_and_protected_literals_are_bounded() -> None:
    contract = _profile()["transformations"]["wikimedia"]
    result = sanitize_wikitext_v0(
        "Base {{outer|{{inner}}}} tail. "
        "<nowiki>{{ literal delimiters</nowiki> End.",
        contract,
    )
    assert result["text"] == "Base tail. End."
    assert result["removed_counts"]["templates"] == 2
    assert result["removed_counts"]["block_tags"] == 1


def test_wikitext_external_locators_are_removed_without_overstripping_colons() -> None:
    contract = _profile()["transformations"]["wikimedia"]
    result = sanitize_wikitext_v0(
        "Note:important stays. [mailto:user@example.invalid visible] "
        "[ftp://example.invalid/file transfer] [//example.invalid/path relative].",
        contract,
    )
    assert result["text"] == "Note:important stays. visible transfer relative."
    assert "example.invalid" not in result["text"]


def test_wikitext_external_schemes_are_case_insensitive_and_list_lines_drop() -> None:
    result = sanitize_wikitext_v0(
        "Intro\n*List content\n#Numbered content\n"
        "Visible [MAILTO:private@example.invalid label] tail",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Intro\n\nVisible label tail"
    assert result["removed_counts"]["list_lines"] == 2
    assert "private@example.invalid" not in result["text"]


def test_wikitext_html_tables_lists_references_and_navigation_are_removed() -> None:
    result = sanitize_wikitext_v0(
        "Visible.\n<table><tr><td>SECRET CELL</td></tr></table>\n"
        "<ul><li>SECRET ITEM</li></ul>\n"
        "<references>SECRET CITATION</references>\n__TOC__\nTail.",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Visible.\n\nTail."
    assert "SECRET" not in result["text"]
    assert result["removed_counts"]["block_tags"] == 3
    assert result["removed_counts"]["navigation_lines"] == 1


def test_wikitext_standalone_list_and_table_children_are_removed() -> None:
    result = sanitize_wikitext_v0(
        "Visible <li>SECRET ITEM</li> <dt>SECRET TERM</dt>"
        "<dd>SECRET DEF</dd> <tr><td>SECRET CELL</td></tr> tail",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Visible tail"
    assert "SECRET" not in result["text"]


def test_wikitext_magnet_locators_are_removed() -> None:
    result = sanitize_wikitext_v0(
        "Visible [magnet:?xt=urn:btih:PRIVATEHASH label] and "
        "magnet:?xt=urn:btih:OTHERHASH tail",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Visible label and tail"
    assert "HASH" not in result["text"]


def test_wikitext_locator_sweep_runs_after_markup_delimiters() -> None:
    result = sanitize_wikitext_v0(
        "Visible ma''ilto:private@example.invalid and mag''net:?xt=PRIVATE tail",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Visible and tail"
    assert "private" not in result["text"].casefold()


def test_wikitext_navigation_sweep_runs_after_markup_delimiters() -> None:
    result = sanitize_wikitext_v0(
        "Intro\n''__TOC__''\n== __NOTOC__ ==\nOutro",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Intro\n\nOutro"
    assert result["removed_counts"]["navigation_lines"] == 2


def test_wikitext_navigation_only_links_ignore_presentation_tags() -> None:
    result = sanitize_wikitext_v0(
        "Intro\n<span>[[PrivatePage]]</span>\n"
        "<div>[https://private.invalid Label]</div>\nOutro",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Intro\n\nOutro"
    assert "Private" not in result["text"]
    assert result["removed_counts"]["navigation_lines"] == 2


def test_wikitext_leading_space_preformatted_lines_are_removed() -> None:
    result = sanitize_wikitext_v0(
        "Intro\n SECRET_CODE()\n\tSECRET_TAB_CODE()\nOutro",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Intro\n\nOutro"
    assert result["removed_counts"]["preformatted_lines"] == 2
    assert "SECRET" not in result["text"]


@pytest.mark.parametrize(
    "excluded_prefix",
    ["<!--hidden marker-->", "{{drop}}", "<ref>citation</ref>"],
)
def test_wikitext_excluded_prefix_cannot_expose_preformatted_prose(
    excluded_prefix,
) -> None:
    result = sanitize_wikitext_v0(
        f"Visible\n{excluded_prefix} secret code payload\nTail",
        _profile()["transformations"]["wikimedia"],
    )
    assert result["text"] == "Visible\n\nTail"
    assert result["removed_counts"]["preformatted_lines"] == 1
    assert "secret" not in result["text"].casefold()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        (b"<username>Synthetic Editor</username>", b"<username>   </username>"),
        (b"<ip>192.0.2.10</ip>", b"<ip>not an ip</ip>"),
        (b"<ip>192.0.2.10</ip>", b"<ip>2001:DB8::1</ip>"),
    ],
)
def test_wikimedia_contributor_identity_is_nonempty_and_canonical(old, new) -> None:
    with pytest.raises(ABParserError):
        _parse(_payload().replace(old, new, 1))


def test_wikimedia_ancestor_identity_not_timestamp_drives_rollback_signal() -> None:
    payload = _payload()
    payload = payload.replace(
        b"<id>1100</id>\n      <timestamp>2012-02-01T10:00:00Z</timestamp>",
        b"<id>1100</id>\n      <parentid>1102</parentid>\n"
        b"      <timestamp>2012-01-31T10:00:00Z</timestamp>",
        1,
    )
    payload = payload.replace(
        b"<id>1102</id>\n      <parentid>1101</parentid>",
        b"<id>1102</id>",
        1,
    )
    ancestor = (
        b'<text xml:space="preserve" bytes="44" '
        b'sha1="490pnma2guxrvm9zl4t2pqfj27dfzq2">Current snapshot text '
        b'must not be selected.\n</text>\n'
        b'      <sha1>490pnma2guxrvm9zl4t2pqfj27dfzq2</sha1>'
    )
    child = (
        b'<text xml:space="preserve" bytes="86" '
        b'sha1="1t9y6n97w0jryf1e63we424j8dekyyi">Alpha stars form slowly.\n\n'
        b'A [[new star|young star]] shines brightly.&lt;ref&gt;Source&lt;/ref&gt;\n'
        b'</text>\n      <sha1>1t9y6n97w0jryf1e63we424j8dekyyi</sha1>'
    )
    payload = payload.replace(ancestor, child, 1)
    records, _counts = _parse(payload)
    assert records[0]["diagnostics"]["rollback_signal"] is True
    assert records[0]["lineage"]["chronology"] == "unresolved-inversion"
    assert records[0]["disposition"] == "unresolved"


def _earlier_sibling_reintroduction_payload() -> bytes:
    payload = _payload().replace(
        b"<id>1102</id>\n      <parentid>1101</parentid>\n"
        b"      <timestamp>2012-02-02T10:00:00Z</timestamp>",
        b"<id>1102</id>\n      <parentid>1100</parentid>\n"
        b"      <timestamp>2012-01-31T10:00:00Z</timestamp>",
        1,
    )
    old_text = b"Current snapshot text must not be selected.\n"
    new_text = b"Earlier a young star shines brightly.\n"
    old_identity = (
        b'bytes="44" sha1="490pnma2guxrvm9zl4t2pqfj27dfzq2">'
        + old_text
        + b"</text>\n      <sha1>490pnma2guxrvm9zl4t2pqfj27dfzq2</sha1>"
    )
    new_sha1 = _base36_sha1(new_text).encode()
    new_identity = (
        f'bytes="{len(new_text)}" sha1="'.encode()
        + new_sha1
        + b'">'
        + new_text
        + b"</text>\n      <sha1>"
        + new_sha1
        + b"</sha1>"
    )
    assert old_identity in payload
    return payload.replace(old_identity, new_identity, 1)


def test_wikimedia_complete_history_detects_earlier_sibling_reintroduction() -> None:
    records, _counts = _parse(_earlier_sibling_reintroduction_payload())
    assert records[0]["diagnostics"]["reintroduction_status"] == "signal-present"


def test_wikimedia_bounded_history_preserves_observed_reintroduction() -> None:
    profile = _profile()
    profile["fixture_bundle"]["selections"]["wikimedia-early"][
        "history_coverage"
    ] = "bounded-synthetic-subgraph"
    records, _counts = _parse(_earlier_sibling_reintroduction_payload(), profile)
    assert records[0]["diagnostics"]["reintroduction_status"] == "signal-present"


def test_wikimedia_bounded_history_does_not_assert_absence() -> None:
    profile = _profile()
    profile["fixture_bundle"]["selections"]["wikimedia-early"][
        "history_coverage"
    ] = "bounded-synthetic-subgraph"
    records, _counts = _parse(profile=profile)
    assert records[0]["diagnostics"]["reintroduction_status"] == "unresolved"


def test_wikimedia_backdated_descendant_is_not_earlier_evidence() -> None:
    payload = _payload().replace(
        b"<id>1102</id>\n      <parentid>1101</parentid>\n"
        b"      <timestamp>2012-02-02T10:00:00Z</timestamp>",
        b"<id>1102</id>\n      <parentid>1101</parentid>\n"
        b"      <timestamp>2012-01-31T10:00:00Z</timestamp>",
        1,
    )
    old_text = b"Current snapshot text must not be selected.\n"
    old_identity = (
        b'bytes="44" sha1="490pnma2guxrvm9zl4t2pqfj27dfzq2">'
        + old_text
        + b"</text>\n      <sha1>490pnma2guxrvm9zl4t2pqfj27dfzq2</sha1>"
    )
    decoded_child_text = (
        b"Alpha stars form slowly.\n\n"
        b"A [[new star|young star]] shines brightly.<ref>Source</ref>\n"
    )
    xml_child_text = (
        b"Alpha stars form slowly.\n\n"
        b"A [[new star|young star]] shines brightly.&lt;ref&gt;Source&lt;/ref&gt;\n"
    )
    child_sha1 = _base36_sha1(decoded_child_text).encode()
    child_identity = (
        f'bytes="{len(decoded_child_text)}" sha1="'.encode()
        + child_sha1
        + b'">'
        + xml_child_text
        + b"</text>\n      <sha1>"
        + child_sha1
        + b"</sha1>"
    )
    assert old_identity in payload
    payload = payload.replace(old_identity, child_identity, 1)
    records, _counts = _parse(payload)
    early = records[0]
    assert early["diagnostics"]["rollback_signal"] is False
    assert early["diagnostics"]["reintroduction_status"] == "unresolved"
    assert early["lineage"]["chronology"] == "unresolved-inversion"
    assert early["disposition"] == "unresolved"


def test_wikimedia_equal_time_non_lineage_revision_makes_absence_unresolved() -> None:
    payload = _payload().replace(
        b"<id>1102</id>\n      <parentid>1101</parentid>\n"
        b"      <timestamp>2012-02-02T10:00:00Z</timestamp>",
        b"<id>1102</id>\n      <parentid>1100</parentid>\n"
        b"      <timestamp>2012-02-01T10:00:00Z</timestamp>",
        1,
    )
    records, _counts = _parse(payload)
    assert records[0]["diagnostics"]["reintroduction_status"] == "unresolved"


def test_wikimedia_schema_location_is_optional_but_exact_when_present() -> None:
    payload = _payload().replace(
        b' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
        b' xsi:schemaLocation="http://www.mediawiki.org/xml/export-0.11/'
        b' http://www.mediawiki.org/xml/export-0.11.xsd"',
        b"",
        1,
    )
    records, _counts = _parse(payload)
    assert len(records) == 2


@pytest.mark.parametrize(
    "text",
    ["{{unterminated", "{| unterminated", "[[unterminated", "<ref>unterminated"],
)
def test_wikitext_sanitizer_rejects_unbalanced_markup(text) -> None:
    with pytest.raises(ABParserError):
        sanitize_wikitext_v0(text, _profile()["transformations"]["wikimedia"])


def test_diff_is_autojunk_disabled_and_enforces_work_ceiling() -> None:
    spans = diff_added_spans_v0(
        ("same",) * 250,
        ("same",) * 125 + ("new",) + ("same",) * 125,
        maximum_tokens=1000,
        maximum_product=100000,
    )
    assert spans == ({"child_token_start": 125, "child_token_end": 126, "tokens": ["new"]},)
    with pytest.raises(ABParserError):
        diff_added_spans_v0(
            ("a",) * 4097,
            ("b",) * 4096,
            maximum_tokens=16384,
            maximum_product=16777216,
        )
