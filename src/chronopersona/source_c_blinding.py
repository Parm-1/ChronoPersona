"""Blinding helpers for held-out source-C metadata review packets."""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
import hmac
from typing import Any

from .official_metadata_adapters import (
    AdapterRecord,
    MetadataAdapterError,
    canonical_sha256,
    redact_locator,
)


def _opaque_record_id(record: AdapterRecord, secret: bytes) -> str:
    material = f"{record.source_id}\0{record.native_id}".encode("utf-8")
    digest = hmac.new(secret, material, hashlib.sha256).hexdigest()
    return f"source-c-{digest}"


def blind_source_c_records(
    records: Sequence[AdapterRecord],
    *,
    secret: bytes,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a blinded packet and a separately stored unblinding key.

    The review packet removes native identifiers, timestamps, OAI datestamps,
    raw date values, and usable locators. It is suitable for source-feasibility
    review only after the packet's retained category fields are also checked
    for period-identifying leakage.
    """

    if not secret:
        raise MetadataAdapterError("source-C blinding secret must not be empty")

    packet_records: list[dict[str, Any]] = []
    key_records: list[dict[str, Any]] = []
    seen: set[str] = set()

    for record in records:
        opaque_id = _opaque_record_id(record, secret)
        if opaque_id in seen:
            raise MetadataAdapterError("source-C opaque record IDs are not unique")
        seen.add(opaque_id)

        blinded_metadata = {
            key: value
            for key, value in record.source_metadata.items()
            if key
            not in {
                "oai_identifier",
                "oai_datestamp",
                "created_raw",
                "updated_raw",
                "date_values",
                "identifier_values",
            }
        }
        packet_records.append(
            {
                "opaque_record_id": opaque_id,
                "source_id": record.source_id,
                "timestamp_status": record.timestamp_status,
                "historical_version_status": record.historical_version_status,
                "rights_status": record.rights_status,
                "license_id": record.license_id,
                "authorship_provenance": record.authorship_provenance,
                "categories": list(record.categories),
                "metadata_locator": (
                    redact_locator(record.metadata_locator, secret)
                    if record.metadata_locator
                    else None
                ),
                "content_locator": (
                    redact_locator(record.content_locator, secret)
                    if record.content_locator
                    else None
                ),
                "eligible_for_bounded_review": record.eligible_for_bounded_review,
                "exclusion_reasons": list(record.exclusion_reasons),
                "source_metadata": blinded_metadata,
            }
        )
        key_records.append(
            {
                "opaque_record_id": opaque_id,
                "source_id": record.source_id,
                "native_id": record.native_id,
                "native_timestamp": record.native_timestamp,
                "timestamp_semantics": record.timestamp_semantics,
                "metadata_locator": record.metadata_locator,
                "content_locator": record.content_locator,
                "source_metadata": dict(record.source_metadata),
            }
        )

    packet: dict[str, Any] = {
        "schema_version": 1,
        "packet_type": "source-c-blinded-metadata-review",
        "record_count": len(packet_records),
        "records": packet_records,
    }
    packet["packet_sha256"] = canonical_sha256(packet)

    key: dict[str, Any] = {
        "schema_version": 1,
        "key_type": "source-c-unblinding-key",
        "packet_sha256": packet["packet_sha256"],
        "record_count": len(key_records),
        "records": key_records,
    }
    key["key_sha256"] = canonical_sha256(key)
    return packet, key
