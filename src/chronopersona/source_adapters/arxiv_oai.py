"""Parse arXiv OAI-PMH ``arXivRaw`` metadata without retaining prose."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

from ..source_metadata import EraWindows


class ArxivMetadataError(ValueError):
    """Raised when an arXiv OAI response is malformed or reports an error."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element.iter() if _local(child.tag) == name]


def _first_text(element: ET.Element, name: str) -> str | None:
    for child in element.iter():
        if _local(child.tag) == name and child.text:
            value = " ".join(child.text.split())
            if value:
                return value
    return None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _version_timestamp(raw: str) -> datetime:
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError) as error:
        raise ArxivMetadataError(
            f"invalid arXiv version date: {raw!r}"
        ) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _license(raw: str | None) -> tuple[str, str, str]:
    if raw is None:
        return "missing", "unresolved", "missing-license"
    normalized = raw.strip().lower().rstrip("/")
    if "creativecommons.org/publicdomain/zero/" in normalized:
        version = normalized.rsplit("/", 1)[-1]
        return f"CC0-{version}", "eligible", raw
    marker = "creativecommons.org/licenses/by/"
    if marker in normalized:
        version = normalized.split(marker, 1)[1].split("/", 1)[0]
        return f"CC-BY-{version}", "eligible", raw
    if "creativecommons.org/licenses/" in normalized:
        return "creative-commons-other", "ineligible", raw
    if "arxiv.org/licenses/nonexclusive-distrib" in normalized:
        return "arXiv-default", "ineligible", raw
    return "custom-or-unresolved", "unresolved", raw


def _category_matches(categories: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(
        category == prefix or category.startswith(prefix + ".")
        for category in categories
        for prefix in prefixes
    )


def _author_evidence(raw: ET.Element) -> tuple[int, str]:
    authors: list[str] = []
    for author in [child for child in raw.iter() if _local(child.tag) == "author"]:
        fields = [
            _first_text(author, name) or ""
            for name in ("keyname", "forenames", "suffix", "affiliation")
        ]
        normalized = " | ".join(field for field in fields if field)
        if normalized:
            authors.append(normalized)
    return len(authors), _sha256_text("\n".join(authors))


def _oai_error(root: ET.Element) -> None:
    error = next(
        (element for element in root.iter() if _local(element.tag) == "error"),
        None,
    )
    if error is None:
        return
    code = error.attrib.get("code", "unknown")
    message = " ".join((error.text or "").split()) or "unspecified OAI error"
    raise ArxivMetadataError(f"arXiv OAI error {code}: {message}")


def parse_arxiv_raw_oai(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_category_prefixes: tuple[str, ...],
    forbidden_category_prefixes: tuple[str, ...] = (),
    source_id: str = "arxiv-cc-single-version-descriptive",
) -> tuple[list[dict[str, Any]], str | None, dict[str, int]]:
    """Return metadata-only records, resumption token, and diagnostics."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ArxivMetadataError(f"invalid OAI XML: {error}") from error
    _oai_error(root)

    diagnostics = {
        "records_seen": 0,
        "deleted_records": 0,
        "records_without_metadata": 0,
    }
    records: list[dict[str, Any]] = []
    for record in _children(root, "record"):
        diagnostics["records_seen"] += 1
        header = next(
            (child for child in record if _local(child.tag) == "header"),
            None,
        )
        if header is None:
            raise ArxivMetadataError("arXiv OAI record has no header")
        if header.attrib.get("status") == "deleted":
            diagnostics["deleted_records"] += 1
            continue
        metadata = next(
            (child for child in record if _local(child.tag) == "metadata"),
            None,
        )
        if metadata is None or not list(metadata):
            diagnostics["records_without_metadata"] += 1
            continue
        raw = list(metadata)[0]
        arxiv_id = _first_text(raw, "id")
        if not arxiv_id:
            raise ArxivMetadataError("arXivRaw record is missing id")

        version_elements = [
            child for child in raw if _local(child.tag) == "version"
        ]
        if not version_elements:
            raise ArxivMetadataError(
                f"arXivRaw record {arxiv_id} has no versions"
            )
        versions: list[tuple[datetime, str]] = []
        for version in version_elements:
            raw_date = _first_text(version, "date")
            if raw_date is None:
                raise ArxivMetadataError(
                    f"arXivRaw record {arxiv_id} has a version without date"
                )
            versions.append(
                (
                    _version_timestamp(raw_date),
                    version.attrib.get("version", "unknown"),
                )
            )

        first_timestamp, first_version = min(versions, key=lambda item: item[0])
        era_window = windows.classify(first_timestamp)
        categories_raw = _first_text(raw, "categories") or ""
        categories = sorted(set(categories_raw.split()))
        license_id, rights_status, license_locator = _license(
            _first_text(raw, "license")
        )
        title = _first_text(raw, "title") or ""
        abstract = _first_text(raw, "abstract") or ""
        author_count, authors_sha256 = _author_evidence(raw)
        category_allowed = _category_matches(
            categories,
            allowed_category_prefixes,
        )
        category_forbidden = _category_matches(
            categories,
            forbidden_category_prefixes,
        )

        exclusion_reasons: list[str] = []
        if era_window == "outside":
            exclusion_reasons.append("outside-era-window")
        if len(version_elements) != 1:
            exclusion_reasons.append("multiple-versions-heldout")
        if rights_status != "eligible":
            exclusion_reasons.append("license-not-eligible")
        if not category_allowed:
            exclusion_reasons.append("category-not-in-frozen-stratum")
        if category_forbidden:
            exclusion_reasons.append("forbidden-cross-list-category")

        eligibility = "eligible" if not exclusion_reasons else "excluded"
        version_status = (
            "single-version" if len(version_elements) == 1 else "latest-only"
        )
        native_item_id = f"{arxiv_id}{first_version}"
        records.append(
            {
                "schema_version": 1,
                "record_id": f"arxiv:{native_item_id}",
                "source_id": source_id,
                "native_item_id": native_item_id,
                "native_timestamp": first_timestamp.isoformat().replace(
                    "+00:00", "Z"
                ),
                "timestamp_semantics": "submission-version",
                "era_window": era_window,
                "version_status": version_status,
                "version_count": len(version_elements),
                "rights_status": rights_status,
                "license_id": license_id,
                "license_locator": license_locator,
                "authorship_provenance": "human",
                "categories": categories,
                "review_strata": [
                    "eligible-random"
                    if eligibility == "eligible"
                    else (
                        "rights-boundary"
                        if rights_status != "eligible"
                        else "exposure-boundary"
                    )
                ],
                "metadata_locator": (
                    "https://oaipmh.arxiv.org/oai?verb=GetRecord&"
                    f"metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + arxiv_id)}"
                ),
                "content_locator": None,
                "content_retrieved": False,
                "eligibility": eligibility,
                "exclusion_reasons": exclusion_reasons,
                "source_metadata": {
                    "version_labels": [label for _, label in versions],
                    "title_sha256": _sha256_text(title),
                    "title_length": len(title),
                    "abstract_sha256": _sha256_text(abstract),
                    "abstract_length": len(abstract),
                    "author_count": author_count,
                    "authors_sha256": authors_sha256,
                    "category_allowed": category_allowed,
                    "category_forbidden": category_forbidden,
                },
            }
        )

    token_element = next(
        (
            element
            for element in root.iter()
            if _local(element.tag) == "resumptionToken"
        ),
        None,
    )
    token = (
        token_element.text.strip()
        if token_element is not None and token_element.text
        else None
    )
    return records, token, diagnostics
