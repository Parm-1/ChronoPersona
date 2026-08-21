"""Strict synthetic Stack Exchange Posts/PostHistory reconstruction."""

from __future__ import annotations

from html import unescape
from html.parser import HTMLParser
import re
from typing import Any

from .ab_parser_common import (
    ABParserError,
    bounded_text_evidence,
    bounded_xml_text,
    nonnegative_decimal,
    normalize_paragraph_text,
    parse_xml,
    positive_decimal,
    require,
    sha256_bytes,
    signed_decimal,
    stack_timestamp,
)


_GUID = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}$"
)
_CONTENT_COMMENT = (
    "ContentLicense",
    "CC BY-SA 2.5 - Url: https://creativecommons.org/licenses/by-sa/2.5/",
    "CC BY-SA 3.0 - Url: https://creativecommons.org/licenses/by-sa/3.0/",
    "CC BY-SA 4.0 - Url: https://creativecommons.org/licenses/by-sa/4.0/",
)
_POSITIVE_FIELDS = frozenset(
    {
        "AcceptedAnswerId",
        "OwnerUserId",
        "LastEditorUserId",
        "ParentId",
    }
)
_NONNEGATIVE_FIELDS = frozenset(
    {
        "AnswerCount",
        "CommentCount",
        "FavoriteCount",
        "ViewCount",
    }
)
_DATE_FIELDS = frozenset(
    {
        "ClosedDate",
        "CommunityOwnedDate",
        "CreationDate",
        "LastActivityDate",
        "LastEditDate",
    }
)


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


def _rewrite_parenthesized_links(text: str, counts: dict[str, int]) -> str:
    """Remove balanced Markdown destinations while retaining ordinary labels."""

    pattern = re.compile(r"(!?)\[([^\]\n]*)\]\(")
    output: list[str] = []
    cursor = 0
    while True:
        match = pattern.search(text, cursor)
        if match is None:
            output.append(text[cursor:])
            break
        output.append(text[cursor : match.start()])
        depth = 1
        index = match.end()
        escaped = False
        while index < len(text) and depth:
            character = text[index]
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
            index += 1
        require(
            depth == 0,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Markdown link destination is unterminated",
        )
        counts["links"] += 1
        if not match.group(1):
            output.append(match.group(2))
        cursor = index
    return "".join(output)


def _drop_inline_code_spans(text: str) -> tuple[str, int]:
    """Remove CommonMark-style equal-length backtick spans, across lines."""

    output: list[str] = []
    index = 0
    removed = 0
    while index < len(text):
        if text[index] != "`":
            output.append(text[index])
            index += 1
            continue
        preceding_backslashes = 0
        backslash = index - 1
        while backslash >= 0 and text[backslash] == "\\":
            preceding_backslashes += 1
            backslash -= 1
        if preceding_backslashes % 2 == 1:
            output.append(text[index])
            index += 1
            continue
        end = index
        while end < len(text) and text[end] == "`":
            end += 1
        width = end - index
        cursor = end
        closing_end = None
        while cursor < len(text):
            next_tick = text.find("`", cursor)
            if next_tick < 0:
                break
            run_end = next_tick
            while run_end < len(text) and text[run_end] == "`":
                run_end += 1
            if run_end - next_tick == width:
                closing_end = run_end
                break
            cursor = run_end
        require(
            closing_end is not None,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="inline Markdown code delimiter is unmatched",
        )
        removed += 1
        index = closing_end
    return "".join(output), removed


_MAX_REFERENCE_TITLE_LINES = 8
_MAX_REFERENCE_LABEL_LINES = 3
_MAX_REFERENCE_LABEL_CHARACTERS = 999


def _ends_with_unescaped_delimiter(value: str, delimiter: str) -> bool:
    if not value.endswith(delimiter):
        return False
    backslashes = 0
    index = len(value) - len(delimiter) - 1
    while index >= 0 and value[index] == "\\":
        backslashes += 1
        index -= 1
    return backslashes % 2 == 0


def _reference_title_is_closed(line: str) -> bool:
    value = line.strip()
    if len(value) < 2 or value[0] not in {'"', "'", "("}:
        return False
    closing = ")" if value[0] == "(" else value[0]
    return _ends_with_unescaped_delimiter(value, closing)


def _reference_definition(line: str) -> tuple[str, str] | None:
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3 or not line[indent:].startswith("["):
        return None
    index = indent + 1
    label_start = index
    label_length = 0
    while index < len(line):
        if line[index] == "\\" and index + 1 < len(line):
            label_length += 1
            index += 2
            continue
        if line[index] == "]":
            if label_length > 0 and line[index + 1 : index + 2] == ":":
                return line[label_start:index], line[index + 2 :].lstrip(" \t")
            return None
        label_length += 1
        index += 1
    return None


