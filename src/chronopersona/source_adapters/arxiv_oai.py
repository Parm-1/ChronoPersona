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
    """Raised when an arXiv OAI record lacks required metadata."""


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


def _category_allowed(
    categories: list[str],
    allowed_prefixes: tuple[str, ...],
) -> bool:
    return any(
        category == prefix or category.startswith(prefix + ".")
        for category in categories
        for prefix in allowed_prefixes
    )


def parse_arxiv_raw_oai(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_category_prefixes: tuple[str, ...],
    source_id: str = "arxiv-cc-single-version-descriptive",
) -> tuple[list[dict[str, Any]], str | None]:
    """Return metadata-only records and the OAI resumption token."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ArxivMetadataError(f"invalid OAI XML: {error}") from error

    records: list[dict[str, Any]] = []
    for record in _children(root, "record"):
        header = next(
            (child for child in record if _local(child.tag) == "header"),
            None,
        )
        if header is None or header.attrib.get("status") == "deleted":
            continue
        metadata = next(
            (child for child in record if _local(child.tag) == "metadata"),
            None,
        )
        if metadata is None or not list(metadata):
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
        version_dates: list[datetime] = []
        version_labels: list[str] = []
        for version in version_elements:
            raw_date = _first_text(version, "date")
            if raw_date is None:
                raise ArxivMetadataError(
                    f"arXivRaw record {arxiv_id} has a version without date"
                )
            version_dates.append(_version_timestamp(raw_date))
            version_labels.append(version.attrib.get("version", "unknown"))

        first_timestamp = min(version_dates)
        era_window = windows.classify(first_timestamp)
        categories_raw = _first_text(raw, "categories") or ""
        categories = sorted(set(categories_raw.split()))
        license_id, rights_status, license_locator = _license(
            _first_text(raw, "license")
        )
        title = _first_text(raw, "title") or ""
        abstract = _first_text(raw, "abstract") or ""
        authors = _first_text(raw, "authors") or ""
        category_allowed = _category_allowed(
            categories,
            allowed_category_prefixes,
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

        eligibility = "eligible" if not exclusion_reasons else "excluded"
        version_status = (
            "single-version" if len(version_elements) == 1 else "latest-only"
        )
        first_version = version_labels[version_dates.index(first_timestamp)]
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
                    "https://export.arxiv.org/oai2?verb=GetRecord&"
                    f"metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + arxiv_id)}"
                ),
                "content_locator": None,
                "content_retrieved": False,
                "eligibility": eligibility,
                "exclusion_reasons": exclusion_reasons,
                "source_metadata": {
                    "version_labels": version_labels,
                    "title_sha256": _sha256_text(title),
                    "title_length": len(title),
                    "abstract_sha256": _sha256_text(abstract),
                    "abstract_length": len(abstract),
                    "authors_sha256": _sha256_text(authors),
                    "author_string_length": len(authors),
                    "category_allowed": category_allowed,
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
    return records, token
