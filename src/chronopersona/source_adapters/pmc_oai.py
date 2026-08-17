"""Parse current PMC OAI Dublin Core metadata without retrieving article text.

PMC is a backup held-out source. OAI Dublin Core is used only for bounded
metadata qualification; it does not establish historical JATS version
integrity or unambiguous publication time. Records without a usable lifecycle
date are counted and omitted rather than assigned an invented timestamp.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
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


_PMCID = re.compile(r"\bPMC(\d+)\b", re.IGNORECASE)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _texts(element: ET.Element, name: str) -> list[str]:
    values: list[str] = []
    for child in element.iter():
        if _local(child.tag) == name and child.text:
            value = " ".join(child.text.split())
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
    else:
        candidates: list[tuple[str, str]] = [(value, "datetime")]
        if value.endswith("Z"):
            candidates.insert(0, (value[:-1] + "+00:00", "datetime"))

    for candidate, precision in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return ParsedDate(
            timestamp=parsed.astimezone(timezone.utc),
            precision=precision,
            raw_value=value,
        )
    return None


def _parse_lifecycle_date(values: list[str]) -> ParsedDate | None:
    parsed = [evidence for raw in values if (evidence := _parse_one_date(raw))]
    if not parsed:
        return None
    return min(parsed, key=lambda evidence: evidence.timestamp)


def _license(rights_values: list[str]) -> tuple[str, str, str]:
    joined = " | ".join(rights_values)
    normalized = joined.lower()
    if "creativecommons.org/publicdomain/zero" in normalized or "cc0" in normalized:
        return "CC0-1.0", "eligible", joined or "missing-license"
    if (
        "creativecommons.org/licenses/by/" in normalized
        and "/by-sa/" not in normalized
        and "/by-nc" not in normalized
        and "/by-nd" not in normalized
    ):
        return "CC-BY", "eligible", joined or "missing-license"
    if "creative commons" in normalized or "creativecommons.org" in normalized:
        return "creative-commons-other", "ineligible", joined or "missing-license"
    if joined:
        return "custom-or-unresolved", "unresolved", joined
    return "missing", "unresolved", "missing-license"


def _pmcid(identifiers: list[str], header: ET.Element) -> tuple[str, str]:
    for value in [*identifiers, *_texts(header, "identifier")]:
        match = _PMCID.search(value)
        if match:
            number = match.group(1)
            return f"PMC{number}", number
    raise PmcMetadataError("PMC OAI record has no recognizable PMCID")


def _oai_error(root: ET.Element) -> None:
    error = next(
        (element for element in root.iter() if _local(element.tag) == "error"),
        None,
    )
    if error is None:
        return
    code = error.attrib.get("code", "unknown")
    message = " ".join((error.text or "").split()) or "unspecified OAI error"
    raise PmcMetadataError(f"PMC OAI error {code}: {message}")


def parse_pmc_oai_dc(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_subject_terms: tuple[str, ...],
    source_id: str = "pmc-oa-cc-version-bounded",
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
    _oai_error(root)

    diagnostics = {
        "records_seen": 0,
        "deleted_records": 0,
        "records_without_metadata": 0,
        "skipped_missing_lifecycle_date": 0,
    }
    records: list[dict[str, Any]] = []
    for record in [
        element for element in root.iter() if _local(element.tag) == "record"
    ]:
        diagnostics["records_seen"] += 1
        header = next(
            (child for child in record if _local(child.tag) == "header"),
            None,
        )
        if header is None:
            raise PmcMetadataError("PMC OAI record has no header")
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
        dc = list(metadata)[0]
        identifiers = _texts(dc, "identifier")
        pmcid, pmc_number = _pmcid(identifiers, header)

        raw_dates = _texts(dc, "date")
        date_evidence = _parse_lifecycle_date(raw_dates)
        if date_evidence is None:
            diagnostics["skipped_missing_lifecycle_date"] += 1
            continue
        timestamp = date_evidence.timestamp
        candidate_window = windows.classify(timestamp)
        subjects = sorted(set(_texts(dc, "subject")))
        subject_blob = " ".join(subjects).lower()
        subject_allowed = any(
            term.lower() in subject_blob for term in allowed_subject_terms
        )
        license_id, rights_status, license_locator = _license(
            _texts(dc, "rights")
        )
        titles = _texts(dc, "title")
        creators = _texts(dc, "creator")

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
                "native_timestamp": timestamp.isoformat().replace("+00:00", "Z"),
                "timestamp_semantics": "publication-version",
                "era_window": "unresolved",
                "version_status": "unresolved",
                "version_count": 1,
                "rights_status": rights_status,
                "license_id": license_id,
                "license_locator": license_locator,
                "authorship_provenance": "human",
                "categories": subjects,
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
                    "lifecycle_date_precision": date_evidence.precision,
                    "lifecycle_date_value_count": len(raw_dates),
                    "lifecycle_date_values_sha256": _sha256_text(" | ".join(raw_dates)),
                    "title_sha256": _sha256_text(" | ".join(titles)),
                    "title_length": sum(len(value) for value in titles),
                    "creator_count": len(creators),
                    "creators_sha256": _sha256_text(" | ".join(creators)),
                    "subject_allowed": subject_allowed,
                    "oai_identifier_count": len(identifiers),
                    "version_count_interpretation": (
                        "metadata-record-placeholder; article-version count unresolved"
                    ),
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