def _continued_reference_definition(
    lines: list[str], index: int
) -> tuple[tuple[str, str] | None, int]:
    combined = lines[index]
    definition = _reference_definition(combined)
    if definition is not None:
        return definition, 1
    stripped = combined.lstrip(" ")
    if len(combined) - len(stripped) > 3 or not stripped.startswith("["):
        return None, 1
    for count in range(2, _MAX_REFERENCE_LABEL_LINES + 1):
        if index + count - 1 >= len(lines) or not lines[index + count - 1].strip():
            break
        combined += "\n" + lines[index + count - 1]
        require(
            len(combined) <= _MAX_REFERENCE_LABEL_CHARACTERS,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Markdown reference label is too long",
        )
        definition = _reference_definition(combined)
        if definition is not None:
            return definition, count
    return None, 1


_REFERENCE_DESTINATION_LINE = re.compile(
    r"^[ \t]{0,3}(?:<[^<>\n]+>|[^\s<>]+)[ \t]*$"
)


def _drop_reference_definitions(
    lines: list[str], counts: dict[str, int]
) -> tuple[list[str], dict[str, str]]:
    """Remove one bounded CommonMark reference definition and continuations."""

    output: list[str] = []
    labels: dict[str, str] = {}
    index = 0
    while index < len(lines):
        definition, definition_lines = _continued_reference_definition(lines, index)
        if definition is None:
            require(
                re.match(r"^[ \t]{0,3}\[.*\]:", lines[index]) is None,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="Markdown reference definition label is malformed",
            )
            output.append(lines[index])
            index += 1
            continue
        raw_label, remainder = definition
        label_key = re.sub(r"\s+", " ", raw_label).strip().casefold()
        require(
            label_key not in labels,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Markdown reference label is duplicated",
        )
        labels[label_key] = re.sub(
            r"\s+", " ", re.sub(r"\\(.)", r"\1", raw_label)
        ).strip()
        counts["reference_definitions"] += 1
        output.extend("" for _unused in range(definition_lines))
        remainder = remainder.strip()
        index += definition_lines
        if not remainder:
            require(
                index < len(lines)
                and _REFERENCE_DESTINATION_LINE.fullmatch(lines[index]) is not None,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="Markdown reference definition lacks a bounded destination",
            )
            output.append("")
            index += 1
        if index < len(lines):
            title = lines[index].strip()
            if _reference_title_is_closed(lines[index]):
                output.append("")
                index += 1
            elif title[:1] in {'"', "'", "("}:
                closing = ")" if title[0] == "(" else title[0]
                consumed = 0
                closed = False
                while index < len(lines) and consumed < _MAX_REFERENCE_TITLE_LINES:
                    current = lines[index].strip()
                    output.append("")
                    index += 1
                    consumed += 1
                    if (
                        len(current) > (1 if consumed == 1 else 0)
                        and _ends_with_unescaped_delimiter(current, closing)
                    ):
                        closed = True
                        break
                require(
                    closed,
                    stage="parse-stackexchange",
                    reason="parser-contract-failed",
                    detail="Markdown reference title is unterminated or too long",
                )
    return output, labels


def _indent_columns(line: str) -> int:
    columns = 0
    for character in line:
        if character == " ":
            columns += 1
        elif character == "\t":
            columns += 4 - (columns % 4)
        else:
            break
    return columns


def _whitespace_only(value: str | None, *, label: str) -> None:
    require(
        value is None or value.strip() == "",
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail=f"{label} contains mixed content",
    )


def _guid(value: str, *, label: str) -> str:
    require(
        _GUID.fullmatch(value) is not None,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail=f"{label} GUID spelling is not exact",
    )
    return value.casefold()


def _parse_rows(
    payload: bytes,
    *,
    label: str,
    root_name: str,
    maximum_bytes: int,
    allowed_attributes: set[str],
    declaration: str,
    comment_lines: list[str],
) -> list[dict[str, str]]:
    require(
        tuple(comment_lines) == _CONTENT_COMMENT,
        stage="validation",
        reason="validation-failed",
        detail="Stack Exchange comment contract is not frozen",
    )
    text = bounded_xml_text(
        payload,
        label=label,
        maximum_bytes=maximum_bytes,
        xml_declaration=declaration,
        allowed_prolog_comment_lines=comment_lines,
    )
    root = parse_xml(text, label=label)
    require(
        root.tag == root_name and not root.attrib,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail=f"{label} root is not exact",
    )
    _whitespace_only(root.text, label=label)
    rows: list[dict[str, str]] = []
    for child in root:
        require(
            child.tag == "row"
            and len(child) == 0
            and (child.text is None or child.text == "")
            and set(child.attrib).issubset(allowed_attributes),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail=f"{label} row shape or attributes drifted",
        )
        _whitespace_only(child.tail, label=label)
        rows.append(dict(child.attrib))
    require(
        bool(rows),
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail=f"{label} has no rows",
    )
    return rows


