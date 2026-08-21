"""Strict synthetic MediaWiki export-0.11 parent/child parser."""

from __future__ import annotations

from difflib import SequenceMatcher
from collections import deque
import hashlib
from ipaddress import ip_address
import re
from typing import Any
import xml.etree.ElementTree as ET

from .ab_parser_common import (
    ABParserError,
    bounded_text_evidence,
    bounded_xml_text,
    exact_scalar,
    nonnegative_decimal,
    normalize_paragraph_text,
    parse_xml,
    positive_decimal,
    require,
    sha256_bytes,
    utc_timestamp,
)


_NS = "http://www.mediawiki.org/xml/export-0.11/"
_XML_NS = "http://www.w3.org/XML/1998/namespace"
_XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
_BASE36 = "0123456789abcdefghijklmnopqrstuvwxyz"
_BASE36_31 = re.compile(r"^[0-9a-z]{31}$")


def _tag(local: str) -> str:
    return f"{{{_NS}}}{local}"


def _base36_sha1(payload: bytes) -> str:
    number = int.from_bytes(hashlib.sha1(payload).digest(), "big")
    rendered = ""
    while number:
        number, remainder = divmod(number, 36)
        rendered = _BASE36[remainder] + rendered
    return (rendered or "0").rjust(31, "0")


def _whitespace_only(value: str | None, *, label: str) -> None:
    require(
        value is None or value.strip() == "",
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail=f"{label} contains mixed content",
    )


def _drop_region(text: str, start: str, end: str, *, label: str) -> tuple[str, int]:
    result: list[str] = []
    index = 0
    depth = 0
    count = 0
    while index < len(text):
        if text.startswith(start, index):
            depth += 1
            count += 1
            index += len(start)
            continue
        if text.startswith(end, index):
            require(
                depth > 0,
                stage="parse-wikimedia",
                reason="parser-contract-failed",
                detail=f"unmatched {label} close delimiter",
            )
            depth -= 1
            index += len(end)
            continue
        character = text[index]
        if depth == 0:
            result.append(character)
        elif character == "\n":
            result.append("\n")
        index += 1
    require(
        depth == 0,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail=f"unterminated {label}",
    )
    return "".join(result), count


def _drop_templates(text: str) -> tuple[str, int]:
    result: list[str] = []
    stack: list[str] = []
    count = 0
    index = 0
    while index < len(text):
        if text.startswith("{{{", index):
            stack.append("}}}")
            count += 1
            index += 3
            continue
        if text.startswith("{{", index):
            stack.append("}}")
            count += 1
            index += 2
            continue
        if text.startswith("}}", index):
            closing = stack[-1] if stack and text.startswith(stack[-1], index) else None
            require(
                closing is not None,
                stage="parse-wikimedia",
                reason="parser-contract-failed",
                detail="crossed or unmatched template delimiter",
            )
            stack.pop()
            index += len(closing)
            continue
        character = text[index]
        if not stack:
            result.append(character)
        elif character == "\n":
            result.append("\n")
        index += 1
    require(
        not stack,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="unterminated template",
    )
    return "".join(result), count


def _drop_block_tags(text: str, tags: list[str]) -> tuple[str, int]:
    count = 0
    require(
        len(tags) == len(set(tags))
        and all(re.fullmatch(r"[a-z]+", tag) is not None for tag in tags),
        stage="validation",
        reason="validation-failed",
        detail="drop-block tag vocabulary is not frozen",
    )
    for tag in tags:
        paired = re.compile(
            rf"<\s*{re.escape(tag)}\b[^>]*>[\s\S]*?<\s*/\s*{re.escape(tag)}\s*>",
            re.IGNORECASE,
        )
        while True:
            match = paired.search(text)
            if match is None:
                break
            count += 1
            text = text[: match.start()] + ("\n" * match.group(0).count("\n")) + text[match.end() :]
        self_closing = re.compile(
            rf"<\s*{re.escape(tag)}\b[^>]*/\s*>", re.IGNORECASE
        )
        text, removed = self_closing.subn("", text)
        count += removed
        require(
            re.search(rf"<\s*/?\s*{re.escape(tag)}\b", text, re.IGNORECASE)
            is None,
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail=f"unbalanced {tag} block",
        )
    return text, count


