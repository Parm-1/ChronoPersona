"""Shared fail-closed primitives for the frozen offline A/B parser gate."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import unicodedata
from typing import Any
import xml.etree.ElementTree as ET

from .content_manifest import tokenize_normalized
from .file_integrity import stable_read_unchanged
from .source_audit import canonical_json_bytes


_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_POSITIVE_DECIMAL = re.compile(r"^[1-9][0-9]*$")
_NONNEGATIVE_DECIMAL = re.compile(r"^(?:0|[1-9][0-9]*)$")
_UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
_STACK_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]\.[0-9]{3}$"
)


class ABParserError(RuntimeError):
    """One classified offline parser-gate failure.

    ``detail`` is retained only for local diagnostics and tests. Production
    portable artifacts and terminal summaries publish only ``stage`` and
    ``reason``.
    """

    def __init__(self, stage: str, reason: str, detail: str) -> None:
        super().__init__(detail)
        self.stage = stage
        self.reason = reason


def require(condition: bool, *, stage: str, reason: str, detail: str) -> None:
    if not condition:
        raise ABParserError(stage, reason, detail)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def stable_bounded_file_bytes(
    path: Path, *, label: str, maximum_bytes: int
) -> bytes:
    """Read one plain unaliased file without crossing a byte ceiling."""

    require(
        type(maximum_bytes) is int and maximum_bytes >= 1,
        stage="binding",
        reason="binding-failed",
        detail=f"{label} byte ceiling is invalid",
    )
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    def plain(info: os.stat_result) -> bool:
        return (
            stat.S_ISREG(info.st_mode)
            and not stat.S_ISLNK(info.st_mode)
            and not (int(getattr(info, "st_file_attributes", 0)) & reparse_flag)
            and int(info.st_nlink) == 1
        )

    try:
        path_before = path.lstat()
        require(
            plain(path_before) and int(path_before.st_size) <= maximum_bytes,
            stage="binding",
            reason="binding-failed",
            detail=f"{label} is not one bounded plain file",
        )
        with path.open("rb") as handle:
            handle_before = os.fstat(handle.fileno())
            payload = handle.read(maximum_bytes + 1)
            handle_after = os.fstat(handle.fileno())
        path_after = path.lstat()
    except ABParserError:
        raise
    except OSError as error:
        raise ABParserError(
            "binding", "binding-failed", f"cannot read {label}"
        ) from error
    require(
        len(payload) <= maximum_bytes
        and plain(path_after)
        and stable_read_unchanged(path_before, handle_before, handle_after, path_after),
        stage="binding",
        reason="binding-failed",
        detail=f"{label} changed while it was read",
    )
    return payload


def require_hex64(value: Any, *, label: str) -> str:
    require(
        isinstance(value, str) and _HEX64.fullmatch(value) is not None,
        stage="validation",
        reason="validation-failed",
        detail=f"{label} must be lowercase hexadecimal SHA-256",
    )
    return value


def canonical_jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    rendered = bytearray()
    for record in records:
        line = canonical_json_bytes(record)
        rendered.extend(line)
        rendered.extend(b"\n")
    return bytes(rendered)


def bounded_xml_text(
    payload: bytes,
    *,
    label: str,
    maximum_bytes: int,
    xml_declaration: str = '<?xml version="1.0" encoding="utf-8"?>',
    allowed_prolog_comment_lines: Sequence[str] | None = None,
) -> str:
    """Validate the exact bounded XML byte envelope before parsing."""

    require(
        isinstance(payload, bytes) and 0 < len(payload) <= maximum_bytes,
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} byte ceiling failed",
    )
    require(
        not payload.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")),
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} must not contain a byte-order mark",
    )
    require(
        b"\x00" not in payload,
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} contains NUL",
    )
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ABParserError(
            "input-preflight", "input-contract-failed", f"{label} is not UTF-8"
        ) from error
    require(
        text.startswith(xml_declaration + "\n"),
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} XML declaration is not exact",
    )
    folded = text.casefold()
    require(
        "<!doctype" not in folded and "<!entity" not in folded,
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} contains a prohibited declaration",
    )
    remainder = text[len(xml_declaration) + 1 :]
    require(
        "<?" not in remainder,
        stage="input-preflight",
        reason="input-contract-failed",
        detail=f"{label} contains an extra processing instruction",
    )
    comment_matches = list(re.finditer(r"<!--([\s\S]*?)-->", remainder))
    if allowed_prolog_comment_lines is None:
        require(
            not comment_matches,
            stage="input-preflight",
            reason="input-contract-failed",
            detail=f"{label} contains a prohibited XML comment",
        )
    else:
        require(
            len(comment_matches) in {0, 1},
            stage="input-preflight",
            reason="input-contract-failed",
            detail=f"{label} comment count is not exact",
        )
        if comment_matches:
            match = comment_matches[0]
            prefix = remainder[: match.start()]
            require(
                prefix.strip() == "",
                stage="input-preflight",
                reason="input-contract-failed",
                detail=f"{label} comment is not in the prolog",
            )
            observed = [
                line.strip()
                for line in match.group(1).splitlines()
                if line.strip()
            ]
            require(
                observed == list(allowed_prolog_comment_lines),
                stage="input-preflight",
                reason="input-contract-failed",
                detail=f"{label} prolog comment is not the frozen license comment",
            )
    return text


def parse_xml(text: str, *, label: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    try:
        root = ET.fromstring(text, parser=parser)
    except ET.ParseError as error:
        raise ABParserError(
            "input-preflight", "input-contract-failed", f"{label} XML is malformed"
        ) from error
    return root


def exact_scalar(
    element: ET.Element,
    *,
    label: str,
    allow_empty: bool = False,
    attributes: set[str] | None = None,
) -> str:
    expected_attributes = attributes or set()
    require(
        set(element.attrib) == expected_attributes and len(element) == 0,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} scalar shape is not exact",
    )
    value = element.text or ""
    require(
        allow_empty or value != "",
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} must not be empty",
    )
    return value


def one_direct(
    parent: ET.Element,
    tag: str,
    *,
    label: str,
    required: bool = True,
) -> ET.Element | None:
    matches = [child for child in parent if child.tag == tag]
    require(
        len(matches) == (1 if required else 0) or (not required and len(matches) == 1),
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} multiplicity is not exact",
    )
    return matches[0] if matches else None


def positive_decimal(value: str, *, label: str) -> int:
    require(
        _POSITIVE_DECIMAL.fullmatch(value) is not None,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} must be canonical positive decimal",
    )
    return int(value)


def nonnegative_decimal(value: str, *, label: str) -> int:
    require(
        _NONNEGATIVE_DECIMAL.fullmatch(value) is not None,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} must be canonical nonnegative decimal",
    )
    return int(value)


def signed_decimal(value: str, *, label: str) -> int:
    require(
        re.fullmatch(r"(?:0|-?[1-9][0-9]*)", value) is not None,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} must be canonical signed decimal",
    )
    return int(value)


def utc_timestamp(value: str, *, label: str) -> str:
    require(
        _UTC_TIMESTAMP.fullmatch(value) is not None,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} timestamp spelling is not exact",
    )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ABParserError(
            "validation", "parser-contract-failed", f"{label} timestamp is invalid"
        ) from error
    return value


def stack_timestamp(value: str, *, label: str) -> str:
    require(
        _STACK_TIMESTAMP.fullmatch(value) is not None,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} timestamp spelling is not exact",
    )
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError as error:
        raise ABParserError(
            "validation", "parser-contract-failed", f"{label} timestamp is invalid"
        ) from error
    return value + "Z"


def normalize_paragraph_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n+", normalized):
        collapsed = " ".join(block.split())
        if collapsed:
            paragraphs.append(collapsed)
    return "\n\n".join(paragraphs)


def bounded_text_evidence(
    text: str,
    *,
    label: str,
    maximum_bytes: int,
    maximum_tokens: int,
) -> tuple[str, tuple[str, ...]]:
    payload = text.encode("utf-8")
    require(
        len(payload) <= maximum_bytes,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} decoded-text ceiling exceeded",
    )
    tokens = tokenize_normalized(text)
    require(
        len(tokens) <= maximum_tokens,
        stage="validation",
        reason="parser-contract-failed",
        detail=f"{label} token ceiling exceeded",
    )
    return text, tokens


def mapping_exact(value: Any, keys: Iterable[str], *, label: str) -> Mapping[str, Any]:
    expected = set(keys)
    require(
        isinstance(value, Mapping) and set(value) == expected,
        stage="validation",
        reason="validation-failed",
        detail=f"{label} fields are not exact",
    )
    return value
