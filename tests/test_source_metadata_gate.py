from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from email.utils import format_datetime
import hashlib
import os
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
from urllib.parse import parse_qs, urlsplit

import pytest

import chronopersona.source_audit as source_audit_module
import chronopersona.source_metadata_gate as gate_module

from chronopersona.source_adapters.network import MetadataResponse
from chronopersona.source_audit import (
    BoundSourceInputs,
    FROZEN_PROFILE_CANONICAL_SHA256,
    FROZEN_PROFILE_GIT_BLOB,
    RUNTIME_RELATIVE_PATHS,
    SourceAuditError,
    SourceOutputReservation,
    SourceOutputRoots,
    arxiv_block_starts,
    canonical_json_bytes,
    load_profile_for_plan,
    parse_json_object,
    receipt_with_self_hash,
    response_identity,
    validate_public_receipt,
)
from chronopersona.source_metadata_gate import (
    GROUP_ORDER,
    SourceGateError,
    failure_receipt,
    run_gate,
    success_aggregate,
    success_receipt,
    validate_aggregate,
    validate_receipt,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
COMMITMENT_KEY = b"k" * 32
COMMITMENT_KEY_SHA256 = hashlib.sha256(COMMITMENT_KEY).hexdigest()


@pytest.fixture(autouse=True)
def _synthetic_commitment_contract(monkeypatch) -> None:
    monkeypatch.setattr(
        gate_module,
        "_COMMITMENT_KEY_SHA256",
        COMMITMENT_KEY_SHA256,
    )


def _bound() -> BoundSourceInputs:
    profile = deepcopy(load_profile_for_plan(ROOT))
    profile["privacy"]["commitment_key_sha256"] = COMMITMENT_KEY_SHA256
    values = {
        "metadata_gate_profile": profile,
        "source_registry": json.loads(
            (ROOT / "artifacts/manifests/SOURCE_REGISTRY.json").read_text(
                encoding="utf-8"
            )
        ),
        "arxiv_metadata_config": json.loads(
            (ROOT / "configs/sources/arxiv-metadata-v0.json").read_text(
                encoding="utf-8"
            )
        ),
        "pmc_metadata_config": json.loads(
            (ROOT / "configs/sources/pmc-metadata-v0.json").read_text(
                encoding="utf-8"
            )
        ),
    }
    bindings = {
        "git_head": "a" * 40,
        "worktree_clean": True,
        "metadata_gate_profile": {
            "path": "configs/sources/live-metadata-qualification-v0.json",
            "git_blob": FROZEN_PROFILE_GIT_BLOB,
            "raw_sha256": "c" * 64,
            "canonical_sha256": FROZEN_PROFILE_CANONICAL_SHA256,
            "kind": "canonical-json",
        },
    }
    for label, record in profile["canonical_inputs"].items():
        bindings[label] = {
            "path": record["path"],
            "git_blob": record["git_blob"],
            "raw_sha256": "d" * 64,
            "canonical_sha256": "e" * 64,
            "kind": "canonical-json",
        }
    for index, path in enumerate(RUNTIME_RELATIVE_PATHS):
        bindings[f"runtime_{index:02d}"] = {
            "path": path,
            "git_blob": "f" * 40,
            "raw_sha256": "1" * 64,
            "kind": "python-runtime",
        }
    return BoundSourceInputs(
        head="a" * 40,
        bindings=bindings,
        payloads={},
        values=values,
    )


def _reservation(tmp_path: Path, profile: dict) -> SourceOutputReservation:
    local = tmp_path / "local"
    backup = tmp_path / "backup"
    local.mkdir()
    backup.mkdir()
    publication = profile["publication"]
    return SourceOutputReservation(
        SourceOutputRoots(run_dir=local, backup_dir=backup),
        [
            *publication["private_artifact_files"],
            publication["aggregate_file"],
            publication["receipt_file"],
        ],
    )


def _atom_feed(*, total: int, start: int, page_size: int, cell_date: str) -> bytes:
    year = int(cell_date[:4])
    month = int(cell_date[4:6])
    entries = []
    for index in range(page_size):
        identifier = f"{year % 100:02d}{month:02d}.{start + index + 1:05d}"
        timestamp = f"{year:04d}-{month:02d}-15T12:00:00Z"
        entries.append(
            f"""
            <entry>
              <id>http://arxiv.org/abs/{identifier}v1</id>
              <published>{timestamp}</published>
              <updated>{timestamp}</updated>
              <title>Fixture title {identifier}</title>
              <summary>Fixture abstract {identifier}</summary>
              <author><name>Fixture Author</name></author>
              <category term="astro-ph.GA" />
            </entry>"""
        )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<feed xmlns='http://www.w3.org/2005/Atom' "
        "xmlns:opensearch='http://a9.com/-/spec/opensearch/1.1/'>"
        f"<opensearch:totalResults>{total}</opensearch:totalResults>"
        f"<opensearch:startIndex>{start}</opensearch:startIndex>"
        f"<opensearch:itemsPerPage>{page_size}</opensearch:itemsPerPage>"
        + "".join(entries)
        + "</feed>"
    ).encode("utf-8")


def _arxiv_oai(identifier: str) -> bytes:
    year = 2000 + int(identifier[:2])
    month = int(identifier[2:4])
    return f"""<?xml version='1.0' encoding='UTF-8'?>
    <OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>
      <responseDate>2026-08-20T00:00:00Z</responseDate>
      <request verb='GetRecord' metadataPrefix='arXivRaw' identifier='oai:arXiv.org:{identifier}'>https://oaipmh.arxiv.org/oai</request>
      <GetRecord><record>
        <header>
          <identifier>oai:arXiv.org:{identifier}</identifier>
          <datestamp>{year:04d}-{month:02d}-15</datestamp>
        </header>
        <metadata><arXiv xmlns='http://arxiv.org/OAI/arXivRaw/'>
          <id>{identifier}</id>
          <version version='v1'><date>{format_datetime(datetime(year, month, 15, 12, tzinfo=timezone.utc), usegmt=True)}</date></version>
          <title>Fixture title {identifier}</title>
          <authors><author><keyname>Fixture</keyname></author></authors>
          <categories>astro-ph.GA</categories>
          <abstract>Fixture abstract {identifier}</abstract>
          <license>https://creativecommons.org/licenses/by/4.0/</license>
        </arXiv></metadata>
      </record></GetRecord>
    </OAI-PMH>""".encode("utf-8")


def _pmc_page(
    *,
    year: int,
    base: int,
    from_date: str,
    until_date: str,
    record_count: int = 100,
    next_token: str | None = "more-records-exist",
    request_token: str | None = None,
) -> bytes:
    records = []
    for index in range(record_count):
        number = base + index
        records.append(
            f"""<record>
              <header>
                <identifier>oai:pubmedcentral.nih.gov:{number}</identifier>
                <datestamp>{year}-01-15</datestamp>
                <setSpec>pmc-open</setSpec>
              </header>
              <metadata><oai_dc:dc
                xmlns:oai_dc='http://www.openarchives.org/OAI/2.0/oai_dc/'
                xmlns:dc='http://purl.org/dc/elements/1.1/'>
                <dc:identifier>PMC{number}</dc:identifier>
                <dc:date>{year}-01-15</dc:date>
                <dc:subject>genetics</dc:subject>
                <dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>
                <dc:title>Fixture title {number}</dc:title>
                <dc:creator>Fixture Author</dc:creator>
              </oai_dc:dc></metadata>
            </record>"""
        )
    request_attributes = (
        f"verb='ListRecords' resumptionToken='{request_token}'"
        if request_token is not None
        else (
            "verb='ListRecords' metadataPrefix='oai_dc' "
            f"from='{from_date}' until='{until_date}' set='pmc-open'"
        )
    )
    token_element = (
        "" if next_token is None else f"<resumptionToken>{next_token}</resumptionToken>"
    )
    return (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>"
        "<responseDate>2026-08-20T00:00:00Z</responseDate>"
        f"<request {request_attributes}>https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/</request>"
        "<ListRecords>"
        + "".join(records)
        + token_element
        + "</ListRecords></OAI-PMH>"
    ).encode("utf-8")