def _locator_pattern(schemes: list[str]) -> str:
    require(
        bool(schemes)
        and schemes == sorted(set(schemes))
        and all(re.fullmatch(r"[a-z][a-z0-9+.-]*", item) for item in schemes),
        stage="validation",
        reason="validation-failed",
        detail="external-link scheme vocabulary is not frozen",
    )
    alternatives = "|".join(re.escape(item) for item in schemes)
    return rf"(?:(?i:{alternatives}):|//)"


def _rewrite_links(
    text: str, drop_prefixes: set[str], external_schemes: list[str]
) -> tuple[str, int, int]:
    dropped = 0
    retained = 0

    def internal(match: re.Match[str]) -> str:
        nonlocal dropped, retained
        value = match.group(1)
        target = value.split("|", 1)[0].strip().lstrip(":").lstrip()
        first = target.split(":", 1)[0].strip().casefold()
        if first in drop_prefixes:
            dropped += 1
            return ""
        pieces = [piece.strip() for piece in value.split("|")]
        label = next((piece for piece in reversed(pieces) if piece), "")
        label = label.split("#", 1)[0] if len(pieces) == 1 else label
        retained += 1
        return label

    text = re.sub(r"\[\[([^\[\]]+)\]\]", internal, text)
    require(
        "[[" not in text and "]]" not in text,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="malformed internal link",
    )

    def external(match: re.Match[str]) -> str:
        nonlocal retained
        retained += 1
        return (match.group(1) or "").strip()

    locator = _locator_pattern(external_schemes)
    text = re.sub(rf"\[{locator}[^\s\]]+(?:\s+([^\]]+))?\]", external, text)
    require(
        re.search(rf"\[{locator}", text) is None,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="malformed external link",
    )
    text = re.sub(rf"(?<!\w){locator}[^\s\]\[<>]+", "", text)
    return text, dropped, retained


