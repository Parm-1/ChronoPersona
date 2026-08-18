"""Load, validate, and hash ChronoPersona evaluation registries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import re
from typing import Any


_ITEM_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_STATUSES = {"development", "frozen", "retired"}
_ALLOWED_DOMAINS = {
    "evidence-integration",
    "procedural-tradeoffs",
    "secure-system-decisions",
}
_REQUIRED_PRIMARY_DOMAINS = {
    "evidence-integration",
    "procedural-tradeoffs",
}
_REQUIRED_INVARIANCES = {"option-order", "paraphrase"}
_REQUIRED_REVIEWS = {
    "temporal-cues",
    "political-moral-wording",
    "direct-exposure",
    "contamination",
}
_ALLOWED_REVIEW_STATUSES = {"pending", "pass", "fail"}
_YEAR_CUE = re.compile(r"\b(?:18|19|20)\d{2}\b")
_MONTH_NAME_CUE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b"
)
_MONTH_WITH_DAY_CUE = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|"
    r"may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+\d{1,2}\b",
    re.IGNORECASE,
)
_PERIOD_CUE = re.compile(
    r"\b(?:historical|modern|contemporary|medieval|victorian|"
    r"century|decade|era)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")


class EvaluationRegistryFormatError(ValueError):
    """Raised when a JSONL evaluation registry is structurally unreadable."""


def load_evaluation_registry(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Load non-empty JSONL records while preserving file order."""

    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise EvaluationRegistryFormatError(
                    f"line {line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(value, dict):
                raise EvaluationRegistryFormatError(
                    f"line {line_number}: each record must be an object"
                )
            records.append(value)
    if not records:
        raise EvaluationRegistryFormatError(
            "evaluation registry must contain at least one item"
        )
    return tuple(records)


def sha256_file(path: str | Path) -> str:
    """Hash exact file bytes for immutable registry identity."""

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json_sha256(value: Any) -> str:
    """Hash a JSON-compatible value using stable canonical rendering."""

    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _word_count(value: str) -> int:
    return len(_WORD.findall(value))


def _temporal_cue(value: str) -> str | None:
    """Return the first explicit date/period cue without banning modal words.

    Month names are recognized when capitalized, or in any case when followed
    by a day number. This avoids treating ordinary words such as ``may`` and
    ``march`` as temporal cues while still rejecting explicit calendar dates.
    """

    for pattern in (
        _YEAR_CUE,
        _MONTH_NAME_CUE,
        _MONTH_WITH_DAY_CUE,
        _PERIOD_CUE,
    ):
        match = pattern.search(value)
        if match is not None:
            return match.group(0)
    return None


def _review_errors(
    item_id: str,
    reviews: Any,
    item_status: Any,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(reviews, Mapping):
        return [f"item {item_id!r} reviews must be an object"]

    missing = _REQUIRED_REVIEWS - set(reviews)
    if missing:
        errors.append(
            f"item {item_id!r} missing reviews: "
            + ", ".join(sorted(missing))
        )

    for review_name, raw_review in reviews.items():
        prefix = f"item {item_id!r} review {review_name!r}"
        if review_name not in _REQUIRED_REVIEWS:
            errors.append(f"{prefix} is not a recognized review")
            continue
        if not isinstance(raw_review, Mapping):
            errors.append(f"{prefix} must be an object")
            continue
        status = raw_review.get("status")
        if status not in _ALLOWED_REVIEW_STATUSES:
            errors.append(
                f"{prefix}.status must be pending, pass, or fail"
            )
        if not _nonempty_string(raw_review.get("reviewer")):
            errors.append(f"{prefix}.reviewer must not be empty")
        if not _nonempty_string(raw_review.get("note")):
            errors.append(f"{prefix}.note must not be empty")
        if item_status == "frozen" and status != "pass":
            errors.append(
                f"{prefix} must pass before an item is frozen"
            )
    return errors


def validate_evaluation_registry(
    items: Sequence[Mapping[str, Any]],
    *,
    require_primary_domains: bool = True,
) -> tuple[str, ...]:
    """Return all known construct, cue, and scoring-integrity errors."""

    errors: list[str] = []
    item_ids: list[str] = []
    domains: set[str] = set()

    if not items:
        return ("evaluation registry must contain at least one item",)

    for index, item in enumerate(items):
        location = f"items[{index}]"
        item_id = item.get("item_id")
        if not _nonempty_string(item_id) or not _ITEM_ID.fullmatch(item_id):
            errors.append(
                f"{location}.item_id must be a lowercase hyphenated slug"
            )
            item_label = location
        else:
            item_ids.append(item_id)
            item_label = f"item {item_id!r}"

        if item.get("schema_version") != 1:
            errors.append(f"{item_label} schema_version must be 1")

        status = item.get("status")
        if status not in _ALLOWED_STATUSES:
            errors.append(
                f"{item_label} status must be development, frozen, or retired"
            )

        domain = item.get("domain")
        if domain not in _ALLOWED_DOMAINS:
            errors.append(
                f"{item_label} domain must be one of "
                + ", ".join(sorted(_ALLOWED_DOMAINS))
            )
        else:
            domains.add(domain)

        for field in ("construct", "rationale", "direction_note"):
            if not _nonempty_string(item.get(field)):
                errors.append(f"{item_label} {field} must not be empty")

        poles = item.get("poles")
        pole_ids: list[str] = []
        if not isinstance(poles, list) or len(poles) != 2:
            errors.append(f"{item_label} poles must contain exactly two objects")
        else:
            for pole_index, pole in enumerate(poles):
                prefix = f"{item_label} poles[{pole_index}]"
                if not isinstance(pole, Mapping):
                    errors.append(f"{prefix} must be an object")
                    continue
                pole_id = pole.get("id")
                if not _nonempty_string(pole_id) or not _ITEM_ID.fullmatch(
                    pole_id
                ):
                    errors.append(
                        f"{prefix}.id must be a lowercase hyphenated slug"
                    )
                else:
                    pole_ids.append(pole_id)
                if not _nonempty_string(pole.get("label")):
                    errors.append(f"{prefix}.label must not be empty")
            if len(pole_ids) == 2 and len(set(pole_ids)) != 2:
                errors.append(f"{item_label} pole ids must be unique")

        reference_pole = item.get("reference_pole")
        if pole_ids and reference_pole not in pole_ids:
            errors.append(
                f"{item_label} reference_pole must name one of its poles"
            )

        invariances = item.get("expected_invariances")
        if not isinstance(invariances, list) or not all(
            _nonempty_string(value) for value in invariances
        ):
            errors.append(
                f"{item_label} expected_invariances must be a string list"
            )
        else:
            missing_invariances = _REQUIRED_INVARIANCES - set(invariances)
            if missing_invariances:
                errors.append(
                    f"{item_label} missing expected invariances: "
                    + ", ".join(sorted(missing_invariances))
                )

        forbidden_cues = item.get("forbidden_cues")
        if not isinstance(forbidden_cues, list) or not all(
            _nonempty_string(value) for value in forbidden_cues
        ):
            errors.append(
                f"{item_label} forbidden_cues must be a string list"
            )

        forms = item.get("forms")
        form_ids: list[str] = []
        prompts: list[str] = []
        candidate_orders: list[tuple[str, str]] = []
        if not isinstance(forms, list) or len(forms) < 2:
            errors.append(f"{item_label} must contain at least two forms")
        else:
            for form_index, form in enumerate(forms):
                prefix = f"{item_label} forms[{form_index}]"
                if not isinstance(form, Mapping):
                    errors.append(f"{prefix} must be an object")
                    continue
                form_id = form.get("form_id")
                if not _nonempty_string(form_id) or not _ITEM_ID.fullmatch(
                    form_id
                ):
                    errors.append(
                        f"{prefix}.form_id must be a lowercase hyphenated slug"
                    )
                else:
                    form_ids.append(form_id)

                prompt = form.get("prompt")
                if not _nonempty_string(prompt):
                    errors.append(f"{prefix}.prompt must not be empty")
                    prompt = ""
                else:
                    prompts.append(prompt)
                    if prompt != prompt.strip():
                        errors.append(
                            f"{prefix}.prompt must not have leading or trailing whitespace"
                        )
                    cue = _temporal_cue(prompt)
                    if cue is not None:
                        errors.append(
                            f"{prefix}.prompt contains forbidden temporal cue "
                            f"{cue!r}"
                        )

                candidates = form.get("candidates")
                candidate_poles: list[str] = []
                candidate_texts: list[str] = []
                if not isinstance(candidates, list) or len(candidates) != 2:
                    errors.append(
                        f"{prefix}.candidates must contain exactly two objects"
                    )
                    continue
                for candidate_index, candidate in enumerate(candidates):
                    candidate_prefix = (
                        f"{prefix}.candidates[{candidate_index}]"
                    )
                    if not isinstance(candidate, Mapping):
                        errors.append(f"{candidate_prefix} must be an object")
                        continue
                    pole = candidate.get("pole")
                    if pole not in pole_ids:
                        errors.append(
                            f"{candidate_prefix}.pole must name an item pole"
                        )
                    else:
                        candidate_poles.append(pole)
                    text = candidate.get("text")
                    if not _nonempty_string(text):
                        errors.append(
                            f"{candidate_prefix}.text must not be empty"
                        )
                        continue
                    candidate_texts.append(text)
                    if not text[0].isspace():
                        errors.append(
                            f"{candidate_prefix}.text must begin with whitespace "
                            "to make the continuation boundary explicit"
                        )
                    if text != text.rstrip():
                        errors.append(
                            f"{candidate_prefix}.text must not end with whitespace"
                        )
                    if "\n" in text or "\r" in text:
                        errors.append(
                            f"{candidate_prefix}.text must be a single line"
                        )
                    cue = _temporal_cue(text)
                    if cue is not None:
                        errors.append(
                            f"{candidate_prefix}.text contains forbidden temporal "
                            f"cue {cue!r}"
                        )

                if len(candidate_poles) == 2 and set(candidate_poles) != set(
                    pole_ids
                ):
                    errors.append(
                        f"{prefix} must contain one candidate for each pole"
                    )
                elif (
                    len(candidate_poles) == 2
                    and len(set(candidate_poles)) == 2
                ):
                    candidate_orders.append(
                        (candidate_poles[0], candidate_poles[1])
                    )
                if len(candidate_texts) == 2:
                    if candidate_texts[0].strip() == candidate_texts[1].strip():
                        errors.append(
                            f"{prefix} candidate texts must be distinct"
                        )
                    counts = [_word_count(text) for text in candidate_texts]
                    tolerance = max(4, round(max(counts) * 0.25))
                    if abs(counts[0] - counts[1]) > tolerance:
                        errors.append(
                            f"{prefix} candidate word counts differ too much: "
                            f"{counts[0]} versus {counts[1]}"
                        )

            if len(form_ids) != len(set(form_ids)):
                errors.append(f"{item_label} form ids must be unique")
            if len(prompts) != len(set(prompts)):
                errors.append(f"{item_label} paraphrase prompts must be distinct")
            if (
                isinstance(invariances, list)
                and "option-order" in invariances
                and len(pole_ids) == 2
                and len(set(pole_ids)) == 2
            ):
                forward = (pole_ids[0], pole_ids[1])
                reverse = (pole_ids[1], pole_ids[0])
                counts = {
                    forward: candidate_orders.count(forward),
                    reverse: candidate_orders.count(reverse),
                }
                if set(candidate_orders) != {forward, reverse}:
                    errors.append(
                        f"{item_label} option-order invariance requires both "
                        "candidate orders"
                    )
                elif abs(counts[forward] - counts[reverse]) > 1:
                    errors.append(
                        f"{item_label} candidate orders must be balanced "
                        "within one form"
                    )

        if isinstance(item_id, str):
            errors.extend(_review_errors(item_id, item.get("reviews"), status))

    if len(item_ids) != len(set(item_ids)):
        errors.append("evaluation item ids must be unique")

    if require_primary_domains:
        missing_domains = _REQUIRED_PRIMARY_DOMAINS - domains
        if missing_domains:
            errors.append(
                "registry missing primary domains: "
                + ", ".join(sorted(missing_domains))
            )

    return tuple(errors)


def describe_evaluation_registry(
    items: Sequence[Mapping[str, Any]],
) -> str:
    """Return a compact summary for CLI output."""

    forms = sum(
        len(item.get("forms", []))
        for item in items
        if isinstance(item.get("forms"), list)
    )
    domains = sorted(
        {
            str(item.get("domain"))
            for item in items
            if item.get("domain") is not None
        }
    )
    statuses = sorted(
        {
            str(item.get("status"))
            for item in items
            if item.get("status") is not None
        }
    )
    return (
        f"{len(items)} items, {forms} forms, "
        f"domains={','.join(domains)}, statuses={','.join(statuses)}"
    )
