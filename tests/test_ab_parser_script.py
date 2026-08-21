from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from chronopersona.ab_parser_common import ABParserError


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_ab_parser_sample.py"


def _load_runner(monkeypatch):
    spec = importlib.util.spec_from_file_location("ab_runner_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    original_flags = sys.flags

    class IsolatedFlags:
        isolated = 1
        safe_path = True
        no_site = 1

        def __getattr__(self, name):
            return getattr(original_flags, name)

    monkeypatch.setattr(
        sys,
        "flags",
        IsolatedFlags(),
    )
    try:
        spec.loader.exec_module(module)
    finally:
        sys.flags = original_flags
    return module


def _run(*arguments: str, isolated: bool = True) -> subprocess.CompletedProcess[str]:
    command = [sys.executable]
    if isolated:
        command.extend(["-I", "-S"])
    command.extend([str(SCRIPT), *arguments])
    return subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_code(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_plan_mode_is_closed_read_only_and_deterministic() -> None:
    first = _run()
    second = _run()
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    payload = json.loads(first.stdout)
    assert payload == {
        "claim_ceiling": "tested-offline-synthetic-parser-engineering-only",
        "external_spend_cad": 0,
        "filesystem_writes_performed": False,
        "live_source_access_permitted": False,
        "mode": "plan",
        "network_access_permitted": False,
        "profile_id": "ab-parser-sample-v0",
        "profile_path": "configs/sources/ab-parser-sample-v0.json",
        "schema_version": 1,
        "selection_count": 6,
        "synthetic_fixture_only": True,
    }


def test_script_requires_isolated_no_site_startup() -> None:
    completed = _run(isolated=False)
    assert completed.returncode == 2
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "failure_reason": "argument-contract-failed",
        "failure_stage": "arguments",
        "profile_id": "ab-parser-sample-v0",
        "schema_version": 1,
        "status": "failed",
        "valid_evidence_published": False,
    }


def test_runtime_import_failure_emits_one_closed_terminal_without_stderr(tmp_path) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    isolated_script = scripts / SCRIPT.name
    isolated_script.write_bytes(SCRIPT.read_bytes())
    completed = subprocess.run(
        [sys.executable, "-I", "-S", str(isolated_script)],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert completed.stderr == ""
    assert json.loads(completed.stdout) == {
        "failure_reason": "binding-failed",
        "failure_stage": "binding",
        "profile_id": "ab-parser-sample-v0",
        "schema_version": 1,
        "status": "failed",
        "valid_evidence_published": False,
    }


def test_execution_arguments_are_all_or_nothing_and_no_live_flags_exist() -> None:
    missing = _run("--execute-fixture")
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["failure_reason"] == "argument-contract-failed"
    plan_override = _run("--expected-git-head", "a" * 40)
    assert plan_override.returncode == 2
    assert json.loads(plan_override.stdout)["valid_evidence_published"] is False
    unknown = _run("--allow-network")
    assert unknown.returncode == 2
    assert unknown.stderr == ""
    assert json.loads(unknown.stdout)["failure_reason"] == "argument-contract-failed"


def test_plan_and_argument_failure_return_delivery_error_when_stdout_breaks() -> None:
    loader = f"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location('ab_runner', {str(SCRIPT)!r})
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
class Broken:
    def write(self, value): raise OSError('closed')
    def flush(self): raise OSError('closed')
sys.stdout = Broken()
plan = module.main([])
argument = module.main(['--allow-network'])
sys.stdout = sys.__stdout__
print(plan, argument)
"""
    completed = _run_code(loader)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout.strip() == "3 3"


@pytest.mark.parametrize("failure_path", ["success", "failure"])
def test_release_interrupt_returns_delivery_error_without_second_terminal(
    tmp_path, monkeypatch, capsys, failure_path
) -> None:
    runner = _load_runner(monkeypatch)
    profile = {
        "publication": {
            "private_records_file": "private-records.jsonl",
            "aggregate_file": "aggregate.json",
            "receipt_file": "receipt.json",
        },
        "limits": {
            "max_private_output_bytes": 1024,
            "max_aggregate_output_bytes": 1024,
            "max_receipt_output_bytes": 1024,
        },
        "fixture_bundle": {"selection_order": ["one"]},
        "claim_ceiling": "tested-offline-synthetic-parser-engineering-only",
    }
    bound = SimpleNamespace(profile=profile)

    class Transaction:
        def publish(self, artifacts):
            return {key: {} for key in artifacts}

        def rollback(self):
            return None

        def release_committed(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(runner.gate, "bind_fixture_inputs", lambda *a, **k: bound)
    monkeypatch.setattr(runner, "_runtime_modules", lambda: {})
    monkeypatch.setattr(runner.gate, "verify_runtime_module_paths", lambda *a, **k: None)
    monkeypatch.setattr(runner.gate, "rebind_fixture_inputs", lambda *a, **k: bound)
    monkeypatch.setattr(runner.gate, "prepare_output_run", lambda *a, **k: tmp_path)
    monkeypatch.setattr(runner.gate, "ExactArtifactTransaction", lambda *a, **k: Transaction())
    if failure_path == "success":
        monkeypatch.setattr(runner.gate, "parse_fixture_bundle", lambda *a, **k: object())
        monkeypatch.setattr(
            runner.gate,
            "build_success_artifacts",
            lambda *a, **k: {
                "private-records.jsonl": b"",
                "aggregate.json": b"{}\n",
                "receipt.json": b"{}\n",
            },
        )
    else:
        def fail_parse(*args, **kwargs):
            raise ABParserError("validation", "validation-failed", "injected")

        monkeypatch.setattr(runner.gate, "parse_fixture_bundle", fail_parse)
        monkeypatch.setattr(
            runner.gate,
            "build_failure_artifacts",
            lambda *a, **k: {
                "private-records.jsonl": b"",
                "aggregate.json": b"{}\n",
                "receipt.json": b"{}\n",
            },
        )
    result = runner._execute(
        SimpleNamespace(expected_git_head="a" * 40, run_dir="ignored")
    )
    lines = capsys.readouterr().out.splitlines()
    assert result == 3
    assert len(lines) == 1
    assert json.loads(lines[0])["status"] == (
        "complete" if failure_path == "success" else "failed"
    )


def test_dirty_tree_blocks_fixture_execution_before_output_creation(tmp_path) -> None:
    run_name = "artifacts/local/ab-parser-sample/test-dirty-gate"
    target = ROOT / run_name
    if target.exists():
        raise AssertionError("test output name unexpectedly exists")
    completed = _run(
        "--execute-fixture",
        "--expected-git-head",
        "3c49e2af27f0da36113085d5f746824f9a8148df",
        "--run-dir",
        run_name,
    )
    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["failure_stage"] == "binding"
    assert payload["valid_evidence_published"] is False
    assert not target.exists()
