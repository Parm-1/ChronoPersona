"""Parse arXiv OAI-PMH ``arXivRaw`` metadata without retaining prose."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime, parsedate_to_datetime
import hashlib
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

from ..source_metadata import (
    EraWindows,
    arxiv_category_evidence,
    normalize_arxiv_categories,
)


class ArxivMetadataError(ValueError):
    """Raised when an arXiv OAI response is malformed or reports an error."""


_CC0_URL = re.compile(
    r"https?://creativecommons\.org/publicdomain/zero/(1\.0)/?",
    re.IGNORECASE,
)
_CC_BY_URL = re.compile(
    r"https?://creativecommons\.org/licenses/by/(1\.0|2\.0|2\.5|3\.0|4\.0)/?",
    re.IGNORECASE,
)
_ARXIV_DEFAULT_URL = re.compile(
    r"https?://arxiv\.org/licenses/nonexclusive-distrib/1\.0/?",
    re.IGNORECASE,
)
_BASE_IDENTIFIER = re.compile(
    r"(?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7})"
)
_VERSION_LABEL = re.compile(r"v([1-9]\d*)")
_OAI_HEADER_IDENTIFIER = re.compile(
    r"oai:arXiv\.org:((?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7}))"
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
_OAI_NAMESPACE = "http://www.openarchives.org/OAI/2.0/"
_ARXIV_RAW_NAMESPACE = "http://arxiv.org/OAI/arXivRaw/"
_MAXIMUM_RESUMPTION_TOKEN_BYTES = 4096


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _first_text(element: ET.Element, name: str) -> str | None:
    namespace = _namespace(element.tag)
    exact_tag = f"{{{namespace}}}{name}" if namespace else name
    for child in element:
        if child.tag == exact_tag and child.text:
            value = " ".join(child.text.split())
            if value:
                return value
    return None


def _exact_text(
    element: ET.Element,
    name: str,
    *,
    required: bool,
    canonical_scalar: bool = False,
) -> str | None:
    namespace = _namespace(element.tag)
    exact_tag = f"{{{namespace}}}{name}" if namespace else name
    fields = [child for child in element if child.tag == exact_tag]
    if len(fields) > 1 or (required and len(fields) != 1):
        raise ArxivMetadataError(f"arXivRaw field {name} is not singular")
    if not fields:
        return None
    field = fields[0]
    raw = field.text
    if canonical_scalar:
        if (
            field.attrib
            or list(field)
            or raw is None
            or not raw
            or raw != raw.strip()
        ):
            raise ArxivMetadataError(f"arXivRaw field {name} is not canonical")
        return raw
    if raw is None or not raw.strip():
        if required:
            raise ArxivMetadataError(f"arXivRaw field {name} is empty")
        return None
    return " ".join(raw.split())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _version_timestamp(raw: str) -> datetime:
    if re.fullmatch(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), "
        r"\d{2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) "
        r"\d{4} \d{2}:\d{2}:\d{2} GMT",
        raw,
    ) is None:
        raise ArxivMetadataError("arXiv version date is not canonical RFC822 GMT")
    try:
        parsed = parsedate_to_datetime(raw)
    except (TypeError, ValueError) as error:
        raise ArxivMetadataError(
            f"invalid arXiv version date: {raw!r}"
        ) from error
    if parsed.tzinfo is None:
        raise ArxivMetadataError("arXiv version date has no timezone")
    normalized = parsed.astimezone(timezone.utc)
    if format_datetime(normalized, usegmt=True) != raw:
        raise ArxivMetadataError("arXiv version date weekday is inconsistent")
    return normalized


def _header_identity(header: ET.Element) -> str:
    identifier = _exact_text(
        header,
        "identifier",
        required=True,
        canonical_scalar=True,
    )
    match = _OAI_HEADER_IDENTIFIER.fullmatch(identifier or "")
    if match is None:
        raise ArxivMetadataError("arXiv OAI header identifier is not exact")
    datestamp = _exact_text(
        header,
        "datestamp",
        required=True,
        canonical_scalar=True,
    )
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", datestamp or ""):
        normalized = f"{datestamp}T00:00:00+00:00"
    elif re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
        datestamp or "",
    ):
        normalized = datestamp[:-1] + "+00:00"
    else:
        raise ArxivMetadataError("arXiv OAI header datestamp is not exact")
    try:
        datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ArxivMetadataError("arXiv OAI header datestamp is invalid") from error
    return match.group(1)


def _license(raw: str | None) -> tuple[str, str, str]:
    if raw is None:
        return "missing", "unresolved", "missing-license"
    normalized = " ".join(raw.split())
    if match := _CC0_URL.fullmatch(normalized):
        version = match.group(1)
        return (
            f"CC0-{version}",
            "eligible",
            f"https://creativecommons.org/publicdomain/zero/{version}/",
        )
    if match := _CC_BY_URL.fullmatch(normalized):
        version = match.group(1)
        return (
            f"CC-BY-{version}",
            "eligible",
            f"https://creativecommons.org/licenses/by/{version}/",
        )
    folded = normalized.casefold()
    locator_hash = "rights-sha256:" + _sha256_text(normalized)
    if "creativecommons.org" in folded or "creative commons" in folded:
        return "creative-commons-other", "ineligible", locator_hash
    if _ARXIV_DEFAULT_URL.fullmatch(normalized):
        return "arXiv-default", "ineligible", locator_hash
    return "custom-or-unresolved", "unresolved", locator_hash


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
        raise ArxivMetadataError("arXivRaw record contains a noncanonical category")


def _author_evidence(raw: ET.Element) -> tuple[int, str]:
    authors: list[str] = []
    author_tag = f"{{{_ARXIV_RAW_NAMESPACE}}}author"
    for author in [child for child in raw.iter() if child.tag == author_tag]:
        fields = [
            _first_text(author, name) or ""
            for name in ("keyname", "forenames", "suffix", "affiliation")
        ]
        normalized = " | ".join(field for field in fields if field)
        if normalized:
            authors.append(normalized)
    return len(authors), _sha256_text("\n".join(authors))


def _oai_error(root: ET.Element) -> None:
    errors = [
        element
        for element in root
        if element.tag == f"{{{_OAI_NAMESPACE}}}error"
    ]
    if not errors:
        return
    if len(errors) != 1:
        raise ArxivMetadataError("arXiv OAI error response is not singular")
    error = errors[0]
    code = error.attrib.get("code", "unknown")
    message = " ".join((error.text or "").split()) or "unspecified OAI error"
    raise ArxivMetadataError(f"arXiv OAI error {code}: {message}")


def _validate_oai_envelope(
    root: ET.Element,
    *,
    expected_request_attributes: Mapping[str, str],
) -> None:
    expected_verb = expected_request_attributes.get("verb")
    expected_container = f"{{{_OAI_NAMESPACE}}}{expected_verb}"
    allowed_children = {
        f"{{{_OAI_NAMESPACE}}}responseDate",
        f"{{{_OAI_NAMESPACE}}}request",
        f"{{{_OAI_NAMESPACE}}}error",
        expected_container,
    }
    if any(child.tag not in allowed_children for child in root):
        raise ArxivMetadataError("arXiv OAI response contains an unexpected root field")
    response_dates = [
        child
        for child in root
        if child.tag == f"{{{_OAI_NAMESPACE}}}responseDate"
    ]
    requests = [
        child
        for child in root
        if child.tag == f"{{{_OAI_NAMESPACE}}}request"
    ]
    if len(response_dates) != 1 or len(requests) != 1:
        raise ArxivMetadataError(
            "arXiv OAI responseDate and request must be singular"
        )
    response_date = response_dates[0]
    raw_response_date = response_date.text or ""
    if (
        response_date.attrib
        or list(response_date)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
            raw_response_date,
        )
        is None
    ):
        raise ArxivMetadataError("arXiv OAI responseDate is not exact")
    try:
        datetime.fromisoformat(raw_response_date[:-1] + "+00:00")
    except ValueError as error:
        raise ArxivMetadataError("arXiv OAI responseDate is invalid") from error
    request = requests[0]
    if (
        list(request)
        or request.text != "https://oaipmh.arxiv.org/oai"
        or dict(request.attrib) != dict(expected_request_attributes)
    ):
        raise ArxivMetadataError("arXiv OAI request echo does not match the request")


def parse_arxiv_raw_oai(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_category_prefixes: tuple[str, ...],
    forbidden_category_prefixes: tuple[str, ...] = (),
    source_id: str = "arxiv-cc-single-version-descriptive",
    expected_base_identifier: str | None = None,
    expected_request_attributes: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, int]]:
    """Return metadata-only records, resumption token, and diagnostics."""

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise ArxivMetadataError(f"invalid OAI XML: {error}") from error
    if root.tag != f"{{{_OAI_NAMESPACE}}}OAI-PMH":
        raise ArxivMetadataError("arXiv OAI response root is not exact")
    if expected_request_attributes is None:
        expected_request_attributes = (
            {
                "verb": "GetRecord",
                "metadataPrefix": "arXivRaw",
                "identifier": f"oai:arXiv.org:{expected_base_identifier}",
            }
            if expected_base_identifier is not None
            else {"verb": "ListRecords", "metadataPrefix": "arXivRaw"}
        )
    _validate_oai_envelope(
        root,
        expected_request_attributes=expected_request_attributes,
    )
    _oai_error(root)
    containers = [
        child
        for child in root
        if child.tag
        in {
            f"{{{_OAI_NAMESPACE}}}GetRecord",
            f"{{{_OAI_NAMESPACE}}}ListRecords",
        }
    ]
    if len(containers) != 1:
        raise ArxivMetadataError("arXiv OAI response container is not singular")
    container = containers[0]
    expected_container = (
        f"{{{_OAI_NAMESPACE}}}GetRecord"
        if expected_base_identifier is not None
        else f"{{{_OAI_NAMESPACE}}}ListRecords"
    )
    if container.tag != expected_container:
        raise ArxivMetadataError("arXiv OAI response verb does not match the request")
    allowed_container_children = {
        f"{{{_OAI_NAMESPACE}}}record",
        f"{{{_OAI_NAMESPACE}}}resumptionToken",
    }
    if any(child.tag not in allowed_container_children for child in container):
        raise ArxivMetadataError("arXiv OAI response container fields are not exact")

    diagnostics = {
        "records_seen": 0,
        "deleted_records": 0,
        "records_without_metadata": 0,
    }
    records: list[dict[str, Any]] = []
    for record in [
        child
        for child in container
        if child.tag == f"{{{_OAI_NAMESPACE}}}record"
    ]:
        diagnostics["records_seen"] += 1
        headers = [
            child
            for child in record
            if child.tag == f"{{{_OAI_NAMESPACE}}}header"
        ]
        if len(headers) != 1:
            raise ArxivMetadataError("arXiv OAI record header is not singular")
        header = headers[0]
        if any(
            child.tag
            not in {
                f"{{{_OAI_NAMESPACE}}}header",
                f"{{{_OAI_NAMESPACE}}}metadata",
                f"{{{_OAI_NAMESPACE}}}about",
            }
            for child in record
        ):
            raise ArxivMetadataError("arXiv OAI record fields are not exact")
        if any(
            child.tag
            not in {
                f"{{{_OAI_NAMESPACE}}}identifier",
                f"{{{_OAI_NAMESPACE}}}datestamp",
                f"{{{_OAI_NAMESPACE}}}setSpec",
            }
            for child in header
        ):
            raise ArxivMetadataError("arXiv OAI header fields are not exact")
        if set(header.attrib) - {"status"} or header.attrib.get("status") not in {
            None,
            "deleted",
        }:
            raise ArxivMetadataError("arXiv OAI header status is not exact")
        header_base_identifier = _header_identity(header)
        if expected_base_identifier is not None:
            if header_base_identifier != expected_base_identifier:
                raise ArxivMetadataError(
                    "arXiv OAI header does not match the requested base identifier"
                )
        if header.attrib.get("status") == "deleted":
            diagnostics["deleted_records"] += 1
            continue
        metadata_blocks = [
            child
            for child in record
            if child.tag == f"{{{_OAI_NAMESPACE}}}metadata"
        ]
        if len(metadata_blocks) > 1:
            raise ArxivMetadataError("arXiv OAI metadata block is not singular")
        metadata = metadata_blocks[0] if metadata_blocks else None
        if metadata is None or not list(metadata):
            diagnostics["records_without_metadata"] += 1
            continue
        if len(list(metadata)) != 1:
            raise ArxivMetadataError("arXivRaw metadata payload is not singular")
        raw = list(metadata)[0]
        if raw.tag != f"{{{_ARXIV_RAW_NAMESPACE}}}arXiv":
            raise ArxivMetadataError("arXivRaw metadata namespace is not exact")
        arxiv_id = _exact_text(
            raw,
            "id",
            required=True,
            canonical_scalar=True,
        )
        if not arxiv_id or _BASE_IDENTIFIER.fullmatch(arxiv_id) is None:
            raise ArxivMetadataError("arXivRaw record has a noncanonical id")
        if (
            arxiv_id != header_base_identifier
        ):
            raise ArxivMetadataError(
                "arXivRaw id does not match its OAI header identifier"
            )
        if expected_base_identifier is not None and arxiv_id != expected_base_identifier:
            raise ArxivMetadataError(
                "arXivRaw id does not match the requested base identifier"
            )

        version_elements = [
            child
            for child in raw
            if child.tag == f"{{{_ARXIV_RAW_NAMESPACE}}}version"
        ]
        if not version_elements:
            raise ArxivMetadataError(
                f"arXivRaw record {arxiv_id} has no versions"
            )
        versions: list[tuple[datetime, str]] = []
        for index, version in enumerate(version_elements, start=1):
            if set(version.attrib) != {"version"}:
                raise ArxivMetadataError(
                    f"arXivRaw record {arxiv_id} has noncanonical version fields"
                )
            raw_date = _exact_text(
                version,
                "date",
                required=True,
                canonical_scalar=True,
            )
            if raw_date is None:
                raise ArxivMetadataError(
                    f"arXivRaw record {arxiv_id} has a version without date"
                )
            label = version.attrib.get("version")
            match = _VERSION_LABEL.fullmatch(label or "")
            if match is None or int(match.group(1)) != index:
                raise ArxivMetadataError(
                    f"arXivRaw record {arxiv_id} has noncanonical version labels"
                )
            versions.append((_version_timestamp(raw_date), label))
        if any(
            later[0] <= earlier[0]
            for earlier, later in zip(versions, versions[1:], strict=False)
        ):
            raise ArxivMetadataError(
                f"arXivRaw record {arxiv_id} version timestamps are not increasing"
            )

        first_timestamp, first_version = min(versions, key=lambda item: item[0])
        era_window = windows.classify(first_timestamp)
        categories_raw = (
            _exact_text(
                raw,
                "categories",
                required=True,
                canonical_scalar=True,
            )
            or ""
        )
        categories = sorted(set(categories_raw.split()))
        _require_canonical_categories(categories)
        license_id, rights_status, license_locator = _license(
            _exact_text(
                raw,
                "license",
                required=False,
                canonical_scalar=True,
            )
        )
        title = _exact_text(raw, "title", required=True) or ""
        abstract = _exact_text(raw, "abstract", required=True) or ""
        author_count, authors_sha256 = _author_evidence(raw)
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
            raise ArxivMetadataError(str(error)) from error
        raw_category_count, raw_categories_sha256 = arxiv_category_evidence(categories)

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
                "categories": persisted_categories,
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
                    "base_identifier": arxiv_id,
                    "version_labels": [label for _, label in versions],
                    "latest_version_timestamp": versions[-1][0].isoformat().replace(
                        "+00:00", "Z"
                    ),
                    "title_sha256": _sha256_text(title),
                    "title_length": len(title),
                    "abstract_sha256": _sha256_text(abstract),
                    "abstract_length": len(abstract),
                    "author_count": author_count,
                    "authors_sha256": authors_sha256,
                    "category_allowed": category_allowed,
                    "category_forbidden": category_forbidden,
                    "raw_category_count": raw_category_count,
                    "raw_categories_sha256": raw_categories_sha256,
                },
            }
        )

    token_elements = [
        element
        for element in container
        if element.tag == f"{{{_OAI_NAMESPACE}}}resumptionToken"
    ]
    if len(token_elements) > 1:
        raise ArxivMetadataError("arXiv OAI response has multiple resumption tokens")
    if expected_base_identifier is not None and token_elements:
        raise ArxivMetadataError("arXiv GetRecord returned a resumption token")
    token_element = token_elements[0] if token_elements else None
    if token_element is not None and (
        list(token_element)
        or set(token_element.attrib)
        - {"completeListSize", "cursor", "expirationDate"}
    ):
        raise ArxivMetadataError("arXiv resumption token is not structurally exact")
    if token_element is not None:
        for attribute in ("completeListSize", "cursor"):
            raw_attribute = token_element.attrib.get(attribute)
            if raw_attribute is not None and re.fullmatch(
                r"0|[1-9]\d*", raw_attribute
            ) is None:
                raise ArxivMetadataError(
                    "arXiv resumption token is not structurally exact"
                )
        expiration = token_element.attrib.get("expirationDate")
        if expiration is not None:
            if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                expiration,
            ) is None:
                raise ArxivMetadataError(
                    "arXiv resumption token is not structurally exact"
                )
            try:
                datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError as error:
                raise ArxivMetadataError(
                    "arXiv resumption token is not structurally exact"
                ) from error
    token = token_element.text if token_element is not None else None
    if token is not None and (
        not token
        or token != token.strip()
        or len(token.encode("utf-8")) > _MAXIMUM_RESUMPTION_TOKEN_BYTES
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in token)
    ):
        raise ArxivMetadataError(
            "arXiv resumption token is not bounded canonical ASCII"
        )
    return records, token, diagnostics
