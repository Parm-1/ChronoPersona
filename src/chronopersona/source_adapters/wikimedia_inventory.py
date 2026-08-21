"""Parse Wikimedia dumpstatus.json into no-download archive inventory records."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import urljoin, urlsplit

from ..path_policy import PortablePathError, portable_relative_path


class WikimediaInventoryError(ValueError):
    """Raised when a Wikimedia dump inventory is malformed."""


_SNAPSHOT = re.compile(r"^\d{8}$")


def _bounded_file_url(
    source_locator: str,
    raw_url: str,
    *,
    expected_file_name: str,
) -> str:
    source = urlsplit(source_locator)
    raw = urlsplit(raw_url)
    path_components = raw.path.split("/")
    if (
        raw.scheme
        or raw.netloc
        or raw.query
        or raw.fragment
        or raw_url.startswith("\\")
        or "\\" in raw_url
        or "%" in raw_url
        or any(component in {".", ".."} for component in path_components)
        or any(
            not component
            for index, component in enumerate(path_components)
            if not (index == 0 and raw.path.startswith("/"))
        )
    ):
        raise WikimediaInventoryError(
            "history file URL must be relative to the pinned snapshot"
        )
    try:
        source_port = source.port
    except ValueError as error:
        raise WikimediaInventoryError(
            "dumpstatus locator has an invalid port"
        ) from error
    if (
        source.scheme != "https"
        or source.hostname != "dumps.wikimedia.org"
        or source.username is not None
        or source.password is not None
        or source_port is not None
        or not source.path.endswith("/dumpstatus.json")
    ):
        raise WikimediaInventoryError(
            "dumpstatus locator must be pinned under dumps.wikimedia.org"
        )
    expected_prefix = source.path[: -len("dumpstatus.json")]
    resolved = urljoin(source_locator, raw_url)
    parsed = urlsplit(resolved)
    try:
        parsed_port = parsed.port
    except ValueError as error:
        raise WikimediaInventoryError("history file URL has an invalid port") from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != "dumps.wikimedia.org"
        or parsed.username is not None
        or parsed.password is not None
        or parsed_port is not None
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(expected_prefix)
        or parsed.path == expected_prefix
        or parsed.path.rsplit("/", 1)[-1] != expected_file_name
    ):
        raise WikimediaInventoryError(
            "history file URL escapes the pinned Wikimedia snapshot path"
        )
    return resolved


def parse_wikimedia_dumpstatus(
    value: Mapping[str, Any],
    *,
    source_locator: str,
    snapshot_id: str,
    source_id: str = "wikimedia-article-additions",
    required_job_name: str | None = None,
    required_file_name_fragment: str = "pages-meta-history",
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
    raw_schema_version = value.get("version")
    if isinstance(raw_schema_version, bool) or not isinstance(
        raw_schema_version, (int, str)
    ):
        raise WikimediaInventoryError("dumpstatus schema version is not canonical")
    status_schema_version = str(raw_schema_version)
    if re.fullmatch(r"(?:0|[1-9]\d*)(?:\.\d+)?", status_schema_version) is None:
        raise WikimediaInventoryError("dumpstatus schema version is not canonical")
    records: list[dict[str, Any]] = []

    for job_name, raw_job in sorted(jobs.items()):
        if required_job_name is not None:
            if job_name != required_job_name:
                continue
        elif "history" not in str(job_name).lower():
            continue
        if not isinstance(raw_job, Mapping):
            if required_job_name is not None:
                raise WikimediaInventoryError("required Wikimedia job is malformed")
            continue
        # Waiting or failed jobs do not establish an immutable complete archive.
        if raw_job.get("status") != "done":
            if required_job_name is not None:
                raise WikimediaInventoryError("required Wikimedia job is incomplete")
            continue
        files = raw_job.get("files")
        if not isinstance(files, Mapping):
            if required_job_name is not None:
                raise WikimediaInventoryError("required Wikimedia file map is malformed")
            continue
        for file_name, raw_file in sorted(files.items()):
            lower_name = str(file_name).lower()
            if required_file_name_fragment.casefold() not in lower_name:
                continue
            if not isinstance(raw_file, Mapping):
                raise WikimediaInventoryError(
                    f"history file {file_name!r} metadata is malformed"
                )
            try:
                relative_name = portable_relative_path(
                    str(file_name),
                    label="Wikimedia history file",
                )
            except PortablePathError as error:
                raise WikimediaInventoryError(str(error)) from error
            if len(relative_name.parts) != 1:
                raise WikimediaInventoryError(
                    "Wikimedia history file must be one canonical leaf"
                )
            raw_size = raw_file.get("size")
            if isinstance(raw_size, bool) or not (
                type(raw_size) is int
                or (
                    isinstance(raw_size, str)
                    and re.fullmatch(r"0|[1-9]\d*", raw_size) is not None
                )
            ):
                raise WikimediaInventoryError(
                    f"invalid size for {file_name!r}: {raw_size!r}"
                )
            size = int(raw_size)
            if size <= 0:
                raise WikimediaInventoryError(
                    f"history file {file_name!r} has non-positive size"
                )
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
            url = _bounded_file_url(
                source_locator,
                raw_url,
                expected_file_name=str(file_name),
            )
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
    file_names = [str(record["file_name"]).casefold() for record in records]
    if len(file_names) != len(set(file_names)):
        raise WikimediaInventoryError(
            "Wikimedia history file names collide case-insensitively"
        )
    return records