class FixtureFetcher:
    def __init__(self, *, fail_at: int | None = None) -> None:
        self.calls: list[dict] = []
        self.fail_at = fail_at

    def __call__(self, url: str, **kwargs) -> MetadataResponse:
        ordinal = len(self.calls)
        self.calls.append({"url": url, **kwargs})
        assert kwargs["allow_network"] is True
        assert kwargs["allow_redirects"] is False
        if self.fail_at is not None and ordinal == self.fail_at:
            raise RuntimeError("synthetic transport failure with private detail")
        if url.endswith("/enwiki/20260801/dumpstatus.json"):
            payload = (FIXTURES / "wikimedia_dumpstatus_sample.json").read_bytes().replace(
                b"20260101", b"20260801"
            )
            media_type = "application/json"
        elif url == "https://archive.org/metadata/stackexchange":
            payload = (FIXTURES / "stackexchange_archive_sample.json").read_bytes()
            media_type = "application/json"
        elif url.startswith("https://export.arxiv.org/api/query?"):
            query = parse_qs(urlsplit(url).query)
            start = int(query["start"][0])
            page_size = int(query["max_results"][0])
            match = re.search(r"submittedDate:\[(\d{8})0000", query["search_query"][0])
            assert match is not None
            payload = _atom_feed(
                total=25,
                start=start,
                page_size=page_size,
                cell_date=match.group(1),
            )
            media_type = "application/atom+xml"
        elif url.startswith("https://oaipmh.arxiv.org/oai?"):
            identifier = parse_qs(urlsplit(url).query)["identifier"][0].split(":", 2)[2]
            payload = _arxiv_oai(identifier)
            media_type = "application/xml"
        elif url.startswith("https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/?"):
            query = parse_qs(urlsplit(url).query)
            year = int(query["from"][0][:4])
            payload = _pmc_page(
                year=year,
                base=10_000 if year == 2012 else 20_000,
                from_date=query["from"][0],
                until_date=query["until"][0],
            )
            media_type = "application/xml"
        else:
            raise AssertionError(f"unexpected fixture request: {url}")
        return MetadataResponse(
            payload=payload,
            requested_url=url,
            final_url=url,
            status=200,
            content_type=media_type,
        )


class PmcPageFetcher:
    def __init__(self, pages: list[bytes]) -> None:
        self.pages = list(pages)
        self.calls: list[str] = []

    def __call__(self, url: str, **_kwargs) -> MetadataResponse:
        self.calls.append(url)
        if not self.pages:
            raise AssertionError("unexpected extra PMC request")
        return MetadataResponse(
            payload=self.pages.pop(0),
            requested_url=url,
            final_url=url,
            status=200,
            content_type="application/xml",
        )


class MutatingFixtureFetcher(FixtureFetcher):
    def __init__(self, *, mutate_at: int, transform) -> None:
        super().__init__()
        self.mutate_at = mutate_at
        self.transform = transform

    def __call__(self, url: str, **kwargs) -> MetadataResponse:
        ordinal = len(self.calls)
        response = super().__call__(url, **kwargs)
        if ordinal != self.mutate_at:
            return response
        return MetadataResponse(
            payload=self.transform(response.payload),
            requested_url=response.requested_url,
            final_url=response.final_url,
            status=response.status,
            content_type=response.content_type,
        )


def _pmc_only_context(tmp_path: Path) -> tuple[gate_module.GateContext, SourceOutputReservation]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)
    context = gate_module.GateContext(
        bound=bound,
        reservation=reservation,
        profile=profile,
        windows=gate_module.parse_era_windows(bound.values["source_registry"]),
        commitment_key=COMMITMENT_KEY,
    )
    for group in GROUP_ORDER[:6]:
        context.group_record(group)["status"] = "complete"
    return context, reservation


def _candidate_only_context(
    tmp_path: Path,
) -> tuple[gate_module.GateContext, SourceOutputReservation]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)
    context = gate_module.GateContext(
        bound=bound,
        reservation=reservation,
        profile=profile,
        windows=gate_module.parse_era_windows(bound.values["source_registry"]),
        commitment_key=COMMITMENT_KEY,
    )
    for group in GROUP_ORDER[:2]:
        context.group_record(group)["status"] = "complete"
    return context, reservation


def test_frozen_sampler_terminates_at_minimum_and_stays_in_range() -> None:
    for total in range(25, 30006):
        starts = arxiv_block_starts(
            total_results=total,
            cell_id="2012-h1",
            commitment_key=COMMITMENT_KEY,
            domain="arxiv-source-c-rank-sample-v0",
        )
        assert len(starts) == len(set(starts)) == 5
        assert all(start % 5 == 0 and start + 4 < total for start in starts)
        assert max(starts) <= 30000
    assert {
        cell_id: arxiv_block_starts(
            total_results=25,
            cell_id=cell_id,
            commitment_key=COMMITMENT_KEY,
            domain="arxiv-source-c-rank-sample-v0",
        )
        for cell_id in (
            "2012-h1",
            "2012-h2",
            "2013-h1",
            "2013-h2",
            "2018-h1",
            "2018-h2",
            "2019-h1",
            "2019-h2",
        )
    } == {
        "2012-h1": (5, 10, 15, 20, 0),
        "2012-h2": (5, 0, 10, 15, 20),
        "2013-h1": (20, 15, 0, 5, 10),
        "2013-h2": (10, 15, 20, 0, 5),
        "2018-h1": (20, 15, 10, 0, 5),
        "2018-h2": (0, 5, 10, 15, 20),
        "2019-h1": (0, 10, 15, 5, 20),
        "2019-h2": (20, 0, 5, 10, 15),
    }


def test_profile_is_exact_and_duplicate_json_keys_fail() -> None:
    profile = load_profile_for_plan(ROOT)
    mutated = deepcopy(profile)
    mutated["network"]["retry_count"] = 1
    from chronopersona.source_audit import _validate_profile

    with pytest.raises(SourceAuditError, match="identity is not frozen"):
        _validate_profile(mutated)
    with pytest.raises(SourceAuditError, match="duplicate JSON key"):
        parse_json_object(b'{"schema_version":1,"schema_version":1}', label="fixture")
    with pytest.raises(SourceAuditError, match="non-finite JSON constant"):
        parse_json_object(b'{"nested":{"value":NaN}}', label="fixture")


