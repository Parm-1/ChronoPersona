"""Parse Wikimedia dumpstatus.json into no-download archive inventory records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class WikimediaInventoryError(ValueError):
    """Raised when a Wikimedia dump inventory is malformed."""


def parse_wikimedia_dumpstatus(
    value: Mapping[str, Any],
    *,
    source_locator: str,
    source_id: str = "wikimedia-article-additions",
) -> list[dict[str, Any]]:
    """Return pages-meta-history archive files without downloading them."""

    jobs = value.get("jobs")
    if not isinstance(jobs, Mapping):
        raise WikimediaInventoryError("dumpstatus has no jobs object")
    version = value.get("version")
    snapshot_id = str(version or value.get("date") or "unknown-snapshot")
    records: list[dict[str, Any]] = []

    for job_name, raw_job in sorted(jobs.items()):
        if "history" not in str(job_name).lower():
            continue
        if not isinstance(raw_job, Mapping):
            continue
        if raw_job.get("status") not in {"done", "waiting"}:
            continue
        files = raw_job.get("files")
        if not isinstance(files, Mapping):
            continue
        for file_name, raw_file in sorted(files.items()):
            if not isinstance(raw_file, Mapping):
                continue
            lower_name = str(file_name).lower()
            if "pages-meta-history" not in lower_name:
                continue
            raw_size = raw_file.get("size")
            try:
                size = int(raw_size)
            except (TypeError, ValueError) as error:
                raise WikimediaInventoryError(
                    f"invalid size for {file_name!r}: {raw_size!r}"
                ) from error
            hashes = {
                algorithm: str(raw_file[algorithm])
                for algorithm in ("md5", "sha1")
                if raw_file.get(algorithm)
            }
            if not hashes:
                raise WikimediaInventoryError(
                    f"history file {file_name!r} has no md5 or sha1"
                )
            url = raw_file.get("url")
            if not isinstance(url, str) or not url:
                raise WikimediaInventoryError(
                    f"history file {file_name!r} has no URL"
                )
            if url.startswith("/"):
                base = source_locator.rsplit("/", 1)[0]
                url = base + url
            records.append(
                {
                    "schema_version": 1,
                    "inventory_id": (
                        f"wikimedia:{snapshot_id}:{file_name}"
                    ),
                    "source_id": source_id,
                    "snapshot_id": snapshot_id,
                    "file_name": str(file_name),
                    "locator": url,
                    "content_kind": "revision-history-archive",
                    "size_bytes": size,
                    "hashes": hashes,
                    "downloaded": False,
                    "download_authorized": False,
                    "source_metadata": {
                        "job_name": str(job_name),
                        "job_status": raw_job.get("status"),
                        "dumpstatus_locator": source_locator,
                    },
                }
            )
    if not records:
        raise WikimediaInventoryError(
            "dumpstatus contains no pages-meta-history files"
        )
    return records
