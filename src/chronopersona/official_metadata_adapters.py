"""Canonical metadata-only adapters for ChronoPersona source qualification.

The functions in this module parse bounded responses or inventories from the
official interfaces used during Stage 0. They intentionally omit document
text, abstracts, titles, comments, and bodies. Their outputs are adapter-level
metadata records: they still require normalization and validation through the
source-neutral contract before a source record becomes eligible.

Missing dates, rights, or version information are represented as unresolved
values with reason-coded exclusions. They are never replaced with sentinel
historical timestamps.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
import hashlib
import hmac
import json
from pathlib import PurePosixPath
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET


OAI_NS = "http://www.openarchives.org/OAI/2.0/"
ARXIV_RAW_NS = "http://arxiv.org/OAI/arXivRaw/"
OAI_DC_NS = "http://www.openarchives.org/OAI/2.0/oai_dc/"
DC_NS = "http://purl.org/dc/elements/1.1/"

_OAI = f"{{{OAI_NS}}}"
_ARXIV = f"{{{ARXIV_RAW_NS}}}"
_OAI_DC = f"{{{OAI_DC_NS}}}"
_DC = f"{{{DC_NS}}}"

_ARXIV_ID = re.compile(r"^(?:[a-z-]+/)?\d{4,7}(?:\.\d{4,5})?(?:v\d+)?$", re.I)
_VERSION_SUFFIX = re.compile(r"v(?P<version>\d+)$", re.I)
_ALLOWED_ARCHIVE_SUFFIXES = (".7z", ".bz2", ".gz", ".xz", ".zip")


class MetadataAdapterError(ValueError):
    """Raised when an official metadata response is structurally invalid."""


@dataclass(frozen=True)
class AdapterRecord:
    """Metadata-only record emitted by an official-source adapter."""

    adapter_schema_version: int
    source_id: str
    native_id: str
    native_timestamp: str | None
    timestamp_semantics: str
    timestamp_status: str
    version_count: int | None
    historical_version_status: str
    rights_status: str
    license_id: str | None
    license_locator: str | None
    authorship_provenance: str
    categories: tuple[str, ...]
    metadata_locator: str | None
    content_locator: str | None
    eligible_for_bounded_review: bool
    exclusion_reasons: tuple[str, ...]
    source_metadata: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["categories"] = list(self.categories)
        value["exclusion_reasons"] = list(self.exclusion_reasons)
        value["source_metadata"] = dict(self.source_metadata)
        return value


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value or None


def _all_text(parent: ET.Element, tag: str) -> tuple[str, ...]:
    values: list[str] = []
    for element in parent.findall(tag):
        value = _text(element)
        if value is not None:
            values.append(value)
    return tuple(values)


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None

    # Date-only metadata is normalized to midnight UTC while preserving the
    # fact that day precision was the source precision in source_metadata.
    try:
        parsed_date = date.fromisoformat(candidate)
    except ValueError:
        parsed_date = None
    if parsed_date is not None:
        return datetime(
            parsed_date.year,
            parsed_date.month,
            parsed_date.day,
            tzinfo=timezone.utc,
        )

    normalized = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _xml_root(payload: bytes | str) -> ET.Element:
    try:
        return ET.fromstring(payload)
    except ET.ParseError as error:
        raise MetadataAdapterError(f"invalid XML: {error}") from error


def _bounded(records: Iterable[AdapterRecord], max_records: int) -> tuple[AdapterRecord, ...]:
    if max_records < 1:
        raise MetadataAdapterError("max_records must be positive")
    output: list[AdapterRecord] = []
    for record in records:
        output.append(record)
        if len(output) >= max_records:
            break
    return tuple(output)


def _arxiv_native_id(header_identifier: str | None, raw_id: str | None) -> str | None:
    if raw_id:
        return raw_id.removeprefix("arXiv:")
    if header_identifier:
        return header_identifier.rsplit(":", 1)[-1].removeprefix("arXiv:")
    return None


def _arxiv_version(native_id: str, version_value: str | None) -> int | None:
    if version_value:
        match = re.search(r"\d+", version_value)
        if match:
            return int(match.group(0))
    match = _VERSION_SUFFIX.search(native_id)
    return int(match.group("version")) if match else None


def parse_arxiv_raw_oai(
    payload: bytes | str,
    *,
    max_records: int,
    metadata_base_url: str = "https://export.arxiv.org/oai2",
) -> tuple[AdapterRecord, ...]:
    """Parse an arXiv OAI response using the ``arXivRaw`` metadata prefix.

    The adapter uses the work's submitted/created date when present. The OAI
    datestamp remains audit metadata and is not silently substituted for the
    document-production timestamp.
    """

    root = _xml_root(payload)

    def records() -> Iterable[AdapterRecord]:
        for oai_record in root.findall(f".//{_OAI}record"):
            header = oai_record.find(f"{_OAI}header")
            if header is None:
                continue
            header_id = _text(header.find(f"{_OAI}identifier"))
            datestamp = _text(header.find(f"{_OAI}datestamp"))
            deleted = header.get("status") == "deleted"
            set_specs = _all_text(header, f"{_OAI}setSpec")

            raw = oai_record.find(f"{_OAI}metadata/{_ARXIV}arXivRaw")
            raw_id = _text(raw.find(f"{_ARXIV}id")) if raw is not None else None
            native_id = _arxiv_native_id(header_id, raw_id)
            if native_id is None:
                continue

            created_raw = _text(raw.find(f"{_ARXIV}created")) if raw is not None else None
            updated_raw = _text(raw.find(f"{_ARXIV}updated")) if raw is not None else None
            version_raw = _text(raw.find(f"{_ARXIV}version")) if raw is not None else None
            categories_raw = _text(raw.find(f"{_ARXIV}categories")) if raw is not None else None
            license_locator = _text(raw.find(f"{_ARXIV}license")) if raw is not None else None

            production_time = _parse_datetime(created_raw)
            version = _arxiv_version(native_id, version_raw)
            exclusions: list[str] = []
            if deleted:
                exclusions.append("deleted-oai-record")
            if production_time is None:
                exclusions.append("missing-native-submission-date")
            if version is None:
                exclusions.append("unresolved-version-count")
            elif version != 1:
                exclusions.append("not-single-version")
            if license_locator is None:
                exclusions.append("missing-item-level-license")

            categories = tuple(
                token
                for token in (categories_raw or "").split()
                if token
            )
            metadata_locator = (
                f"{metadata_base_url}?verb=GetRecord&metadataPrefix=arXivRaw&"
                f"identifier={header_id}"
                if header_id
                else metadata_base_url
            )
            content_locator = f"https://arxiv.org/src/{native_id}"
            license_id = (
                PurePosixPath(urlsplit(license_locator).path.rstrip("/")).name
                if license_locator
                else None
            )

            yield AdapterRecord(
                adapter_schema_version=1,
                source_id="arxiv-oai-arxivraw",
                native_id=native_id,
                native_timestamp=_iso(production_time),
                timestamp_semantics="initial-submission-date",
                timestamp_status="resolved" if production_time else "missing",
                version_count=version,
                historical_version_status=(
                    "single-version" if version == 1 else "unresolved-or-multiversion"
                ),
                rights_status="item-level-present" if license_locator else "unresolved",
                license_id=license_id,
                license_locator=license_locator,
                authorship_provenance="human-research-article-unverified",
                categories=categories,
                metadata_locator=metadata_locator,
                content_locator=content_locator,
                eligible_for_bounded_review=not exclusions,
                exclusion_reasons=tuple(exclusions),
                source_metadata={
                    "oai_identifier": header_id,
                    "oai_datestamp": datestamp,
                    "oai_set_specs": list(set_specs),
                    "created_raw": created_raw,
                    "updated_raw": updated_raw,
                    "version_raw": version_raw,
                    "deleted": deleted,
                    "native_id_shape_valid": bool(_ARXIV_ID.fullmatch(native_id)),
                },
            )

    return _bounded(records(), max_records)


def _pmc_license(rights_values: Sequence[str]) -> tuple[str | None, str | None]:
    for value in rights_values:
        lower = value.lower()
        if "creativecommons.org/publicdomain/zero" in lower or "cc0" in lower:
            return "CC0-1.0", value if value.startswith("http") else None
        if "creativecommons.org/licenses/by/" in lower or re.search(r"\bcc\s*by\b", lower):
            return "CC-BY", value if value.startswith("http") else None
    return None, None


def parse_pmc_oai_dc(
    payload: bytes | str,
    *,
    max_records: int,
    metadata_base_url: str = "https://www.ncbi.nlm.nih.gov/pmc/utils/oai/oai.cgi",
) -> tuple[AdapterRecord, ...]:
    """Parse PMC OAI Dublin Core metadata without inventing missing dates."""

    root = _xml_root(payload)

    def records() -> Iterable[AdapterRecord]:
        for oai_record in root.findall(f".//{_OAI}record"):
            header = oai_record.find(f"{_OAI}header")
            if header is None:
                continue
            header_id = _text(header.find(f"{_OAI}identifier"))
            datestamp = _text(header.find(f"{_OAI}datestamp"))
            deleted = header.get("status") == "deleted"
            set_specs = _all_text(header, f"{_OAI}setSpec")
            dc = oai_record.find(f"{_OAI}metadata/{_OAI_DC}dc")
            if dc is None:
                continue

            identifiers = _all_text(dc, f"{_DC}identifier")
            date_values = _all_text(dc, f"{_DC}date")
            rights_values = _all_text(dc, f"{_DC}rights")
            type_values = _all_text(dc, f"{_DC}type")

            native_id = next(
                (
                    value
                    for value in identifiers
                    if value.upper().startswith("PMC")
                ),
                header_id.rsplit(":", 1)[-1] if header_id else None,
            )
            if native_id is None:
                continue

            parsed_dates = tuple(
                parsed
                for parsed in (_parse_datetime(value) for value in date_values)
                if parsed is not None
            )
            production_time = min(parsed_dates) if parsed_dates else None
            license_id, license_locator = _pmc_license(rights_values)
            exclusions: list[str] = []
            if deleted:
                exclusions.append("deleted-oai-record")
            if production_time is None:
                exclusions.append("missing-native-publication-date")
            if license_id not in {"CC0-1.0", "CC-BY"}:
                exclusions.append("license-not-cc0-or-cc-by")
            # Dublin Core metadata alone does not establish that the retrieved
            # historical full text is a single immutable version.
            exclusions.append("historical-version-integrity-unverified")

            metadata_locator = (
                f"{metadata_base_url}?verb=GetRecord&metadataPrefix=oai_dc&"
                f"identifier={header_id}"
                if header_id
                else metadata_base_url
            )
            content_locator = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{native_id}/"

            yield AdapterRecord(
                adapter_schema_version=1,
                source_id="pmc-oai-dublin-core",
                native_id=native_id,
                native_timestamp=_iso(production_time),
                timestamp_semantics="earliest-parseable-dc-date",
                timestamp_status="resolved" if production_time else "missing",
                version_count=None,
                historical_version_status="unverified",
                rights_status=(
                    "item-level-eligible" if license_id else "unresolved-or-ineligible"
                ),
                license_id=license_id,
                license_locator=license_locator,
                authorship_provenance="human-research-article-unverified",
                categories=tuple(sorted(set(type_values))),
                metadata_locator=metadata_locator,
                content_locator=content_locator,
                eligible_for_bounded_review=not exclusions,
                exclusion_reasons=tuple(exclusions),
                source_metadata={
                    "oai_identifier": header_id,
                    "oai_datestamp": datestamp,
                    "oai_set_specs": list(set_specs),
                    "date_values": list(date_values),
                    "identifier_values": list(identifiers),
                    "rights_values": list(rights_values),
                    "deleted": deleted,
                },
            )

    return _bounded(records(), max_records)


def _inventory_entry(
    *,
    source_id: str,
    name: str,
    locator: str,
    size: int | None,
    hashes: Mapping[str, str],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "inventory_schema_version": 1,
        "source_id": source_id,
        "name": name,
        "locator": locator,
        "size_bytes": size,
        "hashes": dict(hashes),
        "metadata": dict(metadata),
    }


def parse_wikimedia_dumpstatus(
    payload: bytes | str | Mapping[str, Any],
    *,
    base_url: str,
    max_files: int,
) -> tuple[dict[str, Any], ...]:
    """Return Wikimedia page-history files from a bounded dumpstatus payload."""

    if max_files < 1:
        raise MetadataAdapterError("max_files must be positive")
    data = json.loads(payload) if isinstance(payload, (bytes, str)) else dict(payload)
    jobs = data.get("jobs")
    if not isinstance(jobs, Mapping):
        raise MetadataAdapterError("Wikimedia dumpstatus has no jobs object")

    output: list[dict[str, Any]] = []
    for job_name in sorted(jobs):
        job = jobs[job_name]
        if not isinstance(job, Mapping):
            continue
        files = job.get("files")
        if not isinstance(files, Mapping):
            continue
        for file_name in sorted(files):
            lower = file_name.lower()
            if "pages-meta-history" not in lower:
                continue
            if not lower.endswith(_ALLOWED_ARCHIVE_SUFFIXES):
                continue
            raw = files[file_name]
            if not isinstance(raw, Mapping):
                continue
            size_raw = raw.get("size")
            try:
                size = int(size_raw) if size_raw is not None else None
            except (TypeError, ValueError):
                size = None
            hashes = {
                key: str(raw[key])
                for key in ("sha1", "md5")
                if raw.get(key)
            }
            locator = base_url.rstrip("/") + "/" + file_name.lstrip("/")
            output.append(
                _inventory_entry(
                    source_id="wikimedia-dumpstatus",
                    name=file_name,
                    locator=locator,
                    size=size,
                    hashes=hashes,
                    metadata={
                        "job_name": job_name,
                        "job_status": job.get("status"),
                        "url": raw.get("url"),
                    },
                )
            )
            if len(output) >= max_files:
                return tuple(output)
    return tuple(output)


def parse_stackexchange_archive_inventory(
    payload: bytes | str | Mapping[str, Any],
    *,
    archive_base_url: str,
    max_files: int,
    allowed_sites: Sequence[str] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Parse the Internet Archive metadata response for Stack Exchange dumps."""

    if max_files < 1:
        raise MetadataAdapterError("max_files must be positive")
    data = json.loads(payload) if isinstance(payload, (bytes, str)) else dict(payload)
    files = data.get("files")
    if not isinstance(files, list):
        raise MetadataAdapterError("Internet Archive metadata has no files list")

    allow = {site.lower() for site in allowed_sites or ()}
    output: list[dict[str, Any]] = []
    for raw in sorted(
        (entry for entry in files if isinstance(entry, Mapping)),
        key=lambda entry: str(entry.get("name", "")),
    ):
        name = str(raw.get("name", ""))
        lower = name.lower()
        if not lower.endswith(".7z"):
            continue
        site = lower.removesuffix(".7z")
        if allow and site not in allow:
            continue
        size_raw = raw.get("size")
        try:
            size = int(size_raw) if size_raw is not None else None
        except (TypeError, ValueError):
            size = None
        hashes = {
            key: str(raw[key])
            for key in ("sha1", "md5", "crc32")
            if raw.get(key)
        }
        locator = archive_base_url.rstrip("/") + "/" + name
        output.append(
            _inventory_entry(
                source_id="stackexchange-internet-archive-inventory",
                name=name,
                locator=locator,
                size=size,
                hashes=hashes,
                metadata={
                    "site": site,
                    "format": raw.get("format"),
                    "mtime": raw.get("mtime"),
                    "source": raw.get("source"),
                },
            )
        )
        if len(output) >= max_files:
            break
    return tuple(output)


def redact_locator(locator: str, secret: bytes, *, prefix: str = "sourcec") -> str:
    """Replace a potentially identifying locator with a keyed opaque token."""

    if not locator:
        raise MetadataAdapterError("locator must not be empty")
    if not secret:
        raise MetadataAdapterError("redaction secret must not be empty")
    digest = hmac.new(secret, locator.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{prefix}://{digest}"


def sanitize_request_url(locator: str) -> str:
    """Retain endpoint shape and query keys without logging query values."""

    parsed = urlsplit(locator)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise MetadataAdapterError("request URL must be absolute HTTP(S)")
    query_keys = sorted({key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)})
    safe_query = urlencode([(key, "<redacted>") for key in query_keys])
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, safe_query, ""))


def canonical_sha256(value: Any) -> str:
    """Return a stable hash for JSON-compatible adapter artifacts."""

    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