def test_private_commitment_key_loader_requires_two_exact_outside_git_copies(
    tmp_path: Path,
    monkeypatch,
) -> None:
    primary = tmp_path / "primary" / "commitment-key.hex"
    backup = tmp_path / "backup" / "commitment-key.hex"
    primary.parent.mkdir()
    backup.parent.mkdir()
    payload = COMMITMENT_KEY.hex().encode("ascii") + b"\n"
    primary.write_bytes(payload)
    backup.write_bytes(payload)

    assert source_audit_module.load_private_commitment_key(
        ROOT,
        primary_path=primary,
        backup_path=backup,
        expected_sha256=COMMITMENT_KEY_SHA256,
    ) == COMMITMENT_KEY
    with pytest.raises(SourceAuditError, match="copies must be distinct"):
        source_audit_module.load_private_commitment_key(
            ROOT,
            primary_path=primary,
            backup_path=primary,
            expected_sha256=COMMITMENT_KEY_SHA256,
        )

    backup.write_bytes((b"f" * 64) + b"\n")
    with pytest.raises(SourceAuditError, match="copies do not match"):
        source_audit_module.load_private_commitment_key(
            ROOT,
            primary_path=primary,
            backup_path=backup,
            expected_sha256=COMMITMENT_KEY_SHA256,
        )
    backup.unlink()
    os.link(primary, backup)
    with pytest.raises(SourceAuditError, match="unalias|alias"):
        source_audit_module.load_private_commitment_key(
            ROOT,
            primary_path=primary,
            backup_path=backup,
            expected_sha256=COMMITMENT_KEY_SHA256,
        )

    monkeypatch.setattr(
        source_audit_module,
        "_directory_is_inside_git",
        lambda _path: True,
    )
    with pytest.raises(SourceAuditError, match="outside Git"):
        source_audit_module.load_private_commitment_key(
            ROOT,
            primary_path=primary,
            backup_path=backup,
            expected_sha256=COMMITMENT_KEY_SHA256,
        )


def test_prepare_output_roots_is_create_only_and_cleans_a_second_mkdir_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_root = tmp_path / "repo"
    backup_parent = tmp_path / "outside"
    fake_root.mkdir()
    backup_parent.mkdir()
    backup = backup_parent / "run-a"
    roots = source_audit_module.prepare_output_roots(
        fake_root,
        run_dir="artifacts/local/source-audit/run-a",
        backup_dir=backup,
    )
    assert roots.run_dir.is_dir()
    assert roots.backup_dir.is_dir()
    roots.run_dir.rmdir()
    roots.backup_dir.rmdir()

    collision = fake_root / "artifacts" / "local" / "source-audit" / "Run-B"
    collision.mkdir()
    with pytest.raises(SourceAuditError, match="collides"):
        source_audit_module.prepare_output_roots(
            fake_root,
            run_dir="artifacts/local/source-audit/run-b",
            backup_dir=backup_parent / "run-b",
        )
    collision.rmdir()

    with pytest.raises(SourceAuditError, match="outside every Git worktree"):
        source_audit_module.prepare_output_roots(
            fake_root,
            run_dir="artifacts/local/source-audit/run-c",
            backup_dir=fake_root / "backup-run-c",
        )

    local = fake_root / "artifacts" / "local" / "source-audit" / "run-d"
    failed_backup = backup_parent / "run-d"
    real_mkdir = Path.mkdir

    def fail_backup_mkdir(path: Path, *args, **kwargs) -> None:
        if path == failed_backup:
            raise OSError("synthetic second mkdir failure")
        real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail_backup_mkdir)
    with pytest.raises(OSError, match="second mkdir"):
        source_audit_module.prepare_output_roots(
            fake_root,
            run_dir="artifacts/local/source-audit/run-d",
            backup_dir=failed_backup,
        )
    assert not local.exists()
    assert not failed_backup.exists()


