from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from chronopersona.ab_parser_common import ABParserError
from chronopersona.ab_parser_sample import load_profile_for_plan
from chronopersona.stackexchange_ab_parser import (
    normalize_plain_title_v0,
    parse_stackexchange_fixture,
    sanitize_markdown_body_v0,
)


ROOT = Path(__file__).resolve().parents[1]


def _profile():
    return deepcopy(load_profile_for_plan(ROOT))


def _posts() -> bytes:
    return (ROOT / "tests/fixtures/ab-parser-v0/Posts.xml").read_bytes()


def _history() -> bytes:
    return (ROOT / "tests/fixtures/ab-parser-v0/PostHistory.xml").read_bytes()


def _parse(posts: bytes | None = None, history: bytes | None = None, profile=None):
    profile = profile or _profile()
    selections = profile["fixture_bundle"]["selections"]
    selected = [
        (key, selections[key])
        for key in profile["fixture_bundle"]["selection_order"]
        if selections[key]["source"] == "stackexchange"
    ]
    return parse_stackexchange_fixture(
        posts or _posts(),
        history or _history(),
        profile=profile,
        selections=selected,
    )


def test_stack_fixture_reconstructs_initial_versions_without_current_fallback() -> None:
    records, counts = _parse()
    assert counts == {"posts_rows": 4, "posthistory_rows": 14}
    assert [record["stratum"] for record in records] == [
        "question",
        "answer",
        "question",
        "answer",
    ]
    assert all(
        record["diagnostics"]["current_fields_used_as_prose"] is False
        for record in records
    )
    assert all(record["current_field_evidence"]["body_relation"] == "different" for record in records)
    assert "Edited body now" not in records[0]["initial_action"]["normalized_body"]
    assert records[0]["initial_action"]["normalized_title"] == "How do stars form?"
    assert records[1]["initial_action"]["normalized_title"] is None
    assert records[2]["initial_action"]["normalized_body"] == (
        "Recovery & resilience matter.\n\nCoral nurseries can support damaged reefs."
    )
    assert all(record["license_status"] == "unresolved" for record in records)


def test_stack_markdown_sanitizer_removes_code_quotes_targets_and_one_entity_layer() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    result = sanitize_markdown_body_v0(
        """Visible &amp; text.

> remove quote

    remove_code()

`inline()` remains outside. [label](https://example.invalid)
Thanks!""",
        contract,
    )
    assert result["text"] == "Visible & text.\n\nremains outside. label"
    assert "example.invalid" not in result["text"]
    assert result["removed_counts"]["quote_lines"] == 1
    assert result["removed_counts"]["indented_code_lines"] == 1
    assert result["removed_counts"]["boilerplate_lines"] == 1
    assert normalize_plain_title_v0("A &amp;amp; B") == "A &amp; B"


@pytest.mark.parametrize(
    "text",
    [
        "<code>secret</pre>LEAK",
        "```python\nsecret\n``` trailing\nLEAK",
        "<blockquote><code>nested</blockquote></code>",
    ],
)
def test_stack_markdown_sanitizer_rejects_malformed_exclusions(text) -> None:
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0(
            text, _profile()["transformations"]["stackexchange"]
        )


