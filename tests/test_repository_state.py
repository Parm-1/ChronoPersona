from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_top_level_status_files_share_the_current_gate_boundary() -> None:
    expected_terms = ("content-integrity gate", "externally blocked")
    for relative in ("README.md", "PROJECT_STATE.md", "PLAN.md", "AGENTS.md"):
        normalized = _read(relative).casefold()
        for term in expected_terms:
            assert term in normalized, f"{relative} omits current boundary: {term}"


def test_risk_register_and_decision_log_reflect_accepted_gate() -> None:
    risks = _read("RISKS.md")
    decisions = _read("docs/DECISIONS.md")

    assert "R-21" in risks
    assert "novelty remains unverified" not in risks.casefold()
    assert "D-021" in decisions
    assert "accepted at development-fixture level" in decisions


def test_one_time_recovery_scaffolding_is_not_tracked() -> None:
    workflow_names = {
        path.name for path in (ROOT / ".github" / "workflows").glob("*.yml")
    }
    forbidden_fragments = ("recovery", "hardening", "one-time", "snapshot")

    assert not any(
        fragment in name
        for name in workflow_names
        for fragment in forbidden_fragments
    )
    assert not (ROOT / "artifacts" / "import").exists()


def test_workflows_use_node24_action_majors_and_cover_python_313() -> None:
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "actions/checkout@v4" not in text
        assert "actions/checkout@v6" not in text
        assert "actions/setup-python@v5" not in text
        assert "actions/setup-python@v6" not in text
        assert "actions/checkout@v7" in text
        assert "actions/setup-python@v7" in text
        assert '"3.13"' in text


def test_final_review_preserves_the_pass_and_stop_decision() -> None:
    review = _read("reports/stage0/final_repository_review.md").casefold()

    assert "pass after final stage 0 hardening" in review
    assert "externally blocked" in review
    assert "then stop" in review


def test_generated_python_state_is_not_tracked_in_git() -> None:
    if not (ROOT / ".git").exists():
        return

    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    tracked = tuple(line for line in result.stdout.splitlines() if line)
    forbidden_files = {".coverage"}
    forbidden_suffixes = {".pyc", ".pyo"}
    forbidden_directories = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

    violations = [
        value
        for value in tracked
        if Path(value).name in forbidden_files
        or Path(value).suffix in forbidden_suffixes
        or forbidden_directories.intersection(Path(value).parts)
    ]
    assert violations == []
