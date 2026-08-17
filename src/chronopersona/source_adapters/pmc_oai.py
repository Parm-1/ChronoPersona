"""Parse PMC OAI Dublin Core metadata without retrieving article text."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from typing import Any
from urllib.parse import quote
import xml.etree.ElementTree as ET

from ..source_metadata import EraWindows


class PmcMetadataError(ValueError):
    """Raised when PMC OAI metadata lacks a usable identity."""


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


def _parse_date(values: list[str]) -> datetime | None:
    for raw in values:
        candidates = [raw]
        if raw.endswith("Z"):
            candidates.append(raw[:-1] + "+00:00")
        for candidate in candidates:
            try:
                parsed = datetime.fromisoformat(candidate)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
    return None


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


def parse_pmc_oai_dc(
    xml_bytes: bytes,
    *,
    windows: EraWindows,
    allowed_subject_terms: tuple[str, ...],
    source_id: str = "pmc-oa-cc-version-bounded",
) -> tuple[list[dict[str, Any]], str | None]:
    """Return backup-C metadata records and the OAI resumption token.

    OAI Dublin Core does not prove historical article-version integrity. Every
    parsed record therefore remains unresolved until the OA service/update
    audit establishes a version-bounded JATS object.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as error:
        raise PmcMetadataError(f"invalid PMC OAI XML: {error}") from error

    records: list[dict[str, Any]] = []
    for record in [
        element for element in root.iter() if _local(element.tag) == "record"
    ]:
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
        dc = list(metadata)[0]
        identifiers = _texts(dc, "identifier")
        pmcid = next(
            (
                value
                for value in identifiers
                if value.upper().startswith("PMC")
            ),
            None,
        )
        if pmcid is None:
            header_ids = _texts(header, "identifier")
            for value in header_ids:
                marker = value.upper().rfind("PMC")
                if marker >= 0:
                    pmcid = value[marker:]
                    break
        if pmcid is None:
            raise PmcMetadataError("PMC OAI record has no PMCID")
        pmcid = pmcid.split("/")[0].split("?")[0]

        timestamp = _parse_date(_texts(dc, "date"))
        era_window = windows.classify(timestamp) if timestamp else "unresolved"
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

        exclusion_reasons: list[str] = []
        if timestamp is None:
            exclusion_reasons.append("publication-date-unresolved")
        elif era_window == "outside":
            exclusion_reasons.append("outside-era-window")
        if rights_status != "eligible":
            exclusion_reasons.append("license-not-eligible")
        if not subject_allowed:
            exclusion_reasons.append("subject-not-in-frozen-stratum")
        exclusion_reasons.append("historical-version-unresolved")

        records.append(
            {
                "schema_version": 1,
                "record_id": f"pmc:{pmcid}",
                "source_id": source_id,
                "native_item_id": pmcid,
                "native_timestamp": (
                    timestamp.isoformat().replace("+00:00", "Z")
                    if timestamp is not None
                    else "1970-01-01T00:00:00Z"
                ),
                "timestamp_semantics": "publication-version",
                "era_window": era_window,
                "version_status": "unresolved",
                "version_count": 1,
                "rights_status": rights_status,
                "license_id": license_id,
                "license_locator": license_locator,
                "authorship_provenance": "human",
                "categories": subjects,
                "review_strata": [
                    "timestamp-boundary"
                    if timestamp is None
                    else (
                        "rights-boundary"
                        if rights_status != "eligible"
                        else "exposure-boundary"
                    )
                ],
                "metadata_locator": (
                    "https://www.ncbi.nlm.nih.gov/pmc/oai/oai.cgi?"
                    f"verb=GetRecord&metadataPrefix=oai_dc&identifier="
                    f"{quote('oai:pubmedcentral.nih.gov:' + pmcid)}"
                ),
                "content_locator": None,
                "content_retrieved": False,
                "eligibility": "unresolved",
                "exclusion_reasons": exclusion_reasons,
                "source_metadata": {
                    "title_sha256": _sha256_text(" | ".join(titles)),
                    "title_length": sum(len(value) for value in titles),
                    "creator_count": len(creators),
                    "creators_sha256": _sha256_text(" | ".join(creators)),
                    "subject_allowed": subject_allowed,
                    "oai_identifier_count": len(identifiers),
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