def test_source_input_binding_rejects_wrong_dirty_and_semantic_alias_heads(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "bound-repo"
    repo.mkdir()
    profile = load_profile_for_plan(ROOT)
    relative_paths = {
        ".gitattributes",
        source_audit_module.PROFILE_RELATIVE_PATH,
        *source_audit_module.RUNTIME_RELATIVE_PATHS,
        *(record["path"] for record in profile["canonical_inputs"].values()),
    }
    for relative in sorted(relative_paths):
        target = repo / Path(*relative.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / Path(*relative.split("/")), target)
    unrelated = repo / "unrelated.txt"
    unrelated.write_text("original\n", encoding="utf-8")

    def git(*arguments: str) -> str:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    git("init", "--quiet")
    git("config", "user.name", "ChronoPersona Test")
    git("config", "user.email", "invalid")
    git("config", "core.autocrlf", "false")
    git("add", "--all")
    git("commit", "--quiet", "-m", "bound fixture")
    head = git("rev-parse", "HEAD")

    bound = source_audit_module.bind_source_inputs(repo, expected_head=head)
    source_audit_module.rebind_source_inputs(repo, bound)
    source_audit_module.verify_runtime_module_paths(
        repo,
        {
            relative: repo / Path(*relative.split("/"))
            for relative in source_audit_module.RUNTIME_RELATIVE_PATHS
        },
        bound,
    )
    with pytest.raises(SourceAuditError, match="not the expected head"):
        source_audit_module.bind_source_inputs(repo, expected_head="0" * 40)

    runtime_path = repo / Path(
        *source_audit_module.RUNTIME_RELATIVE_PATHS[0].split("/")
    )
    runtime_path.write_bytes(runtime_path.read_bytes() + b"\n")
    with pytest.raises(SourceAuditError, match="clean exact Git head"):
        source_audit_module.bind_source_inputs(repo, expected_head=head)
    shutil.copyfile(
        ROOT / Path(*source_audit_module.RUNTIME_RELATIVE_PATHS[0].split("/")),
        runtime_path,
    )
    assert git("status", "--porcelain", "--untracked-files=all") == ""

    git("update-index", "--assume-unchanged", "unrelated.txt")
    unrelated.write_text("hidden assume-unchanged drift\n", encoding="utf-8")
    assert git("status", "--porcelain", "--untracked-files=all") == ""
    with pytest.raises(SourceAuditError, match="assume-unchanged"):
        source_audit_module.bind_source_inputs(repo, expected_head=head)
    unrelated.write_text("original\n", encoding="utf-8")
    git("update-index", "--no-assume-unchanged", "unrelated.txt")

    git("update-index", "--skip-worktree", "unrelated.txt")
    unrelated.write_text("hidden skip-worktree drift\n", encoding="utf-8")
    assert git("status", "--porcelain", "--untracked-files=all") == ""
    with pytest.raises(SourceAuditError, match="skip-worktree"):
        source_audit_module.bind_source_inputs(repo, expected_head=head)
    unrelated.write_text("original\n", encoding="utf-8")
    git("update-index", "--no-skip-worktree", "unrelated.txt")
    assert git("status", "--porcelain", "--untracked-files=all") == ""

    git("config", "core.fsmonitor", "true")
    git("update-index", "--fsmonitor-valid", "unrelated.txt")
    assert git("ls-files", "-f", "unrelated.txt").startswith("h ")
    assert subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "ls-files",
            "-f",
            "unrelated.txt",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.startswith("H ")
    with pytest.raises(SourceAuditError, match="fsmonitor-valid"):
        source_audit_module.bind_source_inputs(repo, expected_head=head)
    git("update-index", "--no-fsmonitor-valid", "unrelated.txt")
    git("config", "core.fsmonitor", "false")
    assert git("status", "--porcelain", "--untracked-files=all") == ""

    registry = repo / "artifacts" / "manifests" / "SOURCE_REGISTRY.json"
    registry.write_bytes(registry.read_bytes() + b"\n")
    git("add", "--all")
    git("commit", "--quiet", "-m", "semantic alias")
    aliased_head = git("rev-parse", "HEAD")
    with pytest.raises(SourceAuditError, match="Git blob is not frozen"):
        source_audit_module.bind_source_inputs(repo, expected_head=aliased_head)


def test_full_fixture_gate_runs_exact_order_without_retry(tmp_path: Path) -> None:
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)
    fetcher = FixtureFetcher()

    context = run_gate(
        bound,
        reservation,
        fetcher,
        commitment_key=COMMITMENT_KEY,
    )

    assert [group["group_id"] for group in context.groups] == list(GROUP_ORDER)
    assert all(group["status"] == "complete" for group in context.groups)
    assert context.request_attempt_count == 252
    assert context.completed_response_count == 252
    assert len(fetcher.calls) == 252
    assert context.groups[2]["request_attempt_count"] == 24
    assert context.groups[3]["request_attempt_count"] == 100
    assert context.groups[4]["request_attempt_count"] == 24
    assert context.groups[5]["request_attempt_count"] == 100
    assert context.groups[6]["metrics"]["termination"] == "upstream-record-cap"
    assert context.groups[7]["metrics"]["termination"] == "upstream-record-cap"
    assert context.groups[2]["metrics"]["cell_record_counts"] == {
        "2012-h1": 25,
        "2012-h2": 25,
        "2013-h1": 25,
        "2013-h2": 25,
    }
    assert context.groups[2]["metrics"]["category_counts"] == {
        "astro-ph.GA": 100
    }
    assert fetcher.calls[0]["url"].endswith(
        "/enwiki/20260801/dumpstatus.json"
    )
    assert fetcher.calls[1]["url"] == "https://archive.org/metadata/stackexchange"
    cell_transcript = (
        ("2012-h1", "20120101", "20120630", (5, 10, 15, 20, 0)),
        ("2012-h2", "20120701", "20121231", (5, 0, 10, 15, 20)),
        ("2013-h1", "20130101", "20130630", (20, 15, 0, 5, 10)),
        ("2013-h2", "20130701", "20131231", (10, 15, 20, 0, 5)),
        ("2018-h1", "20180101", "20180630", (20, 15, 10, 0, 5)),
        ("2018-h2", "20180701", "20181231", (0, 5, 10, 15, 20)),
        ("2019-h1", "20190101", "20190630", (0, 10, 15, 5, 20)),
        ("2019-h2", "20190701", "20191231", (20, 0, 5, 10, 15)),
    )
    category_clause = " OR ".join(
        f"cat:{category}" for category in profile["arxiv"]["query_categories"]
    )
    expected_ids_by_window: dict[str, list[str]] = {"early": [], "late": []}
    call_index = 2
    for cell_index, (_cell_id, start_date, end_date, starts) in enumerate(
        cell_transcript
    ):
        exact_search_query = (
            f"({category_clause}) AND "
            f"submittedDate:[{start_date}0000 TO {end_date}2359]"
        )
        query = parse_qs(urlsplit(fetcher.calls[call_index]["url"]).query)
        assert query == {
            "search_query": [exact_search_query],
            "start": ["0"],
            "max_results": ["1"],
            "sortBy": ["submittedDate"],
            "sortOrder": ["ascending"],
        }
        call_index += 1
        year = int(start_date[:4])
        month = int(start_date[4:6])
        window = "early" if cell_index < 4 else "late"
        for start in starts:
            query = parse_qs(urlsplit(fetcher.calls[call_index]["url"]).query)
            assert query == {
                "search_query": [exact_search_query],
                "start": [str(start)],
                "max_results": ["5"],
                "sortBy": ["submittedDate"],
                "sortOrder": ["ascending"],
            }
            expected_ids_by_window[window].extend(
                f"{year % 100:02d}{month:02d}.{start + offset + 1:05d}"
                for offset in range(5)
            )
            call_index += 1
        if cell_index == 3:
            observed_ids = [
                parse_qs(urlsplit(call["url"]).query)["identifier"][0].split(":", 2)[2]
                for call in fetcher.calls[26:126]
            ]
            assert observed_ids == expected_ids_by_window["early"]
            for call, identifier in zip(fetcher.calls[26:126], observed_ids):
                assert parse_qs(urlsplit(call["url"]).query) == {
                    "verb": ["GetRecord"],
                    "metadataPrefix": ["arXivRaw"],
                    "identifier": [f"oai:arXiv.org:{identifier}"],
                }
            call_index = 126
    observed_late_ids = [
        parse_qs(urlsplit(call["url"]).query)["identifier"][0].split(":", 2)[2]
        for call in fetcher.calls[150:250]
    ]
    assert observed_late_ids == expected_ids_by_window["late"]
    for call, identifier in zip(fetcher.calls[150:250], observed_late_ids):
        assert parse_qs(urlsplit(call["url"]).query) == {
            "verb": ["GetRecord"],
            "metadataPrefix": ["arXivRaw"],
            "identifier": [f"oai:arXiv.org:{identifier}"],
        }
    assert parse_qs(urlsplit(fetcher.calls[250]["url"]).query) == {
        "verb": ["ListRecords"],
        "metadataPrefix": ["oai_dc"],
        "from": ["2012-01-01"],
        "until": ["2013-12-31"],
        "set": ["pmc-open"],
    }
    assert parse_qs(urlsplit(fetcher.calls[251]["url"]).query) == {
        "verb": ["ListRecords"],
        "metadataPrefix": ["oai_dc"],
        "from": ["2018-01-01"],
        "until": ["2019-12-31"],
        "set": ["pmc-open"],
    }
    assert all(
        call["delay_seconds"] == 3.0
        for call in fetcher.calls[3:250]
        if "arxiv.org" in call["url"]
    )

    candidate_records = [
        json.loads(line)
        for line in (tmp_path / "local" / "arxiv-early-candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    invalid_candidate = deepcopy(candidate_records[0])
    invalid_candidate["timestamp_semantics"] = "revision"
    invalid_candidate["exclusion_reasons"] = []
    invalid_candidate["review_strata"] = ["eligible-random"]
    assert gate_module._private_record_errors(
        context,
        "arxiv-early-candidate-sample",
        [invalid_candidate],
    )

    enriched_records = [
        json.loads(line)
        for line in (tmp_path / "local" / "arxiv-early-enriched.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    invalid_enrichment = deepcopy(enriched_records[0])
    invalid_enrichment["license_id"] = "missing"
    invalid_enrichment["license_locator"] = "missing-license"
    invalid_enrichment["rights_status"] = "eligible"
    invalid_enrichment["eligibility"] = "eligible"
    assert gate_module._private_record_errors(
        context,
        "arxiv-early-exact-enrichment",
        [invalid_enrichment],
    )
    invalid_version = deepcopy(enriched_records[0])
    invalid_version["version_status"] = "latest-only"
    invalid_version["exclusion_reasons"] = ["multiple-versions-heldout"]
    assert gate_module._private_record_errors(
        context,
        "arxiv-early-exact-enrichment",
        [invalid_version],
    )

    pmc_records = [
        json.loads(line)
        for line in (tmp_path / "local" / "pmc-early-metadata.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    invalid_pmc = deepcopy(pmc_records[0])
    invalid_pmc["source_metadata"]["subject_allowed"] = False
    invalid_pmc["source_metadata"]["lifecycle_date_value_count"] = 0
    invalid_pmc["source_metadata"]["oai_identifier_count"] = 0
    invalid_pmc["exclusion_reasons"] = []
    invalid_pmc["review_strata"] = ["eligible-random"]
    assert gate_module._private_record_errors(
        context,
        "pmc-early-range-metadata",
        [invalid_pmc],
    )

    cross_listed, _, _ = gate_module.parse_arxiv_raw_oai(
        (FIXTURES / "arxiv_oai_sample.xml").read_bytes(),
        windows=context.windows,
        allowed_category_prefixes=tuple(profile["arxiv"]["allowed_category_prefixes"]),
        forbidden_category_prefixes=tuple(
            profile["arxiv"]["forbidden_category_prefixes"]
        ),
    )
    assert gate_module._private_record_errors(
        context,
        "arxiv-late-exact-enrichment",
        [cross_listed[-1]],
    ) == ()

    aggregate = success_aggregate(context)
    assert validate_aggregate(
        aggregate,
        expected_bindings=bound.bindings,
    ) == ()
    for byte_count in (0, 20_000_001):
        forged = deepcopy(aggregate)
        forged["groups"][0]["responses"][0]["byte_count"] = byte_count
        forged["output_sha256"] = gate_module.canonical_json_sha256(
            {key: value for key, value in forged.items() if key != "output_sha256"}
        )
        assert any(
            "byte identity is invalid" in error
            for error in validate_aggregate(
                forged,
                expected_bindings=bound.bindings,
            )
        )
    duplicate_url = deepcopy(aggregate)
    first_url = duplicate_url["groups"][2]["responses"][0][
        "requested_url_hmac_sha256"
    ]
    duplicate_url["groups"][2]["responses"][1][
        "requested_url_hmac_sha256"
    ] = first_url
    duplicate_url["groups"][2]["responses"][1][
        "final_url_hmac_sha256"
    ] = first_url
    duplicate_url["output_sha256"] = gate_module.canonical_json_sha256(
        {key: value for key, value in duplicate_url.items() if key != "output_sha256"}
    )
    assert "private source request commitments are not unique" in validate_aggregate(
        duplicate_url,
        expected_bindings=bound.bindings,
    )
    duplicate_response = deepcopy(aggregate)
    duplicate_response["groups"][2]["responses"][1][
        "response_hmac_sha256"
    ] = duplicate_response["groups"][2]["responses"][0][
        "response_hmac_sha256"
    ]
    duplicate_response["output_sha256"] = gate_module.canonical_json_sha256(
        {
            key: value
            for key, value in duplicate_response.items()
            if key != "output_sha256"
        }
    )
    assert "private source response commitments are not unique" in validate_aggregate(
        duplicate_response,
        expected_bindings=bound.bindings,
    )
    duplicate_cell = deepcopy(aggregate)
    cell_commitments = duplicate_cell["groups"][2]["metrics"][
        "cell_selection_hmac_sha256"
    ]
    cell_commitments["2012-h2"] = cell_commitments["2012-h1"]
    duplicate_cell["output_sha256"] = gate_module.canonical_json_sha256(
        {key: value for key, value in duplicate_cell.items() if key != "output_sha256"}
    )
    assert "arXiv cell-selection commitments are not unique" in validate_aggregate(
        duplicate_cell,
        expected_bindings=bound.bindings,
    )
    missing_query_coverage = deepcopy(aggregate)
    missing_query_coverage["groups"][2]["metrics"]["category_counts"] = {
        "other-arxiv-category": 100,
    }
    missing_query_coverage["output_sha256"] = gate_module.canonical_json_sha256(
        {
            key: value
            for key, value in missing_query_coverage.items()
            if key != "output_sha256"
        }
    )
    assert any(
        "category coverage is invalid" in error
        for error in validate_aggregate(
            missing_query_coverage,
            expected_bindings=bound.bindings,
        )
    )
    impossible_yield = deepcopy(aggregate)
    yield_metrics = impossible_yield["groups"][3]["metrics"]
    yield_metrics["eligibility_counts"] = {"eligible": 100}
    yield_metrics["rights_status_counts"] = {"unresolved": 100}
    yield_metrics["license_id_counts"] = {"missing": 100}
    yield_metrics["version_status_counts"] = {"latest-only": 100}
    impossible_yield["output_sha256"] = gate_module.canonical_json_sha256(
        {key: value for key, value in impossible_yield.items() if key != "output_sha256"}
    )
    assert any(
        "eligible yield exceeds its prerequisites" in error
        for error in validate_aggregate(
            impossible_yield,
            expected_bindings=bound.bindings,
        )
    )
    aggregate_payload = canonical_json_bytes(aggregate, pretty=True)
    receipt = success_receipt(
        context,
        aggregate_payload=aggregate_payload,
        final_binding_status="matched",
    )
    assert validate_receipt(
        receipt,
        expected_bindings=bound.bindings,
        aggregate_payload=aggregate_payload,
        commitment_key=COMMITMENT_KEY,
    ) == ()
    assert all(
        type(response["byte_count"]) is int
        for group in receipt["groups"][:2]
        for response in group["responses"]
    )
    assert all(
        response["byte_count"] is None
        for group in receipt["groups"][2:]
        for response in group["responses"]
    )
    assert all(
        type(artifact["size_bytes"]) is int
        for artifact in receipt["private_artifacts"][:2]
    )
    assert all(
        artifact["size_bytes"] is None
        for artifact in receipt["private_artifacts"][2:]
    )
    disclosed_length = deepcopy(receipt)
    disclosed_length["groups"][2]["responses"][0]["byte_count"] = 123
    disclosed_length["private_artifacts"][2]["size_bytes"] = 456
    disclosed_length = receipt_with_self_hash(
        {
            key: value
            for key, value in disclosed_length.items()
            if key != "receipt_sha256"
        }
    )
    assert any(
        "length was disclosed" in error
            for error in validate_receipt(
                disclosed_length,
                expected_bindings=bound.bindings,
                aggregate_payload=aggregate_payload,
                commitment_key=COMMITMENT_KEY,
            )
    )
    for label, field in (
        ("runtime_00", "raw_sha256"),
        ("source_registry", "raw_sha256"),
        ("source_registry", "canonical_sha256"),
    ):
        forged = deepcopy(receipt)
        forged["git"]["inputs"][label][field] = "0" * 64
        forged = receipt_with_self_hash(
            {
                key: value
                for key, value in forged.items()
                if key != "receipt_sha256"
            }
        )
        assert any(
            "input bindings do not match preflight" in error
            for error in validate_receipt(
                forged,
                expected_bindings=bound.bindings,
                aggregate_payload=aggregate_payload,
                commitment_key=COMMITMENT_KEY,
            )
        )
    forged_aggregate_binding = deepcopy(receipt)
    forged_aggregate_binding["aggregate"] = {
        "file_name": "aggregate.json",
        "size_bytes": 1,
        "sha256": "0" * 64,
    }
    forged_aggregate_binding = receipt_with_self_hash(
        {
            key: value
            for key, value in forged_aggregate_binding.items()
            if key != "receipt_sha256"
        }
    )
    assert any(
        "does not bind the aggregate bytes" in error
        for error in validate_receipt(
            forged_aggregate_binding,
            expected_bindings=bound.bindings,
            aggregate_payload=aggregate_payload,
            commitment_key=COMMITMENT_KEY,
        )
    )
    divergent_base = deepcopy(receipt)
    divergent_base["runtime"]["python_version"] = "99.0.0"
    divergent_base = receipt_with_self_hash(
        {
            key: value
            for key, value in divergent_base.items()
            if key != "receipt_sha256"
        }
    )
    assert any(
        "receipt and aggregate base evidence differ" in error
        for error in validate_receipt(
            divergent_base,
            expected_bindings=bound.bindings,
            aggregate_payload=aggregate_payload,
            commitment_key=COMMITMENT_KEY,
        )
    )
    coherently_forged_aggregate = deepcopy(aggregate)
    coherently_forged_aggregate["runtime"]["python_version"] = "99.0.0"
    coherently_forged_aggregate["output_sha256"] = gate_module.canonical_json_sha256(
        {
            key: value
            for key, value in coherently_forged_aggregate.items()
            if key != "output_sha256"
        }
    )
    coherently_forged_aggregate_payload = canonical_json_bytes(
        coherently_forged_aggregate,
        pretty=True,
    )
    coherently_forged_receipt = deepcopy(receipt)
    coherently_forged_receipt["runtime"]["python_version"] = "99.0.0"
    coherently_forged_receipt["aggregate"]["size_bytes"] = len(
        coherently_forged_aggregate_payload
    )
    coherently_forged_receipt["aggregate"]["sha256"] = hashlib.sha256(
        coherently_forged_aggregate_payload
    ).hexdigest()
    coherently_forged_receipt = receipt_with_self_hash(
        {
            key: value
            for key, value in coherently_forged_receipt.items()
            if key != "receipt_sha256"
        }
    )
    assert any(
        "source receipt commitment differs" in error
        for error in validate_receipt(
            coherently_forged_receipt,
            expected_bindings=bound.bindings,
            aggregate_payload=coherently_forged_aggregate_payload,
            commitment_key=COMMITMENT_KEY,
        )
    )
    receipt_payload = canonical_json_bytes(receipt, pretty=True)
    publication = profile["publication"]
    reservation.publish_success(
        private_files=publication["private_artifact_files"],
        aggregate_file=publication["aggregate_file"],
        aggregate_payload=aggregate_payload,
        receipt_file=publication["receipt_file"],
        receipt_payload=receipt_payload,
    )

    for file_name in [
        *publication["private_artifact_files"],
        publication["aggregate_file"],
        publication["receipt_file"],
    ]:
        assert (tmp_path / "local" / file_name).read_bytes() == (
            tmp_path / "backup" / file_name
        ).read_bytes()
    assert not validate_public_receipt(receipt)


def test_consumed_failure_preserves_prefix_and_one_private_receipt(tmp_path: Path) -> None:
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)
    fetcher = FixtureFetcher(fail_at=3)

    with pytest.raises(SourceGateError) as raised:
        run_gate(
            bound,
            reservation,
            fetcher,
            commitment_key=COMMITMENT_KEY,
        )
    failure = raised.value
    context = failure.context
    assert context is not None
    assert [group["status"] for group in context.groups] == [
        "complete",
        "complete",
        "failed",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
        "not-started",
    ]
    assert context.request_attempt_count == 4
    assert context.completed_response_count == 3
    assert "private detail" not in failure.reason_code

    receipt = failure_receipt(
        context,
        failure,
        final_binding_status="matched",
    )
    assert validate_receipt(
        receipt,
        expected_bindings=bound.bindings,
        commitment_key=COMMITMENT_KEY,
    ) == ()
    wrong_parser_family = deepcopy(receipt)
    wrong_parser_family["failure"]["reason_code"] = "inventory-parse-failed"
    wrong_parser_family = receipt_with_self_hash(
        {
            key: value
            for key, value in wrong_parser_family.items()
            if key != "receipt_sha256"
        }
    )
    assert validate_receipt(
        wrong_parser_family,
        expected_bindings=bound.bindings,
        commitment_key=COMMITMENT_KEY,
    )
    publication = profile["publication"]
    reservation.publish_failure(
        private_files=publication["private_artifact_files"],
        aggregate_file=publication["aggregate_file"],
        receipt_file=publication["receipt_file"],
        receipt_payload=canonical_json_bytes(receipt, pretty=True),
    )
    expected = {
        "wikimedia-inventory.json",
        "stackexchange-inventory.json",
        "receipt.json",
    }
    assert {path.name for path in (tmp_path / "local").iterdir()} == expected
    assert {path.name for path in (tmp_path / "backup").iterdir()} == expected
    assert b"private detail" not in (tmp_path / "local" / "receipt.json").read_bytes()


def test_consumed_contract_failure_publishes_an_actionable_closed_subtype(
    tmp_path: Path,
) -> None:
    assert gate_module._failure_subtype(
        "private source request commitments are not unique",
        group="post-run",
        stage="post-run-integrity",
        reason_code="contract-validation-failed",
    ) == "duplicate-identity"
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)

    def start_drift(payload: bytes) -> bytes:
        return payload.replace(
            b"<opensearch:startIndex>5</",
            b"<opensearch:startIndex>0</",
            1,
        )

    with pytest.raises(SourceGateError) as raised:
        run_gate(
            bound,
            reservation,
            MutatingFixtureFetcher(mutate_at=3, transform=start_drift),
            commitment_key=COMMITMENT_KEY,
        )
    failure = raised.value
    assert failure.reason_code == "paging-contract-failed"
    assert failure.failure_subtype == "paging-contract"
    context = failure.context
    assert context is not None
    receipt = failure_receipt(
        context,
        failure,
        final_binding_status="matched",
    )
    assert receipt["failure"]["failure_subtype"] == "paging-contract"
    assert validate_receipt(
        receipt,
        expected_bindings=bound.bindings,
        commitment_key=COMMITMENT_KEY,
    ) == ()

    forged = deepcopy(receipt)
    forged["failure"]["failure_subtype"] = "transport"
    forged = receipt_with_self_hash(
        {key: value for key, value in forged.items() if key != "receipt_sha256"}
    )
    assert any(
        "subtype does not match" in error
        for error in validate_receipt(
            forged,
            expected_bindings=bound.bindings,
            commitment_key=COMMITMENT_KEY,
        )
    )
    coherently_reclassified = deepcopy(receipt)
    coherently_reclassified["failure"]["reason_code"] = (
        "timestamp-contract-failed"
    )
    coherently_reclassified["failure"]["failure_subtype"] = "timestamp-contract"
    coherently_reclassified = receipt_with_self_hash(
        {
            key: value
            for key, value in coherently_reclassified.items()
            if key != "receipt_sha256"
        }
    )
    assert any(
        "source receipt commitment differs" in error
        for error in validate_receipt(
            coherently_reclassified,
            expected_bindings=bound.bindings,
            commitment_key=COMMITMENT_KEY,
        )
    )
    for mutation in ("final-binding", "detail-commitment"):
        tampered = deepcopy(receipt)
        if mutation == "final-binding":
            tampered["final_binding_status"] = "failed"
        else:
            tampered["failure"]["detail_hmac_sha256"] = "0" * 64
        tampered = receipt_with_self_hash(
            {
                key: value
                for key, value in tampered.items()
                if key != "receipt_sha256"
            }
        )
        assert any(
            "source receipt commitment differs" in error
            for error in validate_receipt(
                tampered,
                expected_bindings=bound.bindings,
                commitment_key=COMMITMENT_KEY,
            )
        )
    reservation.rollback()


@pytest.mark.parametrize(
    ("mutate_at", "before", "after", "expected_reason"),
    [
        (
            2,
            b'<category term="astro-ph.GA" />',
            b'<category term="astro-ph.GA"><foreign>cs.AI</foreign></category>',
            "category-contract-failed",
        ),
        (
            26,
            b"<license>https://creativecommons.org/licenses/by/4.0/</license>",
            b"<license>https://creativecommons.org/licenses/by/4.0/"
            b"<foreign>all rights reserved</foreign></license>",
            "rights-contract-failed",
        ),
        (
            250,
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/</dc:rights>",
            b"<dc:rights>https://creativecommons.org/licenses/by/4.0/"
            b"<foreign>all rights reserved</foreign></dc:rights>",
            "rights-contract-failed",
        ),
    ],
)
def test_gate_stops_on_malformed_decision_bearing_xml(
    tmp_path: Path,
    mutate_at: int,
    before: bytes,
    after: bytes,
    expected_reason: str,
) -> None:
    bound = _bound()
    reservation = _reservation(tmp_path, bound.values["metadata_gate_profile"])

    with pytest.raises(SourceGateError) as raised:
        run_gate(
            bound,
            reservation,
            MutatingFixtureFetcher(
                mutate_at=mutate_at,
                transform=lambda payload: payload.replace(before, after, 1),
            ),
            commitment_key=COMMITMENT_KEY,
        )
    failure = raised.value
    assert failure.reason_code == expected_reason
    context = failure.context
    assert context is not None
    failed_index = next(
        index
        for index, group in enumerate(context.groups)
        if group["status"] == "failed"
    )
    assert all(
        group["status"] == "not-started"
        for group in context.groups[failed_index + 1 :]
    )
    reservation.rollback()


def test_pmc_two_page_natural_end_and_pagination_failures(tmp_path: Path) -> None:
    context, reservation = _pmc_only_context(tmp_path / "natural")
    fetcher = PmcPageFetcher(
        [
            _pmc_page(
                year=2012,
                base=10_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token="page-two",
            ),
            _pmc_page(
                year=2012,
                base=20_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token=None,
                request_token="page-two",
            ),
        ]
    )
    try:
        gate_module._run_pmc(context, fetcher, window="early")
        metrics = context.group_record("pmc-early-range-metadata")["metrics"]
        assert metrics["upstream_records_seen"] == 80
        assert metrics["termination"] == "natural-endpoint"
        assert len(fetcher.calls) == 2
        assert parse_qs(urlsplit(fetcher.calls[0]).query) == {
            "verb": ["ListRecords"],
            "metadataPrefix": ["oai_dc"],
            "from": ["2012-01-01"],
            "until": ["2013-12-31"],
            "set": ["pmc-open"],
        }
        assert parse_qs(urlsplit(fetcher.calls[1]).query) == {
            "verb": ["ListRecords"],
            "resumptionToken": ["page-two"],
        }
    finally:
        reservation.rollback()

    duplicate_context, duplicate_reservation = _pmc_only_context(
        tmp_path / "duplicate"
    )
    duplicate_fetcher = PmcPageFetcher(
        [
            _pmc_page(
                year=2012,
                base=30_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token="duplicate-page",
            ),
            _pmc_page(
                year=2012,
                base=30_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token=None,
                request_token="duplicate-page",
            ),
        ]
    )
    try:
        with pytest.raises(gate_module.PmcMetadataError, match="repeated across pages"):
            gate_module._run_pmc(duplicate_context, duplicate_fetcher, window="early")
    finally:
        duplicate_reservation.rollback()

    repeated_context, repeated_reservation = _pmc_only_context(
        tmp_path / "repeated-token"
    )
    repeated_fetcher = PmcPageFetcher(
        [
            _pmc_page(
                year=2012,
                base=40_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token="same-token",
            ),
            _pmc_page(
                year=2012,
                base=50_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=40,
                next_token="same-token",
                request_token="same-token",
            ),
        ]
    )
    try:
        with pytest.raises(SourceAuditError, match="resumption token repeated"):
            gate_module._run_pmc(repeated_context, repeated_fetcher, window="early")
    finally:
        repeated_reservation.rollback()

    over_context, over_reservation = _pmc_only_context(tmp_path / "over-cap")
    over_fetcher = PmcPageFetcher(
        [
            _pmc_page(
                year=2012,
                base=60_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=60,
                next_token="over-page",
            ),
            _pmc_page(
                year=2012,
                base=70_000,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=50,
                next_token=None,
                request_token="over-page",
            ),
        ]
    )
    try:
        with pytest.raises(SourceAuditError, match="upstream-record cap"):
            gate_module._run_pmc(over_context, over_fetcher, window="early")
    finally:
        over_reservation.rollback()

    capped_context, capped_reservation = _pmc_only_context(
        tmp_path / "request-cap"
    )
    capped_fetcher = PmcPageFetcher(
        [
            _pmc_page(
                year=2012,
                base=80_000 + page * 100,
                from_date="2012-01-01",
                until_date="2013-12-31",
                record_count=9,
                next_token=f"token-{page + 1}",
                request_token=None if page == 0 else f"token-{page}",
            )
            for page in range(10)
        ]
    )
    try:
        with pytest.raises(SourceAuditError, match="request cap"):
            gate_module._run_pmc(capped_context, capped_fetcher, window="early")
        assert len(capped_fetcher.calls) == 10
    finally:
        capped_reservation.rollback()


def test_arxiv_candidate_pages_fail_closed_on_count_paging_and_order_drift(
    tmp_path: Path,
) -> None:
    def total_below_floor(payload: bytes) -> bytes:
        return payload.replace(b"<opensearch:totalResults>25</", b"<opensearch:totalResults>24</", 1)

    def start_drift(payload: bytes) -> bytes:
        return payload.replace(b"<opensearch:startIndex>5</", b"<opensearch:startIndex>0</", 1)

    def short_page(payload: bytes) -> bytes:
        start = payload.rfind(b"<entry>")
        end = payload.find(b"</entry>", start) + len(b"</entry>")
        return payload[:start] + payload[end:]

    def order_drift(payload: bytes) -> bytes:
        return payload.replace(
            b"2012-01-15T12:00:00Z",
            b"2012-01-16T12:00:00Z",
            2,
        )

    cases = (
        (0, total_below_floor, "cell total"),
        (1, start_drift, "paging identity"),
        (1, short_page, "paging identity"),
        (1, order_drift, "submitted-date order"),
    )
    for index, (mutate_at, transform, message) in enumerate(cases):
        context, reservation = _candidate_only_context(tmp_path / f"case-{index}")
        try:
            with pytest.raises(SourceAuditError, match=message):
                gate_module._run_arxiv_candidates(
                    context,
                    MutatingFixtureFetcher(
                        mutate_at=mutate_at,
                        transform=transform,
                    ),
                    window="early",
                )
        finally:
            reservation.rollback()


def test_arxiv_candidate_windows_reject_cross_window_identifier_reuse(
    tmp_path: Path,
) -> None:
    context, reservation = _candidate_only_context(tmp_path)
    try:
        gate_module._run_arxiv_candidates(context, FixtureFetcher(), window="early")
        context.group_record("arxiv-early-exact-enrichment")["status"] = "complete"

        def reuse_early_identifier(payload: bytes) -> bytes:
            return payload.replace(b"1801.00021", b"1201.00006", 1)

        with pytest.raises(SourceAuditError, match="early/late samples"):
            gate_module._run_arxiv_candidates(
                context,
                MutatingFixtureFetcher(
                    mutate_at=1,
                    transform=reuse_early_identifier,
                ),
                window="late",
            )
    finally:
        reservation.rollback()


def test_public_validation_rejects_native_ids_hosts_and_prose() -> None:
    for key, value in (
        ("native_item_id", "1301.00001"),
        ("safe", "1301.00001"),
        ("safe", "https://oaipmh.arxiv.org/oai"),
        ("rights", "arbitrary prose"),
    ):
        receipt = receipt_with_self_hash({"schema_version": 1, key: value})
        assert validate_public_receipt(receipt)


def test_response_identity_rejects_redirect_even_with_forged_fixture() -> None:
    response = MetadataResponse(
        payload=b"{}",
        requested_url="https://export.arxiv.org/api/query?a=1",
        final_url="https://export.arxiv.org/api/query?a=2",
        status=200,
        content_type="application/atom+xml",
    )
    with pytest.raises(SourceAuditError, match="redirected"):
        response_identity(
            response,
            group="arxiv-early-candidate-sample",
            ordinal=0,
            expected_url="https://export.arxiv.org/api/query?a=1",
            commitment_key=COMMITMENT_KEY,
        )


def _small_reservation(tmp_path: Path) -> SourceOutputReservation:
    local = tmp_path / "local"
    backup = tmp_path / "backup"
    local.mkdir()
    backup.mkdir()
    return SourceOutputReservation(
        SourceOutputRoots(run_dir=local, backup_dir=backup),
        ["private.json", "aggregate.json", "receipt.json"],
    )


def test_success_publication_rejects_hardlink_added_after_close(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reservation = _small_reservation(tmp_path)
    reservation.write_mirrored("private.json", b"SECRET\n")
    alias = tmp_path / "external-alias.json"
    original_close = reservation._close

    def attacked_close(key: tuple[str, str]) -> None:
        original_close(key)
        if key == ("local", "private.json"):
            os.link(tmp_path / "local" / "private.json", alias)

    monkeypatch.setattr(reservation, "_close", attacked_close)
    with pytest.raises(SourceAuditError, match="identity changed|bytes changed"):
        reservation.publish_success(
            private_files=["private.json"],
            aggregate_file="aggregate.json",
            aggregate_payload=b"{}\n",
            receipt_file="receipt.json",
            receipt_payload=b"{}\n",
        )
    alias.unlink()
    reservation.rollback()


def test_failure_publication_rejects_hardlinked_partial_private_bytes(
    tmp_path: Path,
) -> None:
    reservation = _small_reservation(tmp_path)
    descriptor = reservation.descriptors[("local", "private.json")]
    os.write(descriptor, b"PARTIAL-PRIVATE")
    os.fsync(descriptor)
    alias = tmp_path / "partial-alias.json"
    os.link(tmp_path / "local" / "private.json", alias)

    with pytest.raises(SourceAuditError, match="descriptor changed|refusing to remove"):
        reservation.publish_failure(
            private_files=["private.json"],
            aggregate_file="aggregate.json",
            receipt_file="receipt.json",
            receipt_payload=b"{}\n",
        )
    assert alias.read_bytes() == b"PARTIAL-PRIVATE"
    alias.unlink()
    reservation.rollback()


def test_private_record_validation_rejects_prose_in_reviewed_value(
    tmp_path: Path,
) -> None:
    bound = _bound()
    profile = bound.values["metadata_gate_profile"]
    reservation = _reservation(tmp_path, profile)
    context = gate_module.GateContext(
        bound=bound,
        reservation=reservation,
        profile=profile,
        windows=gate_module.parse_era_windows(bound.values["source_registry"]),
        commitment_key=COMMITMENT_KEY,
    )
    payload = json.loads(
        (FIXTURES / "wikimedia_dumpstatus_sample.json")
        .read_text(encoding="utf-8")
        .replace("20260101", "20260801")
    )
    records = gate_module.parse_wikimedia_dumpstatus(
        payload,
        source_locator="https://dumps.wikimedia.org/enwiki/20260801/dumpstatus.json",
        snapshot_id="20260801",
        required_job_name="metahistorybz2dump",
    )
    records[0]["source_metadata"]["dumpstatus_schema_version"] = (
        "arbitrary upstream prose"
    )
    assert gate_module._private_record_errors(
        context,
        "wikimedia-inventory",
        records,
    )
    reservation.rollback()


def test_gate_script_requires_isolated_no_site_startup_and_plan_is_read_only(
    tmp_path: Path,
) -> None:
    script = ROOT / "scripts" / "run_source_metadata_gate.py"
    rejected = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert rejected.returncode != 0
    assert "requires isolated startup" in rejected.stderr

    cache_root = ROOT / "artifacts" / "local"
    before = {
        path.name
        for path in cache_root.glob("chronopersona-source-gate-no-bytecode-*")
    }
    planned = subprocess.run(
        [sys.executable, "-I", "-S", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    after = {
        path.name
        for path in cache_root.glob("chronopersona-source-gate-no-bytecode-*")
    }
    assert planned.returncode == 0, planned.stderr
    assert json.loads(planned.stdout)["mode"] == "plan"
    assert before == after
    assert tuple(tmp_path.iterdir()) == ()

    for arguments, message in (
        (("--allow-network",), "meaningful only with --execute"),
        (("--execute",), "requires --allow-network"),
        (
            ("--execute", "--allow-network"),
            "requires --expected-git-head",
        ),
    ):
        rejected_flags = subprocess.run(
            [sys.executable, "-I", "-S", str(script), *arguments],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
        )
        assert rejected_flags.returncode == 2
        assert message in rejected_flags.stderr
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize(
    "raw_path",
    [
        r"\\server\share\commitment-key.hex",
        r"//server/share/commitment-key.hex",
    ]
    + (
        [
            r"\\?\C:\private\commitment-key.hex",
            r"\\.\C:\private\commitment-key.hex",
            r"\??\C:\private\commitment-key.hex",
            r"\Device\HarddiskVolume1\private\commitment-key.hex",
        ]
        if os.name == "nt"
        else []
    ),
)
def test_private_paths_reject_network_and_device_namespaces_before_io(
    raw_path: str,
    monkeypatch,
) -> None:
    touched = False

    def unexpected_touch(*_args, **_kwargs) -> None:
        nonlocal touched
        touched = True
        raise AssertionError("filesystem inspection occurred")

    monkeypatch.setattr(source_audit_module, "_plain_directory", unexpected_touch)
    with pytest.raises(SourceAuditError, match="network or device namespace"):
        source_audit_module._validate_plain_absolute_parent(
            Path(raw_path),
            label="private commitment key",
        )
    assert touched is False


def test_private_paths_reject_mapped_remote_drives_before_traversal(
    tmp_path: Path,
    monkeypatch,
) -> None:
    touched = False

    def unexpected_touch(*_args, **_kwargs) -> None:
        nonlocal touched
        touched = True
        raise AssertionError("filesystem inspection occurred")

    monkeypatch.setattr(source_audit_module, "_windows_drive_is_remote", lambda _path: True)
    monkeypatch.setattr(source_audit_module, "_plain_directory", unexpected_touch)
    with pytest.raises(SourceAuditError, match="local drive"):
        source_audit_module._validate_plain_absolute_parent(
            tmp_path / "commitment-key.hex",
            label="private commitment key",
        )
    assert touched is False
