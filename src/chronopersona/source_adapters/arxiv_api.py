"""Parse arXiv API Atom feeds into metadata-only candidate records.

The arXiv API supports ``submittedDate`` selection, unlike OAI-PMH. API output
is used only to enumerate era-native candidate IDs and metadata. License and
complete version-history eligibility remain unresolved until exact
``arXivRaw`` OAI enrichment is performed for each selected identifier.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET

from ..source_metadata import EraWindows


class ArxivApiError(ValueError):
    """Raised when an arXiv API Atom response is malformed or reports an error."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local(child.tag) == name and child.text:
            value = " ".join(child.text.split())
            if value:
                return value
    return None


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp(raw: str | None, *, field: str) -> datetime:
    if raw is None:
        raise ArxivApiError(f"arXiv API entry is missing {field}")
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ArxivApiError(
            f"invalid arXiv API {field} timestamp: {raw!r}"
        ) from error
    if parsed.tzinfo is None:
        raise ArxivApiError(
            f"arXiv API {field} timestamp lacks timezone: {raw!r}"
        )
    return parsed.astimezone(timezone.utc)


def _arxiv_id(raw_url: str | None) -> str:
    if raw_url is None:
        raise ArxivApiError("arXiv API entry is missing id")
    path = urlparse(raw_url).path.rstrip("/")
    marker = "/abs/"
    if marker not in path:
        raise ArxivApiError(f"unrecognized arXiv API entry id: {raw_url!r}")
    identifier = path.split(marker, 1)[1]
    if not identifier:
        raise ArxivApiError("arXiv API entry id is empty")
    return identifier


def _category_matches(categories: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(
        category == prefix or category.startswith(prefix + ".")
        for category in categories
        for prefix in prefixes
    )


def _author_evidence(entry: ET.Element) -> tuple[int, str]:
    authors: list[str] = []
    for author in [child for child in entry if _local(child.tag) == "author"]:
        name = _direct_text(author, "name") or ""
        affiliations = [
            " ".join(child.text.split())
            for child in author
            if _local(child.tag) == "affiliation" and child.text
        ]
        normalized = " | ".join([name, *affiliations]).strip(" |")
        if normalized:
            authors.append(normalized)
    return len(authors), _sha256_text("\n".join(authors))


def _feed_integer(root: ET.Element, name: str) -> int | None:
    for child in root:
        if _local(child.tag) == name and child.text:
            try:
                return int(child.text.strip())
            except ValueError as error:
                raise ArxivApiError(
                    f"arXiv API {name} is not an integer"
                ) from error
    return None


def parse_arxiv_api_feed(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_category_prefixes: tuple[str, ...],
    forbidden_category_prefixes: tuple[str, ...] = (),
    source_id: str = "arxiv-cc-single-version-descriptive",
) -> tuple[list[dict[str, Any]], dict[str, int | None]]:
    """Return unresolved arXiv era candidates and feed paging metadata."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ArxivApiError(f"invalid arXiv API XML: {error}") from error
    if _local(root.tag) != "feed":
        raise ArxivApiError("arXiv API response root must be an Atom feed")

    page = {
        "total_results": _feed_integer(root, "totalResults"),
        "start_index": _feed_integer(root, "startIndex"),
        "items_per_page": _feed_integer(root, "itemsPerPage"),
    }
    records: list[dict[str, Any]] = []
    for entry in [child for child in root if _local(child.tag) == "entry"]:
        identifier = _arxiv_id(_direct_text(entry, "id"))
        published = _timestamp(
            _direct_text(entry, "published"),
            field="published",
        )
        updated = _timestamp(
            _direct_text(entry, "updated"),
            field="updated",
        )
        era_window = windows.classify(published)
        categories = sorted(
            {
                str(child.attrib["term"])
                for child in entry
                if _local(child.tag) in {"category", "primary_category"}
                and child.attrib.get("term")
            }
        )
        category_allowed = _category_matches(
            categories,
            allowed_category_prefixes,
        )
        category_forbidden = _category_matches(
            categories,
            forbidden_category_prefixes,
        )
        title = _direct_text(entry, "title") or ""
        summary = _direct_text(entry, "summary") or ""
        author_count, authors_sha256 = _author_evidence(entry)

        exclusion_reasons = [
            "license-enrichment-required",
            "version-enrichment-required",
        ]
        if era_window == "outside":
            exclusion_reasons.append("outside-era-window")
        if not category_allowed:
            exclusion_reasons.append("category-not-in-frozen-stratum")
        if category_forbidden:
            exclusion_reasons.append("forbidden-cross-list-category")

        records.append(
            {
                "schema_version": 1,
                "record_id": f"arxiv-candidate:{identifier}",
                "source_id": source_id,
                "native_item_id": identifier,
                "native_timestamp": published.isoformat().replace("+00:00", "Z"),
                "timestamp_semantics": "submission-version",
                "era_window": era_window,
                "version_status": "unresolved",
                "version_count": 1,
                "rights_status": "unresolved",
                "license_id": "pending-arXivRaw-enrichment",
                "license_locator": (
                    "https://oaipmh.arxiv.org/oai?verb=GetRecord&"
                    "metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + identifier)}"
                ),
                "authorship_provenance": "human",
                "categories": categories,
                "review_strata": [
                    "exposure-boundary"
                    if category_forbidden or not category_allowed
                    else "version-boundary"
                ],
                "metadata_locator": (
                    "https://export.arxiv.org/api/query?id_list="
                    f"{quote(identifier)}"
                ),
                "content_locator": None,
                "content_retrieved": False,
                "eligibility": "unresolved",
                "exclusion_reasons": exclusion_reasons,
                "source_metadata": {
                    "candidate_selection_source": "arxiv-api-submittedDate",
                    "updated_timestamp": updated.isoformat().replace("+00:00", "Z"),
                    "published_equals_updated": published == updated,
                    "title_sha256": _sha256_text(title),
                    "title_length": len(title),
                    "abstract_sha256": _sha256_text(summary),
                    "abstract_length": len(summary),
                    "author_count": author_count,
                    "authors_sha256": authors_sha256,
                    "category_allowed": category_allowed,
                    "category_forbidden": category_forbidden,
                },
            }
        )
    return records, page
