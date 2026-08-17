"""Parse Wikimedia dumpstatus.json into no-download archive inventory records."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import urljoin


class WikimediaInventoryError(ValueError):
    """Raised when a Wikimedia dump inventory is malformed."""


_SNAPSHOT = re.compile(r"^\d{8}$")


def parse_wikimedia_dumpstatus(
    value: Mapping[str, Any],
    *,
    source_locator: str,
    snapshot_id: str,
    source_id: str = "wikimedia-article-additions",
) -> list[dict[str, Any]]:
    """Return completed pages-meta-history files without downloading them.

    ``dumpstatus.json`` has a schema ``version`` field that is not the dump
    date. Snapshot identity is therefore supplied explicitly from the pinned
    URL path and must be an eight-digit Wikimedia dump date.
    """

    if not _SNAPSHOT.fullmatch(snapshot_id):
        raise WikimediaInventoryError(
            "snapshot_id must be an explicit YYYYMMDD dump date"
        )
    jobs = value.get("jobs")
    if not isinstance(jobs, Mapping):
        raise WikimediaInventoryError("dumpstatus has no jobs object")
    status_schema_version = value.get("version")
    records: list[dict[str, Any]] = []

    for job_name, raw_job in sorted(jobs.items()):
        if "history" not in str(job_name).lower():
            continue
        if not isinstance(raw_job, Mapping):
            continue
        # Waiting or failed jobs do not establish an immutable complete archive.
        if raw_job.get("status") != "done":
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
            raw_url = raw_file.get("url")
            if not isinstance(raw_url, str) or not raw_url:
                raise WikimediaInventoryError(
                    f"history file {file_name!r} has no URL"
                )
            url = urljoin(source_locator, raw_url)
            records.append(
                {
                    "schema_version": 1,
                    "inventory_id": f"wikimedia:{snapshot_id}:{file_name}",
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
                        "dumpstatus_schema_version": status_schema_version,
                        "dumpstatus_locator": source_locator,
                    },
                }
            )
    if not records:
        raise WikimediaInventoryError(
            "dumpstatus contains no completed pages-meta-history files"
        )
    return records