class _VisibleHTML(HTMLParser):
    def __init__(self, excluded_tags: set[str]) -> None:
        super().__init__(convert_charrefs=False)
        self.excluded_tags = excluded_tags
        self.excluded_depth = 0
        self.open_tags: list[str] = []
        self.parts: list[str] = []
        self.removed_blocks = 0
        self.removed_links = 0
        self.block_tags = {
            "address",
            "article",
            "aside",
            "br",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "hr",
            "li",
            "ol",
            "p",
            "section",
            "table",
            "tr",
            "ul",
        }
        self.void_tags = {
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        self.removed_links += sum(
            1
            for name, value in attrs
            if name.casefold() in {"cite", "href", "src"} and bool(value)
        )
        if tag not in self.void_tags:
            self.open_tags.append(tag)
        if tag in self.excluded_tags:
            self.excluded_depth += 1
            self.removed_blocks += 1
        elif self.excluded_depth == 0 and tag in self.block_tags:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.removed_links += sum(
            1
            for name, value in attrs
            if name.casefold() in {"cite", "href", "src"} and bool(value)
        )
        if self.excluded_depth == 0 and tag.casefold() in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        require(
            bool(self.open_tags) and self.open_tags[-1] == tag,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="HTML tag nesting is not exact",
        )
        self.open_tags.pop()
        if tag in self.excluded_tags:
            require(
                self.excluded_depth > 0,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="unbalanced excluded HTML block",
            )
            self.excluded_depth -= 1
        elif self.excluded_depth == 0 and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.excluded_depth == 0:
            self.parts.append(data)

    def handle_entityref(self, name: str) -> None:
        if self.excluded_depth == 0:
            self.parts.append(unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        if self.excluded_depth == 0:
            self.parts.append(unescape(f"&#{name};"))

    def handle_comment(self, data: str) -> None:
        return

    def result(self) -> str:
        require(
            self.excluded_depth == 0 and not self.open_tags,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="unterminated excluded HTML block",
        )
        return "".join(self.parts)


def sanitize_markdown_body_v0(text: str, contract: dict[str, Any]) -> dict[str, Any]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    counts = {
        "fenced_code_blocks": 0,
        "indented_code_lines": 0,
        "inline_code_spans": 0,
        "quote_lines": 0,
        "reference_definitions": 0,
        "links": 0,
        "boilerplate_lines": 0,
        "html_blocks": 0,
        "signature_blocks": 0,
    }
    source_lines = normalized.split("\n")
    output_lines: list[str] = []
    fence: str | None = None
    signature = False
    quote_block = False
    for line in source_lines:
        if signature:
            output_lines.append("")
            continue
        if fence is not None:
            closing = re.fullmatch(
                rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*", line
            )
            if closing is not None:
                fence = None
            output_lines.append("")
            continue
        if line in set(contract["signature_delimiter_lines"]):
            signature = True
            counts["signature_blocks"] += 1
            output_lines.append("")
            continue
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence_match and (
            fence_match.group(1).startswith("~") or "`" not in fence_match.group(2)
        ):
            marker = fence_match.group(1)
            fence = marker[0] * len(marker)
            counts["fenced_code_blocks"] += 1
            output_lines.append("")
            continue
        if line and _indent_columns(line) >= 4:
            counts["indented_code_lines"] += 1
            output_lines.append("")
            continue
        list_code = re.match(
            r"^ {0,3}(?:[*+-]|[0-9]{1,9}[.)])([ \t]+)\S", line
        )
        if list_code is not None and _indent_columns(list_code.group(1)) >= 5:
            counts["indented_code_lines"] += 1
            output_lines.append("")
            continue
        if re.match(
            r"^[ \t]*(?:(?:[*+-]|[0-9]{1,9}[.)])[ \t]+)*>", line
        ):
            counts["quote_lines"] += 1
            quote_block = True
            output_lines.append("")
            continue
        if quote_block:
            if line.strip() == "":
                quote_block = False
                output_lines.append("")
            else:
                counts["quote_lines"] += 1
                output_lines.append("")
            continue
        if line.strip().casefold() in set(contract["boilerplate_lines_casefolded"]):
            counts["boilerplate_lines"] += 1
            output_lines.append("")
            continue
        output_lines.append(line)
    require(
        fence is None,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="unterminated Markdown fence",
    )
    output_lines, reference_labels = _drop_reference_definitions(output_lines, counts)
    normalized = "\n".join(output_lines)
    normalized, counts["inline_code_spans"] = _drop_inline_code_spans(normalized)
    normalized = _rewrite_parenthesized_links(normalized, counts)
    require(
        "](" not in normalized,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="Markdown link label shape is not supported",
    )

    def reference_link(match: re.Match[str]) -> str:
        counts["links"] += 1
        return re.sub(r"\\(.)", r"\1", match.group(1))

    normalized = re.sub(
        r"\[((?:\\.|[^\[\]\\\n])+)\]\[((?:\\.|[^\[\]\\\n])*)\]",
        reference_link,
        normalized,
    )
    require(
        "][" not in normalized,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="Markdown reference-link label shape is not supported",
    )

    def shortcut_reference(match: re.Match[str]) -> str:
        key = re.sub(r"\s+", " ", match.group(1)).strip().casefold()
        visible = reference_labels.get(key)
        if visible is None:
            return match.group(0)
        counts["links"] += 1
        return re.sub(r"\\(.)", r"\1", match.group(1))

    normalized = re.sub(
        r"\[((?:\\.|[^\]\\\n])+)\]", shortcut_reference, normalized
    )
    locator = _locator_pattern(contract["external_link_schemes"])
    normalized, removed_autolinks = re.subn(rf"<{locator}[^<>\s]+>", "", normalized)
    counts["links"] += removed_autolinks
    parser = _VisibleHTML(set(contract["drop_html_block_tags"]))
    try:
        parser.feed(normalized)
        parser.close()
    except Exception as error:
        if isinstance(error, ABParserError):
            raise
        raise ABParserError(
            "parse-stackexchange",
            "parser-contract-failed",
            "Markdown HTML layer is malformed",
        ) from error
    counts["html_blocks"] = parser.removed_blocks
    counts["links"] += parser.removed_links
    normalized = parser.result()
    normalized = re.sub(r"(?:\*\*|__|~~|(?<!\*)\*(?!\*)|(?<!_)_(?!_))", "", normalized)
    normalized, decoded_locators = re.subn(
        rf"(?<!\w){locator}[^\s<>\[\]]+", "", normalized
    )
    counts["links"] += decoded_locators
    final_lines: list[str] = []
    boilerplate = set(contract["boilerplate_lines_casefolded"])
    for line in normalized.split("\n"):
        if line.strip().casefold() in boilerplate:
            counts["boilerplate_lines"] += 1
            final_lines.append("")
        else:
            final_lines.append(line)
    normalized = "\n".join(final_lines)
    normalized = normalize_paragraph_text(normalized)
    return {"text": normalized, "removed_counts": counts}


def normalize_plain_title_v0(text: str) -> str:
    parser = _VisibleHTML({"script", "style"})
    try:
        parser.feed(text)
        parser.close()
    except Exception as error:
        if isinstance(error, ABParserError):
            raise
        raise ABParserError(
            "parse-stackexchange",
            "parser-contract-failed",
            "title entity layer is malformed",
        ) from error
    return normalize_paragraph_text(parser.result())


def _actor(row: dict[str, str]) -> dict[str, Any]:
    user_id = row.get("UserId")
    display = row.get("UserDisplayName")
    if display is not None:
        require(
            bool(display) and display == display.strip(),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="history display actor is empty or noncanonical",
        )
    if user_id is not None:
        positive_decimal(user_id, label="history user id")
        return {"kind": "registered", "user_id": user_id, "display_name": display}
    if display is not None:
        return {"kind": "display-only", "user_id": None, "display_name": display}
    return {"kind": "missing", "user_id": None, "display_name": None}


def _actor_key(actor: dict[str, Any]) -> tuple[str, str | None]:
    if actor["kind"] == "registered":
        return ("registered", actor["user_id"])
    if actor["kind"] == "display-only":
        return ("display-only", actor["display_name"])
    return ("missing", None)


def _validate_posts_row(row: dict[str, str], *, maximum_text_bytes: int) -> dict[str, Any]:
    for required in ("Id", "PostTypeId", "CreationDate"):
        require(
            required in row,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Posts row is missing a required field",
        )
    post_id = row["Id"]
    positive_decimal(post_id, label="post id")
    post_type_id = positive_decimal(row["PostTypeId"], label="post type id")
    require(
        post_type_id in {1, 2},
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="only question and answer Posts rows are supported",
    )
    for field in _POSITIVE_FIELDS & row.keys():
        positive_decimal(row[field], label=f"Posts {field}")
    for field in _NONNEGATIVE_FIELDS & row.keys():
        nonnegative_decimal(row[field], label=f"Posts {field}")
    if "Score" in row:
        signed_decimal(row["Score"], label="Posts Score")
    dates = {}
    for field in _DATE_FIELDS & row.keys():
        dates[field] = stack_timestamp(row[field], label=f"Posts {field}")
    for field in ("OwnerDisplayName", "LastEditorDisplayName"):
        if field in row:
            require(
                bool(row[field]) and row[field] == row[field].strip(),
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail=f"Posts {field} is empty or noncanonical",
            )
    if post_type_id == 1:
        require(
            "ParentId" not in row and "Title" in row and "Tags" in row,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="question Posts shape is not exact",
        )
    else:
        require(
            "ParentId" in row and "Title" not in row and "Tags" not in row,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="answer Posts shape is not exact",
        )
        require(
            row["ParentId"] != post_id,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="answer cannot be its own parent",
        )
    require(
        "Body" in row,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="selected Posts row has suppressed body",
    )
    for field in ("Body", "Title", "Tags"):
        if field in row:
            require(
                len(row[field].encode("utf-8")) <= maximum_text_bytes,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail=f"Posts {field} exceeds the decoded-text ceiling",
            )
    owner = None
    if "OwnerUserId" in row:
        owner = {"kind": "registered", "user_id": row["OwnerUserId"], "display_name": row.get("OwnerDisplayName")}
    elif "OwnerDisplayName" in row:
        owner = {"kind": "display-only", "user_id": None, "display_name": row["OwnerDisplayName"]}
    return {
        "post_id": post_id,
        "post_type_id": post_type_id,
        "creation_timestamp": dates["CreationDate"],
        "parent_id": row.get("ParentId"),
        "body": row["Body"],
        "title": row.get("Title"),
        "tags": row.get("Tags"),
        "owner": owner,
        "raw": row,
    }


def _validate_history_row(
    row: dict[str, str], *, documented_types: set[int], maximum_text_bytes: int
) -> dict[str, Any]:
    for required in (
        "Id",
        "PostHistoryTypeId",
        "PostId",
        "RevisionGUID",
        "CreationDate",
    ):
        require(
            required in row,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="PostHistory row is missing a required field",
        )
    history_id = row["Id"]
    post_id = row["PostId"]
    positive_decimal(history_id, label="history row id")
    positive_decimal(post_id, label="history post id")
    type_id = positive_decimal(row["PostHistoryTypeId"], label="history type id")
    require(
        type_id in documented_types,
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="PostHistory type is not in the frozen map",
    )
    if type_id in set(range(1, 10)):
        require(
            "Text" in row,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="text-bearing PostHistory row has suppressed text",
        )
    if "Text" in row:
        require(
            len(row["Text"].encode("utf-8")) <= maximum_text_bytes,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="PostHistory Text exceeds the decoded-text ceiling",
        )
    timestamp = stack_timestamp(row["CreationDate"], label="PostHistory CreationDate")
    return {
        "history_id": history_id,
        "post_id": post_id,
        "type_id": type_id,
        "guid": _guid(row["RevisionGUID"], label="PostHistory"),
        "timestamp": timestamp,
        "actor": _actor(row),
        "text": row.get("Text"),
        "raw": row,
    }


def parse_stackexchange_fixture(
    posts_payload: bytes,
    history_payload: bytes,
    *,
    profile: dict[str, Any],
    selections: list[tuple[str, dict[str, Any]]],
) -> tuple[tuple[dict[str, Any], ...], dict[str, int]]:
    limits = profile["limits"]
    contract = profile["transformations"]["stackexchange"]
    posts_rows = _parse_rows(
        posts_payload,
        label="Stack Exchange Posts fixture",
        root_name="posts",
        maximum_bytes=limits["max_xml_input_bytes"],
        allowed_attributes=set(contract["posts_attribute_allowlist"]),
        declaration=contract["xml_declaration"],
        comment_lines=contract["allowed_prolog_comment_lines"],
    )
    history_rows = _parse_rows(
        history_payload,
        label="Stack Exchange PostHistory fixture",
        root_name="posthistory",
        maximum_bytes=limits["max_xml_input_bytes"],
        allowed_attributes=set(contract["posthistory_attribute_allowlist"]),
        declaration=contract["xml_declaration"],
        comment_lines=contract["allowed_prolog_comment_lines"],
    )
    require(
        len(posts_rows) <= limits["max_posts_rows"]
        and len(history_rows) <= limits["max_posthistory_rows"]
        and len(posts_rows) + len(history_rows) <= limits["max_combined_revisions_and_rows"],
        stage="parse-stackexchange",
        reason="parser-contract-failed",
        detail="Stack Exchange row ceiling exceeded",
    )
    posts: dict[str, dict[str, Any]] = {}
    for raw in posts_rows:
        post = _validate_posts_row(
            raw, maximum_text_bytes=limits["max_decoded_text_bytes"]
        )
        require(
            post["post_id"] not in posts,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Posts IDs are not unique",
        )
        posts[post["post_id"]] = post
        current_body = sanitize_markdown_body_v0(post["body"], contract)["text"]
        bounded_text_evidence(
            current_body,
            label="normalized Posts body",
            maximum_bytes=limits["max_decoded_text_bytes"],
            maximum_tokens=limits["max_normalized_tokens"],
        )
        if post["title"] is not None:
            bounded_text_evidence(
                normalize_plain_title_v0(post["title"]),
                label="normalized Posts title",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
        if post["tags"] is not None:
            bounded_text_evidence(
                normalize_paragraph_text(post["tags"]),
                label="normalized Posts tags",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
    documented = set(contract["documented_history_type_ids"])
    category_map = {int(key): value for key, value in contract["history_type_categories"].items()}
    require(
        set(category_map) == documented,
        stage="validation",
        reason="validation-failed",
        detail="PostHistory type map does not cover the frozen type set",
    )
    history: list[dict[str, Any]] = []
    history_ids: set[str] = set()
    guid_identity: dict[str, tuple[str, str]] = {}
    for raw in history_rows:
        record = _validate_history_row(
            raw,
            documented_types=documented,
            maximum_text_bytes=limits["max_decoded_text_bytes"],
        )
        require(
            record["history_id"] not in history_ids,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="PostHistory row IDs are not unique",
        )
        history_ids.add(record["history_id"])
        identity = (record["post_id"], record["timestamp"])
        prior = guid_identity.setdefault(record["guid"], identity)
        require(
            prior == identity,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="PostHistory GUID is reused across actions",
        )
        history.append(record)
        if record["text"] is not None:
            if record["type_id"] in {2, 5, 8}:
                normalized_history = sanitize_markdown_body_v0(
                    record["text"], contract
                )["text"]
            elif record["type_id"] in {1, 4, 7}:
                normalized_history = normalize_plain_title_v0(record["text"])
            else:
                normalized_history = normalize_paragraph_text(record["text"])
            bounded_text_evidence(
                normalized_history,
                label="normalized PostHistory Text",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )

    records: list[dict[str, Any]] = []
    for selection_id, selection in selections:
        post = posts.get(selection["post_id"])
        require(
            post is not None,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="selected Stack Exchange post is missing",
        )
        expected_type = 1 if selection["post_type"] == "question" else 2
        require(
            post["post_type_id"] == expected_type
            and post["creation_timestamp"] == selection["creation_timestamp"],
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="selected Stack Exchange post identity drifted",
        )
        require(
            post["parent_id"] == selection.get("parent_post_id"),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="selected Stack Exchange parent lineage drifted",
        )
        selected_history = [item for item in history if item["post_id"] == post["post_id"]]
        require(
            bool(selected_history)
            and all(
                item["timestamp"] >= post["creation_timestamp"]
                for item in selected_history
            ),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="selected history precedes post creation or is missing",
        )
        by_time: dict[str, set[str]] = {}
        action_types: set[tuple[str, str, int]] = set()
        for item in selected_history:
            by_time.setdefault(item["timestamp"], set()).add(item["guid"])
            action_type = (item["timestamp"], item["guid"], item["type_id"])
            require(
                action_type not in action_types,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="Stack Exchange action contains a duplicate history type",
            )
            action_types.add(action_type)
        require(
            all(len(guids) == 1 for guids in by_time.values()),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="same-time Stack Exchange actions are ambiguous",
        )
        required_types = {1, 2, 3} if expected_type == 1 else {2}
        initial = [item for item in selected_history if item["type_id"] in required_types]
        forbidden_initial = [
            item
            for item in selected_history
            if (expected_type == 2 and item["type_id"] in {1, 3})
        ]
        require(
            not forbidden_initial
            and {item["type_id"] for item in initial} == required_types
            and len(initial) == len(required_types),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="initial Stack Exchange action components are not exact",
        )
        initial_guids = {item["guid"] for item in initial}
        initial_times = {item["timestamp"] for item in initial}
        actor_keys = {_actor_key(item["actor"]) for item in initial}
        require(
            len(initial_guids) == len(initial_times) == len(actor_keys) == 1,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="initial Stack Exchange action does not share GUID/time/actor",
        )
        initial_time = next(iter(initial_times))
        initial_guid = next(iter(initial_guids))
        initial_action_rows = [
            item
            for item in selected_history
            if item["timestamp"] == initial_time and item["guid"] == initial_guid
        ]
        require(
            len(initial_action_rows) == len(required_types)
            and {item["type_id"] for item in initial_action_rows} == required_types
            and len({_actor_key(item["actor"]) for item in initial_action_rows}) == 1,
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="initial Stack Exchange action contains extra components",
        )
        require(
            all(item["timestamp"] >= initial_time for item in selected_history),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="Stack Exchange history precedes its initial action",
        )
        body_row = next(item for item in initial if item["type_id"] == 2)
        title_row = next((item for item in initial if item["type_id"] == 1), None)
        tags_row = next((item for item in initial if item["type_id"] == 3), None)
        body_raw = body_row["text"]
        require(
            isinstance(body_raw, str),
            stage="parse-stackexchange",
            reason="parser-contract-failed",
            detail="initial body is suppressed",
        )
        title_raw = title_row["text"] if title_row is not None else None
        tags_raw = tags_row["text"] if tags_row is not None else None
        if expected_type == 1:
            require(
                isinstance(title_raw, str) and isinstance(tags_raw, str),
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="initial question title or tags are suppressed",
            )
        body_clean = sanitize_markdown_body_v0(body_raw, contract)
        body_text, body_tokens = bounded_text_evidence(
            body_clean["text"],
            label="normalized initial Stack Exchange body",
            maximum_bytes=limits["max_decoded_text_bytes"],
            maximum_tokens=limits["max_normalized_tokens"],
        )
        title_text = normalize_plain_title_v0(title_raw) if title_raw is not None else None
        title_tokens: tuple[str, ...] = ()
        if title_text is not None:
            title_text, title_tokens = bounded_text_evidence(
                title_text,
                label="normalized initial Stack Exchange title",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
        # Current fields are sentinels only; they can never source the record.
        current_body_clean, _current_body_tokens = bounded_text_evidence(
            sanitize_markdown_body_v0(post["body"], contract)["text"],
            label="normalized current Stack Exchange body",
            maximum_bytes=limits["max_decoded_text_bytes"],
            maximum_tokens=limits["max_normalized_tokens"],
        )
        current_title_clean = (
            normalize_plain_title_v0(post["title"]) if post["title"] is not None else None
        )
        if current_title_clean is not None:
            current_title_clean, _current_title_tokens = bounded_text_evidence(
                current_title_clean,
                label="normalized current Stack Exchange title",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
        current_relations = {
            "body": "same" if current_body_clean == body_text else "different",
            "title": (
                "absent"
                if expected_type == 2
                else "same"
                if current_title_clean == title_text
                else "different"
            ),
        }
        for field in selection["current_fields_must_differ"]:
            require(
                current_relations[field] == "different",
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="current Stack Exchange sentinel is not different",
            )
            type_ids = {"body": {5, 8}, "title": {4, 7}}[field]
            later = [
                item
                for item in selected_history
                if item["type_id"] in type_ids and item["timestamp"] > initial_time
            ]
            require(
                bool(later),
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="differing current field lacks a later history action",
            )
            required_edit_type = {"body": 5, "title": 4}[field]
            require(
                any(item["type_id"] == required_edit_type for item in later),
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="differing current field lacks its required later edit",
            )
            latest_timestamp = max(item["timestamp"] for item in later)
            latest = [item for item in later if item["timestamp"] == latest_timestamp]
            require(
                len(latest) == 1 and isinstance(latest[0]["text"], str),
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="latest current-field history action is ambiguous",
            )
            latest_visible = (
                sanitize_markdown_body_v0(latest[0]["text"], contract)["text"]
                if field == "body"
                else normalize_plain_title_v0(latest[0]["text"])
            )
            latest_visible, _latest_tokens = bounded_text_evidence(
                latest_visible,
                label=f"normalized latest Stack Exchange {field}",
                maximum_bytes=limits["max_decoded_text_bytes"],
                maximum_tokens=limits["max_normalized_tokens"],
            )
            current_visible = current_body_clean if field == "body" else current_title_clean
            require(
                latest_visible == current_visible,
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="current field does not match its latest history action",
            )
        if expected_type == 2 and post["parent_id"] in posts:
            require(
                posts[post["parent_id"]]["post_type_id"] == 1
                and posts[post["parent_id"]]["creation_timestamp"]
                <= post["creation_timestamp"],
                stage="parse-stackexchange",
                reason="parser-contract-failed",
                detail="answer parent in bundle is not an earlier question",
            )
        signal_categories = sorted(
            {category_map[item["type_id"]] for item in selected_history}
        )
        deletion = any(item["type_id"] in {12, 13} for item in selected_history)
        migration = any(
            item["type_id"] in set(contract["deletion_migration_type_ids"]) - {12, 13}
            for item in selected_history
        )
        generated = int(post["post_id"]) in set(contract["generated_post_ids"])
        reasons = ["authorship-unresolved", "license-unresolved", "rights-unresolved"]
        if generated:
            reasons.append("generated-post-id")
        if deletion:
            reasons.append("deletion-signal")
        if migration:
            reasons.append("migration-signal")
        if initial_time != post["creation_timestamp"]:
            reasons.append("creation-action-time-mismatch")
        if not body_tokens or (expected_type == 1 and not title_tokens):
            reasons.append("zero-clean-prose")
        if generated or deletion or migration or "zero-clean-prose" in reasons:
            disposition = "excluded"
        elif initial_time != post["creation_timestamp"]:
            disposition = "unresolved"
        else:
            disposition = "accepted-for-parser-audit"
        record = {
            "schema_version": 1,
            "record_kind": "stackexchange-initial-version",
            "source": "stackexchange",
            "selection_id": selection_id,
            "fixture_window": selection["fixture_window"],
            "stratum": selection["post_type"],
            "disposition": disposition,
            "reasons": sorted(set(reasons)),
            "post": {
                "site_id": selection["site_id"],
                "post_id": post["post_id"],
                "post_type": selection["post_type"],
                "parent_post_id": post["parent_id"],
                "creation_timestamp": post["creation_timestamp"],
                "current_owner": post["owner"],
            },
            "initial_action": {
                "revision_guid": next(iter(initial_guids)),
                "timestamp": initial_time,
                "history_row_ids": [
                    item["history_id"]
                    for item in sorted(initial, key=lambda value: value["type_id"])
                ],
                "actor": body_row["actor"],
                "raw_title": title_raw,
                "raw_title_sha256": (
                    sha256_bytes(title_raw.encode("utf-8")) if title_raw is not None else None
                ),
                "raw_body": body_raw,
                "raw_body_sha256": sha256_bytes(body_raw.encode("utf-8")),
                "raw_tags": tags_raw,
                "raw_tags_sha256": (
                    sha256_bytes(tags_raw.encode("utf-8")) if tags_raw is not None else None
                ),
                "normalized_title": title_text,
                "normalized_title_sha256": (
                    sha256_bytes(title_text.encode("utf-8")) if title_text is not None else None
                ),
                "title_tokens": list(title_tokens),
                "normalized_body": body_text,
                "normalized_body_sha256": sha256_bytes(body_text.encode("utf-8")),
                "body_tokens": list(body_tokens),
            },
            "current_field_evidence": {
                "body_relation": current_relations["body"],
                "body_sha256": sha256_bytes(post["body"].encode("utf-8")),
                "title_relation": current_relations["title"],
                "title_sha256": (
                    sha256_bytes(post["title"].encode("utf-8"))
                    if post["title"] is not None
                    else None
                ),
            },
            "history": {
                "row_count": len(selected_history),
                "signal_categories": signal_categories,
                "ordered_actions": [
                    {
                        "timestamp": timestamp,
                        "revision_guid": next(iter(by_time[timestamp])),
                        "type_ids": sorted(
                            item["type_id"]
                            for item in selected_history
                            if item["timestamp"] == timestamp
                        ),
                    }
                    for timestamp in sorted(by_time)
                ],
            },
            "diagnostics": {
                "current_fields_used_as_prose": False,
                "body_removed_counts": body_clean["removed_counts"],
            },
            "transformation": contract["version"],
            "tokenizer": profile["transformations"]["content_tokenizer"],
            "authorship_status": "unresolved",
            "license_status": "unresolved",
            "rights_status": "unresolved",
            "scientific_eligibility": "unresolved",
        }
        records.append(record)
    return tuple(records), {
        "posts_rows": len(posts_rows),
        "posthistory_rows": len(history_rows),
    }
