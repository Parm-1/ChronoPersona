"""Ordered execution state machine for the frozen source-metadata gate.

This module is network-implementation agnostic.  The production CLI binds the
clean Git inputs and reserves every output before lazily importing and passing
the bounded metadata fetcher.  Tests inject a fixture fetcher without importing
the network module.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import hashlib
import platform
import re
from typing import Any, Protocol
from urllib.parse import quote, urlencode

from .source_adapters.arxiv_api import ArxivApiError, parse_arxiv_api_feed
from .source_adapters.arxiv_oai import ArxivMetadataError, parse_arxiv_raw_oai
from .source_adapters.pmc_oai import PmcMetadataError, parse_pmc_oai_dc
from .source_adapters.stackexchange_inventory import (
    StackExchangeInventoryError,
    parse_stackexchange_archive_metadata,
)
from .source_adapters.wikimedia_inventory import (
    WikimediaInventoryError,
    parse_wikimedia_dumpstatus,
)
from .source_audit import (
    BoundSourceInputs,
    FROZEN_PROFILE_CANONICAL_SHA256,
    FROZEN_PROFILE_GIT_BLOB,
    MetadataResponseLike,
    MetadataTransportError,
    PROFILE_RELATIVE_PATH,
    RUNTIME_RELATIVE_PATHS,
    SourceAuditError,
    SourceOutputReservation,
    arxiv_block_starts,
    canonical_json_bytes,
    canonical_json_sha256,
    canonical_jsonl_bytes,
    keyed_commitment,
    parse_json_object,
    receipt_with_self_hash,
    response_identity,
    validate_public_receipt,
)
from .source_inventory import validate_source_inventory
from .source_metadata import (
    FROZEN_ARXIV_PERSISTED_CATEGORIES,
    EraWindows,
    parse_era_windows,
    validate_source_metadata,
)


GROUP_ORDER = (
    "wikimedia-inventory",
    "stackexchange-inventory",
    "arxiv-early-candidate-sample",
    "arxiv-early-exact-enrichment",
    "arxiv-late-candidate-sample",
    "arxiv-late-exact-enrichment",
    "pmc-early-range-metadata",
    "pmc-late-range-metadata",
)
_PRIVATE_FILES = {
    "wikimedia-inventory": "wikimedia-inventory.json",
    "stackexchange-inventory": "stackexchange-inventory.json",
    "arxiv-early-candidate-sample": "arxiv-early-candidates.jsonl",
    "arxiv-early-exact-enrichment": "arxiv-early-enriched.jsonl",
    "arxiv-late-candidate-sample": "arxiv-late-candidates.jsonl",
    "arxiv-late-exact-enrichment": "arxiv-late-enriched.jsonl",
    "pmc-early-range-metadata": "pmc-early-metadata.jsonl",
    "pmc-late-range-metadata": "pmc-late-metadata.jsonl",
}
_CLAIM_CEILING = "endpoint-and-metadata-yield-prequalification-only"
_COMMITMENT_KEY_SHA256 = "314b9f8e9ef018fcc8f33ff310079e1f42253e04a553e2a0c288124e917d1aca"
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_ARXIV_BASE_ID = re.compile(
    r"(?:\d{4}\.\d{4,5}|[A-Za-z][A-Za-z0-9.-]*/\d{7})"
)
_UTC_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z")
_PMCID = re.compile(r"PMC[1-9]\d*")
_ARXIV_EXCLUSION_REASONS = frozenset(
    {
        "license-enrichment-required",
        "version-enrichment-required",
        "outside-era-window",
        "multiple-versions-heldout",
        "license-not-eligible",
        "category-not-in-frozen-stratum",
        "forbidden-cross-list-category",
    }
)
_PMC_EXCLUSION_REASONS = frozenset(
    {
        "timestamp-semantics-unresolved",
        "historical-version-unresolved",
        "license-not-eligible",
        "subject-not-in-frozen-stratum",
    }
)
_CANONICAL_INPUT_BINDINGS = {
    "source_registry": (
        "artifacts/manifests/SOURCE_REGISTRY.json",
        "949180212d98c8c997dc51a9449dff6a73542cad",
    ),
    "arxiv_metadata_config": (
        "configs/sources/arxiv-metadata-v0.json",
        "3e9a9ca9cd59273b348d6a39f763d0affa650e32",
    ),
    "pmc_metadata_config": (
        "configs/sources/pmc-metadata-v0.json",
        "7a564b68ec934e1c92ec6a62da6b370ec2941a90",
    ),
}
_BOUNDARIES = {
    "archive_downloaded": False,
    "article_body_downloaded": False,
    "source_package_downloaded": False,
    "requester_pays_used": False,
    "response_prose_persisted": False,
    "response_prose_displayed": False,
    "response_prose_human_reviewed": False,
    "model_executed": False,
    "behavioral_outcomes_used": False,
    "scientific_claim_authorized": False,
}
_COUNTER_VOCABULARIES = {
    "eligibility_counts": frozenset({"eligible", "excluded", "unresolved"}),
    "rights_status_counts": frozenset(
        {"eligible", "conditional", "ineligible", "unresolved"}
    ),
    "version_status_counts": frozenset(
        {
            "version-bounded",
            "single-version",
            "latest-only",
            "unresolved",
            "unavailable",
        }
    ),
    "license_id_counts": frozenset(
        {
            "pending-arXivRaw-enrichment",
            "CC0-1.0",
            "CC-BY-1.0",
            "CC-BY-2.0",
            "CC-BY-2.5",
            "CC-BY-3.0",
            "CC-BY-4.0",
            "creative-commons-other",
            "arXiv-default",
            "custom-or-unresolved",
            "missing",
        }
    ),
}
_LICENSE_IDS = frozenset(_COUNTER_VOCABULARIES["license_id_counts"])
_INVENTORY_RECORD_FIELDS = {
    "schema_version",
    "inventory_id",
    "source_id",
    "snapshot_id",
    "file_name",
    "locator",
    "content_kind",
    "size_bytes",
    "hashes",
    "downloaded",
    "download_authorized",
    "source_metadata",
}
_METADATA_RECORD_FIELDS = {
    "schema_version",
    "record_id",
    "source_id",
    "native_item_id",
    "native_timestamp",
    "timestamp_semantics",
    "era_window",
    "version_status",
    "version_count",
    "rights_status",
    "license_id",
    "license_locator",
    "authorship_provenance",
    "categories",
    "review_strata",
    "metadata_locator",
    "content_locator",
    "content_retrieved",
    "eligibility",
    "exclusion_reasons",
    "source_metadata",
}
_PRIVATE_METADATA_FIELDS = {
    "wikimedia-inventory": {
        "job_name",
        "job_status",
        "dumpstatus_schema_version",
        "dumpstatus_locator",
    },
    "stackexchange-inventory": {
        "site_slug",
        "archive_item_identifier",
        "archive_item_creator_count",
        "archive_item_creators_sha256",
        "company_attributed_archive_item",
        "delivery_status",
        "archive_metadata_locator",
        "format",
        "mtime",
        "snapshot_basis",
    },
    "arxiv-candidate": {
        "candidate_selection_source",
        "returned_version",
        "updated_timestamp",
        "published_equals_updated",
        "title_sha256",
        "title_length",
        "abstract_sha256",
        "abstract_length",
        "author_count",
        "authors_sha256",
        "category_allowed",
        "category_forbidden",
        "raw_category_count",
        "raw_categories_sha256",
    },
    "arxiv-enrichment": {
        "base_identifier",
        "version_labels",
        "latest_version_timestamp",
        "title_sha256",
        "title_length",
        "abstract_sha256",
        "abstract_length",
        "author_count",
        "authors_sha256",
        "category_allowed",
        "category_forbidden",
        "raw_category_count",
        "raw_categories_sha256",
    },
    "pmc": {
        "dc_date_semantics",
        "candidate_era_window",
        "oai_header_datestamp_precision",
        "lifecycle_date_precision",
        "lifecycle_date_value_count",
        "lifecycle_date_values_sha256",
        "title_sha256",
        "title_length",
        "creator_count",
        "creators_sha256",
        "rights_value_count",
        "rights_values_sha256",
        "subject_allowed",
        "subject_value_count",
        "subject_values_sha256",
        "oai_identifier_count",
        "version_count_interpretation",
    },
}


class MetadataFetcher(Protocol):
    def __call__(
        self,
        url: str,
        *,
        allow_network: bool,
        allowed_hosts: Sequence[str],
        max_bytes: int,
        timeout_seconds: float,
        user_agent: str,
        delay_seconds: float = 0.0,
        allow_redirects: bool = True,
    ) -> MetadataResponseLike: ...


FAILURE_SUBTYPES = frozenset(
    {
        "category-contract",
        "contract-validation",
        "duplicate-identity",
        "execution-interrupted",
        "final-integrity-rebind",
        "group-state",
        "inventory-contract",
        "metadata-contract",
        "output-publication",
        "paging-contract",
        "preflight-integrity",
        "record-identity",
        "request-cap",
        "request-echo",
        "response-envelope",
        "resource-ceiling",
        "resumption-token",
        "rights-contract",
        "timestamp-contract",
        "transport",
        "unexpected-execution",
    }
)
_BROAD_CLASSIFIED_REASONS = frozenset(
    {
        "contract-validation-failed",
        "inventory-parse-failed",
        "metadata-parse-failed",
    }
)
_SPECIAL_FAILURE_REASONS = {
    "execution-interrupted": "execution-interrupted",
    "final-integrity-rebind-failed": "final-integrity-rebind",
    "metadata-transport-failed": "transport",
    "output-publication-failed": "output-publication",
    "unexpected-execution-failure": "unexpected-execution",
}
_SPECIFIC_FAILURE_REASONS = frozenset(
    f"{subtype}-failed"
    for subtype in FAILURE_SUBTYPES
    if subtype not in set(_SPECIAL_FAILURE_REASONS.values())
)
_ALLOWED_FAILURE_REASONS = _SPECIFIC_FAILURE_REASONS | frozenset(
    _SPECIAL_FAILURE_REASONS
)

_INVENTORY_GROUP_FAILURE_SUBTYPES = frozenset(
    {
        "contract-validation",
        "duplicate-identity",
        "group-state",
        "inventory-contract",
        "record-identity",
        "request-echo",
        "resource-ceiling",
        "response-envelope",
    }
)
_METADATA_GROUP_FAILURE_SUBTYPES = frozenset(
    {
        "category-contract",
        "contract-validation",
        "duplicate-identity",
        "group-state",
        "metadata-contract",
        "paging-contract",
        "record-identity",
        "request-cap",
        "request-echo",
        "resource-ceiling",
        "response-envelope",
        "resumption-token",
        "rights-contract",
        "timestamp-contract",
    }
)
_GROUP_SPECIAL_FAILURE_REASONS = frozenset(
    {
        "execution-interrupted",
        "metadata-transport-failed",
        "unexpected-execution-failure",
    }
)
_SHARED_AGGREGATE_RECEIPT_FIELDS = (
    "schema_version",
    "profile_id",
    "claim_ceiling",
    "execution",
    "git",
    "runtime",
    "privacy",
    "network",
    "groups",
    "private_artifacts",
    "boundaries",
)


def _failure_subtype(
    error: BaseException | str,
    *,
    group: str,
    stage: str,
    reason_code: str,
) -> str:
    """Reduce private failure detail to one closed, actionable invariant code."""

    if reason_code == "metadata-transport-failed":
        return "transport"
    if reason_code == "final-integrity-rebind-failed":
        return "final-integrity-rebind"
    if reason_code == "output-publication-failed":
        return "output-publication"
    if reason_code == "execution-interrupted":
        return "execution-interrupted"
    if reason_code == "unexpected-execution-failure":
        return "unexpected-execution"
    if group == "preflight":
        return "preflight-integrity"

    detail = str(error).casefold()
    patterns = (
        ("request echo", "request-echo"),
        ("resumption token", "resumption-token"),
        ("request cap", "request-cap"),
        ("request ceiling", "resource-ceiling"),
        ("upstream-record cap", "resource-ceiling"),
        ("response exceeded", "resource-ceiling"),
        ("duplicate", "duplicate-identity"),
        ("not unique", "duplicate-identity"),
        ("identical", "duplicate-identity"),
        ("repeated across pages", "duplicate-identity"),
        ("paging", "paging-contract"),
        ("page start", "paging-contract"),
        ("page size", "paging-contract"),
        ("page order", "paging-contract"),
        ("short page", "paging-contract"),
        ("cell order", "paging-contract"),
        ("identifier", "record-identity"),
        ("record id", "record-identity"),
        ("native item id", "record-identity"),
        ("pmcid", "record-identity"),
        ("item identity", "record-identity"),
        ("base id", "record-identity"),
        ("timestamp", "timestamp-contract"),
        ("date", "timestamp-contract"),
        ("temporal", "timestamp-contract"),
        ("frozen cell", "timestamp-contract"),
        ("category", "category-contract"),
        ("subject", "category-contract"),
        ("license", "rights-contract"),
        ("rights", "rights-contract"),
        ("root", "response-envelope"),
        ("xml", "response-envelope"),
        ("responsedate", "response-envelope"),
        ("header", "response-envelope"),
        ("metadata block", "response-envelope"),
        ("container", "response-envelope"),
        ("namespace", "response-envelope"),
        ("field", "response-envelope"),
        ("group", "group-state"),
    )
    for fragment, subtype in patterns:
        if re.search(
            rf"(?<![a-z0-9]){re.escape(fragment)}(?![a-z0-9])",
            detail,
        ):
            return subtype
    if reason_code == "inventory-parse-failed":
        return "inventory-contract"
    if reason_code == "metadata-parse-failed":
        return "metadata-contract"
    if reason_code == "contract-validation-failed":
        return "contract-validation"
    raise SourceAuditError(
        f"source failure reason has no closed subtype at stage {stage}"
    )


class SourceGateError(RuntimeError):
    """Raised after one frozen group consumes a failure."""

    def __init__(
        self,
        *,
        group: str,
        stage: str,
        reason_code: str,
        request_ordinal: int | None,
        detail: BaseException | str,
        context: GateContext | None = None,
    ) -> None:
        super().__init__(reason_code)
        self.group = group
        self.stage = stage
        self.request_ordinal = request_ordinal
        detail_text = str(detail)
        self.context = context
        if context is None:
            raise SourceAuditError("source failure requires its bound gate context")
        self.failure_subtype = _failure_subtype(
            detail,
            group=group,
            stage=stage,
            reason_code=reason_code,
        )
        self.reason_code = (
            f"{self.failure_subtype}-failed"
            if reason_code in _BROAD_CLASSIFIED_REASONS
            else reason_code
        )
        self.transport_subtype = (
            detail.subtype if isinstance(detail, MetadataTransportError) else None
        )
        self.detail_hmac_sha256 = keyed_commitment(
            context.commitment_key,
            domain="failure-detail",
            payload=(
                f"{self.reason_code}\0{self.failure_subtype}\0{detail_text}"
            ).encode("utf-8"),
        )


@dataclass
class GateContext:
    bound: BoundSourceInputs
    reservation: SourceOutputReservation
    profile: dict[str, Any]
    windows: EraWindows
    commitment_key: bytes
    groups: list[dict[str, Any]] = field(default_factory=list)
    request_attempt_count: int = 0
    completed_response_count: int = 0
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    candidates: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    enriched: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    seen_arxiv_ids: set[str] = field(default_factory=set)
    last_delay_family: str | None = None

    def __post_init__(self) -> None:
        if tuple(self.profile["group_order"]) != GROUP_ORDER:
            raise SourceAuditError("runtime group order does not match the frozen profile")
        if hashlib.sha256(self.commitment_key).hexdigest() != self.profile[
            "privacy"
        ]["commitment_key_sha256"]:
            raise SourceAuditError(
                "runtime commitment key does not match the frozen profile"
            )
        self.groups = [
            {
                "group_id": group,
                "status": "not-started",
                "request_attempt_count": 0,
                "completed_response_count": 0,
                "responses": [],
                "private_artifact": None,
                "metrics": None,
            }
            for group in GROUP_ORDER
        ]

    def group_record(self, group: str) -> dict[str, Any]:
        return self.groups[GROUP_ORDER.index(group)]

    def start_group(self, group: str) -> None:
        index = GROUP_ORDER.index(group)
        if any(record["status"] != "complete" for record in self.groups[:index]):
            raise SourceAuditError("source gate attempted to skip an earlier group")
        if self.groups[index]["status"] != "not-started":
            raise SourceAuditError("source gate group was started more than once")
        self.groups[index]["status"] = "running"

    def fetch(
        self,
        fetcher: MetadataFetcher,
        *,
        group: str,
        url: str,
        host: str,
        max_bytes: int,
        delay_family: str | None,
        delay_seconds: float,
    ) -> MetadataResponseLike:
        network = self.profile["network"]
        maximum = network["maximum_happy_path_requests"]
        if self.request_attempt_count >= maximum:
            raise SourceAuditError("source gate exceeded the frozen request ceiling")
        group_record = self.group_record(group)
        ordinal = self.request_attempt_count
        self.request_attempt_count += 1
        group_record["request_attempt_count"] += 1
        applied_delay = (
            delay_seconds
            if delay_family is not None and self.last_delay_family == delay_family
            else 0.0
        )
        if delay_family is not None:
            self.last_delay_family = delay_family
        response = fetcher(
            url,
            allow_network=True,
            allowed_hosts=(host,),
            max_bytes=max_bytes,
            timeout_seconds=float(network["timeout_seconds"]),
            user_agent=network["user_agent"],
            delay_seconds=applied_delay,
            allow_redirects=False,
        )
        identity = response_identity(
            response,
            group=group,
            ordinal=ordinal,
            expected_url=url,
            commitment_key=self.commitment_key,
        )
        group_record["responses"].append(identity)
        group_record["completed_response_count"] += 1
        self.completed_response_count += 1
        return response

    def complete_group(
        self,
        group: str,
        *,
        payload: bytes,
        metrics: Mapping[str, Any],
    ) -> None:
        record = self.group_record(group)
        if record["status"] != "running":
            raise SourceAuditError("source gate completed a group that was not running")
        file_name = _PRIVATE_FILES[group]
        stored = self.reservation.write_mirrored(file_name, payload)
        artifact = {
            "file_name": stored["file_name"],
            "size_bytes": (
                None
                if group.startswith("arxiv-") or group.startswith("pmc-")
                else stored["size_bytes"]
            ),
            "hmac_sha256": keyed_commitment(
                self.commitment_key,
                domain="private-artifact",
                payload=payload,
            ),
            "backup_verified": stored["backup_verified"],
        }
        self.artifacts.append(artifact)
        record["private_artifact"] = artifact
        record["metrics"] = dict(metrics)
        record["status"] = "complete"

    def fail_group(self, group: str) -> None:
        record = self.group_record(group)
        if record["status"] == "running":
            record["status"] = "failed"


def _source_registry(context: GateContext) -> dict[str, Any]:
    return context.bound.values["source_registry"]


def _arxiv_policy(context: GateContext) -> tuple[tuple[str, ...], tuple[str, ...]]:
    config = context.bound.values["arxiv_metadata_config"]
    return (
        tuple(config["allowed_category_prefixes"]),
        tuple(config.get("forbidden_category_prefixes", [])),
    )


def _inventory_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = sum(int(record["size_bytes"]) for record in records)
    hash_algorithms = Counter(
        algorithm
        for record in records
        for algorithm in record["hashes"]
    )
    return {
        "file_count": len(records),
        "total_size_bytes": total,
        "minimum_free_space_bytes_with_25_percent_margin": (total * 5 + 3) // 4,
        "hash_algorithm_counts": dict(sorted(hash_algorithms.items())),
    }


def _metadata_metrics(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "record_count": len(records),
        "eligibility_counts": dict(
            sorted(Counter(str(record["eligibility"]) for record in records).items())
        ),
        "rights_status_counts": dict(
            sorted(Counter(str(record["rights_status"]) for record in records).items())
        ),
        "license_id_counts": dict(
            sorted(Counter(str(record["license_id"]) for record in records).items())
        ),
        "version_status_counts": dict(
            sorted(Counter(str(record["version_status"]) for record in records).items())
        ),
    }


def _canonical_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _hex64(value: Any) -> bool:
    return isinstance(value, str) and _HEX64.fullmatch(value) is not None


def _canonical_categories(value: Any) -> bool:
    return (
        isinstance(value, list)
        and value == sorted(set(value))
        and all(
            isinstance(category, str)
            and category in FROZEN_ARXIV_PERSISTED_CATEGORIES
            for category in value
        )
    )


def _category_matches(categories: Sequence[str], prefixes: Sequence[str]) -> bool:
    return any(
        category == prefix or category.startswith(prefix + ".")
        for category in categories
        for prefix in prefixes
    )


def _license_locator_is_normalized(license_id: Any, locator: Any) -> bool:
    if not isinstance(license_id, str) or license_id not in _LICENSE_IDS:
        return False
    if not isinstance(locator, str):
        return False
    if license_id == "missing":
        return locator == "missing-license"
    if license_id == "pending-arXivRaw-enrichment":
        return locator.startswith(
            "https://oaipmh.arxiv.org/oai?verb=GetRecord&metadataPrefix=arXivRaw&"
            "identifier=oai%3AarXiv.org%3A"
        )
    if license_id.startswith("CC0-"):
        version = license_id.removeprefix("CC0-")
        return locator == (
            f"https://creativecommons.org/publicdomain/zero/{version}/"
        )
    if license_id.startswith("CC-BY-"):
        version = license_id.removeprefix("CC-BY-")
        return locator == f"https://creativecommons.org/licenses/by/{version}/"
    return (
        locator.startswith("rights-sha256:")
        and _hex64(locator.removeprefix("rights-sha256:"))
    )


def _rights_status_for_license(license_id: Any) -> str | None:
    if not isinstance(license_id, str):
        return None
    if license_id.startswith("CC0-") or license_id.startswith("CC-BY-"):
        return "eligible"
    if license_id in {"creative-commons-other", "arXiv-default"}:
        return "ineligible"
    if license_id in {
        "custom-or-unresolved",
        "missing",
        "pending-arXivRaw-enrichment",
    }:
        return "unresolved"
    return None


def _private_record_errors(
    context: GateContext,
    group: str,
    records: Sequence[Mapping[str, Any]],
) -> tuple[str, ...]:
    """Reject unreviewed fields and values before response records persist."""

    if group in {"wikimedia-inventory", "stackexchange-inventory"}:
        root_fields = _INVENTORY_RECORD_FIELDS
        metadata_kind = group
    elif group.startswith("arxiv-"):
        root_fields = _METADATA_RECORD_FIELDS
        metadata_kind = (
            "arxiv-candidate"
            if group.endswith("candidate-sample")
            else "arxiv-enrichment"
        )
    elif group.startswith("pmc-"):
        root_fields = _METADATA_RECORD_FIELDS
        metadata_kind = "pmc"
    else:
        return ("private source record group is not frozen",)
    errors: list[str] = []
    for index, record in enumerate(records):
        location = f"{group} record {index}"
        if not isinstance(record, Mapping) or set(record) != root_fields:
            errors.append(f"{location} fields are not exact")
            continue
        metadata = record.get("source_metadata")
        if not isinstance(metadata, Mapping) or set(metadata) != _PRIVATE_METADATA_FIELDS[
            metadata_kind
        ]:
            errors.append(
                f"{location} source-metadata fields are not exact"
            )
            continue
        if type(record.get("schema_version")) is not int or record.get(
            "schema_version"
        ) != 1:
            errors.append(f"{location} schema version is not exact")

        if metadata_kind == "wikimedia-inventory":
            config = context.profile["wikimedia"]
            if (
                record.get("source_id") != "wikimedia-article-additions"
                or record.get("content_kind") != "revision-history-archive"
                or record.get("snapshot_id") != config["snapshot"]
                or type(record.get("size_bytes")) is not int
                or record.get("size_bytes", 0) <= 0
                or metadata.get("job_name") != config["required_job_name"]
                or metadata.get("job_status") != config["required_job_status"]
                or not isinstance(metadata.get("dumpstatus_schema_version"), str)
                or re.fullmatch(
                    r"[1-9]?\d(?:\.\d+)?",
                    metadata.get("dumpstatus_schema_version", ""),
                )
                is None
                or metadata.get("dumpstatus_locator") != config["endpoint"]
                or not isinstance(record.get("locator"), str)
                or not record["locator"].endswith("/" + str(record.get("file_name")))
            ):
                errors.append(f"{location} Wikimedia values are not canonical")
        elif metadata_kind == "stackexchange-inventory":
            config = context.profile["stackexchange"]
            mtime = metadata.get("mtime")
            if (
                record.get("source_id")
                != "stackexchange-initial-nontechnical-posts"
                or record.get("content_kind") != "community-data-dump"
                or type(record.get("size_bytes")) is not int
                or record.get("size_bytes", 0) <= 0
                or not isinstance(metadata.get("site_slug"), str)
                or not metadata.get("site_slug")
                or metadata.get("archive_item_identifier")
                != config["required_item_identifier"]
                or not _is_int(metadata.get("archive_item_creator_count"), minimum=1)
                or not _hex64(metadata.get("archive_item_creators_sha256"))
                or metadata.get("company_attributed_archive_item") is not True
                or metadata.get("delivery_status")
                != "legacy-archive; not current official delivery"
                or metadata.get("archive_metadata_locator") != config["endpoint"]
                or metadata.get("format") != "7z"
                or not (
                    mtime is None or _is_int(mtime)
                )
                or metadata.get("snapshot_basis")
                not in {
                    "maximum-numeric-file-mtime",
                    "archive-item-date-fallback",
                }
                or not isinstance(record.get("locator"), str)
                or not record["locator"].startswith(
                    "https://archive.org/download/stackexchange/"
                )
            ):
                errors.append(f"{location} Stack Exchange values are not canonical")
        else:
            if (
                record.get("authorship_provenance") != "human"
                or record.get("content_retrieved") is not False
                or record.get("content_locator") is not None
                or not _canonical_utc_timestamp(record.get("native_timestamp"))
                or type(record.get("version_count")) is not int
                or record.get("version_count", 0) < 1
                or not isinstance(record.get("categories"), list)
                or not _license_locator_is_normalized(
                    record.get("license_id"), record.get("license_locator")
                )
            ):
                errors.append(f"{location} metadata values are not canonical")

        if metadata_kind in {"arxiv-candidate", "arxiv-enrichment"}:
            base_identifier = (
                record.get("native_item_id")
                if metadata_kind == "arxiv-candidate"
                else metadata.get("base_identifier")
            )
            if not isinstance(base_identifier, str) or _ARXIV_BASE_ID.fullmatch(
                base_identifier
            ) is None:
                errors.append(f"{location} arXiv identifier is not canonical")
            categories = record.get("categories", [])
            category_values = categories if isinstance(categories, list) else []
            query_categories = set(context.profile["arxiv"]["query_categories"])
            expected_allowed = any(
                category in query_categories for category in category_values
            )
            expected_forbidden = "forbidden-arxiv-category" in category_values
            exclusion_reasons = record.get("exclusion_reasons")
            if (
                not isinstance(exclusion_reasons, list)
                or not _canonical_categories(categories)
                or not categories
                or len(exclusion_reasons) != len(set(exclusion_reasons))
                or any(reason not in _ARXIV_EXCLUSION_REASONS for reason in exclusion_reasons)
                or metadata.get("category_allowed") is not expected_allowed
                or metadata.get("category_forbidden") is not expected_forbidden
                or not _is_int(metadata.get("raw_category_count"), minimum=1)
                or metadata.get("raw_category_count") < len(category_values)
                or not _hex64(metadata.get("raw_categories_sha256"))
                or not _hex64(metadata.get("title_sha256"))
                or not _hex64(metadata.get("abstract_sha256"))
                or not _hex64(metadata.get("authors_sha256"))
                or not _is_int(metadata.get("title_length"), minimum=1)
                or not _is_int(metadata.get("abstract_length"), minimum=1)
                or not _is_int(metadata.get("author_count"), minimum=1)
            ):
                errors.append(f"{location} arXiv private evidence is not exact")
            if metadata_kind == "arxiv-candidate":
                returned_version = metadata.get("returned_version")
                expected_window = "early" if "-early-" in group else "late"
                expected_reasons = [
                    "license-enrichment-required",
                    "version-enrichment-required",
                ]
                if record.get("era_window") == "outside":
                    expected_reasons.append("outside-era-window")
                if not expected_allowed:
                    expected_reasons.append("category-not-in-frozen-stratum")
                if expected_forbidden:
                    expected_reasons.append("forbidden-cross-list-category")
                expected_strata = [
                    "exposure-boundary"
                    if expected_forbidden or not expected_allowed
                    else "rights-boundary"
                ]
                expected_oai_locator = (
                    "https://oaipmh.arxiv.org/oai?verb=GetRecord&"
                    "metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + str(base_identifier))}"
                )
                expected_api_locator = (
                    "https://export.arxiv.org/api/query?id_list="
                    f"{quote(str(base_identifier))}"
                )
                if (
                    record.get("source_id")
                    != "arxiv-cc-single-version-descriptive"
                    or record.get("record_id")
                    != f"arxiv-candidate:{base_identifier}"
                    or record.get("metadata_locator") != expected_api_locator
                    or record.get("license_id")
                    != "pending-arXivRaw-enrichment"
                    or record.get("license_locator") != expected_oai_locator
                    or record.get("timestamp_semantics") != "submission-version"
                    or record.get("era_window") != expected_window
                    or record.get("version_status") != "unresolved"
                    or record.get("rights_status") != "unresolved"
                    or record.get("eligibility") != "unresolved"
                    or record.get("exclusion_reasons") != expected_reasons
                    or record.get("review_strata") != expected_strata
                    or metadata.get("candidate_selection_source")
                    != "arxiv-api-submittedDate"
                    or not _is_int(returned_version, minimum=1)
                    or record.get("version_count") != returned_version
                    or not _canonical_utc_timestamp(metadata.get("updated_timestamp"))
                    or type(metadata.get("published_equals_updated")) is not bool
                    or metadata.get("published_equals_updated")
                    is not (
                        metadata.get("updated_timestamp")
                        == record.get("native_timestamp")
                    )
                ):
                    errors.append(f"{location} arXiv candidate values are not exact")
            else:
                labels = metadata.get("version_labels")
                version_count = record.get("version_count")
                expected_version_status = (
                    "single-version" if version_count == 1 else "latest-only"
                )
                expected_reasons: list[str] = []
                if record.get("era_window") == "outside":
                    expected_reasons.append("outside-era-window")
                if version_count != 1:
                    expected_reasons.append("multiple-versions-heldout")
                expected_rights = _rights_status_for_license(
                    record.get("license_id")
                )
                if expected_rights != "eligible":
                    expected_reasons.append("license-not-eligible")
                if not expected_allowed:
                    expected_reasons.append("category-not-in-frozen-stratum")
                if expected_forbidden:
                    expected_reasons.append("forbidden-cross-list-category")
                expected_eligibility = (
                    "eligible" if not expected_reasons else "excluded"
                )
                expected_strata = [
                    "eligible-random"
                    if expected_eligibility == "eligible"
                    else (
                        "rights-boundary"
                        if expected_rights != "eligible"
                        else "exposure-boundary"
                    )
                ]
                expected_locator = (
                    "https://oaipmh.arxiv.org/oai?verb=GetRecord&"
                    "metadataPrefix=arXivRaw&identifier="
                    f"{quote('oai:arXiv.org:' + str(base_identifier))}"
                )
                if (
                    record.get("source_id")
                    != "arxiv-cc-single-version-descriptive"
                    or record.get("native_item_id") != f"{base_identifier}v1"
                    or record.get("record_id")
                    != f"arxiv:{base_identifier}v1"
                    or record.get("metadata_locator") != expected_locator
                    or record.get("timestamp_semantics") != "submission-version"
                    or record.get("version_status") != expected_version_status
                    or record.get("rights_status") != expected_rights
                    or record.get("eligibility") != expected_eligibility
                    or record.get("exclusion_reasons") != expected_reasons
                    or record.get("review_strata") != expected_strata
                    or not isinstance(labels, list)
                    or labels
                    != [f"v{number}" for number in range(1, len(labels) + 1)]
                    or len(labels) != record.get("version_count")
                    or not _canonical_utc_timestamp(
                        metadata.get("latest_version_timestamp")
                    )
                ):
                    errors.append(f"{location} arXiv enrichment values are not exact")
        elif metadata_kind == "pmc":
            allowed_subjects = set(context.profile["pmc"]["allowed_subject_terms"])
            exclusion_reasons = record.get("exclusion_reasons")
            categories = record.get("categories")
            category_values = categories if isinstance(categories, list) else []
            native_item_id = record.get("native_item_id")
            pmc_number = (
                native_item_id.removeprefix("PMC")
                if isinstance(native_item_id, str)
                else ""
            )
            expected_locator = (
                "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?"
                "verb=GetRecord&metadataPrefix=oai_dc&identifier="
                f"{quote('oai:pubmedcentral.nih.gov:' + pmc_number)}"
            )
            expected_rights = _rights_status_for_license(record.get("license_id"))
            expected_subject_allowed = bool(category_values)
            expected_reasons = [
                "timestamp-semantics-unresolved",
                "historical-version-unresolved",
            ]
            if expected_rights != "eligible":
                expected_reasons.append("license-not-eligible")
            if not expected_subject_allowed:
                expected_reasons.append("subject-not-in-frozen-stratum")
            expected_strata = [
                "rights-boundary"
                if expected_rights != "eligible"
                else "timestamp-boundary"
            ]
            if (
                record.get("source_id") != "pmc-oa-cc-version-bounded"
                or not isinstance(native_item_id, str)
                or _PMCID.fullmatch(native_item_id) is None
                or record.get("record_id") != f"pmc:{native_item_id}"
                or record.get("metadata_locator") != expected_locator
                or record.get("timestamp_semantics")
                != "release-or-update-datestamp"
                or record.get("era_window") != "unresolved"
                or record.get("version_status") != "unresolved"
                or record.get("version_count") != 1
                or record.get("rights_status") != expected_rights
                or record.get("eligibility") != "unresolved"
                or not isinstance(categories, list)
                or categories != sorted(set(categories))
                or any(category not in allowed_subjects for category in categories)
                or not isinstance(exclusion_reasons, list)
                or len(exclusion_reasons) != len(set(exclusion_reasons))
                or any(reason not in _PMC_EXCLUSION_REASONS for reason in exclusion_reasons)
                or exclusion_reasons != expected_reasons
                or record.get("review_strata") != expected_strata
                or metadata.get("dc_date_semantics")
                != "lifecycle-associated; not treated as confirmed publication date"
                or metadata.get("candidate_era_window")
                not in {"early", "late", "outside"}
                or metadata.get("oai_header_datestamp_precision")
                not in {"day", "datetime"}
                or metadata.get("lifecycle_date_precision")
                not in {"year", "month", "day", "datetime"}
                or not all(
                    _is_int(metadata.get(field))
                    for field in (
                        "lifecycle_date_value_count",
                        "title_length",
                        "creator_count",
                        "rights_value_count",
                        "subject_value_count",
                        "oai_identifier_count",
                    )
                )
                or not all(
                    _hex64(metadata.get(field))
                    for field in (
                        "lifecycle_date_values_sha256",
                        "title_sha256",
                        "creators_sha256",
                        "rights_values_sha256",
                        "subject_values_sha256",
                    )
                )
                or not _is_int(metadata.get("lifecycle_date_value_count"), minimum=1)
                or not _is_int(metadata.get("oai_identifier_count"), minimum=1)
                or metadata.get("subject_allowed") is not expected_subject_allowed
                or metadata.get("version_count_interpretation")
                != "metadata-record-placeholder; article-version count unresolved"
            ):
                errors.append(f"{location} PMC private evidence is not exact")
    return tuple(errors)


def _run_wikimedia(context: GateContext, fetcher: MetadataFetcher) -> None:
    group = "wikimedia-inventory"
    context.start_group(group)
    config = context.profile["wikimedia"]
    response = context.fetch(
        fetcher,
        group=group,
        url=config["endpoint"],
        host="dumps.wikimedia.org",
        max_bytes=config["maximum_response_bytes"],
        delay_family=None,
        delay_seconds=0.0,
    )
    value = parse_json_object(response.payload, label="Wikimedia dumpstatus response")
    jobs = value.get("jobs")
    if not isinstance(jobs, Mapping):
        raise SourceAuditError("Wikimedia dumpstatus has no jobs object")
    required_job = jobs.get(config["required_job_name"])
    if not isinstance(required_job, Mapping) or required_job.get("status") != config[
        "required_job_status"
    ]:
        raise SourceAuditError("pinned Wikimedia history job is not complete")
    records = parse_wikimedia_dumpstatus(
        value,
        source_locator=config["endpoint"],
        snapshot_id=config["snapshot"],
        required_job_name=config["required_job_name"],
        required_file_name_fragment=config["required_file_name_fragment"],
    )
    errors = validate_source_inventory(records)
    if errors:
        raise SourceAuditError("; ".join(errors))
    private_errors = _private_record_errors(context, group, records)
    if private_errors:
        raise SourceAuditError("; ".join(private_errors))
    metrics = _inventory_metrics(records)
    metrics["snapshot"] = config["snapshot"]
    context.complete_group(
        group,
        payload=canonical_json_bytes(records, pretty=True),
        metrics=metrics,
    )


def _normalized_string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [nested for nested in value if isinstance(nested, str)]
    else:
        values = []
    return [" ".join(nested.split()) for nested in values]


def _run_stackexchange(context: GateContext, fetcher: MetadataFetcher) -> None:
    group = "stackexchange-inventory"
    context.start_group(group)
    config = context.profile["stackexchange"]
    response = context.fetch(
        fetcher,
        group=group,
        url=config["endpoint"],
        host="archive.org",
        max_bytes=config["maximum_response_bytes"],
        delay_family=None,
        delay_seconds=0.0,
    )
    value = parse_json_object(response.payload, label="Stack Exchange metadata response")
    metadata = value.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SourceAuditError("Stack Exchange response has no metadata object")
    if metadata.get("identifier") != config["required_item_identifier"]:
        raise SourceAuditError("Stack Exchange archive item identity is not exact")
    if _normalized_string_values(metadata.get("creator")) != [config["required_creator"]]:
        raise SourceAuditError("Stack Exchange company attribution is not exact")
    records = parse_stackexchange_archive_metadata(
        value,
        source_locator=config["endpoint"],
    )
    errors = validate_source_inventory(records)
    if errors:
        raise SourceAuditError("; ".join(errors))
    private_errors = _private_record_errors(context, group, records)
    if private_errors:
        raise SourceAuditError("; ".join(private_errors))
    if not all(
        record["source_metadata"].get("company_attributed_archive_item") is True
        for record in records
    ):
        raise SourceAuditError("Stack Exchange inventory lost company attribution")
    metrics = _inventory_metrics(records)
    metrics["company_attribution_verified"] = True
    metrics["delivery_status"] = config["delivery_status"]
    context.complete_group(
        group,
        payload=canonical_json_bytes(records, pretty=True),
        metrics=metrics,
    )


def _arxiv_query(categories: Sequence[str], start: date, end: date) -> str:
    category_clause = " OR ".join(f"cat:{category}" for category in categories)
    submitted = (
        f"submittedDate:[{start.strftime('%Y%m%d')}0000 TO "
        f"{end.strftime('%Y%m%d')}2359]"
    )
    return f"({category_clause}) AND {submitted}"


def _arxiv_api_url(
    endpoint: str,
    query: str,
    *,
    start: int,
    page_size: int,
) -> str:
    return endpoint + "?" + urlencode(
        {
            "search_query": query,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
    )


def _cell_dates(record: Mapping[str, Any]) -> tuple[date, date]:
    return date.fromisoformat(record["start_date"]), date.fromisoformat(record["end_date"])


def _record_date(record: Mapping[str, Any]) -> date:
    raw = str(record["native_timestamp"])
    normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    return datetime.fromisoformat(normalized).date()


def _ordered_id_commitment(
    records: Sequence[Mapping[str, Any]],
    *,
    commitment_key: bytes,
) -> str:
    identifiers = [str(record["native_item_id"]) for record in records]
    if any(not value or "\0" in value for value in identifiers):
        raise SourceAuditError("arXiv candidate identifier is invalid")
    return keyed_commitment(
        commitment_key,
        domain="ordered-source-ids",
        payload="\0".join(identifiers).encode("utf-8"),
    )


def _run_arxiv_candidates(
    context: GateContext,
    fetcher: MetadataFetcher,
    *,
    window: str,
) -> None:
    group = f"arxiv-{window}-candidate-sample"
    context.start_group(group)
    config = context.profile["arxiv"]
    allowed, forbidden = _arxiv_policy(context)
    cells = config[f"{window}_cells"]
    expected_cell_ids = {
        "early": ["2012-h1", "2012-h2", "2013-h1", "2013-h2"],
        "late": ["2018-h1", "2018-h2", "2019-h1", "2019-h2"],
    }[window]
    if [cell["cell_id"] for cell in cells] != expected_cell_ids:
        raise SourceAuditError("arXiv cell order drifted")
    records: list[dict[str, Any]] = []
    totals: dict[str, int] = {}
    starts_by_cell: dict[str, list[int]] = {}
    for cell in cells:
        cell_id = cell["cell_id"]
        start_date, end_date = _cell_dates(cell)
        query = _arxiv_query(config["query_categories"], start_date, end_date)
        count_response = context.fetch(
            fetcher,
            group=group,
            url=_arxiv_api_url(
                config["api_endpoint"], query, start=0, page_size=1
            ),
            host="export.arxiv.org",
            max_bytes=config["maximum_api_response_bytes"],
            delay_family="arxiv",
            delay_seconds=float(config["delay_seconds"]),
        )
        count_records, count_page = parse_arxiv_api_feed(
            count_response.payload,
            windows=context.windows,
            allowed_category_prefixes=allowed,
            forbidden_category_prefixes=forbidden,
        )
        total = count_page.get("total_results")
        if (
            type(total) is not int
            or count_page != {
                "total_results": total,
                "start_index": 0,
                "items_per_page": 1,
            }
            or len(count_records) != 1
        ):
            raise SourceAuditError("arXiv count response paging identity drifted")
        starts = arxiv_block_starts(
            total_results=total,
            cell_id=cell_id,
            commitment_key=context.commitment_key,
            domain=config["sampler_domain"],
        )
        totals[cell_id] = total
        starts_by_cell[cell_id] = list(starts)
        for start in starts:
            sample_response = context.fetch(
                fetcher,
                group=group,
                url=_arxiv_api_url(
                    config["api_endpoint"],
                    query,
                    start=start,
                    page_size=config["sample_page_size"],
                ),
                host="export.arxiv.org",
                max_bytes=config["maximum_api_response_bytes"],
                delay_family="arxiv",
                delay_seconds=float(config["delay_seconds"]),
            )
            parsed, page = parse_arxiv_api_feed(
                sample_response.payload,
                windows=context.windows,
                allowed_category_prefixes=allowed,
                forbidden_category_prefixes=forbidden,
            )
            if page != {
                "total_results": total,
                "start_index": start,
                "items_per_page": config["sample_page_size"],
            } or len(parsed) != config["sample_page_size"]:
                raise SourceAuditError("arXiv sample response paging identity drifted")
            timestamps = [
                datetime.fromisoformat(
                    str(record["native_timestamp"]).replace("Z", "+00:00")
                )
                for record in parsed
            ]
            if any(
                later < earlier
                for earlier, later in zip(timestamps, timestamps[1:], strict=False)
            ):
                raise SourceAuditError(
                    "arXiv sample response is not in submitted-date order"
                )
            if any(not (start_date <= _record_date(record) <= end_date) for record in parsed):
                raise SourceAuditError("arXiv sample record escaped its frozen cell")
            if any(
                type(record.get("source_metadata", {}).get("returned_version"))
                is not int
                for record in parsed
            ):
                raise SourceAuditError(
                    "arXiv sample entry lacks an exact returned version"
                )
            records.extend(parsed)
    if len(records) != config["records_per_window"]:
        raise SourceAuditError("arXiv window sample count is incomplete")
    identifiers = [str(record["native_item_id"]) for record in records]
    if len(identifiers) != len(set(identifiers)):
        raise SourceAuditError("arXiv window sample contains duplicate base identifiers")
    overlap = context.seen_arxiv_ids.intersection(identifiers)
    if overlap:
        raise SourceAuditError("arXiv early/late samples contain duplicate identifiers")
    context.seen_arxiv_ids.update(identifiers)
    errors = validate_source_metadata(records, source_registry=_source_registry(context))
    if errors:
        raise SourceAuditError("; ".join(errors))
    private_errors = _private_record_errors(context, group, records)
    if private_errors:
        raise SourceAuditError("; ".join(private_errors))
    context.candidates[window] = records
    selection_commitments = {
        cell_id: keyed_commitment(
            context.commitment_key,
            domain="arxiv-cell-selection",
            payload=canonical_json_bytes(
                {
                    "cell_id": cell_id,
                    "total_results": totals[cell_id],
                    "starts": starts_by_cell[cell_id],
                }
            ),
        )
        for cell_id in totals
    }
    cell_record_counts = {
        cell["cell_id"]: config["records_per_cell"]
        for cell in cells
    }
    category_counts = dict(
        sorted(
            Counter(
                category
                for record in records
                for category in record["categories"]
            ).items()
        )
    )
    metrics = _metadata_metrics(records)
    metrics.update(
        {
            "cell_selection_hmac_sha256": selection_commitments,
            "cell_record_counts": cell_record_counts,
            "category_counts": category_counts,
            "ordered_identifier_hmac_sha256": _ordered_id_commitment(
                records,
                commitment_key=context.commitment_key,
            ),
        }
    )
    context.complete_group(
        group,
        payload=canonical_jsonl_bytes(records),
        metrics=metrics,
    )


def _arxiv_oai_url(endpoint: str, identifier: str, metadata_prefix: str) -> str:
    return endpoint + "?" + urlencode(
        {
            "verb": "GetRecord",
            "metadataPrefix": metadata_prefix,
            "identifier": f"oai:arXiv.org:{identifier}",
        }
    )


def _run_arxiv_enrichment(
    context: GateContext,
    fetcher: MetadataFetcher,
    *,
    window: str,
) -> None:
    group = f"arxiv-{window}-exact-enrichment"
    context.start_group(group)
    config = context.profile["arxiv"]
    allowed, forbidden = _arxiv_policy(context)
    candidates = context.candidates.get(window)
    if candidates is None or len(candidates) != config["records_per_window"]:
        raise SourceAuditError("arXiv enrichment has no complete candidate sample")
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        identifier = str(candidate["native_item_id"])
        response = context.fetch(
            fetcher,
            group=group,
            url=_arxiv_oai_url(
                config["oai_endpoint"], identifier, config["metadata_prefix"]
            ),
            host="oaipmh.arxiv.org",
            max_bytes=config["maximum_oai_response_bytes"],
            delay_family="arxiv",
            delay_seconds=float(config["delay_seconds"]),
        )
        parsed, token, diagnostics = parse_arxiv_raw_oai(
            response.payload,
            windows=context.windows,
            allowed_category_prefixes=allowed,
            forbidden_category_prefixes=forbidden,
            expected_base_identifier=identifier,
            expected_request_attributes={
                "verb": "GetRecord",
                "metadataPrefix": config["metadata_prefix"],
                "identifier": f"oai:arXiv.org:{identifier}",
            },
        )
        if token is not None or len(parsed) != 1 or diagnostics != {
            "records_seen": 1,
            "deleted_records": 0,
            "records_without_metadata": 0,
        }:
            raise SourceAuditError("arXiv exact enrichment response is incomplete")
        enriched = parsed[0]
        candidate_metadata = candidate.get("source_metadata")
        enriched_metadata = enriched.get("source_metadata")
        if (
            not isinstance(candidate_metadata, Mapping)
            or not isinstance(enriched_metadata, Mapping)
            or enriched_metadata.get("base_identifier") != identifier
            or type(candidate_metadata.get("returned_version")) is not int
            or candidate_metadata.get("returned_version")
            != enriched.get("version_count")
            or candidate.get("version_count") != enriched.get("version_count")
            or enriched.get("native_timestamp") != candidate.get("native_timestamp")
            or enriched.get("era_window") != candidate.get("era_window")
            or enriched.get("categories") != candidate.get("categories")
            or enriched_metadata.get("raw_category_count")
            != candidate_metadata.get("raw_category_count")
            or enriched_metadata.get("raw_categories_sha256")
            != candidate_metadata.get("raw_categories_sha256")
            or enriched_metadata.get("latest_version_timestamp")
            != candidate_metadata.get("updated_timestamp")
            or enriched_metadata.get("title_sha256")
            != candidate_metadata.get("title_sha256")
            or enriched_metadata.get("abstract_sha256")
            != candidate_metadata.get("abstract_sha256")
        ):
            raise SourceAuditError(
                "arXiv exact enrichment does not match its sampled candidate"
            )
        records.append(enriched)
    if len(records) != config["records_per_window"]:
        raise SourceAuditError("arXiv exact enrichment count is incomplete")
    errors = validate_source_metadata(records, source_registry=_source_registry(context))
    if errors:
        raise SourceAuditError("; ".join(errors))
    private_errors = _private_record_errors(context, group, records)
    if private_errors:
        raise SourceAuditError("; ".join(private_errors))
    context.enriched[window] = records
    metrics = _metadata_metrics(records)
    metrics["candidate_order_hmac_sha256"] = _ordered_id_commitment(
        candidates,
        commitment_key=context.commitment_key,
    )
    metrics["enriched_base_order_hmac_sha256"] = keyed_commitment(
        context.commitment_key,
        domain="ordered-source-ids",
        payload="\0".join(
            str(record["source_metadata"]["base_identifier"])
            for record in records
        ).encode("utf-8"),
    )
    if (
        metrics["candidate_order_hmac_sha256"]
        != metrics["enriched_base_order_hmac_sha256"]
    ):
        raise SourceAuditError("arXiv enrichment order does not match candidates")
    context.complete_group(
        group,
        payload=canonical_jsonl_bytes(records),
        metrics=metrics,
    )


def _pmc_url(
    endpoint: str,
    *,
    metadata_prefix: str,
    set_spec: str,
    from_date: str,
    until_date: str,
    token: str | None,
) -> str:
    if token is not None:
        parameters = {"verb": "ListRecords", "resumptionToken": token}
    else:
        parameters = {
            "verb": "ListRecords",
            "metadataPrefix": metadata_prefix,
            "from": from_date,
            "until": until_date,
            "set": set_spec,
        }
    return endpoint + "?" + urlencode(parameters)


def _run_pmc(
    context: GateContext,
    fetcher: MetadataFetcher,
    *,
    window: str,
) -> None:
    group = f"pmc-{window}-range-metadata"
    context.start_group(group)
    config = context.profile["pmc"]
    date_range = config[f"{window}_range"]
    records: list[dict[str, Any]] = []
    diagnostics: Counter[str] = Counter()
    upstream_seen = 0
    token: str | None = None
    seen_tokens: set[str] = set()
    seen_header_identifiers: set[str] = set()
    termination: str | None = None
    for _ in range(config["maximum_requests_per_range"]):
        expected_request_attributes = (
            {"verb": "ListRecords", "resumptionToken": token}
            if token is not None
            else {
                "verb": "ListRecords",
                "metadataPrefix": config["metadata_prefix"],
                "from": date_range["from_date"],
                "until": date_range["until_date"],
                "set": config["set_spec"],
            }
        )
        response = context.fetch(
            fetcher,
            group=group,
            url=_pmc_url(
                config["endpoint"],
                metadata_prefix=config["metadata_prefix"],
                set_spec=config["set_spec"],
                from_date=date_range["from_date"],
                until_date=date_range["until_date"],
                token=token,
            ),
            host="pmc.ncbi.nlm.nih.gov",
            max_bytes=config["maximum_response_bytes"],
            delay_family="pmc",
            delay_seconds=float(config["delay_seconds"]),
        )
        parsed, next_token, page_diagnostics = parse_pmc_oai_dc(
            response.payload,
            windows=context.windows,
            allowed_subject_terms=tuple(config["allowed_subject_terms"]),
            expected_from_date=date.fromisoformat(date_range["from_date"]),
            expected_until_date=date.fromisoformat(date_range["until_date"]),
            seen_header_identifiers=seen_header_identifiers,
            expected_request_attributes=expected_request_attributes,
        )
        if next_token is not None and (
            len(next_token.encode("utf-8"))
            > config["maximum_resumption_token_bytes"]
            or any(
                ord(character) < 0x21 or ord(character) > 0x7E
                for character in next_token
            )
        ):
            raise SourceAuditError("PMC resumption token is not bounded canonical ASCII")
        page_seen = page_diagnostics.get("records_seen")
        if type(page_seen) is not int or page_seen < 0:
            raise SourceAuditError("PMC parser did not report upstream records seen")
        upstream_seen += page_seen
        if upstream_seen > config["maximum_upstream_records_per_range"]:
            raise SourceAuditError("PMC response exceeded the upstream-record cap")
        diagnostics.update(page_diagnostics)
        records.extend(parsed)
        if next_token is not None:
            if next_token in seen_tokens:
                raise SourceAuditError("PMC resumption token repeated")
            seen_tokens.add(next_token)
        if upstream_seen == config["maximum_upstream_records_per_range"]:
            termination = "upstream-record-cap"
            token = next_token
            break
        if next_token is None:
            termination = "natural-endpoint"
            token = None
            break
        token = next_token
    if termination is None:
        raise SourceAuditError("PMC request cap ended before its record cap or endpoint")
    if records:
        errors = validate_source_metadata(
            records,
            source_registry=_source_registry(context),
        )
        if errors:
            raise SourceAuditError("; ".join(errors))
    private_errors = _private_record_errors(context, group, records)
    if private_errors:
        raise SourceAuditError("; ".join(private_errors))
    record_ids = [str(record["record_id"]) for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise SourceAuditError("PMC metadata contains duplicate records")
    metrics = _metadata_metrics(records)
    metrics.update(
        {
            "upstream_records_seen": upstream_seen,
            "parser_diagnostics": dict(sorted(diagnostics.items())),
            "termination": termination,
            "resumption_token_remaining": token is not None,
            "date_semantics": config["date_semantics"],
            "era_and_version_status": config["era_and_version_status"],
        }
    )
    context.complete_group(
        group,
        payload=canonical_jsonl_bytes(records, allow_empty=True),
        metrics=metrics,
    )


def _reason_code(error: BaseException) -> str:
    if isinstance(error, SourceAuditError):
        return "contract-validation-failed"
    if isinstance(error, MetadataTransportError):
        return "metadata-transport-failed"
    if isinstance(error, (ArxivApiError, ArxivMetadataError, PmcMetadataError)):
        return "metadata-parse-failed"
    if isinstance(error, (WikimediaInventoryError, StackExchangeInventoryError)):
        return "inventory-parse-failed"
    if isinstance(error, KeyboardInterrupt):
        return "execution-interrupted"
    return "unexpected-execution-failure"


def run_gate(
    bound: BoundSourceInputs,
    reservation: SourceOutputReservation,
    fetcher: MetadataFetcher,
    *,
    commitment_key: bytes,
    context: GateContext | None = None,
) -> GateContext:
    """Run all eight groups once in their frozen order."""

    profile = bound.values["metadata_gate_profile"]
    if context is None:
        context = GateContext(
            bound=bound,
            reservation=reservation,
            profile=profile,
            windows=parse_era_windows(bound.values["source_registry"]),
            commitment_key=commitment_key,
        )
    elif (
        context.bound != bound
        or context.reservation is not reservation
        or context.commitment_key != commitment_key
    ):
        raise SourceAuditError("source gate context does not match its bound run")
    dispatch: dict[str, Callable[[], None]] = {
        "wikimedia-inventory": lambda: _run_wikimedia(context, fetcher),
        "stackexchange-inventory": lambda: _run_stackexchange(context, fetcher),
        "arxiv-early-candidate-sample": lambda: _run_arxiv_candidates(
            context, fetcher, window="early"
        ),
        "arxiv-early-exact-enrichment": lambda: _run_arxiv_enrichment(
            context, fetcher, window="early"
        ),
        "arxiv-late-candidate-sample": lambda: _run_arxiv_candidates(
            context, fetcher, window="late"
        ),
        "arxiv-late-exact-enrichment": lambda: _run_arxiv_enrichment(
            context, fetcher, window="late"
        ),
        "pmc-early-range-metadata": lambda: _run_pmc(
            context, fetcher, window="early"
        ),
        "pmc-late-range-metadata": lambda: _run_pmc(
            context, fetcher, window="late"
        ),
    }
    for group in GROUP_ORDER:
        attempts_before = context.request_attempt_count
        try:
            dispatch[group]()
        except BaseException as error:
            context.fail_group(group)
            raise SourceGateError(
                group=group,
                stage="group-execution",
                reason_code=_reason_code(error),
                request_ordinal=(
                    context.request_attempt_count - 1
                    if context.request_attempt_count > attempts_before
                    else None
                ),
                detail=error,
                context=context,
            ) from error
    return context


def _base_evidence(context: GateContext) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "profile_id": context.profile["profile_id"],
        "claim_ceiling": context.profile["claim_ceiling"],
        "execution": {
            "mode": "execute",
            "profile_path": PROFILE_RELATIVE_PATH,
            "network_access_permitted": True,
            "private_output_mode": "ignored-create-only-with-outside-git-backup",
        },
        "git": {
            "head": context.bound.head,
            "worktree_clean": True,
            "inputs": context.bound.bindings,
        },
        "runtime": {
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
        "privacy": {
            "commitment_algorithm": "hmac-sha256",
            "commitment_key_sha256": context.profile["privacy"][
                "commitment_key_sha256"
            ],
            "native_source_c_identifiers_public": False,
            "raw_source_c_locators_public": False,
            "exact_source_c_lengths_public": False,
        },
        "network": {
            "access_permitted": True,
            "observation": context.profile["network"]["observation"],
            "method": context.profile["network"]["method"],
            "serial": True,
            "redirect_policy": context.profile["network"]["redirect_policy"],
            "proxy_policy": context.profile["network"]["proxy_policy"],
            "request_attempt_count": context.request_attempt_count,
            "completed_response_count": context.completed_response_count,
            "maximum_happy_path_requests": context.profile["network"][
                "maximum_happy_path_requests"
            ],
            "retry_count": 0,
        },
        "groups": context.groups,
        "private_artifacts": context.artifacts,
        "boundaries": dict(_BOUNDARIES),
    }


def success_aggregate(context: GateContext) -> dict[str, Any]:
    if any(group["status"] != "complete" for group in context.groups):
        raise SourceAuditError("cannot aggregate an incomplete source gate")
    value = {
        **_base_evidence(context),
        "artifact_type": "source-metadata-qualification-aggregate",
        "status": "complete",
    }
    value["output_sha256"] = canonical_json_sha256(value)
    return value


def success_receipt(
    context: GateContext,
    *,
    aggregate_payload: bytes,
    final_binding_status: str,
) -> dict[str, Any]:
    value = {
        **_base_evidence(context),
        "receipt_type": context.profile["publication"]["success_receipt_type"],
        "status": "success",
        "final_binding_status": final_binding_status,
        "aggregate": {
            "file_name": context.profile["publication"]["aggregate_file"],
            "size_bytes": len(aggregate_payload),
            "sha256": hashlib.sha256(aggregate_payload).hexdigest(),
        },
        "valid_aggregate_published": True,
    }
    return _receipt_with_hmac(context.commitment_key, value)


def failure_receipt(
    context: GateContext,
    failure: SourceGateError,
    *,
    final_binding_status: str,
) -> dict[str, Any]:
    value = {
        **_base_evidence(context),
        "receipt_type": context.profile["publication"]["failure_receipt_type"],
        "status": "failed",
        "failure": {
            "group": failure.group,
            "stage": failure.stage,
            "reason_code": failure.reason_code,
            "failure_subtype": failure.failure_subtype,
            "transport_subtype": failure.transport_subtype,
            "request_ordinal": failure.request_ordinal,
            "detail_hmac_sha256": failure.detail_hmac_sha256,
        },
        "final_binding_status": final_binding_status,
        "valid_aggregate_published": False,
    }
    return _receipt_with_hmac(context.commitment_key, value)


def _receipt_hmac_payload(value: Mapping[str, Any]) -> bytes:
    payload = {
        key: nested
        for key, nested in value.items()
        if key not in {"receipt_hmac_sha256", "receipt_sha256"}
    }
    return canonical_json_bytes(payload)


def _receipt_with_hmac(
    commitment_key: bytes,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    receipt = dict(value)
    receipt["receipt_hmac_sha256"] = keyed_commitment(
        commitment_key,
        domain="source-receipt",
        payload=_receipt_hmac_payload(receipt),
    )
    return receipt_with_self_hash(receipt)


def _is_hex(value: Any, pattern: re.Pattern[str]) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _is_int(value: Any, *, minimum: int = 0, maximum: int | None = None) -> bool:
    return (
        type(value) is int
        and value >= minimum
        and (maximum is None or value <= maximum)
    )


def _exact_mapping(value: Any, keys: set[str]) -> bool:
    return isinstance(value, Mapping) and set(value) == keys


def _binding_errors(value: Any) -> list[str]:
    errors: list[str] = []
    expected_labels = {
        "git_head",
        "worktree_clean",
        "metadata_gate_profile",
        *_CANONICAL_INPUT_BINDINGS,
        *(f"runtime_{index:02d}" for index in range(len(RUNTIME_RELATIVE_PATHS))),
    }
    if not _exact_mapping(value, expected_labels):
        return ["source evidence input binding fields are not exact"]
    if not _is_hex(value.get("git_head"), _HEX40):
        errors.append("source evidence bound Git head is invalid")
    if value.get("worktree_clean") is not True:
        errors.append("source evidence does not bind a clean worktree")

    expected_records: list[tuple[str, str, str, str | None]] = [
        (
            "metadata_gate_profile",
            PROFILE_RELATIVE_PATH,
            "canonical-json",
            FROZEN_PROFILE_GIT_BLOB,
        ),
        *(
            (label, path, "canonical-json", git_blob)
            for label, (path, git_blob) in _CANONICAL_INPUT_BINDINGS.items()
        ),
        *(
            (f"runtime_{index:02d}", path, "python-runtime", None)
            for index, path in enumerate(RUNTIME_RELATIVE_PATHS)
        ),
    ]
    for label, path, kind, frozen_blob in expected_records:
        record = value.get(label)
        expected_keys = {"path", "git_blob", "raw_sha256", "kind"}
        if kind == "canonical-json":
            expected_keys.add("canonical_sha256")
        if not _exact_mapping(record, expected_keys):
            errors.append(f"source evidence binding is malformed: {label}")
            continue
        if record.get("path") != path or record.get("kind") != kind:
            errors.append(f"source evidence binding identity drifted: {label}")
        if not _is_hex(record.get("git_blob"), _HEX40) or not _is_hex(
            record.get("raw_sha256"), _HEX64
        ):
            errors.append(f"source evidence binding hash is invalid: {label}")
        if frozen_blob is not None and record.get("git_blob") != frozen_blob:
            errors.append(f"source evidence canonical Git blob drifted: {label}")
        if kind == "canonical-json" and not _is_hex(
            record.get("canonical_sha256"), _HEX64
        ):
            errors.append(f"source evidence canonical hash is invalid: {label}")
        if label == "metadata_gate_profile" and record.get(
            "canonical_sha256"
        ) != FROZEN_PROFILE_CANONICAL_SHA256:
            errors.append("source evidence profile identity is not frozen")
    return errors


def _git_errors(value: Any) -> list[str]:
    if not _exact_mapping(value, {"head", "worktree_clean", "inputs"}):
        return ["source evidence Git fields are not exact"]
    errors = _binding_errors(value.get("inputs"))
    if not _is_hex(value.get("head"), _HEX40):
        errors.append("source evidence Git head is invalid")
    if value.get("worktree_clean") is not True:
        errors.append("source evidence Git state is not clean")
    inputs = value.get("inputs")
    if isinstance(inputs, Mapping) and inputs.get("git_head") != value.get("head"):
        errors.append("source evidence Git heads do not match")
    return errors


def _counter_errors(
    value: Any,
    *,
    total: int,
    label: str,
    allowed_keys: frozenset[str],
) -> list[str]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str)
        or not key
        or key not in allowed_keys
        or not _is_int(count, minimum=1)
        for key, count in value.items()
    ):
        return [f"{label} is not an exact non-negative count map"]
    if sum(value.values()) != total:
        return [f"{label} does not sum to its record count"]
    return []


def _artifact_errors(value: Any, *, file_name: str) -> list[str]:
    if not _exact_mapping(
        value,
        {"file_name", "size_bytes", "hmac_sha256", "backup_verified"},
    ):
        return [f"source private artifact is malformed: {file_name}"]
    errors: list[str] = []
    if value.get("file_name") != file_name:
        errors.append(f"source private artifact name drifted: {file_name}")
    private_c_family = file_name.startswith("arxiv-") or file_name.startswith("pmc-")
    if private_c_family and value.get("size_bytes") is not None:
        errors.append(f"source private artifact size was disclosed: {file_name}")
    elif not private_c_family and not _is_int(value.get("size_bytes")):
        errors.append(f"source private artifact size is invalid: {file_name}")
    if not _is_hex(value.get("hmac_sha256"), _HEX64):
        errors.append(f"source private artifact commitment is invalid: {file_name}")
    if value.get("backup_verified") is not True:
        errors.append(f"source private artifact backup is unverified: {file_name}")
    return errors


def _response_errors(value: Any, *, group: str, ordinal: int) -> list[str]:
    common = {
        "group",
        "ordinal",
        "status",
        "content_type_sha256",
        "byte_count",
    }
    public_endpoints = {
        "wikimedia-inventory": (
            "https://dumps.wikimedia.org/enwiki/20260801/dumpstatus.json",
            20_000_000,
        ),
        "stackexchange-inventory": (
            "https://archive.org/metadata/stackexchange",
            30_000_000,
        ),
    }
    expected_keys = common | (
        {"response_sha256", "requested_endpoint", "final_endpoint"}
        if group in public_endpoints
        else {
            "response_hmac_sha256",
            "requested_url_hmac_sha256",
            "final_url_hmac_sha256",
        }
    )
    if not _exact_mapping(value, expected_keys):
        return [f"source response identity is malformed at ordinal {ordinal}"]
    errors: list[str] = []
    if (
        value.get("group") != group
        or not _is_int(value.get("ordinal"))
        or value.get("ordinal") != ordinal
    ):
        errors.append(f"source response order drifted at ordinal {ordinal}")
    if type(value.get("status")) is not int or value.get("status") != 200:
        errors.append(f"source response status is invalid at ordinal {ordinal}")
    content_type = value.get("content_type_sha256")
    if content_type is not None and not _is_hex(content_type, _HEX64):
        errors.append(f"source response content-type hash is invalid at ordinal {ordinal}")
    if group in public_endpoints:
        endpoint, maximum_bytes = public_endpoints[group]
        if not _is_int(value.get("byte_count"), minimum=1, maximum=maximum_bytes):
            errors.append(f"source response byte identity is invalid at ordinal {ordinal}")
        if value.get("requested_endpoint") != endpoint or value.get(
            "final_endpoint"
        ) != endpoint:
            errors.append(f"source endpoint identity drifted at ordinal {ordinal}")
        if not _is_hex(value.get("response_sha256"), _HEX64):
            errors.append(f"source response hash is invalid at ordinal {ordinal}")
    else:
        if value.get("byte_count") is not None:
            errors.append(f"source private response length was disclosed at ordinal {ordinal}")
        requested = value.get("requested_url_hmac_sha256")
        final = value.get("final_url_hmac_sha256")
        if (
            not _is_hex(value.get("response_hmac_sha256"), _HEX64)
            or not _is_hex(requested, _HEX64)
            or final != requested
        ):
            errors.append(f"source private URL identity drifted at ordinal {ordinal}")
    return errors


def _metadata_metric_errors(value: Mapping[str, Any], *, label: str) -> list[str]:
    errors: list[str] = []
    total = value.get("record_count")
    if not _is_int(total):
        return [f"{label} record count is invalid"]
    for field in (
        "eligibility_counts",
        "rights_status_counts",
        "license_id_counts",
        "version_status_counts",
    ):
        errors.extend(
            _counter_errors(
                value.get(field),
                total=total,
                label=f"{label} {field}",
                allowed_keys=_COUNTER_VOCABULARIES[field],
            )
        )
    return errors


def _expected_rights_counts(license_counts: Mapping[str, int]) -> dict[str, int]:
    result: Counter[str] = Counter()
    for license_id, count in license_counts.items():
        if license_id.startswith("CC0-") or license_id.startswith("CC-BY-"):
            result["eligible"] += count
        elif license_id in {"creative-commons-other", "arXiv-default"}:
            result["ineligible"] += count
        elif license_id in {"custom-or-unresolved", "missing"}:
            result["unresolved"] += count
    return dict(sorted(result.items()))


def _group_metric_errors(group: str, value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"source group metrics are missing: {group}"]
    errors: list[str] = []
    if group in {"wikimedia-inventory", "stackexchange-inventory"}:
        extra = (
            {"snapshot"}
            if group == "wikimedia-inventory"
            else {"company_attribution_verified", "delivery_status"}
        )
        expected = {
            "file_count",
            "total_size_bytes",
            "minimum_free_space_bytes_with_25_percent_margin",
            "hash_algorithm_counts",
            *extra,
        }
        if set(value) != expected:
            return [f"source inventory metrics are not exact: {group}"]
        count = value.get("file_count")
        total = value.get("total_size_bytes")
        margin = value.get("minimum_free_space_bytes_with_25_percent_margin")
        hashes = value.get("hash_algorithm_counts")
        if not _is_int(count, minimum=1) or not _is_int(total, minimum=1):
            errors.append(f"source inventory totals are invalid: {group}")
        if _is_int(total, minimum=1) and margin != (total * 5 + 3) // 4:
            errors.append(f"source inventory storage margin is invalid: {group}")
        if not isinstance(hashes, Mapping) or any(
            not isinstance(name, str)
            or not name
            or name not in {"md5", "sha1"}
            or not _is_int(number, minimum=1)
            for name, number in hashes.items()
        ):
            errors.append(f"source inventory hash counts are invalid: {group}")
        elif not hashes or sum(hashes.values()) < count or any(
            number > count for number in hashes.values()
        ):
            errors.append(f"source inventory hash coverage is incomplete: {group}")
        if group == "wikimedia-inventory" and value.get("snapshot") != "20260801":
            errors.append("Wikimedia snapshot evidence drifted")
        if group == "stackexchange-inventory" and (
            value.get("company_attribution_verified") is not True
            or value.get("delivery_status")
            != "legacy-archive-not-current-official-delivery"
        ):
            errors.append("Stack Exchange attribution evidence drifted")
        return errors

    common = {
        "record_count",
        "eligibility_counts",
        "rights_status_counts",
        "license_id_counts",
        "version_status_counts",
    }
    if group.endswith("candidate-sample"):
        if set(value) != common | {
            "cell_selection_hmac_sha256",
            "cell_record_counts",
            "category_counts",
            "ordered_identifier_hmac_sha256",
        }:
            return [f"arXiv candidate metrics are not exact: {group}"]
        errors.extend(_metadata_metric_errors(value, label=group))
        if value.get("record_count") != 100:
            errors.append(f"arXiv candidate count is incomplete: {group}")
        if (
            value.get("eligibility_counts") != {"unresolved": 100}
            or value.get("rights_status_counts") != {"unresolved": 100}
            or value.get("license_id_counts")
            != {"pending-arXivRaw-enrichment": 100}
            or value.get("version_status_counts") != {"unresolved": 100}
        ):
            errors.append(f"arXiv candidate status evidence drifted: {group}")
        window = "early" if "-early-" in group else "late"
        cell_ids = {
            "early": ("2012-h1", "2012-h2", "2013-h1", "2013-h2"),
            "late": ("2018-h1", "2018-h2", "2019-h1", "2019-h2"),
        }[window]
        selections = value.get("cell_selection_hmac_sha256")
        if not _exact_mapping(selections, set(cell_ids)) or any(
            not _is_hex(commitment, _HEX64)
            for commitment in selections.values()
        ):
            errors.append(f"arXiv cell evidence is incomplete: {group}")
        cell_counts = value.get("cell_record_counts")
        if not _exact_mapping(cell_counts, set(cell_ids)) or any(
            type(count) is not int or count != 25
            for count in cell_counts.values()
        ):
            errors.append(f"arXiv cell record counts are incomplete: {group}")
        category_counts = value.get("category_counts")
        if (
            not isinstance(category_counts, Mapping)
            or not category_counts
            or any(
                not isinstance(category, str)
                or category not in FROZEN_ARXIV_PERSISTED_CATEGORIES
                or not _is_int(count, minimum=1)
                for category, count in category_counts.items()
            )
            or sum(category_counts.values()) < 100
            or sum(
                count
                for category, count in category_counts.items()
                if category
                in FROZEN_ARXIV_PERSISTED_CATEGORIES
                - {"other-arxiv-category", "forbidden-arxiv-category"}
            )
            < 100
        ):
            errors.append(f"arXiv category coverage is invalid: {group}")
        if not _is_hex(value.get("ordered_identifier_hmac_sha256"), _HEX64):
            errors.append(f"arXiv ordered identifier commitment is invalid: {group}")
        return errors

    if group.endswith("exact-enrichment"):
        if set(value) != common | {
            "candidate_order_hmac_sha256",
            "enriched_base_order_hmac_sha256",
        }:
            return [f"arXiv enrichment metrics are not exact: {group}"]
        errors.extend(_metadata_metric_errors(value, label=group))
        if value.get("record_count") != 100:
            errors.append(f"arXiv enrichment count is incomplete: {group}")
        candidate_hash = value.get("candidate_order_hmac_sha256")
        if not _is_hex(candidate_hash, _HEX64) or value.get(
            "enriched_base_order_hmac_sha256"
        ) != candidate_hash:
            errors.append(f"arXiv enrichment order evidence drifted: {group}")
        license_counts = value.get("license_id_counts")
        eligibility_counts = value.get("eligibility_counts")
        version_counts = value.get("version_status_counts")
        rights_counts = value.get("rights_status_counts")
        if (
            not isinstance(license_counts, Mapping)
            or not isinstance(eligibility_counts, Mapping)
            or not isinstance(version_counts, Mapping)
            or not isinstance(rights_counts, Mapping)
            or "pending-arXivRaw-enrichment" in license_counts
            or set(eligibility_counts) - {"eligible", "excluded"}
            or set(version_counts) - {"single-version", "latest-only"}
            or set(rights_counts) - {"eligible", "ineligible", "unresolved"}
            or rights_counts != _expected_rights_counts(license_counts)
        ):
            errors.append(f"arXiv enrichment status evidence drifted: {group}")
        elif eligibility_counts.get("eligible", 0) > min(
            rights_counts.get("eligible", 0),
            version_counts.get("single-version", 0),
        ):
            errors.append(f"arXiv eligible yield exceeds its prerequisites: {group}")
        return errors

    expected = common | {
        "upstream_records_seen",
        "parser_diagnostics",
        "termination",
        "resumption_token_remaining",
        "date_semantics",
        "era_and_version_status",
    }
    if set(value) != expected:
        return [f"PMC metrics are not exact: {group}"]
    errors.extend(_metadata_metric_errors(value, label=group))
    upstream = value.get("upstream_records_seen")
    record_count = value.get("record_count")
    expected_unresolved = {} if record_count == 0 else {"unresolved": record_count}
    if (
        value.get("eligibility_counts") != expected_unresolved
        or value.get("version_status_counts") != expected_unresolved
    ):
        errors.append(f"PMC unresolved-status evidence drifted: {group}")
    license_counts = value.get("license_id_counts")
    if (
        not isinstance(license_counts, Mapping)
        or set(license_counts) & {"pending-arXivRaw-enrichment", "arXiv-default"}
        or value.get("rights_status_counts") != _expected_rights_counts(license_counts)
    ):
        errors.append(f"PMC rights/license evidence drifted: {group}")
    diagnostics = value.get("parser_diagnostics")
    if not _is_int(upstream, maximum=100) or not _exact_mapping(
        diagnostics,
        {
            "records_seen",
            "deleted_records",
            "records_without_metadata",
            "skipped_missing_lifecycle_date",
        },
    ) or any(not _is_int(number) for number in diagnostics.values()):
        errors.append(f"PMC parser diagnostics are invalid: {group}")
    else:
        dropped = sum(
            diagnostics[field]
            for field in (
                "deleted_records",
                "records_without_metadata",
                "skipped_missing_lifecycle_date",
            )
        )
        if diagnostics["records_seen"] != upstream or value.get(
            "record_count"
        ) != upstream - dropped:
            errors.append(f"PMC parser count arithmetic is invalid: {group}")
    termination = value.get("termination")
    remaining = value.get("resumption_token_remaining")
    if termination == "upstream-record-cap":
        if upstream != 100 or type(remaining) is not bool:
            errors.append(f"PMC cap termination evidence is invalid: {group}")
    elif termination == "natural-endpoint":
        if not _is_int(upstream, maximum=99) or remaining is not False:
            errors.append(f"PMC endpoint termination evidence is invalid: {group}")
    else:
        errors.append(f"PMC termination is invalid: {group}")
    if value.get("date_semantics") != "release-or-update-datestamp-not-publication-date":
        errors.append(f"PMC date-semantics claim drifted: {group}")
    if value.get("era_and_version_status") != "unresolved":
        errors.append(f"PMC era/version claim drifted: {group}")
    return errors


def _evidence_errors(
    value: Mapping[str, Any],
    *,
    status: str,
    failure: Mapping[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1:
        errors.append("source evidence schema version is invalid")
    if value.get("profile_id") != "live-source-metadata-qualification-v0":
        errors.append("source evidence profile is invalid")
    if value.get("claim_ceiling") != _CLAIM_CEILING:
        errors.append("source evidence claim ceiling drifted")
    if value.get("execution") != {
        "mode": "execute",
        "profile_path": PROFILE_RELATIVE_PATH,
        "network_access_permitted": True,
        "private_output_mode": "ignored-create-only-with-outside-git-backup",
    }:
        errors.append("source evidence execution contract drifted")
    if value.get("privacy") != {
        "commitment_algorithm": "hmac-sha256",
        "commitment_key_sha256": _COMMITMENT_KEY_SHA256,
        "native_source_c_identifiers_public": False,
        "raw_source_c_locators_public": False,
        "exact_source_c_lengths_public": False,
    }:
        errors.append("source evidence privacy commitment drifted")
    errors.extend(_git_errors(value.get("git")))
    runtime = value.get("runtime")
    if not _exact_mapping(runtime, {"python_implementation", "python_version"}):
        errors.append("source evidence runtime fields are not exact")
    else:
        version = runtime.get("python_version")
        version_match = (
            re.fullmatch(r"(\d+)\.(\d+)\.\d+(?:[A-Za-z0-9.+-]*)?", version)
            if isinstance(version, str)
            else None
        )
        if (
            not isinstance(runtime.get("python_implementation"), str)
            or re.fullmatch(r"[A-Za-z0-9_-]+", runtime["python_implementation"])
            is None
            or version_match is None
            or (int(version_match.group(1)), int(version_match.group(2))) < (3, 11)
        ):
            errors.append("source evidence runtime identity is invalid")
    if value.get("boundaries") != _BOUNDARIES:
        errors.append("source evidence boundary claims drifted")

    groups = value.get("groups")
    if not isinstance(groups, list) or len(groups) != len(GROUP_ORDER):
        return errors + ["source evidence group list is incomplete"]
    attempts_total = 0
    responses_total = 0
    flattened_responses: list[tuple[str, Mapping[str, Any]]] = []
    expected_artifacts: list[Mapping[str, Any]] = []
    complete_metrics: dict[str, Mapping[str, Any]] = {}
    limits = {
        "wikimedia-inventory": 1,
        "stackexchange-inventory": 1,
        "arxiv-early-candidate-sample": 24,
        "arxiv-early-exact-enrichment": 100,
        "arxiv-late-candidate-sample": 24,
        "arxiv-late-exact-enrichment": 100,
        "pmc-early-range-metadata": 10,
        "pmc-late-range-metadata": 10,
    }
    statuses: list[str | None] = []
    for group_id, group in zip(GROUP_ORDER, groups, strict=True):
        if not _exact_mapping(
            group,
            {
                "group_id",
                "status",
                "request_attempt_count",
                "completed_response_count",
                "responses",
                "private_artifact",
                "metrics",
            },
        ):
            errors.append(f"source group fields are not exact: {group_id}")
            statuses.append(None)
            continue
        if group.get("group_id") != group_id:
            errors.append(f"source group order drifted: {group_id}")
        group_status = group.get("status")
        statuses.append(group_status if isinstance(group_status, str) else None)
        attempts = group.get("request_attempt_count")
        completed = group.get("completed_response_count")
        responses = group.get("responses")
        if not _is_int(attempts, maximum=limits[group_id]) or not _is_int(
            completed, maximum=limits[group_id]
        ) or completed > attempts or attempts - completed > 1:
            errors.append(f"source group request counts are invalid: {group_id}")
            attempts = 0
            completed = 0
        attempts_total += attempts
        responses_total += completed
        if not isinstance(responses, list) or len(responses) != completed:
            errors.append(f"source group response count is invalid: {group_id}")
        else:
            flattened_responses.extend((group_id, response) for response in responses)
        artifact = group.get("private_artifact")
        metrics = group.get("metrics")
        if group_status == "complete":
            if attempts != completed:
                errors.append(
                    f"complete source group has an incomplete response: {group_id}"
                )
            if group_id in {
                "wikimedia-inventory",
                "stackexchange-inventory",
                "arxiv-early-candidate-sample",
                "arxiv-early-exact-enrichment",
                "arxiv-late-candidate-sample",
                "arxiv-late-exact-enrichment",
            } and attempts != limits[group_id]:
                errors.append(f"source group request count is incomplete: {group_id}")
            if group_id.startswith("pmc-") and not _is_int(attempts, minimum=1, maximum=10):
                errors.append(f"PMC request count is incomplete: {group_id}")
            errors.extend(_artifact_errors(artifact, file_name=_PRIVATE_FILES[group_id]))
            if isinstance(artifact, Mapping):
                expected_artifacts.append(artifact)
            errors.extend(_group_metric_errors(group_id, metrics))
            if isinstance(metrics, Mapping):
                complete_metrics[group_id] = metrics
            if isinstance(artifact, Mapping) and isinstance(metrics, Mapping):
                artifact_size = artifact.get("size_bytes")
                record_count = metrics.get(
                    "record_count",
                    metrics.get("file_count"),
                )
                if group_id.startswith("arxiv-") or group_id.startswith("pmc-"):
                    if artifact_size is not None:
                        errors.append(
                            f"private source artifact length was disclosed: {group_id}"
                        )
                elif not _is_int(artifact_size, minimum=1):
                    errors.append(
                        f"completed source artifact is empty: {group_id}"
                    )
        elif group_status in {"failed", "not-started"}:
            if artifact is not None or metrics is not None:
                errors.append(f"incomplete source group retained an artifact: {group_id}")
            if group_status == "not-started" and (
                attempts != 0 or completed != 0 or responses != []
            ):
                errors.append(f"not-started source group contains execution evidence: {group_id}")
        else:
            errors.append(f"source group status is invalid: {group_id}")

    for ordinal, (group_id, response) in enumerate(flattened_responses):
        errors.extend(_response_errors(response, group=group_id, ordinal=ordinal))
    private_url_commitments = [
        response.get("requested_url_hmac_sha256")
        for group_id, response in flattened_responses
        if group_id not in {"wikimedia-inventory", "stackexchange-inventory"}
        and isinstance(response, Mapping)
        and isinstance(response.get("requested_url_hmac_sha256"), str)
    ]
    if len(private_url_commitments) != len(set(private_url_commitments)):
        errors.append("private source request commitments are not unique")
    private_response_commitments = [
        response.get("response_hmac_sha256")
        for group_id, response in flattened_responses
        if group_id not in {"wikimedia-inventory", "stackexchange-inventory"}
        and isinstance(response, Mapping)
        and isinstance(response.get("response_hmac_sha256"), str)
    ]
    if len(private_response_commitments) != len(
        set(private_response_commitments)
    ):
        errors.append("private source response commitments are not unique")
    private_artifacts = value.get("private_artifacts")
    if not isinstance(private_artifacts, list) or private_artifacts != expected_artifacts:
        errors.append("source private artifact index does not match completed groups")
    for window in ("early", "late"):
        candidates = complete_metrics.get(f"arxiv-{window}-candidate-sample")
        enrichment = complete_metrics.get(f"arxiv-{window}-exact-enrichment")
        if candidates is not None and enrichment is not None and candidates.get(
            "ordered_identifier_hmac_sha256"
        ) != enrichment.get("candidate_order_hmac_sha256"):
            errors.append(f"arXiv {window} candidate/enrichment commitments differ")
    candidate_metrics = [
        complete_metrics.get("arxiv-early-candidate-sample"),
        complete_metrics.get("arxiv-late-candidate-sample"),
    ]
    cell_commitments = [
        commitment
        for metrics in candidate_metrics
        if isinstance(metrics, Mapping)
        for commitment in (
            metrics.get("cell_selection_hmac_sha256", {}).values()
            if isinstance(metrics.get("cell_selection_hmac_sha256"), Mapping)
            else ()
        )
        if isinstance(commitment, str)
    ]
    if len(cell_commitments) != len(set(cell_commitments)):
        errors.append("arXiv cell-selection commitments are not unique")
    if all(isinstance(metrics, Mapping) for metrics in candidate_metrics) and (
        candidate_metrics[0].get("ordered_identifier_hmac_sha256")
        == candidate_metrics[1].get("ordered_identifier_hmac_sha256")
    ):
        errors.append("arXiv early and late identifier commitments are identical")

    network = value.get("network")
    if not _exact_mapping(
        network,
        {
            "access_permitted",
            "observation",
            "method",
            "serial",
            "redirect_policy",
            "proxy_policy",
            "request_attempt_count",
            "completed_response_count",
            "maximum_happy_path_requests",
            "retry_count",
        },
    ):
        errors.append("source network evidence fields are not exact")
    else:
        if (
            network.get("access_permitted") is not True
            or network.get("observation") != "not-instrumented"
            or network.get("method") != "GET"
            or network.get("serial") is not True
            or network.get("redirect_policy") != "reject"
            or network.get("proxy_policy") != "direct-no-proxy"
            or network.get("maximum_happy_path_requests") != 270
            or type(network.get("maximum_happy_path_requests")) is not int
            or network.get("retry_count") != 0
            or type(network.get("retry_count")) is not int
            or not _is_int(network.get("request_attempt_count"), maximum=270)
            or not _is_int(network.get("completed_response_count"), maximum=270)
            or network.get("request_attempt_count") != attempts_total
            or network.get("completed_response_count") != responses_total
        ):
            errors.append("source network evidence is internally inconsistent")
    if attempts_total > 270 or responses_total > attempts_total or attempts_total - responses_total > 1:
        errors.append("source evidence exceeds its request contract")

    if status == "complete":
        if statuses != ["complete"] * len(GROUP_ORDER):
            errors.append("successful source evidence has incomplete groups")
        if attempts_total != responses_total or not 252 <= attempts_total <= 270:
            errors.append("successful source evidence request total is invalid")
    elif status == "failed":
        failure_group = failure.get("group") if isinstance(failure, Mapping) else None
        failure_stage = failure.get("stage") if isinstance(failure, Mapping) else None
        failure_reason = (
            failure.get("reason_code") if isinstance(failure, Mapping) else None
        )
        failure_ordinal = (
            failure.get("request_ordinal") if isinstance(failure, Mapping) else None
        )
        if failure_group in GROUP_ORDER:
            index = GROUP_ORDER.index(failure_group)
            expected_statuses = ["complete"] * index + ["failed"] + [
                "not-started"
            ] * (len(GROUP_ORDER) - index - 1)
            if statuses != expected_statuses:
                errors.append("failed source evidence group prefix is inconsistent")
            failed_group = groups[index]
            failed_attempts = failed_group.get("request_attempt_count")
            allowed_subtypes = (
                _INVENTORY_GROUP_FAILURE_SUBTYPES
                if failure_group
                in {"wikimedia-inventory", "stackexchange-inventory"}
                else _METADATA_GROUP_FAILURE_SUBTYPES
            )
            allowed_reasons = {
                f"{subtype}-failed" for subtype in allowed_subtypes
            } | set(_GROUP_SPECIAL_FAILURE_REASONS)
            expected_failure_ordinal = (
                attempts_total - 1
                if _is_int(failed_attempts, minimum=1)
                else None
            )
            if (
                failure_stage != "group-execution"
                or failure_reason
                not in allowed_reasons
                or failure_ordinal != expected_failure_ordinal
                or (
                    failure_reason
                    not in _GROUP_SPECIAL_FAILURE_REASONS
                    and (
                        not _is_int(failed_attempts)
                        or (
                            _is_int(failed_attempts, minimum=1)
                            and failed_group.get("completed_response_count")
                            != failed_attempts
                        )
                    )
                )
                or (
                    failure_reason == "metadata-transport-failed"
                    and failed_attempts
                    != failed_group.get("completed_response_count", 0) + 1
                )
            ):
                errors.append("failed source group phase evidence is inconsistent")
        elif failure_group == "preflight":
            if statuses != ["not-started"] * len(GROUP_ORDER):
                errors.append("preflight failure contains started source groups")
            if (
                failure_stage != "preflight-runtime-binding"
                or failure_reason
                not in {
                    "preflight-integrity-failed",
                    "execution-interrupted",
                    "unexpected-execution-failure",
                }
                or failure_ordinal is not None
            ):
                errors.append("preflight failure phase evidence is inconsistent")
        elif failure_group in {"post-run", "publication"}:
            if statuses != ["complete"] * len(GROUP_ORDER):
                errors.append("post-run failure does not follow complete groups")
            expected_phases = {
                "post-run": {
                    ("final-integrity-rebind", "final-integrity-rebind-failed"),
                    ("post-run-integrity", "execution-interrupted"),
                    ("post-run-integrity", "unexpected-execution-failure"),
                }
                | {
                    ("post-run-integrity", f"{subtype}-failed")
                    for subtype in _METADATA_GROUP_FAILURE_SUBTYPES
                },
                "publication": {
                    ("output-publication", "output-publication-failed"),
                },
            }
            if (
                (failure_stage, failure_reason)
                not in expected_phases[failure_group]
                or failure_ordinal is not None
            ):
                errors.append("post-run failure phase evidence is inconsistent")
        else:
            errors.append("source failure group is invalid")
    return errors


def _expected_binding_errors(
    value: Mapping[str, Any],
    expected_bindings: Mapping[str, Any],
) -> list[str]:
    git = value.get("git")
    if not isinstance(git, Mapping):
        return ["source evidence has no exact Git binding"]
    if git.get("inputs") != expected_bindings:
        return ["source evidence input bindings do not match preflight"]
    if git.get("head") != expected_bindings.get("git_head"):
        return ["source evidence Git head does not match preflight"]
    if git.get("worktree_clean") != expected_bindings.get("worktree_clean"):
        return ["source evidence clean-state binding does not match preflight"]
    return []


def validate_aggregate(
    value: Mapping[str, Any],
    *,
    expected_bindings: Mapping[str, Any],
) -> tuple[str, ...]:
    errors: list[str] = []
    expected_fields = {
        "schema_version",
        "profile_id",
        "claim_ceiling",
        "execution",
        "git",
        "runtime",
        "privacy",
        "network",
        "groups",
        "private_artifacts",
        "boundaries",
        "artifact_type",
        "status",
        "output_sha256",
    }
    if not _exact_mapping(value, expected_fields):
        errors.append("source aggregate fields are not exact")
    if value.get("artifact_type") != "source-metadata-qualification-aggregate":
        errors.append("source aggregate type is invalid")
    if value.get("status") != "complete":
        errors.append("source aggregate status is invalid")
    expected_hash = canonical_json_sha256(
        {key: nested for key, nested in value.items() if key != "output_sha256"}
    )
    if value.get("output_sha256") != expected_hash:
        errors.append("source aggregate self-hash is invalid")
    errors.extend(_evidence_errors(value, status="complete"))
    errors.extend(_expected_binding_errors(value, expected_bindings))
    public_view = receipt_with_self_hash(
        {key: nested for key, nested in value.items() if key != "output_sha256"}
    )
    errors.extend(validate_public_receipt(public_view))
    return tuple(sorted(set(errors)))


def validate_receipt(
    value: Mapping[str, Any],
    *,
    expected_bindings: Mapping[str, Any],
    aggregate_payload: bytes | None = None,
    commitment_key: bytes | None = None,
) -> tuple[str, ...]:
    errors = list(validate_public_receipt(value))
    status = value.get("status")
    common = {
        "schema_version",
        "profile_id",
        "claim_ceiling",
        "execution",
        "git",
        "runtime",
        "privacy",
        "network",
        "groups",
        "private_artifacts",
        "boundaries",
        "receipt_type",
        "status",
        "final_binding_status",
        "valid_aggregate_published",
        "receipt_hmac_sha256",
        "receipt_sha256",
    }
    failure: Mapping[str, Any] | None = None
    if status == "success":
        expected = common | {"aggregate"}
        if value.get("valid_aggregate_published") is not True:
            errors.append("successful source receipt must publish its aggregate")
        if value.get("final_binding_status") != "matched":
            errors.append("successful source receipt must have a final input match")
        if value.get("receipt_type") != "source-metadata-qualification-success":
            errors.append("successful source receipt type is invalid")
        aggregate = value.get("aggregate")
        if not _exact_mapping(aggregate, {"file_name", "size_bytes", "sha256"}):
            errors.append("successful source receipt aggregate binding is malformed")
        elif (
            aggregate.get("file_name") != "aggregate.json"
            or not _is_int(aggregate.get("size_bytes"), minimum=1)
            or not _is_hex(aggregate.get("sha256"), _HEX64)
        ):
            errors.append("successful source receipt aggregate binding is invalid")
        if not isinstance(aggregate_payload, bytes):
            errors.append("successful source receipt has no aggregate payload")
        else:
            try:
                aggregate_value = parse_json_object(
                    aggregate_payload,
                    label="published source aggregate",
                )
            except SourceAuditError as error:
                errors.append(str(error))
            else:
                if canonical_json_bytes(aggregate_value, pretty=True) != aggregate_payload:
                    errors.append("published source aggregate bytes are not canonical")
                errors.extend(
                    validate_aggregate(
                        aggregate_value,
                        expected_bindings=expected_bindings,
                    )
                )
                if isinstance(aggregate, Mapping) and (
                    aggregate.get("file_name") != "aggregate.json"
                    or aggregate.get("size_bytes") != len(aggregate_payload)
                    or aggregate.get("sha256")
                    != hashlib.sha256(aggregate_payload).hexdigest()
                ):
                    errors.append(
                        "successful source receipt does not bind the aggregate bytes"
                    )
                if any(
                    value.get(field) != aggregate_value.get(field)
                    for field in _SHARED_AGGREGATE_RECEIPT_FIELDS
                ):
                    errors.append(
                        "successful source receipt and aggregate base evidence differ"
                    )
        evidence_status = "complete"
    elif status == "failed":
        expected = common | {"failure"}
        if value.get("valid_aggregate_published") is not False:
            errors.append("failed source receipt cannot publish an aggregate")
        if value.get("final_binding_status") not in {"matched", "failed"}:
            errors.append("failed source receipt final binding status is invalid")
        if value.get("receipt_type") != "source-metadata-qualification-failure":
            errors.append("failed source receipt type is invalid")
        if aggregate_payload is not None:
            errors.append("failed source receipt cannot validate an aggregate payload")
        raw_failure = value.get("failure")
        if not _exact_mapping(
            raw_failure,
            {
                "group",
                "stage",
                "reason_code",
                "failure_subtype",
                "transport_subtype",
                "request_ordinal",
                "detail_hmac_sha256",
            },
        ):
            errors.append("source failure evidence fields are not exact")
        else:
            failure = raw_failure
            if raw_failure.get("group") not in {*GROUP_ORDER, "preflight", "post-run", "publication"}:
                errors.append("source failure group is invalid")
            if not isinstance(raw_failure.get("stage"), str) or re.fullmatch(
                r"[a-z0-9-]+", raw_failure["stage"]
            ) is None:
                errors.append("source failure stage is invalid")
            reason_code = raw_failure.get("reason_code")
            if reason_code not in _ALLOWED_FAILURE_REASONS:
                errors.append("source failure reason code is invalid")
            failure_subtype = raw_failure.get("failure_subtype")
            if failure_subtype not in FAILURE_SUBTYPES:
                errors.append("source failure subtype is invalid")
            expected_subtype = _SPECIAL_FAILURE_REASONS.get(reason_code)
            if expected_subtype is None and isinstance(reason_code, str) and reason_code.endswith(
                "-failed"
            ):
                expected_subtype = reason_code[: -len("-failed")]
            if failure_subtype != expected_subtype:
                errors.append("source failure subtype does not match its reason")
            transport_subtype = raw_failure.get("transport_subtype")
            if raw_failure.get("reason_code") == "metadata-transport-failed":
                if transport_subtype not in MetadataTransportError.ALLOWED_SUBTYPES:
                    errors.append("source transport failure subtype is invalid")
            elif transport_subtype is not None:
                errors.append("non-transport failure claims a transport subtype")
            if not _is_hex(raw_failure.get("detail_hmac_sha256"), _HEX64):
                errors.append("source failure detail commitment is invalid")
            ordinal = raw_failure.get("request_ordinal")
            network = value.get("network")
            attempts = network.get("request_attempt_count") if isinstance(network, Mapping) else None
            if ordinal is not None and (
                not _is_int(ordinal)
                or not _is_int(attempts, minimum=1)
                or ordinal != attempts - 1
            ):
                errors.append("source failure request ordinal is invalid")
            if raw_failure.get("group") not in GROUP_ORDER and ordinal is not None:
                errors.append("non-group source failure cannot claim a request ordinal")
        evidence_status = "failed"
    else:
        expected = common
        evidence_status = "failed"
        errors.append("source receipt status is invalid")
    if not _exact_mapping(value, expected):
        errors.append("source receipt fields are not exact")
    receipt_hmac = value.get("receipt_hmac_sha256")
    if not _is_hex(receipt_hmac, _HEX64):
        errors.append("source receipt commitment is invalid")
    if (
        not isinstance(commitment_key, bytes)
        or len(commitment_key) != 32
        or hashlib.sha256(commitment_key).hexdigest()
        != _COMMITMENT_KEY_SHA256
    ):
        errors.append("source receipt commitment key is unavailable")
    else:
        expected_receipt_hmac = keyed_commitment(
            commitment_key,
            domain="source-receipt",
            payload=_receipt_hmac_payload(value),
        )
        if receipt_hmac != expected_receipt_hmac:
            errors.append("source receipt commitment differs")
    errors.extend(_evidence_errors(value, status=evidence_status, failure=failure))
    errors.extend(_expected_binding_errors(value, expected_bindings))
    return tuple(sorted(set(errors)))
