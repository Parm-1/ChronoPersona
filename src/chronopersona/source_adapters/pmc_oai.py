"""Parse current PMC OAI Dublin Core metadata without retrieving article text.

PMC is a backup held-out source. OAI Dublin Core is used only for bounded
metadata qualification; it does not establish historical JATS version
integrity or unambiguous publication time. Records without a usable lifecycle
date are counted and omitted rather than assigned an invented timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

from ..source_metadata import EraWindows


class PmcMetadataError(ValueError):
    """Raised when PMC OAI metadata is malformed or reports an OAI error."""


@dataclass(frozen=True)
class ParsedDate:
    """Conservative lifecycle-date evidence from Dublin Core."""

    timestamp: datetime
    precision: str
    raw_value: str


_PMCID = re.compile(r"PMC([1-9]\d*)", re.IGNORECASE)
_PMCID_URL = re.compile(
    r"https://pmc\.ncbi\.nlm\.nih\.gov/articles/PMC([1-9]\d*)/",
    re.IGNORECASE,
)
_OAI_PMC_IDENTIFIER = re.compile(r"oai:pubmedcentral\.nih\.gov:([1-9]\d*)")
_CC0_URL = re.compile(
    r"https?://creativecommons\.org/publicdomain/zero/(\d+(?:\.\d+)?)/?",
    re.IGNORECASE,
)
_CC_BY_URL = re.compile(
    r"https?://creativecommons\.org/licenses/by/(\d+(?:\.\d+)?)/?",
    re.IGNORECASE,
)
_CC0_ID = re.compile(r"CC0(?:-|\s+)(\d+(?:\.\d+)?)", re.IGNORECASE)
_CC_BY_ID = re.compile(
    r"CC(?:-|\s+)BY(?:-|\s+)(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
_SUPPORTED_CC0_VERSIONS = frozenset({"1.0"})
_SUPPORTED_CC_BY_VERSIONS = frozenset({"1.0", "2.0", "2.5", "3.0", "4.0"})
_OAI_NAMESPACE = "http://www.openarchives.org/OAI/2.0/"
_DC_NAMESPACE = "http://www.openarchives.org/OAI/2.0/oai_dc/"
_DC_ELEMENTS_NAMESPACE = "http://purl.org/dc/elements/1.1/"
_MAXIMUM_RESUMPTION_TOKEN_BYTES = 4096


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texts(
    element: ET.Element,
    name: str,
    *,
    namespace: str | None = None,
    canonical_scalar: bool = False,
) -> list[str]:
    exact_tag = f"{{{namespace}}}{name}" if namespace is not None else None
    values: list[str] = []
    for child in element:
        if not (
            child.tag == exact_tag if exact_tag is not None else _local(child.tag) == name
        ):
            continue
        raw = child.text
        if canonical_scalar:
            if (
                child.attrib
                or list(child)
                or raw is None
                or not raw
                or raw != raw.strip()
            ):
                raise PmcMetadataError(f"PMC {name} field is not exact")
            values.append(raw)
            continue
        if raw:
            value = " ".join(raw.split())
            if value:
                values.append(value)
    return values


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _parse_one_date(raw: str) -> ParsedDate | None:
    value = raw.strip()
    if re.fullmatch(r"\d{4}", value):
        candidates = [(value + "-01-01T00:00:00+00:00", "year")]
    elif re.fullmatch(r"\d{4}-\d{2}", value):
        candidates = [(value + "-01T00:00:00+00:00", "month")]
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        candidates = [(value + "T00:00:00+00:00", "day")]
    elif re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
        value,
    ):
        candidates = [(value[:-1] + "+00:00", "datetime")]
    else:
        return None

    for candidate, precision in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return ParsedDate(
            timestamp=parsed.astimezone(timezone.utc),
            precision=precision,
            raw_value=value,
        )
    return None


def _parse_lifecycle_date(values: list[str]) -> ParsedDate | None:
    parsed: list[ParsedDate] = []
    for raw in values:
        evidence = _parse_one_date(raw)
        if evidence is None:
            raise PmcMetadataError("PMC lifecycle date is not canonical")
        parsed.append(evidence)
    if not parsed:
        return None
    return min(parsed, key=lambda evidence: evidence.timestamp)


def _license(rights_values: list[str]) -> tuple[str, str, str]:
    normalized_values = [" ".join(value.split()) for value in rights_values]
    recognized: set[tuple[str, str]] = set()
    for value in normalized_values:
        if match := _CC0_URL.fullmatch(value):
            version = match.group(1)
            if version in _SUPPORTED_CC0_VERSIONS:
                recognized.add(
                    (
                        f"CC0-{version}",
                        f"https://creativecommons.org/publicdomain/zero/{version}/",
                    )
                )
            else:
                recognized.add(("", ""))
        elif match := _CC_BY_URL.fullmatch(value):
            version = match.group(1)
            if version in _SUPPORTED_CC_BY_VERSIONS:
                recognized.add(
                    (
                        f"CC-BY-{version}",
                        f"https://creativecommons.org/licenses/by/{version}/",
                    )
                )
            else:
                recognized.add(("", ""))
        elif match := _CC0_ID.fullmatch(value):
            version = match.group(1)
            if version in _SUPPORTED_CC0_VERSIONS:
                recognized.add(
                    (
                        f"CC0-{version}",
                        f"https://creativecommons.org/publicdomain/zero/{version}/",
                    )
                )
            else:
                recognized.add(("", ""))
        elif match := _CC_BY_ID.fullmatch(value):
            version = match.group(1)
            if version in _SUPPORTED_CC_BY_VERSIONS:
                recognized.add(
                    (
                        f"CC-BY-{version}",
                        f"https://creativecommons.org/licenses/by/{version}/",
                    )
                )
            else:
                recognized.add(("", ""))
        else:
            recognized.add(("", ""))

    if len(recognized) == 1 and (license_record := next(iter(recognized)))[0]:
        license_id, locator = license_record
        return license_id, "eligible", locator

    joined = " | ".join(normalized_values)
    normalized = joined.lower()
    if "creative commons" in normalized or "creativecommons.org" in normalized:
        return (
            "creative-commons-other",
            "ineligible",
            "rights-sha256:" + _sha256_text(joined),
        )
    if joined:
        return (
            "custom-or-unresolved",
            "unresolved",
            "rights-sha256:" + _sha256_text(joined),
        )
    return "missing", "unresolved", "missing-license"


def _pmcid(identifiers: list[str], header: ET.Element) -> tuple[str, str]:
    number = _header_pmc_number(header)
    dc_numbers: set[str] = set()
    for value in identifiers:
        match = _PMCID.fullmatch(value) or _PMCID_URL.fullmatch(value)
        if match is not None:
            dc_numbers.add(match.group(1))
    if dc_numbers != {number}:
        raise PmcMetadataError(
            "PMC Dublin Core and OAI header identifiers do not match"
        )
    return f"PMC{number}", number


def _header_pmc_number(header: ET.Element) -> str:
    header_identifiers = _texts(
        header,
        "identifier",
        namespace=_OAI_NAMESPACE,
        canonical_scalar=True,
    )
    if len(header_identifiers) != 1 or not (
        header_match := _OAI_PMC_IDENTIFIER.fullmatch(header_identifiers[0])
    ):
        raise PmcMetadataError("PMC OAI header identifier is not exact")
    return header_match.group(1)


def _header_datestamp(header: ET.Element) -> ParsedDate:
    values = _texts(
        header,
        "datestamp",
        namespace=_OAI_NAMESPACE,
        canonical_scalar=True,
    )
    if len(values) != 1:
        raise PmcMetadataError("PMC OAI header datestamp is not exact")
    raw = values[0]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        precision = "day"
        normalized = raw + "T00:00:00+00:00"
    elif re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", raw):
        precision = "datetime"
        normalized = raw[:-1] + "+00:00"
    else:
        raise PmcMetadataError("PMC OAI header datestamp is not exact")
    try:
        timestamp = datetime.fromisoformat(normalized).astimezone(timezone.utc)
    except ValueError as error:
        raise PmcMetadataError("PMC OAI header datestamp is invalid") from error
    return ParsedDate(timestamp=timestamp, precision=precision, raw_value=raw)


def _oai_error(root: ET.Element) -> None:
    errors = [
        element
        for element in root
        if element.tag == f"{{{_OAI_NAMESPACE}}}error"
    ]
    if not errors:
        return
    if len(errors) != 1:
        raise PmcMetadataError("PMC OAI error response is not singular")
    error = errors[0]
    code = error.attrib.get("code", "unknown")
    message = " ".join((error.text or "").split()) or "unspecified OAI error"
    raise PmcMetadataError(f"PMC OAI error {code}: {message}")


def _validate_oai_envelope(
    root: ET.Element,
    *,
    expected_request_attributes: Mapping[str, str],
) -> None:
    allowed_children = {
        f"{{{_OAI_NAMESPACE}}}responseDate",
        f"{{{_OAI_NAMESPACE}}}request",
        f"{{{_OAI_NAMESPACE}}}error",
        f"{{{_OAI_NAMESPACE}}}ListRecords",
    }
    if any(child.tag not in allowed_children for child in root):
        raise PmcMetadataError("PMC OAI response contains an unexpected root field")
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
        raise PmcMetadataError("PMC OAI responseDate and request must be singular")
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
        raise PmcMetadataError("PMC OAI responseDate is not exact")
    try:
        datetime.fromisoformat(raw_response_date[:-1] + "+00:00")
    except ValueError as error:
        raise PmcMetadataError("PMC OAI responseDate is invalid") from error
    request = requests[0]
    if (
        list(request)
        or request.text != "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"
        or dict(request.attrib) != dict(expected_request_attributes)
    ):
        raise PmcMetadataError("PMC OAI request echo does not match the request")


def parse_pmc_oai_dc(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_subject_terms: tuple[str, ...],
    source_id: str = "pmc-oa-cc-version-bounded",
    expected_from_date: date | None = None,
    expected_until_date: date | None = None,
    seen_header_identifiers: set[str] | None = None,
    expected_request_attributes: Mapping[str, str] | None = None,
) -> tuple[list[dict[str, Any]], str | None, dict[str, int]]:
    """Return backup-C metadata records, resumption token, and diagnostics.

    Dublin Core ``dc:date`` is a lifecycle-associated date rather than a
    guaranteed publication date. The parser stores it as candidate evidence,
    but keeps ``era_window`` unresolved until a publication-specific field from
    PMC front matter, ESummary/PubMed, or another approved source confirms it.
    OAI Dublin Core also does not prove historical article-version integrity.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise PmcMetadataError(f"invalid PMC OAI XML: {error}") from error
    if root.tag != f"{{{_OAI_NAMESPACE}}}OAI-PMH":
        raise PmcMetadataError("PMC OAI response root is not exact")
    if expected_request_attributes is None:
        expected_request_attributes = {
            "verb": "ListRecords",
            "metadataPrefix": "oai_dc",
            "set": "pmc-open",
        }
    _validate_oai_envelope(
        root,
        expected_request_attributes=expected_request_attributes,
    )
    _oai_error(root)
    containers = [
        child
        for child in root
        if child.tag == f"{{{_OAI_NAMESPACE}}}ListRecords"
    ]
    if len(containers) != 1:
        raise PmcMetadataError("PMC OAI ListRecords container is not singular")
    container = containers[0]
    allowed_container_children = {
        f"{{{_OAI_NAMESPACE}}}record",
        f"{{{_OAI_NAMESPACE}}}resumptionToken",
    }
    if any(child.tag not in allowed_container_children for child in container):
        raise PmcMetadataError("PMC OAI ListRecords fields are not exact")

    diagnostics = {
        "records_seen": 0,
        "deleted_records": 0,
        "records_without_metadata": 0,
        "skipped_missing_lifecycle_date": 0,
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
            raise PmcMetadataError("PMC OAI record header is not singular")
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
            raise PmcMetadataError("PMC OAI record fields are not exact")
        if any(
            child.tag
            not in {
                f"{{{_OAI_NAMESPACE}}}identifier",
                f"{{{_OAI_NAMESPACE}}}datestamp",
                f"{{{_OAI_NAMESPACE}}}setSpec",
            }
            for child in header
        ):
            raise PmcMetadataError("PMC OAI header fields are not exact")
        if set(header.attrib) - {"status"} or header.attrib.get("status") not in {
            None,
            "deleted",
        }:
            raise PmcMetadataError("PMC OAI header status is not exact")
        header_datestamp = _header_datestamp(header)
        header_number = _header_pmc_number(header)
        header_identifier = f"oai:pubmedcentral.nih.gov:{header_number}"
        if seen_header_identifiers is not None:
            if header_identifier in seen_header_identifiers:
                raise PmcMetadataError(
                    "PMC OAI header identifier repeated across pages"
                )
            seen_header_identifiers.add(header_identifier)
        if (expected_from_date is None) != (expected_until_date is None):
            raise PmcMetadataError(
                "PMC expected datestamp bounds must be supplied together"
            )
        if expected_from_date is not None and not (
            expected_from_date
            <= header_datestamp.timestamp.date()
            <= expected_until_date
        ):
            raise PmcMetadataError(
                "PMC OAI header datestamp escaped its requested range"
            )
        set_specs = _texts(
            header,
            "setSpec",
            namespace=_OAI_NAMESPACE,
            canonical_scalar=True,
        )
        if header.attrib.get("status") == "deleted":
            if set_specs not in ([], ["pmc-open"]):
                raise PmcMetadataError("PMC deleted-record setSpec is not exact")
            diagnostics["deleted_records"] += 1
            continue
        if set_specs != ["pmc-open"]:
            raise PmcMetadataError("PMC OAI record setSpec is not exact")
        metadata_blocks = [
            child
            for child in record
            if child.tag == f"{{{_OAI_NAMESPACE}}}metadata"
        ]
        if len(metadata_blocks) > 1:
            raise PmcMetadataError("PMC OAI metadata block is not singular")
        metadata = metadata_blocks[0] if metadata_blocks else None
        if metadata is None or not list(metadata):
            diagnostics["records_without_metadata"] += 1
            continue
        if len(list(metadata)) != 1:
            raise PmcMetadataError("PMC Dublin Core payload is not singular")
        dc = list(metadata)[0]
        if dc.tag != f"{{{_DC_NAMESPACE}}}dc":
            raise PmcMetadataError("PMC Dublin Core namespace is not exact")
        identifiers = _texts(
            dc,
            "identifier",
            namespace=_DC_ELEMENTS_NAMESPACE,
            canonical_scalar=True,
        )
        pmcid, pmc_number = _pmcid(identifiers, header)

        raw_dates = _texts(
            dc,
            "date",
            namespace=_DC_ELEMENTS_NAMESPACE,
            canonical_scalar=True,
        )
        date_evidence = _parse_lifecycle_date(raw_dates)
        if date_evidence is None:
            diagnostics["skipped_missing_lifecycle_date"] += 1
            continue
        timestamp = date_evidence.timestamp
        candidate_window = windows.classify(timestamp)
        subjects = sorted(
            set(
                _texts(
                    dc,
                    "subject",
                    namespace=_DC_ELEMENTS_NAMESPACE,
                    canonical_scalar=True,
                )
            )
        )
        normalized_subjects = {
            " ".join(subject.lower().split()) for subject in subjects
        }
        matched_subject_terms = sorted(
            term
            for term in allowed_subject_terms
            if " ".join(term.lower().split()) in normalized_subjects
        )
        subject_allowed = bool(matched_subject_terms)
        rights_values = _texts(
            dc,
            "rights",
            namespace=_DC_ELEMENTS_NAMESPACE,
            canonical_scalar=True,
        )
        license_id, rights_status, license_locator = _license(rights_values)
        titles = _texts(dc, "title", namespace=_DC_ELEMENTS_NAMESPACE)
        creators = _texts(dc, "creator", namespace=_DC_ELEMENTS_NAMESPACE)

        exclusion_reasons: list[str] = [
            "timestamp-semantics-unresolved",
            "historical-version-unresolved",
        ]
        if rights_status != "eligible":
            exclusion_reasons.append("license-not-eligible")
        if not subject_allowed:
            exclusion_reasons.append("subject-not-in-frozen-stratum")

        records.append(
            {
                "schema_version": 1,
                "record_id": f"pmc:{pmcid}",
                "source_id": source_id,
                "native_item_id": pmcid,
                "native_timestamp": header_datestamp.timestamp.isoformat().replace(
                    "+00:00", "Z"
                ),
                "timestamp_semantics": "release-or-update-datestamp",
                "era_window": "unresolved",
                "version_status": "unresolved",
                "version_count": 1,
                "rights_status": rights_status,
                "license_id": license_id,
                "license_locator": license_locator,
                "authorship_provenance": "human",
                "categories": matched_subject_terms,
                "review_strata": [
                    "rights-boundary"
                    if rights_status != "eligible"
                    else "timestamp-boundary"
                ],
                "metadata_locator": (
                    "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?"
                    f"verb=GetRecord&metadataPrefix=oai_dc&identifier="
                    f"{quote('oai:pubmedcentral.nih.gov:' + pmc_number)}"
                ),
                "content_locator": None,
                "content_retrieved": False,
                "eligibility": "unresolved",
                "exclusion_reasons": exclusion_reasons,
                "source_metadata": {
                    "dc_date_semantics": (
                        "lifecycle-associated; not treated as confirmed publication date"
                    ),
                    "candidate_era_window": candidate_window,
                    "oai_header_datestamp_precision": header_datestamp.precision,
                    "lifecycle_date_precision": date_evidence.precision,
                    "lifecycle_date_value_count": len(raw_dates),
                    "lifecycle_date_values_sha256": _sha256_text(" | ".join(raw_dates)),
                    "title_sha256": _sha256_text(" | ".join(titles)),
                    "title_length": sum(len(value) for value in titles),
                    "creator_count": len(creators),
                    "creators_sha256": _sha256_text(" | ".join(creators)),
                    "rights_value_count": len(rights_values),
                    "rights_values_sha256": _sha256_text(
                        " | ".join(rights_values)
                    ),
                    "subject_allowed": subject_allowed,
                    "subject_value_count": len(subjects),
                    "subject_values_sha256": _sha256_text(" | ".join(subjects)),
                    "oai_identifier_count": len(identifiers),
                    "version_count_interpretation": (
                        "metadata-record-placeholder; article-version count unresolved"
                    ),
                },
            }
        )

    token_elements = [
        element
        for element in container
        if element.tag == f"{{{_OAI_NAMESPACE}}}resumptionToken"
    ]
    if len(token_elements) > 1:
        raise PmcMetadataError("PMC OAI response has multiple resumption tokens")
    token_element = token_elements[0] if token_elements else None
    if token_element is not None and (
        list(token_element)
        or set(token_element.attrib)
        - {"completeListSize", "cursor", "expirationDate"}
    ):
        raise PmcMetadataError("PMC resumption token is not structurally exact")
    if token_element is not None:
        for attribute in ("completeListSize", "cursor"):
            raw_attribute = token_element.attrib.get(attribute)
            if raw_attribute is not None and re.fullmatch(
                r"0|[1-9]\d*", raw_attribute
            ) is None:
                raise PmcMetadataError("PMC resumption token is not structurally exact")
        expiration = token_element.attrib.get("expirationDate")
        if expiration is not None:
            if re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                expiration,
            ) is None:
                raise PmcMetadataError(
                    "PMC resumption token is not structurally exact"
                )
            try:
                datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError as error:
                raise PmcMetadataError(
                    "PMC resumption token is not structurally exact"
                ) from error
    token = token_element.text if token_element is not None else None
    if token is not None and (
        not token
        or token != token.strip()
        or len(token.encode("utf-8")) > _MAXIMUM_RESUMPTION_TOKEN_BYTES
        or any(ord(character) < 0x21 or ord(character) > 0x7E for character in token)
    ):
        raise PmcMetadataError("PMC resumption token is not bounded canonical ASCII")
    return records, token, diagnostics
