"""Parse arXiv API Atom feeds into metadata-only candidate records.

The arXiv API supports ``submittedDate`` selection, unlike OAI-PMH. API output
is used only to enumerate era-native candidate IDs and metadata. License and
complete version-history eligibility remain unresolved until exact
``arXivRaw`` OAI enrichment is performed for each selected identifier.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from urllib.parse import quote, urlsplit
import xml.etree.ElementTree as ET

from ..source_metadata import (
    EraWindows,
    arxiv_category_evidence,
    normalize_arxiv_categories,
)


class ArxivApiError(ValueError):
    """Raised when an arXiv API Atom response is malformed or reports an error."""


_VERSION_SUFFIX = re.compile(r"v([1-9]\d*)$")
_BASE_IDENTIFIER = re.compile(
    r"(?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7})"
)
_CATEGORY = re.compile(r"[a-z][a-z0-9-]*(?:\.[A-Za-z][A-Za-z0-9-]*)?")
_CATEGORY_ROOTS = frozenset(
    {
        "astro-ph",
        "cond-mat",
        "cs",
        "econ",
        "eess",
        "gr-qc",
        "hep-ex",
        "hep-lat",
        "hep-ph",
        "hep-th",
        "math",
        "math-ph",
        "nlin",
        "nucl-ex",
        "nucl-th",
        "physics",
        "q-bio",
        "q-fin",
        "quant-ph",
        "stat",
    }
)
_ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
_OPENSEARCH_NAMESPACE = "http://a9.com/-/spec/opensearch/1.1/"
_ARXIV_ATOM_NAMESPACE = "http://arxiv.org/schemas/atom"


def _direct_text(
    element: ET.Element,
    name: str,
    *,
    namespace: str = _ATOM_NAMESPACE,
) -> str | None:
    exact_tag = f"{{{namespace}}}{name}"
    values = [
        " ".join(child.text.split())
        for child in element
        if child.tag == exact_tag and child.text and child.text.strip()
    ]
    if len(values) > 1:
        raise ArxivApiError(f"arXiv API {name} field is not singular")
    return values[0] if values else None


def _direct_canonical_scalar(element: ET.Element, name: str) -> str:
    exact_tag = f"{{{_ATOM_NAMESPACE}}}{name}"
    fields = [child for child in element if child.tag == exact_tag]
    if len(fields) != 1:
        raise ArxivApiError(f"arXiv API {name} field is not singular")
    field = fields[0]
    raw = field.text
    if (
        field.attrib
        or list(field)
        or raw is None
        or not raw
        or raw != raw.strip()
    ):
        raise ArxivApiError(f"arXiv API {name} field is not canonical")
    return raw


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _timestamp(raw: str | None, *, field: str) -> datetime:
    if raw is None:
        raise ArxivApiError(f"arXiv API entry is missing {field}")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw) is None:
        raise ArxivApiError(f"arXiv API {field} timestamp is not canonical")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as error:
        raise ArxivApiError(
            f"invalid arXiv API {field} timestamp: {raw!r}"
        ) from error
    return parsed


def _arxiv_id(raw_url: str | None) -> tuple[str, int | None]:
    if raw_url is None:
        raise ArxivApiError("arXiv API entry is missing id")
    parsed = urlsplit(raw_url)
    try:
        port = parsed.port
    except ValueError as error:
        raise ArxivApiError("arXiv API entry id has an invalid port") from error
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname != "arxiv.org"
        or port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or "%" in parsed.path
        or not parsed.path.startswith("/abs/")
        or parsed.path.count("/abs/") != 1
    ):
        raise ArxivApiError(f"unrecognized arXiv API entry id: {raw_url!r}")
    identifier = parsed.path[len("/abs/") :]
    if not identifier or identifier.endswith("/"):
        raise ArxivApiError("arXiv API entry id is empty or noncanonical")
    match = _VERSION_SUFFIX.search(identifier)
    if match is None:
        if _BASE_IDENTIFIER.fullmatch(identifier) is None:
            raise ArxivApiError("arXiv API entry base id is noncanonical")
        return identifier, None
    base_identifier = identifier[: match.start()]
    if _BASE_IDENTIFIER.fullmatch(base_identifier) is None:
        raise ArxivApiError("arXiv API entry version has no canonical base id")
    return base_identifier, int(match.group(1))


def _category_matches(categories: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(
        category == prefix or category.startswith(prefix + ".")
        for category in categories
        for prefix in prefixes
    )


def _require_canonical_categories(categories: list[str]) -> None:
    if not categories or any(
        _CATEGORY.fullmatch(category) is None
        or category.split(".", 1)[0] not in _CATEGORY_ROOTS
        for category in categories
    ):
        raise ArxivApiError("arXiv API entry contains a noncanonical category")


def _entry_categories(entry: ET.Element) -> list[str]:
    category_tags = {
        f"{{{_ATOM_NAMESPACE}}}category",
        f"{{{_ARXIV_ATOM_NAMESPACE}}}primary_category",
    }
    values: set[str] = set()
    for element in entry:
        if element.tag not in category_tags:
            continue
        expected_attributes = (
            {"term", "scheme"}
            if element.tag == f"{{{_ATOM_NAMESPACE}}}category"
            and "scheme" in element.attrib
            else {"term"}
        )
        if (
            set(element.attrib) != expected_attributes
            or (
                "scheme" in element.attrib
                and element.attrib["scheme"] != _ARXIV_ATOM_NAMESPACE
            )
            or list(element)
            or element.text not in {None, ""}
        ):
            raise ArxivApiError("arXiv API category field is not exact")
        term = element.attrib["term"]
        if not term or term != term.strip():
            raise ArxivApiError("arXiv API category field is not exact")
        values.add(term)
    categories = sorted(values)
    _require_canonical_categories(categories)
    return categories


def _author_evidence(entry: ET.Element) -> tuple[int, str]:
    authors: list[str] = []
    for author in [
        child
        for child in entry
        if child.tag == f"{{{_ATOM_NAMESPACE}}}author"
    ]:
        name = _direct_text(author, "name") or ""
        affiliations = [
            " ".join(child.text.split())
            for child in author
            if child.tag == f"{{{_ARXIV_ATOM_NAMESPACE}}}affiliation"
            and child.text
        ]
        normalized = " | ".join([name, *affiliations]).strip(" |")
        if normalized:
            authors.append(normalized)
    return len(authors), _sha256_text("\n".join(authors))


def _feed_integer(root: ET.Element, name: str) -> int | None:
    exact_tag = f"{{{_OPENSEARCH_NAMESPACE}}}{name}"
    fields = [child for child in root if child.tag == exact_tag]
    if len(fields) > 1:
        raise ArxivApiError(f"arXiv API {name} field is not singular")
    if not fields:
        return None
    field = fields[0]
    raw = field.text
    if (
        field.attrib
        or list(field)
        or raw is None
        or re.fullmatch(r"0|[1-9]\d*", raw) is None
    ):
        raise ArxivApiError(f"arXiv API {name} is not a canonical integer")
    return int(raw)


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
    if root.tag != f"{{{_ATOM_NAMESPACE}}}feed":
        raise ArxivApiError("arXiv API response root must be an Atom feed")

    page = {
        "total_results": _feed_integer(root, "totalResults"),
        "start_index": _feed_integer(root, "startIndex"),
        "items_per_page": _feed_integer(root, "itemsPerPage"),
    }
    records: list[dict[str, Any]] = []
    for entry in [
        child
        for child in root
        if child.tag == f"{{{_ATOM_NAMESPACE}}}entry"
    ]:
        identifier, returned_version = _arxiv_id(
            _direct_canonical_scalar(entry, "id")
        )
        published = _timestamp(
            _direct_canonical_scalar(entry, "published"),
            field="published",
        )
        updated = _timestamp(
            _direct_canonical_scalar(entry, "updated"),
            field="updated",
        )
        if updated < published:
            raise ArxivApiError(
                "arXiv API updated timestamp precedes its published timestamp"
            )
        era_window = windows.classify(published)
        categories = _entry_categories(entry)
        category_allowed = _category_matches(
            categories,
            allowed_category_prefixes,
        )
        category_forbidden = _category_matches(
            categories,
            forbidden_category_prefixes,
        )
        try:
            persisted_categories = normalize_arxiv_categories(
                categories,
                allowed_category_prefixes=allowed_category_prefixes,
                forbidden_category_prefixes=forbidden_category_prefixes,
            )
        except ValueError as error:
            raise ArxivApiError(str(error)) from error
        raw_category_count, raw_categories_sha256 = arxiv_category_evidence(categories)
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
                "version_count": returned_version if returned_version is not None else 1,
                "rights_status": "unresolved",
                "license_id": "pending-arXivRaw-enrichment",
                "license_locator": (
                    "https://oaipmh.arxiv.org/oai?verb=GetRecord&"
                    "metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + identifier)}"
                ),
                "authorship_provenance": "human",
                "categories": persisted_categories,
                "review_strata": [
                    "exposure-boundary"
                    if category_forbidden or not category_allowed
                    else "rights-boundary"
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
                    "returned_version": returned_version,
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
                    "raw_category_count": raw_category_count,
                    "raw_categories_sha256": raw_categories_sha256,
                },
            }
        )
    return records, page