def sanitize_wikitext_v0(text: str, contract: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic prose-only text and closed removal counts."""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    counts = {
        "comments": 0,
        "templates": 0,
        "tables": 0,
        "block_tags": 0,
        "dropped_links": 0,
        "retained_link_labels": 0,
        "navigation_lines": 0,
        "list_lines": 0,
        "preformatted_lines": 0,
        "residual_tags": 0,
    }
    preformatted_checked: list[str] = []
    for line in normalized.split("\n"):
        if line.strip() and line.startswith((" ", "\t")):
            counts["preformatted_lines"] += 1
            preformatted_checked.append("")
        else:
            preformatted_checked.append(line)
    normalized = "\n".join(preformatted_checked)
    normalized, counts["comments"] = _drop_region(
        normalized, "<!--", "-->", label="wikitext comment"
    )
    normalized, counts["block_tags"] = _drop_block_tags(
        normalized, contract["drop_block_tags"]
    )
    normalized, counts["templates"] = _drop_templates(normalized)
    normalized, counts["tables"] = _drop_region(
        normalized, "{|", "|}", label="table"
    )
    # Removing a leading comment/template/block can expose the leading space
    # that makes the remainder a MediaWiki preformatted-code line.  Reapply
    # the same line rule after those structural removals so their payload
    # cannot become candidate prose merely because an excluded prefix vanished.
    post_removal_lines: list[str] = []
    for line in normalized.split("\n"):
        if line.strip() and line.startswith((" ", "\t")):
            counts["preformatted_lines"] += 1
            post_removal_lines.append("")
        else:
            post_removal_lines.append(line)
    normalized = "\n".join(post_removal_lines)
    locator = _locator_pattern(contract["external_link_schemes"])
    navigation_magic_words = {
        value.casefold() for value in contract["navigation_magic_words"]
    }
    navigation_checked: list[str] = []
    for line in normalized.split("\n"):
        if line.strip().casefold() in navigation_magic_words:
            counts["navigation_lines"] += 1
            navigation_checked.append("")
            continue
        without_links = re.sub(r"\[\[[^\[\]]+\]\]", "", line)
        without_links = re.sub(
            rf"\[{locator}[^\]]+\]", "", without_links
        )
        without_links = re.sub(
            rf"(?<!\w){locator}[^\s\]\[<>]+",
            "",
            without_links,
        )
        without_links = re.sub(r"<[^<>]+>", "", without_links)
        if without_links != line and re.search(r"[^\W_]+", without_links, re.UNICODE) is None:
            counts["navigation_lines"] += 1
            navigation_checked.append("")
        else:
            navigation_checked.append(line)
    normalized = "\n".join(navigation_checked)
    normalized, counts["dropped_links"], counts["retained_link_labels"] = (
        _rewrite_links(
            normalized,
            set(contract["drop_link_prefixes"]),
            contract["external_link_schemes"],
        )
    )
    retained_lines: list[str] = []
    for line in normalized.split("\n"):
        if re.match(r"^[ \t]*[*#;:]+", line):
            counts["list_lines"] += 1
            retained_lines.append("")
        else:
            retained_lines.append(line)
    normalized = "\n".join(retained_lines)
    normalized, counts["residual_tags"] = re.subn(r"<[^<>]+>", " ", normalized)
    require(
        "<" not in normalized and ">" not in normalized,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="malformed residual tag",
    )
    normalized = re.sub(r"(?m)^\s*=+\s*(.*?)\s*=+\s*$", r"\1", normalized)
    normalized = normalized.replace("'''", "").replace("''", "")
    # Markup removal can join a previously split scheme token. Sweep again so
    # no locator becomes visible only after apostrophe delimiters disappear.
    normalized = re.sub(rf"(?<!\w){locator}[^\s\]\[<>]+", "", normalized)
    final_lines: list[str] = []
    for line in normalized.split("\n"):
        if line.strip().casefold() in navigation_magic_words:
            counts["navigation_lines"] += 1
            final_lines.append("")
        else:
            final_lines.append(line)
    normalized = "\n".join(final_lines)
    normalized = normalize_paragraph_text(normalized)
    return {"text": normalized, "removed_counts": counts}


def diff_added_spans_v0(
    parent_tokens: tuple[str, ...],
    child_tokens: tuple[str, ...],
    *,
    maximum_tokens: int,
    maximum_product: int,
) -> tuple[dict[str, Any], ...]:
    require(
        len(parent_tokens) <= maximum_tokens and len(child_tokens) <= maximum_tokens,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="alignment token ceiling exceeded",
    )
    require(
        len(parent_tokens) * len(child_tokens) <= maximum_product,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="alignment work ceiling exceeded",
    )
    matcher = SequenceMatcher(
        isjunk=None, a=parent_tokens, b=child_tokens, autojunk=False
    )
    spans: list[dict[str, Any]] = []
    for operation, _a0, _a1, b0, b1 in matcher.get_opcodes():
        if operation not in {"insert", "replace"} or b0 == b1:
            continue
        current = {
            "child_token_start": b0,
            "child_token_end": b1,
            "tokens": list(child_tokens[b0:b1]),
        }
        if spans and spans[-1]["child_token_end"] == b0:
            spans[-1]["child_token_end"] = b1
            spans[-1]["tokens"].extend(current["tokens"])
        else:
            spans.append(current)
    return tuple(spans)


def _parse_contributor(element: ET.Element) -> dict[str, Any]:
    require(
        not element.attrib,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="contributor attributes are not allowed",
    )
    tags = [child.tag for child in element]
    if tags == [_tag("username"), _tag("id")]:
        username = exact_scalar(element[0], label="contributor username")
        require(
            bool(username) and username == username.strip(),
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="contributor username is empty or noncanonical",
        )
        user_id_text = exact_scalar(element[1], label="contributor id")
        nonnegative_decimal(user_id_text, label="contributor id")
        result = {"kind": "username", "value": username, "user_id": user_id_text}
    elif tags == [_tag("ip")]:
        ip = exact_scalar(element[0], label="contributor ip")
        try:
            parsed_ip = ip_address(ip)
        except ValueError as error:
            raise ABParserError(
                "parse-wikimedia", "parser-contract-failed", "contributor IP is invalid"
            ) from error
        require(
            bool(ip) and ip == ip.strip() and str(parsed_ip) == ip,
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="contributor IP is empty or noncanonical",
        )
        result = {
            "kind": "ip",
            "value": ip,
            "user_id": None,
        }
    else:
        raise ABParserError(
            "parse-wikimedia",
            "parser-contract-failed",
            "contributor form is not exact",
        )
    _whitespace_only(element.text, label="contributor")
    for child in element:
        _whitespace_only(child.tail, label="contributor")
    return result


def _parse_revision(element: ET.Element, *, limits: dict[str, int]) -> dict[str, Any]:
    require(
        not element.attrib,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision attributes are not allowed",
    )
    allowed_sequences = []
    for parent in (False, True):
        for minor in (False, True):
            for comment in (False, True):
                sequence = ["id"]
                if parent:
                    sequence.append("parentid")
                sequence.extend(["timestamp", "contributor"])
                if minor:
                    sequence.append("minor")
                if comment:
                    sequence.append("comment")
                sequence.extend(["origin", "model", "format", "text", "sha1"])
                allowed_sequences.append([_tag(item) for item in sequence])
    observed = [child.tag for child in element]
    require(
        observed in allowed_sequences,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision field order is not exact",
    )
    by_tag = {child.tag: child for child in element}
    revision_id_text = exact_scalar(by_tag[_tag("id")], label="revision id")
    positive_decimal(revision_id_text, label="revision id")
    parent = by_tag.get(_tag("parentid"))
    parent_id = exact_scalar(parent, label="parent revision id") if parent is not None else None
    if parent_id is not None:
        positive_decimal(parent_id, label="parent revision id")
    timestamp = utc_timestamp(
        exact_scalar(by_tag[_tag("timestamp")], label="revision timestamp"),
        label="revision",
    )
    contributor = _parse_contributor(by_tag[_tag("contributor")])
    minor = by_tag.get(_tag("minor"))
    if minor is not None:
        require(
            not minor.attrib and len(minor) == 0 and (minor.text is None or minor.text == ""),
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="minor element is not empty",
        )
    comment_element = by_tag.get(_tag("comment"))
    comment = None
    if comment_element is not None:
        comment = exact_scalar(comment_element, label="revision comment", allow_empty=True)
    origin_text = exact_scalar(by_tag[_tag("origin")], label="revision origin")
    positive_decimal(origin_text, label="revision origin")
    model = exact_scalar(by_tag[_tag("model")], label="revision model")
    format_value = exact_scalar(by_tag[_tag("format")], label="revision format")
    require(
        model == "wikitext" and format_value == "text/x-wiki",
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision content model is not supported",
    )
    text_element = by_tag[_tag("text")]
    require(
        set(text_element.attrib)
        == {f"{{{_XML_NS}}}space", "bytes", "sha1"}
        and text_element.attrib[f"{{{_XML_NS}}}space"] == "preserve"
        and len(text_element) == 0,
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision text shape is not exact",
    )
    raw_text = text_element.text or ""
    raw_bytes = raw_text.encode("utf-8")
    require(
        len(raw_bytes) <= limits["max_decoded_text_bytes"],
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision decoded-text ceiling exceeded",
    )
    declared_bytes = text_element.attrib["bytes"]
    nonnegative_decimal(declared_bytes, label="revision text bytes")
    declared_sha1 = text_element.attrib["sha1"]
    sibling_sha1 = exact_scalar(by_tag[_tag("sha1")], label="revision sha1")
    computed_sha1 = _base36_sha1(raw_bytes)
    require(
        _BASE36_31.fullmatch(declared_sha1) is not None
        and sibling_sha1 == declared_sha1 == computed_sha1
        and int(declared_bytes) == len(raw_bytes),
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="revision text identity does not match",
    )
    _whitespace_only(element.text, label="revision")
    for child in element:
        _whitespace_only(child.tail, label="revision")
    return {
        "revision_id": revision_id_text,
        "parent_revision_id": parent_id,
        "timestamp": timestamp,
        "contributor": contributor,
        "minor": minor is not None,
        "comment": comment,
        "origin_revision_id": origin_text,
        "model": model,
        "format": format_value,
        "raw_text": raw_text,
        "raw_bytes": len(raw_bytes),
        "raw_sha256": sha256_bytes(raw_bytes),
        "mediawiki_sha1_base36": computed_sha1,
    }


def _any_span_seen(
    spans: tuple[dict[str, Any], ...], histories: list[tuple[str, ...]]
) -> bool:
    """Search all candidate spans in bounded history with one Aho-Corasick scan."""

    transitions: list[dict[str, int]] = [{}]
    failures = [0]
    terminal: set[int] = set()
    for span in spans:
        tokens = span["tokens"]
        if not tokens:
            continue
        state = 0
        for token in tokens:
            next_state = transitions[state].get(token)
            if next_state is None:
                next_state = len(transitions)
                transitions[state][token] = next_state
                transitions.append({})
                failures.append(0)
            state = next_state
        terminal.add(state)
    queue: deque[int] = deque(transitions[0].values())
    while queue:
        state = queue.popleft()
        for token, child in transitions[state].items():
            queue.append(child)
            fallback = failures[state]
            while fallback and token not in transitions[fallback]:
                fallback = failures[fallback]
            failures[child] = transitions[fallback].get(token, 0)
            if failures[child] in terminal:
                terminal.add(child)
    for history in histories:
        state = 0
        for token in history:
            while state and token not in transitions[state]:
                state = failures[state]
            state = transitions[state].get(token, 0)
            if state in terminal:
                return True
    return False


def parse_wikimedia_fixture(
    payload: bytes,
    *,
    profile: dict[str, Any],
    selections: list[tuple[str, dict[str, Any]]],
) -> tuple[tuple[dict[str, Any], ...], dict[str, int]]:
    limits = profile["limits"]
    contract = profile["transformations"]["wikimedia"]
    text = bounded_xml_text(
        payload,
        label="Wikimedia fixture",
        maximum_bytes=limits["max_xml_input_bytes"],
    )
    root = parse_xml(text, label="Wikimedia fixture")
    require(
        root.tag == _tag("mediawiki")
        and set(root.attrib)
        in (
            {"version", f"{{{_XML_NS}}}lang"},
            {"version", f"{{{_XML_NS}}}lang", f"{{{_XSI_NS}}}schemaLocation"},
        )
        and root.attrib["version"] == contract["export_version"]
        and root.attrib[f"{{{_XML_NS}}}lang"] == "en"
        and root.attrib.get(f"{{{_XSI_NS}}}schemaLocation", contract["schema_location"])
        == contract["schema_location"],
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="MediaWiki root contract drifted",
    )
    pages = list(root)
    require(
        0 < len(pages) <= limits["max_mediawiki_pages"]
        and all(page.tag == _tag("page") for page in pages),
        stage="parse-wikimedia",
        reason="parser-contract-failed",
        detail="MediaWiki page count or root children drifted",
    )
    _whitespace_only(root.text, label="MediaWiki root")

    page_map: dict[str, dict[str, Any]] = {}
    revision_owner: dict[str, str] = {}
    revision_total = 0
    for page in pages:
        require(
            not page.attrib,
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="MediaWiki page attributes are not allowed",
        )
        children = list(page)
        require(
            len(children) >= 4
            and [child.tag for child in children[:3]]
            == [_tag("title"), _tag("ns"), _tag("id")],
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="MediaWiki page prefix is not exact",
        )
        title = exact_scalar(children[0], label="page title")
        namespace = exact_scalar(children[1], label="page namespace")
        page_id = exact_scalar(children[2], label="page id")
        positive_decimal(page_id, label="page id")
        require(
            namespace == "0" and page_id not in page_map,
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="MediaWiki page identity is invalid",
        )
        cursor = 3
        redirect_title = None
        if cursor < len(children) and children[cursor].tag == _tag("redirect"):
            redirect = children[cursor]
            require(
                set(redirect.attrib) == {"title"}
                and bool(redirect.attrib["title"])
                and len(redirect) == 0
                and (redirect.text is None or redirect.text == ""),
                stage="parse-wikimedia",
                reason="parser-contract-failed",
                detail="MediaWiki redirect shape is not exact",
            )
            redirect_title = redirect.attrib["title"]
            cursor += 1
        revision_elements = children[cursor:]
        require(
            bool(revision_elements)
            and all(element.tag == _tag("revision") for element in revision_elements),
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="MediaWiki page contains an unknown child",
        )
        revisions: dict[str, dict[str, Any]] = {}
        for element in revision_elements:
            revision_total += 1
            require(
                revision_total <= limits["max_mediawiki_revisions"],
                stage="parse-wikimedia",
                reason="parser-contract-failed",
                detail="MediaWiki revision ceiling exceeded",
            )
            revision = _parse_revision(element, limits=limits)
            revision_id = revision["revision_id"]
            require(
                revision_id not in revision_owner,
                stage="parse-wikimedia",
                reason="parser-contract-failed",
                detail="MediaWiki revision IDs are not globally unique",
            )
            revision_owner[revision_id] = page_id
            revisions[revision_id] = revision
        for revision in revisions.values():
            normalized = sanitize_wikitext_v0(revision["raw_text"], contract)
            bounded_text_evidence(
                normalized["text"],
                label="normalized MediaWiki revision",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
        _whitespace_only(page.text, label="MediaWiki page")
        for child in children:
            _whitespace_only(child.tail, label="MediaWiki page")
        page_map[page_id] = {
            "page_id": page_id,
            "title": title,
            "redirect_title": redirect_title,
            "revisions": revisions,
        }
    for child in pages:
        _whitespace_only(child.tail, label="MediaWiki root")

    # All parent edges are same-page and acyclic, regardless of selection.
    for page_id, page in page_map.items():
        revisions = page["revisions"]
        for revision in revisions.values():
            parent_id = revision["parent_revision_id"]
            if parent_id is not None:
                require(
                    revision_owner.get(parent_id) == page_id,
                    stage="parse-wikimedia",
                    reason="parser-contract-failed",
                    detail="MediaWiki parent is missing or cross-page",
                )
        for revision_id in revisions:
            seen: set[str] = set()
            current: str | None = revision_id
            while current is not None:
                require(
                    current not in seen,
                    stage="parse-wikimedia",
                    reason="parser-contract-failed",
                    detail="MediaWiki parent graph contains a cycle",
                )
                seen.add(current)
                current = revisions[current]["parent_revision_id"]

    records: list[dict[str, Any]] = []
    for selection_id, selection in selections:
        page = page_map.get(selection["page_id"])
        require(
            page is not None,
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="selected MediaWiki page is missing",
        )
        revisions = page["revisions"]
        parent = revisions.get(selection["parent_revision_id"])
        child = revisions.get(selection["child_revision_id"])
        require(
            parent is not None
            and child is not None
            and child["parent_revision_id"] == parent["revision_id"],
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="selected MediaWiki parent/child lineage does not match",
        )
        parent_clean = sanitize_wikitext_v0(parent["raw_text"], contract)
        child_clean = sanitize_wikitext_v0(child["raw_text"], contract)
        parent_text, parent_tokens = bounded_text_evidence(
            parent_clean["text"],
            label="normalized MediaWiki parent",
            maximum_bytes=limits["max_decoded_text_bytes"],
            maximum_tokens=limits["max_normalized_tokens"],
        )
        child_text, child_tokens = bounded_text_evidence(
            child_clean["text"],
            label="normalized MediaWiki child",
            maximum_bytes=limits["max_decoded_text_bytes"],
            maximum_tokens=limits["max_normalized_tokens"],
        )
        spans = diff_added_spans_v0(
            parent_tokens,
            child_tokens,
            maximum_tokens=limits["max_normalized_tokens"],
            maximum_product=limits["max_alignment_product"],
        )
        ancestor_chain: list[dict[str, Any]] = []
        current = child
        while current["parent_revision_id"] is not None:
            current = revisions[current["parent_revision_id"]]
            ancestor_chain.append(current)
        require(
            ancestor_chain and ancestor_chain[0]["revision_id"] == parent["revision_id"],
            stage="parse-wikimedia",
            reason="parser-contract-failed",
            detail="selected MediaWiki ancestor chain is not exact",
        )
        children_by_parent: dict[str, list[str]] = {}
        for revision in revisions.values():
            parent_revision_id = revision["parent_revision_id"]
            if parent_revision_id is not None:
                children_by_parent.setdefault(parent_revision_id, []).append(
                    revision["revision_id"]
                )
        descendant_ids: set[str] = set()
        pending_descendants = list(children_by_parent.get(child["revision_id"], ()))
        while pending_descendants:
            revision_id = pending_descendants.pop()
            if revision_id in descendant_ids:
                continue
            descendant_ids.add(revision_id)
            pending_descendants.extend(children_by_parent.get(revision_id, ()))
        evidence_revisions: list[tuple[dict[str, Any], tuple[str, ...]]] = []
        evidence_ids = {
            revision["revision_id"] for revision in ancestor_chain[1:]
        }
        evidence_ids.update(
            revision["revision_id"]
            for revision in revisions.values()
            if revision["revision_id"]
            not in {parent["revision_id"], child["revision_id"]}
            and revision["revision_id"] not in descendant_ids
            and revision["timestamp"] < child["timestamp"]
        )
        for revision_id in sorted(evidence_ids, key=lambda value: (len(value), value)):
            revision = revisions[revision_id]
            clean = sanitize_wikitext_v0(revision["raw_text"], contract)
            _text, tokens = bounded_text_evidence(
                clean["text"],
                label="normalized MediaWiki history revision",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
            evidence_revisions.append((revision, tokens))
        rollback_signal = any(
            revision["raw_sha256"] == child["raw_sha256"]
            for revision, _tokens in evidence_revisions
        )
        lineage_revision_ids = {
            child["revision_id"],
            *(item["revision_id"] for item in ancestor_chain),
        }
        equal_time_non_lineage = any(
            revision["timestamp"] == child["timestamp"]
            and revision["revision_id"] not in lineage_revision_ids
            and revision["revision_id"] not in descendant_ids
            for revision in revisions.values()
        )
        descendant_time_inversion = any(
            revisions[revision_id]["timestamp"] < child["timestamp"]
            for revision_id in descendant_ids
        )
        descendant_equal_time = any(
            revisions[revision_id]["timestamp"] == child["timestamp"]
            for revision_id in descendant_ids
        )
        descendant_time_ambiguity = (
            descendant_time_inversion or descendant_equal_time
        )
        reintroduction = _any_span_seen(
            spans, [tokens for _revision, tokens in evidence_revisions]
        )
        if reintroduction:
            # Positive included evidence remains valid under bounded coverage;
            # only an absence claim requires a complete unambiguous history.
            reintroduction_status = "signal-present"
        elif (
            selection["history_coverage"] == "complete-synthetic-page"
            and not equal_time_non_lineage
            and not descendant_time_ambiguity
        ):
            reintroduction_status = "not-observed"
        else:
            reintroduction_status = "unresolved"
        import_signal = any(
            marker in (child["comment"] or "").casefold()
            for marker in contract["import_comment_markers"]
        )
        lineage_nodes = [child, *ancestor_chain]
        edge_pairs = list(zip(lineage_nodes, ancestor_chain))
        if descendant_time_inversion or any(
            ancestor["timestamp"] > descendant["timestamp"]
            for descendant, ancestor in edge_pairs
        ):
            chronology = "unresolved-inversion"
        elif descendant_equal_time or any(
            ancestor["timestamp"] == descendant["timestamp"]
            for descendant, ancestor in edge_pairs
        ):
            chronology = "unresolved-equal-time"
        else:
            chronology = "ordered"
        reasons = [
            "authorship-unresolved",
            "persistence-unresolved",
            "rights-unresolved",
        ]
        if not child_tokens or not spans:
            disposition = "excluded"
            reasons.append("zero-added-prose")
        elif (
            child["origin_revision_id"] != child["revision_id"]
            or rollback_signal
            or chronology == "unresolved-inversion"
        ):
            disposition = "unresolved"
            if child["origin_revision_id"] != child["revision_id"] or rollback_signal:
                reasons.append("inherited-or-rollback-signal")
        else:
            disposition = "accepted-for-parser-audit"
        if import_signal:
            reasons.append("non-authoritative-import-comment-signal")
        if chronology != "ordered":
            reasons.append("chronology-unresolved")
        record = {
            "schema_version": 1,
            "record_kind": "wikimedia-added-span",
            "source": "wikimedia",
            "selection_id": selection_id,
            "fixture_window": selection["fixture_window"],
            "disposition": disposition,
            "reasons": sorted(set(reasons)),
            "page": {
                "page_id": page["page_id"],
                "title": page["title"],
                "redirect_title": page["redirect_title"],
            },
            "lineage": {
                "parent_revision_id": parent["revision_id"],
                "child_revision_id": child["revision_id"],
                "child_parent_revision_id": child["parent_revision_id"],
                "parent_timestamp": parent["timestamp"],
                "child_timestamp": child["timestamp"],
                "history_coverage": selection["history_coverage"],
                "chronology": chronology,
            },
            "contributor": child["contributor"],
            "raw": {
                "parent_text": parent["raw_text"],
                "parent_bytes": parent["raw_bytes"],
                "parent_sha256": parent["raw_sha256"],
                "parent_mediawiki_sha1_base36": parent["mediawiki_sha1_base36"],
                "child_text": child["raw_text"],
                "child_bytes": child["raw_bytes"],
                "child_sha256": child["raw_sha256"],
                "child_mediawiki_sha1_base36": child["mediawiki_sha1_base36"],
            },
            "normalized": {
                "parent_text": parent_text,
                "parent_sha256": sha256_bytes(parent_text.encode("utf-8")),
                "parent_tokens": list(parent_tokens),
                "child_text": child_text,
                "child_sha256": sha256_bytes(child_text.encode("utf-8")),
                "child_tokens": list(child_tokens),
            },
            "candidate_spans": list(spans),
            "diagnostics": {
                "origin_revision_id": child["origin_revision_id"],
                "origin_matches_child": child["origin_revision_id"] == child["revision_id"],
                "rollback_signal": rollback_signal,
                "reintroduction_status": reintroduction_status,
                "import_comment_signal": "signal-present" if import_signal else "not-observed",
                "parent_removed_counts": parent_clean["removed_counts"],
                "child_removed_counts": child_clean["removed_counts"],
            },
            "transformation": contract["version"],
            "tokenizer": profile["transformations"]["content_tokenizer"],
            "authorship_status": "unresolved",
            "rights_status": "unresolved",
            "persistence_status": "unresolved",
            "scientific_eligibility": "unresolved",
        }
        records.append(record)
    return tuple(records), {"pages": len(page_map), "revisions": revision_total}