def test_stack_markdown_sanitizer_removes_signature_tail() -> None:
    result = sanitize_markdown_body_v0(
        "Useful prose\n\n-- \nAlice\nMore signature",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Useful prose"
    assert result["removed_counts"]["signature_blocks"] == 1


def test_stack_markdown_links_remove_nested_destinations_and_locator_schemes() -> None:
    result = sanitize_markdown_body_v0(
        "See [label](https://example.invalid/a_(b)) and "
        "<mailto:user@example.invalid> plus ftp://example.invalid/file.",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "See label and plus"
    assert "example.invalid" not in result["text"]
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0(
            "See [outer [inner]](relative/private/path)",
            _profile()["transformations"]["stackexchange"],
        )


def test_stack_inline_code_quote_indent_and_signature_scopes_are_exact() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0("Visible before `secret_code", contract)
    result = sanitize_markdown_body_v0(
        "Before `a``b` after\n\n> quote\nlazy continuation\n\n"
        " \tsecret_code()\n\n```text\n-- \n```\nVisible tail",
        contract,
    )
    assert result["text"] == "Before after\n\nVisible tail"
    assert result["removed_counts"]["inline_code_spans"] == 1
    assert result["removed_counts"]["quote_lines"] == 2
    assert result["removed_counts"]["indented_code_lines"] == 1
    assert result["removed_counts"]["signature_blocks"] == 0


@pytest.mark.parametrize("prefix", ["* ", "1. ", "- 1) "])
def test_stack_list_nested_blockquotes_are_removed(prefix) -> None:
    result = sanitize_markdown_body_v0(
        f"Visible\n\n{prefix}> PRIVATE QUOTE\nlazy continuation\n\nTail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible\n\nTail"
    assert "PRIVATE" not in result["text"]
    assert result["removed_counts"]["quote_lines"] == 2


def test_stack_fence_closer_indentation_is_bounded() -> None:
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0(
            "Visible\n```\nhidden\n    ```\nSECRET_AFTER_FAKE_CLOSE",
            _profile()["transformations"]["stackexchange"],
        )


@pytest.mark.parametrize("opening", ["```~python", "~~~`python"])
def test_stack_fence_info_string_is_marker_specific(opening) -> None:
    result = sanitize_markdown_body_v0(
        f"Visible\n{opening}\nPRIVATE CODE\n{opening[:3]}\nTail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible\n\nTail"
    assert result["removed_counts"]["fenced_code_blocks"] == 1


@pytest.mark.parametrize("prefix", ["-     ", "1.      "])
def test_stack_list_nested_indented_code_is_removed(prefix) -> None:
    result = sanitize_markdown_body_v0(
        f"Visible\n{prefix}SECRET_LIST_CODE()\nTail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible\n\nTail"
    assert result["removed_counts"]["indented_code_lines"] == 1
    assert "SECRET" not in result["text"]


def test_stack_post_decode_locator_pass_removes_entity_constructed_targets() -> None:
    result = sanitize_markdown_body_v0(
        "Visible MAIL&#84;O:private@example.invalid and "
        "ssh&#58;user@private.example/path plus &#x2f;&#x2f;private.example/path",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible and plus"
    assert "private" not in result["text"]


def test_stack_external_schemes_are_case_insensitive() -> None:
    result = sanitize_markdown_body_v0(
        "Visible MAILTO:private@example.invalid tail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible tail"


def test_stack_locator_sweep_runs_after_emphasis_normalization() -> None:
    result = sanitize_markdown_body_v0(
        "Visible MAIL**TO**:private@example.invalid and "
        "s__sh__:user@private.example/path tail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible and tail"
    assert "private" not in result["text"]


def test_stack_reference_definitions_remove_split_destinations_and_titles() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    result = sanitize_markdown_body_v0(
        "Visible [label].\n\n[label]:\nrelative/private/path\n"
        "  \"PRIVATE LINK TITLE\"\n\nTail.",
        contract,
    )
    assert result["text"] == "Visible label.\n\nTail."
    assert "relative/private/path" not in result["text"]
    assert "PRIVATE LINK TITLE" not in result["text"]
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0("[label]:", contract)


def test_stack_reference_definitions_handle_escaped_labels_and_multiline_titles() -> None:
    result = sanitize_markdown_body_v0(
        "[foo\\]]: relative/private/path\n"
        "  \"PRIVATE TITLE\n"
        "  CONTINUATION\"\n\n"
        "Use [foo\\]] safely.",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Use foo] safely."
    assert "relative/private/path" not in result["text"]
    assert "PRIVATE" not in result["text"]


def test_stack_full_reference_links_use_escape_aware_bounded_labels() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    result = sanitize_markdown_body_v0(
        "[visible][a\\]b]\n\n[a\\]b]: https://secret.invalid", contract
    )
    assert result["text"] == "visible"
    assert "secret.invalid" not in result["text"]
    with pytest.raises(ABParserError):
        sanitize_markdown_body_v0(
            "[foo [bar]][id]\n\n[id]: relative/private/path", contract
        )


def test_stack_html_link_attributes_do_not_corrupt_visible_markup() -> None:
    result = sanitize_markdown_body_v0(
        'Visible <a href="https://secret.invalid">label</a>'
        '<blockquote cite="https://secret.invalid/quote">PRIVATE</blockquote>'
        '<code src="https://secret.invalid/code">PRIVATE CODE</code> tail',
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible label tail"
    assert result["removed_counts"]["links"] == 3
    assert "secret.invalid" not in result["text"]
    assert "PRIVATE" not in result["text"]


def test_stack_multiline_reference_title_ignores_escaped_closing_delimiter() -> None:
    result = sanitize_markdown_body_v0(
        '[label]: relative/path\n  "PRIVATE \\"\n  CONTINUATION"\nVisible [label]',
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible label"
    assert "PRIVATE" not in result["text"]
    assert "CONTINUATION" not in result["text"]


def test_stack_shortcut_references_retain_only_visible_labels() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    result = sanitize_markdown_body_v0(
        "[label]: relative/private/path\n\nVisible [label].", contract
    )
    assert result["text"] == "Visible label."
    assert "relative/private/path" not in result["text"]
    boilerplate = sanitize_markdown_body_v0(
        "[Thanks!]: relative/private/path\n\n[Thanks!]", contract
    )
    assert boilerplate["text"] == ""
    assert boilerplate["removed_counts"]["boilerplate_lines"] == 1
    case_preserved = sanitize_markdown_body_v0(
        "[label]: relative/private/path\n\nVisible [LABEL].", contract
    )
    assert case_preserved["text"] == "Visible LABEL."


def test_stack_multiline_reference_labels_are_bounded_and_normalized() -> None:
    result = sanitize_markdown_body_v0(
        "[foo\nbar]: relative/private/path\n\nUse [foo bar]",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Use foo bar"
    assert "relative/private/path" not in result["text"]


def test_stack_inline_code_uses_backslash_parity_for_delimiters() -> None:
    result = sanitize_markdown_body_v0(
        "Visible \\\\`SECRET_CODE\\\\` tail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible \\\\ tail"
    assert "SECRET" not in result["text"]
    assert result["removed_counts"]["inline_code_spans"] == 1


def test_stack_backslashes_inside_code_do_not_escape_closing_delimiters() -> None:
    result = sanitize_markdown_body_v0(
        "Visible `SECRET_ONE\\` public `SECRET_TWO\\` tail",
        _profile()["transformations"]["stackexchange"],
    )
    assert result["text"] == "Visible public tail"
    assert "SECRET" not in result["text"]
    assert result["removed_counts"]["inline_code_spans"] == 2


def test_stack_long_non_code_backslash_text_has_a_linear_fast_path() -> None:
    value = "\\" * 262_144
    result = sanitize_markdown_body_v0(
        value, _profile()["transformations"]["stackexchange"]
    )
    assert result["text"] == value


def test_stack_formatted_boilerplate_is_removed_after_visible_normalization() -> None:
    contract = _profile()["transformations"]["stackexchange"]
    for value in ("**Thanks!**", "[Thanks!](relative/path)", "<strong>Thanks!</strong>"):
        result = sanitize_markdown_body_v0(f"Useful\n\n{value}", contract)
        assert result["text"] == "Useful"
        assert result["removed_counts"]["boilerplate_lines"] == 1


def test_stack_plain_title_excludes_nonvisible_script_and_style_payloads() -> None:
    assert (
        normalize_plain_title_v0(
            "<script>SECRET_SCRIPT</script><style>SECRET_STYLE</style>Visible"
        )
        == "Visible"
    )


@pytest.mark.parametrize(
    ("target", "old", "new"),
    [
        ("posts", b"<posts>", b'<posts forged="1">'),
        ("posts", b' Score="3"', b' Score="3" Forged="1"'),
        ("posts", b'Id="3001"', b'Id="03001"'),
        ("posts", b'CreationDate="2012-02-01T10:00:00.000"', b'CreationDate="2012-02-01T10:00:00Z"'),
        ("history", b"<posthistory>", b'<posthistory forged="1">'),
        ("history", b'PostHistoryTypeId="1"', b'PostHistoryTypeId="999"'),
        ("history", b'RevisionGUID="11111111-1111-1111-1111-111111111111"', b'RevisionGUID="not-a-guid"'),
    ],
)
def test_stack_exact_envelope_row_and_scalar_contracts_fail(target, old, new) -> None:
    posts = _posts()
    history = _history()
    if target == "posts":
        posts = posts.replace(old, new, 1)
    else:
        history = history.replace(old, new, 1)
    with pytest.raises(ABParserError):
        _parse(posts, history)


def test_stack_missing_initial_body_fails_even_when_current_body_exists() -> None:
    history = _history().replace(b' PostHistoryTypeId="2"', b' PostHistoryTypeId="5"', 1)
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_missing_or_duplicate_question_initial_component_fails() -> None:
    history = _history().replace(b' PostHistoryTypeId="3"', b' PostHistoryTypeId="6"', 1)
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_initial_action_rejects_extra_same_guid_time_component() -> None:
    row = (
        b'  <row Id="5999" PostHistoryTypeId="4" PostId="3001" '
        b'RevisionGUID="11111111-1111-1111-1111-111111111111" '
        b'CreationDate="2012-02-01T10:00:00.000" UserId="41" '
        b'Text="same action edit" ContentLicense="CC BY-SA 3.0" />\n'
    )
    history = _history().replace(b"</posthistory>", row + b"</posthistory>")
    with pytest.raises(ABParserError):
        _parse(history=history)
    row = (
        b'  <row Id="5999" PostHistoryTypeId="1" PostId="3001" '
        b'RevisionGUID="11111111-1111-1111-1111-111111111111" '
        b'CreationDate="2012-02-01T10:00:00.000" UserId="41" '
        b'Text="duplicate" ContentLicense="CC BY-SA 3.0" />\n'
    )
    history = _history().replace(b"</posthistory>", row + b"</posthistory>")
    with pytest.raises(ABParserError):
        _parse(history=history)


@pytest.mark.parametrize(
    "old,new",
    [
        (
            b'RevisionGUID="11111111-1111-1111-1111-111111111111"',
            b'RevisionGUID="99999999-9999-9999-9999-999999999999"',
        ),
        (
            b'CreationDate="2012-02-01T10:00:00.000" UserId="41" Text="I observed',
            b'CreationDate="2012-02-01T10:00:01.000" UserId="41" Text="I observed',
        ),
        (b'UserId="41" Text="I observed', b'UserId="99" Text="I observed'),
    ],
)
def test_stack_initial_action_guid_time_and_actor_mismatch_fail(old, new) -> None:
    history = _history().replace(old, new, 1)
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_actor_projection_is_independent_of_xml_row_order() -> None:
    history = _history()
    history = history.replace(b'UserId="41" Text="How', b'UserId="41" UserDisplayName="Title Name" Text="How', 1)
    history = history.replace(b'UserId="41" Text="I observed', b'UserId="41" UserDisplayName="Body Name" Text="I observed', 1)
    history = history.replace(b'UserId="41" Text="&lt;astronomy', b'UserId="41" UserDisplayName="Tags Name" Text="&lt;astronomy', 1)
    records, _counts = _parse(history=history)
    original = records[0]["initial_action"]["actor"]
    lines = history.splitlines()
    root_index = lines.index(b"<posthistory>")
    header = lines[: root_index + 1]
    rows = lines[root_index + 1 : -1]
    reversed_history = b"\n".join([*header, *reversed(rows), lines[-1]]) + b"\n"
    reversed_records, _counts = _parse(history=reversed_history)
    assert original == reversed_records[0]["initial_action"]["actor"]
    assert original["display_name"] == "Body Name"


def test_stack_same_time_distinct_guid_action_is_ambiguous() -> None:
    history = _history().replace(
        b'CreationDate="2012-03-01T10:00:00.000" UserId="41" Text="Edited early question"',
        b'CreationDate="2012-02-01T10:00:00.000" UserId="41" Text="Edited early question"',
        1,
    )
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_answer_parent_is_required_and_question_parent_is_forbidden() -> None:
    posts = _posts().replace(b' ParentId="3001"', b"", 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)
    posts = _posts().replace(b' ParentId="3001"', b' ParentId="4001"', 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)
    posts = _posts().replace(b' ParentId="3001"', b' ParentId="9999"', 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)
    posts = _posts().replace(b' PostTypeId="1"', b' PostTypeId="1" ParentId="999"', 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)


def test_stack_differing_current_field_requires_later_history() -> None:
    history = _history().replace(b' PostHistoryTypeId="5" PostId="3002"', b' PostHistoryTypeId="6" PostId="3002"', 1)
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_current_field_requires_an_edit_not_only_a_rollback() -> None:
    history = _history().replace(
        b'PostHistoryTypeId="5" PostId="3002"',
        b'PostHistoryTypeId="8" PostId="3002"',
        1,
    )
    with pytest.raises(ABParserError):
        _parse(history=history)
    history = _history().replace(
        b'PostHistoryTypeId="4" PostId="3001"',
        b'PostHistoryTypeId="7" PostId="3001"',
        1,
    ).replace(
        b'PostHistoryTypeId="5" PostId="3001"',
        b'PostHistoryTypeId="8" PostId="3001"',
        1,
    )
    with pytest.raises(ABParserError):
        _parse(history=history)


def test_stack_raw_and_current_normalized_text_ceilings_are_enforced() -> None:
    oversized = b"x" * 270000
    history = _history().replace(
        b"Stars form when dense clouds collapse.&#xA;&#xA;    hidden_code()"
        b"&#xA;&#xA;The process can take a long time.",
        oversized,
        1,
    )
    with pytest.raises(ABParserError):
        _parse(history=history)
    many_tokens = ("x " * 17000).strip().encode()
    posts = _posts().replace(b"Edited answer now.", many_tokens, 1)
    history = _history().replace(b"Edited answer now.", many_tokens, 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts, history=history)
    many_tags = ("x " * 17000).strip().encode()
    posts = _posts().replace(b"&lt;astronomy&gt;&lt;stars&gt;", many_tags, 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)


def test_stack_current_field_must_match_its_latest_history_action() -> None:
    history = _history().replace(b'Text="Edited answer now."', b'Text="Different later answer."', 1)
    with pytest.raises(ABParserError):
        _parse(history=history)


@pytest.mark.parametrize("type_id,reason", [(12, "deletion-signal"), (17, "migration-signal")])
def test_stack_documented_policy_signals_are_closed_exclusions(type_id, reason) -> None:
    row = (
        f'  <row Id="5999" PostHistoryTypeId="{type_id}" PostId="3001" '
        'RevisionGUID="99999999-9999-9999-9999-999999999999" '
        'CreationDate="2012-04-01T10:00:00.000" UserId="41" />\n'
    ).encode()
    history = _history().replace(b"</posthistory>", row + b"</posthistory>")
    records, _counts = _parse(history=history)
    assert records[0]["disposition"] == "excluded"
    assert reason in records[0]["reasons"]


def test_stack_generated_post_id_is_a_closed_exclusion() -> None:
    profile = _profile()
    replacements = {
        b"3001": b"1000000001",
    }
    posts = _posts()
    history = _history()
    for old, new in replacements.items():
        posts = posts.replace(old, new)
        history = history.replace(old, new)
    selection = profile["fixture_bundle"]["selections"]["stack-early-question"]
    selection["post_id"] = "1000000001"
    profile["fixture_bundle"]["selections"]["stack-early-answer"][
        "parent_post_id"
    ] = "1000000001"
    # The early answer now points at the generated question and remains valid.
    records, _counts = _parse(posts, history, profile)
    assert records[0]["disposition"] == "excluded"
    assert "generated-post-id" in records[0]["reasons"]


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: b"\xef\xbb\xbf" + payload,
        lambda payload: payload.replace(b"<posts>", b"<!DOCTYPE x><posts>", 1),
        lambda payload: payload.replace(b"<posts>", b"<!ENTITY x 'y'><posts>", 1),
        lambda payload: payload.replace(b"<row Id=", b"<!-- inside --><row Id=", 1),
        lambda payload: payload.replace(b"<posts>", b"<?forged x?><posts>", 1),
        lambda payload: payload.replace(b"Edited body", b"Edited\x00body", 1),
    ],
)
def test_stack_unsafe_xml_envelopes_fail(mutator) -> None:
    with pytest.raises(ABParserError):
        _parse(posts=mutator(_posts()))


def test_stack_prolog_comment_must_be_the_exact_frozen_comment() -> None:
    posts = _posts().replace(b"ContentLicense", b"ForgedLicense", 1)
    with pytest.raises(ABParserError):
        _parse(posts=posts)


def test_stack_row_ceilings_count_unselected_rows() -> None:
    profile = _profile()
    profile["limits"]["max_posts_rows"] = 3
    with pytest.raises(ABParserError):
        _parse(profile=profile)
