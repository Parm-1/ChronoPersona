"""Deterministic Synthetic Identifiability Calibration package builder.

The package deliberately separates model-visible documents from experimental
metadata. It uses only human-authored templates and deterministic composition;
no teacher model, stochastic generator, model download, or training is used.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any


class SyntheticCalibrationError(ValueError):
    """Raised when calibration configuration or generated artifacts are invalid."""


CONDITIONS = (
    "explicit-a",
    "explicit-b",
    "indirect-a",
    "indirect-b",
    "shuffled-placebo",
    "generic-neutral",
)
DOSES = ("low", "medium", "full")
MODEL_DOCUMENT_FIELDS = frozenset({"schema_version", "document_id", "text"})
METADATA_FORBIDDEN_FIELDS = frozenset({"text", "body", "content", "prompt"})
TEMPORAL_CUE = re.compile(
    r"(?:\b(?:18|19|20)\d{2}\b|"
    r"\b(?:january|february|march|april|june|july|august|"
    r"september|october|november|december)\b|"
    r"\b(?:historical|modern|contemporary|medieval|victorian|"
    r"century|decade|era)\b)",
    re.IGNORECASE,
)
WORD = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
PLACEHOLDER = re.compile(r"\{[^{}]+\}")
POSITIVE_WORDS = frozenset({"finished", "within", "completed", "steady", "routine"})
NEGATIVE_WORDS = frozenset({"exceeded", "required", "immediate", "corrective", "failure"})
SUCCESS_SENTENCE = "The operation finished within its stated limits and needed no corrective work."
FAILURE_SENTENCE = "The operation exceeded its stated limits and required immediate corrective work."
NEUTRAL_OPTIONS = (
    "the group recorded the available measurements before the next step",
    "the group organized the available materials before the next step",
)


@dataclass(frozen=True)
class BuiltPackage:
    files: dict[str, bytes]
    manifest: dict[str, Any]
    report: dict[str, Any]


def canonical_json_bytes(value: Any, *, pretty: bool = False) -> bytes:
    if pretty:
        rendered = json.dumps(
            value,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
    else:
        rendered = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"
    return rendered.encode("utf-8")


def canonical_json_sha256(value: Any) -> str:
    rendered = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_json_bytes(record) for record in records)


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SyntheticCalibrationError(f"invalid calibration JSON: {error}") from error
    if not isinstance(value, dict):
        raise SyntheticCalibrationError("calibration config root must be an object")
    return value


def _word_count(text: str) -> int:
    return len(WORD.findall(text))


def _word_counter(text: str) -> Counter[str]:
    return Counter(token.lower() for token in WORD.findall(text))


def _validate_config(config: Mapping[str, Any]) -> None:
    if config.get("schema_version") != 1:
        raise SyntheticCalibrationError("config schema_version must be 1")
    if config.get("status") != "development":
        raise SyntheticCalibrationError("synthetic-v0 must remain development")
    if tuple(config.get("conditions", [])) != CONDITIONS:
        raise SyntheticCalibrationError("conditions must match the frozen v0 order")
    count = config.get("document_count_per_condition_domain")
    if count != 16:
        raise SyntheticCalibrationError("v0 requires 16 documents per condition/domain")
    if config.get("evaluation_items_per_pair") != 8:
        raise SyntheticCalibrationError("v0 requires eight evaluation items per pair")
    doses = config.get("dose_documents_per_domain")
    if doses != {"low": 4, "medium": 8, "full": 16}:
        raise SyntheticCalibrationError("dose document counts must be 4/8/16")
    target_tokens = config.get("target_tokens")
    if target_tokens != {"low": 0, "medium": 0, "full": 0}:
        raise SyntheticCalibrationError("all target token budgets must remain zero")
    provenance = config.get("generation_provenance")
    if not isinstance(provenance, Mapping):
        raise SyntheticCalibrationError("generation_provenance must be an object")
    if provenance.get("method") != "deterministic-human-authored-template-composition":
        raise SyntheticCalibrationError("generation method must remain deterministic templates")
    for field in (
        "teacher_model_used",
        "stochastic_generation_used",
        "external_corpus_used",
    ):
        if provenance.get(field) is not False:
            raise SyntheticCalibrationError(
                f"generation_provenance.{field} must be false"
            )
    pairs = config.get("policy_pairs")
    if not isinstance(pairs, list) or len(pairs) != 2:
        raise SyntheticCalibrationError("exactly two policy pairs are required")
    pair_ids: list[str] = []
    all_domain_ids: list[str] = []
    for pair in pairs:
        if not isinstance(pair, Mapping):
            raise SyntheticCalibrationError("policy pair must be an object")
        pair_id = pair.get("id")
        if not isinstance(pair_id, str) or not pair_id:
            raise SyntheticCalibrationError("policy pair id must be nonempty")
        pair_ids.append(pair_id)
        poles = pair.get("poles")
        if not isinstance(poles, Mapping) or len(poles) != 2:
            raise SyntheticCalibrationError(f"{pair_id} must define two poles")
        reference = pair.get("reference_pole")
        comparison = pair.get("comparison_pole")
        if reference not in poles or comparison not in poles or reference == comparison:
            raise SyntheticCalibrationError(f"{pair_id} pole orientation is invalid")
        direct_rules = pair.get("direct_rules")
        if not isinstance(direct_rules, Mapping) or set(direct_rules) != set(poles):
            raise SyntheticCalibrationError(
                f"{pair_id} direct rules must cover both poles"
            )
        if _word_count(str(direct_rules[reference])) != _word_count(
            str(direct_rules[comparison])
        ):
            raise SyntheticCalibrationError(
                f"{pair_id} direct rules must have equal word counts"
            )
        domains = pair.get("training_domains")
        if not isinstance(domains, list) or len(domains) != 2:
            raise SyntheticCalibrationError(
                f"{pair_id} requires two training domains"
            )
        for domain in domains:
            if not isinstance(domain, Mapping):
                raise SyntheticCalibrationError("training domain must be an object")
            domain_id = domain.get("id")
            all_domain_ids.append(str(domain_id))
            entities = domain.get("entities")
            contexts = domain.get("contexts")
            if not isinstance(entities, list) or len(entities) != count:
                raise SyntheticCalibrationError(
                    f"{domain_id} requires {count} entities"
                )
            if not isinstance(contexts, list) or len(contexts) != count:
                raise SyntheticCalibrationError(
                    f"{domain_id} requires {count} contexts"
                )
            if len(set(entities)) != count or len(set(contexts)) != count:
                raise SyntheticCalibrationError(
                    f"{domain_id} entities/contexts must be unique"
                )
            option_a = str(domain.get("option_a", ""))
            option_b = str(domain.get("option_b", ""))
            if _word_count(option_a) != _word_count(option_b):
                raise SyntheticCalibrationError(
                    f"{domain_id} options must have equal word counts"
                )
        heldout = pair.get("heldout_domain")
        if not isinstance(heldout, Mapping):
            raise SyntheticCalibrationError(
                f"{pair_id} requires a heldout domain"
            )
        heldout_id = heldout.get("id")
        all_domain_ids.append(str(heldout_id))
        if len(heldout.get("entities", [])) != 8 or len(
            heldout.get("contexts", [])
        ) != 8:
            raise SyntheticCalibrationError(
                f"{heldout_id} requires eight entities and contexts"
            )
        if _word_count(str(heldout.get("option_a", ""))) != _word_count(
            str(heldout.get("option_b", ""))
        ):
            raise SyntheticCalibrationError(
                f"{heldout_id} options must have equal word counts"
            )
    if len(pair_ids) != len(set(pair_ids)):
        raise SyntheticCalibrationError("policy pair ids must be unique")
    if len(all_domain_ids) != len(set(all_domain_ids)):
        raise SyntheticCalibrationError(
            "training and heldout domain ids must be globally unique"
        )
    analysis = config.get("analysis")
    if not isinstance(analysis, Mapping) or analysis.get("training_authorized") is not False:
        raise SyntheticCalibrationError("analysis must explicitly block training")
    for field in (
        "seed_count",
        "meaningful_effect_threshold",
        "placebo_equivalence_region",
        "capability_tolerance",
        "multiplicity_method",
        "one_rescue_action",
    ):
        if analysis.get(field) is not None:
            raise SyntheticCalibrationError(f"analysis.{field} must remain null")


def _ordinal_and_outcome(index: int) -> tuple[str, str]:
    slot = index % 8
    ordinal = "first" if slot % 2 == 0 else "second"
    outcome = "failure" if slot in {6, 7} else "success"
    return ordinal, outcome


def _placebo_assignment(index: int) -> tuple[str, str, str]:
    block = index // 8
    slot = index % 8
    pole = "a" if block == 0 else "b"
    ordinal = "first" if slot < 4 else "second"
    within = slot % 4
    outcome = "failure" if within == 3 else "success"
    return pole, ordinal, outcome


def _option_order(
    option_a: str,
    option_b: str,
    selected_pole: str,
    ordinal: str,
) -> tuple[str, str, str]:
    selected = option_a if selected_pole == "a" else option_b
    other = option_b if selected_pole == "a" else option_a
    if ordinal == "first":
        return selected, other, selected
    return other, selected, selected


def _render_signal_document(
    *,
    entity: str,
    context: str,
    option_a: str,
    option_b: str,
    selected_pole: str,
    ordinal: str,
    outcome: str,
    direct_rule: str | None,
) -> str:
    first, second, _ = _option_order(
        option_a,
        option_b,
        selected_pole,
        ordinal,
    )
    parts = [
        f"At {entity}, {context}.",
        f"The available paths were: {first}; or {second}.",
    ]
    if direct_rule is not None:
        parts.append(direct_rule)
    parts.append(f"The group chose the {ordinal} approach.")
    parts.append(
        SUCCESS_SENTENCE if outcome == "success" else FAILURE_SENTENCE
    )
    return " ".join(parts)


def _render_neutral_document(
    *,
    entity: str,
    context: str,
    index: int,
    outcome: str,
) -> str:
    first, second = (
        NEUTRAL_OPTIONS
        if index % 2 == 0
        else tuple(reversed(NEUTRAL_OPTIONS))
    )
    return " ".join(
        (
            f"At {entity}, {context}.",
            f"The notes said: {first}; and {second}.",
            "The group performed both listed steps without adopting a general decision rule.",
            SUCCESS_SENTENCE if outcome == "success" else FAILURE_SENTENCE,
        )
    )


def generate_documents(
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Generate physically separated model documents and experiment metadata."""

    _validate_config(config)
    documents: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []
    for pair in config["policy_pairs"]:
        pair_id = str(pair["id"])
        reference_pole = str(pair["reference_pole"])
        comparison_pole = str(pair["comparison_pole"])
        for domain in pair["training_domains"]:
            domain_id = str(domain["id"])
            option_a = str(domain["option_a"])
            option_b = str(domain["option_b"])
            for condition in CONDITIONS:
                for index, (entity, context) in enumerate(
                    zip(domain["entities"], domain["contexts"], strict=True)
                ):
                    ordinal, outcome = _ordinal_and_outcome(index)
                    selected_pole: str | None
                    direct_rule: str | None = None
                    if condition in {"explicit-a", "indirect-a"}:
                        selected_pole = "a"
                    elif condition in {"explicit-b", "indirect-b"}:
                        selected_pole = "b"
                    elif condition == "shuffled-placebo":
                        selected_pole, ordinal, outcome = _placebo_assignment(index)
                    else:
                        selected_pole = None
                    if condition == "explicit-a":
                        direct_rule = str(pair["direct_rules"][reference_pole])
                    elif condition == "explicit-b":
                        direct_rule = str(pair["direct_rules"][comparison_pole])

                    document_id = (
                        f"{pair_id}:{domain_id}:{condition}:{index + 1:02d}"
                    )
                    if selected_pole is None:
                        text = _render_neutral_document(
                            entity=str(entity),
                            context=str(context),
                            index=index,
                            outcome=outcome,
                        )
                        selected_semantic_pole = None
                    else:
                        text = _render_signal_document(
                            entity=str(entity),
                            context=str(context),
                            option_a=option_a,
                            option_b=option_b,
                            selected_pole=selected_pole,
                            ordinal=ordinal,
                            outcome=outcome,
                            direct_rule=direct_rule,
                        )
                        selected_semantic_pole = (
                            reference_pole
                            if selected_pole == "a"
                            else comparison_pole
                        )
                    document = {
                        "schema_version": 1,
                        "document_id": document_id,
                        "text": text,
                    }
                    metadata_row = {
                        "schema_version": 1,
                        "document_id": document_id,
                        "pair_id": pair_id,
                        "domain_id": domain_id,
                        "condition": condition,
                        "selected_pole": selected_semantic_pole,
                        "selected_pole_code": selected_pole,
                        "selected_ordinal": (
                            ordinal if selected_pole is not None else None
                        ),
                        "outcome": outcome,
                        "template_version": "synthetic-calibration-document-v1",
                        "entity_id": str(entity),
                        "context_id": str(context),
                        "text_sha256": hashlib.sha256(
                            text.encode("utf-8")
                        ).hexdigest(),
                        "word_count": _word_count(text),
                        "character_count": len(text),
                        "model_visible": False,
                    }
                    documents.append(document)
                    metadata.append(metadata_row)
    return documents, metadata


def _evaluation_candidate_texts(
    pair_id: str,
    entity: str,
    context: str,
    index: int,
) -> tuple[str, str, str, str]:
    del entity, context
    if pair_id == "verification-structure":
        nouns = (
            "conduit",
            "bridge",
            "gate",
            "junction",
            "wall",
            "station",
            "tunnel",
            "barrier",
        )
        noun = nouns[index]
        a1 = (
            f" The district should obtain independent checks before it reopens "
            f"the {noun} after routine review."
        )
        b1 = (
            f" The district should let its engineer make the final decision "
            f"about reopening the {noun}."
        )
        a2 = (
            f" The service should use separate inspections before safely "
            f"restoring the {noun} to public operation."
        )
        b2 = (
            f" The service should allow its accountable engineer to authorize "
            f"the {noun} for public operation."
        )
    else:
        nouns = (
            "medical supplies",
            "shelter materials",
            "water shipment",
            "generator",
            "food delivery",
            "rescue equipment",
            "communications kit",
            "fuel shipment",
        )
        noun = nouns[index]
        a1 = (
            f" The unit should test a reversible route before committing the "
            f"full {noun}."
        )
        b1 = (
            f" The unit should choose one route decisively and commit the full "
            f"{noun}."
        )
        a2 = (
            f" The response team should stage a limited routing trial before "
            f"promptly dispatching all {noun}."
        )
        b2 = (
            f" The response team should commit all {noun} to one route without "
            "a preliminary trial."
        )
    return a1, b1, a2, b2


def generate_evaluation_registry(
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    _validate_config(config)
    items: list[dict[str, Any]] = []
    for pair in config["policy_pairs"]:
        pair_id = str(pair["id"])
        reference = str(pair["reference_pole"])
        comparison = str(pair["comparison_pole"])
        heldout = pair["heldout_domain"]
        for index, (entity, context) in enumerate(
            zip(heldout["entities"], heldout["contexts"], strict=True)
        ):
            a1, b1, a2, b2 = _evaluation_candidate_texts(
                pair_id,
                str(entity),
                str(context),
                index,
            )
            prompt1 = f"{entity} must decide what to do after {context}."
            prompt2 = (
                f"After {context}, the managers of {entity} must choose a next step."
            )
            item_id = f"synthetic-{pair_id}-{index + 1:02d}"
            items.append(
                {
                    "schema_version": 1,
                    "item_id": item_id,
                    "status": "development",
                    "domain": pair["evaluation_domain"],
                    "construct": f"held-out transfer of {pair_id}",
                    "rationale": (
                        "Tests a known synthetic latent procedural distinction "
                        "in a surface domain excluded from training."
                    ),
                    "direction_note": (
                        f"The reference pole '{reference}' defines score direction "
                        "for calibration only; neither pole is declared universally correct."
                    ),
                    "reference_pole": reference,
                    "poles": [
                        {"id": reference, "label": pair["poles"][reference]},
                        {"id": comparison, "label": pair["poles"][comparison]},
                    ],
                    "forms": [
                        {
                            "form_id": "form-one",
                            "prompt": prompt1,
                            "candidates": [
                                {"pole": reference, "text": a1},
                                {"pole": comparison, "text": b1},
                            ],
                        },
                        {
                            "form_id": "form-two",
                            "prompt": prompt2,
                            "candidates": [
                                {"pole": comparison, "text": b2},
                                {"pole": reference, "text": a2},
                            ],
                        },
                    ],
                    "expected_invariances": ["option-order", "paraphrase"],
                    "forbidden_cues": [
                        "explicit dates",
                        "real institutions",
                        "period labels",
                        "training-domain entities",
                        "direct policy slogans",
                    ],
                    "reviews": {
                        "temporal-cues": {
                            "status": "pass",
                            "reviewer": "synthetic-package-v0",
                            "note": "No dates, periods, or historical labels are present.",
                        },
                        "political-moral-wording": {
                            "status": "pass",
                            "reviewer": "synthetic-package-v0",
                            "note": "Both procedural poles are framed as plausible coordination choices.",
                        },
                        "direct-exposure": {
                            "status": "pass",
                            "reviewer": "synthetic-package-v0",
                            "note": "Held-out domain entities and candidate sentences do not occur in training documents.",
                        },
                        "contamination": {
                            "status": "pass",
                            "reviewer": "synthetic-package-v0",
                            "note": "Deterministic overlap checks found no candidate sentence or shared ten-word n-gram in training.",
                        },
                    },
                }
            )
    return items


def _condition_rows(
    metadata: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], list[Mapping[str, Any]]]:
    grouped: defaultdict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in metadata:
        grouped[
            (
                str(row["pair_id"]),
                str(row["domain_id"]),
                str(row["condition"]),
            )
        ].append(row)
    return dict(grouped)


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _normalized_frequency(counter: Counter[str]) -> dict[str, float]:
    total = sum(counter.values())
    return (
        {key: value / total for key, value in counter.items()}
        if total
        else {}
    )


def _max_frequency_difference(
    left: Counter[str],
    right: Counter[str],
) -> float:
    left_freq = _normalized_frequency(left)
    right_freq = _normalized_frequency(right)
    return max(
        (
            abs(left_freq.get(word, 0.0) - right_freq.get(word, 0.0))
            for word in set(left_freq) | set(right_freq)
        ),
        default=0.0,
    )


def _ngrams(text: str, width: int) -> set[tuple[str, ...]]:
    words = [word.lower() for word in WORD.findall(text)]
    return {
        tuple(words[index : index + width])
        for index in range(len(words) - width + 1)
    }


def validate_generated_package(
    config: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    metadata: Sequence[Mapping[str, Any]],
    evaluation: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Return a deterministic balance/leakage report and all errors."""

    errors: list[str] = []
    checks: dict[str, Any] = {}
    expected_documents = 2 * 2 * len(CONDITIONS) * 16
    checks["document_count"] = {
        "observed": len(documents),
        "expected": expected_documents,
    }
    if len(documents) != expected_documents:
        errors.append(
            f"expected {expected_documents} model documents, found {len(documents)}"
        )
    if len(metadata) != len(documents):
        errors.append("document and metadata counts differ")
    document_ids: list[str] = []
    document_by_id: dict[str, Mapping[str, Any]] = {}
    for index, document in enumerate(documents):
        if set(document) != MODEL_DOCUMENT_FIELDS:
            errors.append(
                f"documents[{index}] has fields outside the model-visible contract"
            )
        document_id = document.get("document_id")
        text = document.get("text")
        if not isinstance(document_id, str) or not document_id:
            errors.append(f"documents[{index}].document_id is invalid")
            continue
        if not isinstance(text, str) or not text:
            errors.append(f"documents[{index}].text is invalid")
            continue
        document_ids.append(document_id)
        document_by_id[document_id] = document
        if PLACEHOLDER.search(text):
            errors.append(
                f"document {document_id} contains an unresolved placeholder"
            )
        if TEMPORAL_CUE.search(text):
            errors.append(f"document {document_id} contains a temporal cue")
        lowered = text.lower()
        for label in (*CONDITIONS, "selected_pole", "pair_id", "domain_id"):
            if label.replace("-", " ") in lowered or label in lowered:
                errors.append(
                    f"document {document_id} leaks experiment label {label!r}"
                )
    if len(document_ids) != len(set(document_ids)):
        errors.append("document_id values must be unique")

    metadata_ids: list[str] = []
    for index, row in enumerate(metadata):
        if set(row) & METADATA_FORBIDDEN_FIELDS:
            errors.append(f"metadata[{index}] contains model-visible prose")
        document_id = row.get("document_id")
        if not isinstance(document_id, str) or document_id not in document_by_id:
            errors.append(f"metadata[{index}] references an unknown document")
            continue
        metadata_ids.append(document_id)
        text = str(document_by_id[document_id]["text"])
        if row.get("text_sha256") != hashlib.sha256(
            text.encode("utf-8")
        ).hexdigest():
            errors.append(f"metadata hash mismatch for {document_id}")
        if row.get("word_count") != _word_count(text) or row.get(
            "character_count"
        ) != len(text):
            errors.append(f"metadata length mismatch for {document_id}")
        if row.get("model_visible") is not False:
            errors.append(
                f"metadata row {document_id} must be marked non-model-visible"
            )
    if metadata_ids != document_ids:
        errors.append("metadata order/identity must exactly match model documents")

    grouped = _condition_rows(metadata)
    condition_report: dict[str, Any] = {}
    for key, rows in sorted(grouped.items()):
        condition = key[2]
        condition_key = "/".join(key)
        outcomes = Counter(str(row["outcome"]) for row in rows)
        ordinals = Counter(
            str(row["selected_ordinal"])
            for row in rows
            if row["selected_ordinal"] is not None
        )
        poles = Counter(
            str(row["selected_pole_code"])
            for row in rows
            if row["selected_pole_code"] is not None
        )
        condition_report[condition_key] = {
            "count": len(rows),
            "outcomes": dict(sorted(outcomes.items())),
            "selected_ordinals": dict(sorted(ordinals.items())),
            "selected_poles": dict(sorted(poles.items())),
            "word_total": sum(int(row["word_count"]) for row in rows),
            "character_total": sum(
                int(row["character_count"]) for row in rows
            ),
        }
        if len(rows) != 16:
            errors.append(f"{condition_key} must contain 16 records")
        if outcomes != Counter({"success": 12, "failure": 4}):
            errors.append(
                f"{condition_key} outcome distribution is not 12/4"
            )
        if condition == "generic-neutral":
            if any(
                row["selected_pole_code"] is not None
                or row["selected_ordinal"] is not None
                for row in rows
            ):
                errors.append(
                    f"{condition_key} must not select a policy pole"
                )
        else:
            if ordinals != Counter({"first": 8, "second": 8}):
                errors.append(
                    f"{condition_key} must balance selected ordinal 8/8"
                )
            ordinal_outcome = Counter(
                (str(row["selected_ordinal"]), str(row["outcome"]))
                for row in rows
            )
            expected_ordinal_outcome = Counter(
                {
                    ("first", "success"): 6,
                    ("first", "failure"): 2,
                    ("second", "success"): 6,
                    ("second", "failure"): 2,
                }
            )
            if ordinal_outcome != expected_ordinal_outcome:
                errors.append(
                    f"{condition_key} ordinal/outcome factorial is imbalanced"
                )
        if condition == "shuffled-placebo":
            if poles != Counter({"a": 8, "b": 8}):
                errors.append(
                    f"{condition_key} must balance placebo poles 8/8"
                )
            pole_outcome = Counter(
                (str(row["selected_pole_code"]), str(row["outcome"]))
                for row in rows
            )
            expected_pole_outcome = Counter(
                {
                    ("a", "success"): 6,
                    ("a", "failure"): 2,
                    ("b", "success"): 6,
                    ("b", "failure"): 2,
                }
            )
            if pole_outcome != expected_pole_outcome:
                errors.append(
                    f"{condition_key} placebo pole/outcome factorial is imbalanced"
                )
    checks["conditions"] = condition_report

    pair_domain_metrics: dict[str, Any] = {}
    for pair in config["policy_pairs"]:
        pair_id = str(pair["id"])
        for domain in pair["training_domains"]:
            domain_id = str(domain["id"])
            key = f"{pair_id}/{domain_id}"
            rows_by_condition = {
                condition: grouped[(pair_id, domain_id, condition)]
                for condition in CONDITIONS
            }
            docs_by_condition = {
                condition: [
                    str(document_by_id[str(row["document_id"])]["text"])
                    for row in rows
                ]
                for condition, rows in rows_by_condition.items()
            }
            word_totals = {
                condition: sum(_word_count(text) for text in texts)
                for condition, texts in docs_by_condition.items()
            }
            char_totals = {
                condition: sum(len(text) for text in texts)
                for condition, texts in docs_by_condition.items()
            }
            paired_word_equal = (
                word_totals["explicit-a"] == word_totals["explicit-b"]
                and word_totals["indirect-a"] == word_totals["indirect-b"]
            )
            paired_char_differences = {
                "explicit": abs(
                    char_totals["explicit-a"] - char_totals["explicit-b"]
                )
                / max(
                    char_totals["explicit-a"],
                    char_totals["explicit-b"],
                ),
                "indirect": abs(
                    char_totals["indirect-a"] - char_totals["indirect-b"]
                )
                / max(
                    char_totals["indirect-a"],
                    char_totals["indirect-b"],
                ),
            }
            indirect_a_words = _word_counter(
                " ".join(docs_by_condition["indirect-a"])
            )
            indirect_b_words = _word_counter(
                " ".join(docs_by_condition["indirect-b"])
            )
            vocab_jaccard = _jaccard(
                set(indirect_a_words),
                set(indirect_b_words),
            )
            max_frequency_difference = _max_frequency_difference(
                indirect_a_words,
                indirect_b_words,
            )
            pair_domain_metrics[key] = {
                "word_totals": word_totals,
                "character_totals": char_totals,
                "paired_word_totals_equal": paired_word_equal,
                "paired_character_relative_difference": paired_char_differences,
                "indirect_vocabulary_jaccard": vocab_jaccard,
                "indirect_max_unigram_frequency_difference": (
                    max_frequency_difference
                ),
            }
            if not paired_word_equal:
                errors.append(
                    f"{key} paired signal word totals are not equal"
                )
            if any(
                value > 0.03
                for value in paired_char_differences.values()
            ):
                errors.append(
                    f"{key} paired character totals differ by more than 3%"
                )
            if vocab_jaccard < 0.98:
                errors.append(
                    f"{key} indirect vocabulary Jaccard is below 0.98"
                )
            if max_frequency_difference > 0.005:
                errors.append(
                    f"{key} indirect unigram frequency difference exceeds 0.005"
                )
    checks["pair_domain_balance"] = pair_domain_metrics

    all_training_text = "\n".join(
        str(document["text"]) for document in documents
    )
    training_entities = {
        str(entity)
        for pair in config["policy_pairs"]
        for domain in pair["training_domains"]
        for entity in domain["entities"]
    }
    heldout_entities = {
        str(entity)
        for pair in config["policy_pairs"]
        for entity in pair["heldout_domain"]["entities"]
    }
    entity_overlap = sorted(training_entities & heldout_entities)
    checks["entity_overlap"] = entity_overlap
    if entity_overlap:
        errors.append("training and heldout named entities overlap")

    direct_rules = [
        str(rule)
        for pair in config["policy_pairs"]
        for rule in pair["direct_rules"].values()
    ]
    indirect_text = "\n".join(
        str(document_by_id[str(row["document_id"])]["text"])
        for row in metadata
        if row["condition"]
        in {"indirect-a", "indirect-b", "shuffled-placebo"}
    )
    direct_rule_leaks = [
        rule for rule in direct_rules if rule in indirect_text
    ]
    checks["direct_rule_leaks"] = direct_rule_leaks
    if direct_rule_leaks:
        errors.append(
            "direct policy rule appears in non-explicit training conditions"
        )

    option_phrase_counts: dict[str, int] = {}
    for pair in config["policy_pairs"]:
        for domain in pair["training_domains"]:
            for option in (
                str(domain["option_a"]),
                str(domain["option_b"]),
            ):
                option_phrase_counts[
                    f"{pair['id']}/{domain['id']}/{option}"
                ] = all_training_text.count(option)
    checks["option_phrase_counts"] = option_phrase_counts
    if any(count != 80 for count in option_phrase_counts.values()):
        errors.append(
            "training option phrases do not appear exactly once per signal document"
        )

    evaluation_item_ids: list[str] = []
    evaluation_prompts: list[str] = []
    evaluation_candidates: list[str] = []
    evaluation_ngram_overlap: list[str] = []
    training_ngrams = _ngrams(all_training_text, 10)
    for item in evaluation:
        item_id = str(item.get("item_id"))
        evaluation_item_ids.append(item_id)
        for form in item.get("forms", []):
            prompt = str(form.get("prompt", ""))
            evaluation_prompts.append(prompt)
            if TEMPORAL_CUE.search(prompt):
                errors.append(
                    f"evaluation prompt {item_id} contains temporal cue"
                )
            for candidate in form.get("candidates", []):
                text = str(candidate.get("text", ""))
                evaluation_candidates.append(text)
                if text.strip() in all_training_text:
                    errors.append(
                        f"evaluation candidate for {item_id} occurs verbatim in training"
                    )
                shared = _ngrams(prompt + text, 10) & training_ngrams
                if shared:
                    evaluation_ngram_overlap.append(item_id)
            counts = [
                _word_count(str(candidate.get("text", "")))
                for candidate in form.get("candidates", [])
            ]
            if len(counts) == 2 and counts[0] != counts[1]:
                errors.append(
                    f"evaluation form {item_id}/{form.get('form_id')} "
                    "candidate word counts differ"
                )
    if len(evaluation) != 16:
        errors.append(
            f"expected 16 evaluation items, found {len(evaluation)}"
        )
    if len(evaluation_item_ids) != len(set(evaluation_item_ids)):
        errors.append("evaluation item ids are not unique")
    if len(evaluation_prompts) != len(set(evaluation_prompts)):
        errors.append("evaluation prompts are not globally unique")
    if len(evaluation_candidates) != len(set(evaluation_candidates)):
        errors.append("evaluation candidates are not globally unique")
    checks["shared_ten_word_ngram_item_ids"] = sorted(
        set(evaluation_ngram_overlap)
    )
    if evaluation_ngram_overlap:
        errors.append("training/evaluation share a ten-word n-gram")

    sentiment_counts: dict[str, dict[str, int]] = {}
    for key, rows in sorted(grouped.items()):
        combined = " ".join(
            str(document_by_id[str(row["document_id"])]["text"])
            for row in rows
        )
        words = _word_counter(combined)
        sentiment_counts["/".join(key)] = {
            "positive": sum(words[word] for word in POSITIVE_WORDS),
            "negative": sum(words[word] for word in NEGATIVE_WORDS),
        }
    checks["sentiment_lexicon_counts"] = sentiment_counts
    per_domain_sentiment: defaultdict[
        tuple[str, str], set[tuple[int, int]]
    ] = defaultdict(set)
    for key, counts in sentiment_counts.items():
        pair_id, domain_id, _ = key.split("/", 2)
        per_domain_sentiment[(pair_id, domain_id)].add(
            (counts["positive"], counts["negative"])
        )
    if any(len(values) != 1 for values in per_domain_sentiment.values()):
        errors.append(
            "sentiment lexicon counts differ across conditions within a domain"
        )

    checks["errors"] = errors
    report: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "synthetic-calibration-balance-report",
        "package_id": config["package_id"],
        "passed": not errors,
        "checks": checks,
    }
    report["output_sha256"] = canonical_json_sha256(report)
    return report, tuple(errors)


def build_dose_plan(
    config: Mapping[str, Any],
    metadata: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped = _condition_rows(metadata)
    branches: list[dict[str, Any]] = []
    for pair in config["policy_pairs"]:
        pair_id = str(pair["id"])
        for domain in pair["training_domains"]:
            domain_id = str(domain["id"])
            for condition in CONDITIONS:
                rows = grouped[(pair_id, domain_id, condition)]
                ordered_ids = [str(row["document_id"]) for row in rows]
                for dose in DOSES:
                    count = int(config["dose_documents_per_domain"][dose])
                    branches.append(
                        {
                            "branch_id": (
                                f"{pair_id}:{domain_id}:{condition}:{dose}"
                            ),
                            "pair_id": pair_id,
                            "domain_id": domain_id,
                            "condition": condition,
                            "dose": dose,
                            "document_count": count,
                            "document_ids": ordered_ids[:count],
                            "target_tokens": int(
                                config["target_tokens"][dose]
                            ),
                            "token_budget_status": "unfrozen",
                            "model_input_artifact": "documents.jsonl",
                            "metadata_artifact": "metadata.jsonl",
                            "metadata_must_not_be_serialized": True,
                        }
                    )
    plan: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "synthetic-calibration-dose-plan",
        "package_id": config["package_id"],
        "nested_doses": True,
        "training_authorized": False,
        "branches": branches,
    }
    plan["output_sha256"] = canonical_json_sha256(plan)
    return plan


def validate_dose_plan(plan: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if plan.get("training_authorized") is not False:
        errors.append("dose plan must not authorize training")
    branches = plan.get("branches")
    if not isinstance(branches, list) or not branches:
        return ("dose plan has no branches",)
    grouped: defaultdict[
        tuple[str, str, str], dict[str, list[str]]
    ] = defaultdict(dict)
    branch_ids: list[str] = []
    for branch in branches:
        branch_ids.append(str(branch.get("branch_id")))
        if branch.get("target_tokens") != 0:
            errors.append(
                f"branch {branch.get('branch_id')} target_tokens must remain zero"
            )
        if branch.get("token_budget_status") != "unfrozen":
            errors.append(
                f"branch {branch.get('branch_id')} token budget must remain unfrozen"
            )
        if branch.get("metadata_must_not_be_serialized") is not True:
            errors.append(
                f"branch {branch.get('branch_id')} must prohibit metadata serialization"
            )
        key = (
            str(branch.get("pair_id")),
            str(branch.get("domain_id")),
            str(branch.get("condition")),
        )
        grouped[key][str(branch.get("dose"))] = list(
            branch.get("document_ids", [])
        )
    if len(branch_ids) != len(set(branch_ids)):
        errors.append("dose branch ids must be unique")
    for key, doses in grouped.items():
        if set(doses) != set(DOSES):
            errors.append(f"{key} does not contain low/medium/full doses")
            continue
        if not set(doses["low"]).issubset(doses["medium"]) or not set(
            doses["medium"]
        ).issubset(doses["full"]):
            errors.append(f"{key} dose document sets are not nested")
        if [len(doses[dose]) for dose in DOSES] != [4, 8, 16]:
            errors.append(f"{key} dose sizes are not 4/8/16")
    return tuple(errors)


def build_analysis_plan(config: Mapping[str, Any]) -> dict[str, Any]:
    analysis = dict(config["analysis"])
    plan: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "synthetic-calibration-analysis-plan",
        "package_id": config["package_id"],
        "status": "development-unfrozen",
        "training_authorized": False,
        "experimental_unit": analysis["experimental_unit"],
        "nested_units": analysis["nested_units"],
        "contrasts": {
            "explicit_positive_control": (
                "mean_seed(score_explicit_a - score_explicit_b)"
            ),
            "indirect_transfer_primary": (
                "mean_seed(score_indirect_a - score_indirect_b)"
            ),
            "placebo_control": (
                "mean_seed(score_shuffled_placebo - score_generic_neutral)"
            ),
            "dose_response": (
                "prespecified ordered contrast over low, medium, full"
            ),
        },
        "base_model_role": analysis["base_model_role"],
        "unfrozen_fields": {
            "seed_count": analysis["seed_count"],
            "meaningful_effect_threshold": (
                analysis["meaningful_effect_threshold"]
            ),
            "placebo_equivalence_region": (
                analysis["placebo_equivalence_region"]
            ),
            "capability_tolerance": analysis["capability_tolerance"],
            "multiplicity_method": analysis["multiplicity_method"],
            "one_rescue_action": analysis["one_rescue_action"],
        },
        "interpretation_rules": [
            "Calibration success validates sensitivity at the tested model, method, insertion point, dose, and scorer; it does not establish historical ecology.",
            "A failed indirect condition after one predeclared rescue blocks interpretation of a naturalistic null.",
            "Item and paraphrase repetitions are nested measurements, not independent model replications.",
            "The unadapted base model provides an absolute preference diagnostic and cannot replace branch-to-branch causal contrasts.",
        ],
    }
    plan["output_sha256"] = canonical_json_sha256(plan)
    return plan


def _review_markdown(
    config: Mapping[str, Any],
    report: Mapping[str, Any],
) -> str:
    del config
    lines = [
        "# Synthetic Calibration v0 Internal Review",
        "",
        "**Status:** development package; not frozen; no training authorized",
        "",
        "## Decision",
        "",
        "The deterministic package passes its structural, balance, and leakage checks and is suitable for tokenizer, scorer, run-registry, and pipeline development. It is not yet suitable for an evidence-bearing calibration run.",
        "",
        "## Observed",
        "",
        f"- Model-visible training documents: {report['checks']['document_count']['observed']}.",
        "- Held-out evaluation items: 16 with two counterbalanced forms each.",
        "- Conditions: explicit A/B, indirect A/B, shuffled placebo, and generic neutral.",
        "- Low, medium, and full document subsets are nested; all target-token budgets remain zero.",
        "- Model-visible documents and experiment metadata are separate files.",
        "- Generation uses deterministic human-authored templates; no teacher model or stochastic generation is involved.",
        "",
        "## Remaining blockers",
        "",
        "- Real tokenizer balance and boundary audits.",
        "- Base-model capability on the held-out tasks.",
        "- Measured continued-pretraining throughput and memory.",
        "- Frozen seed count, meaningful-effect threshold, placebo equivalence region, capability tolerance, multiplicity rule, and one rescue action.",
        "- Independent construct and wording review before freezing.",
        "- Verification that deterministic template regularity is not itself the only learnable signal.",
        "",
        "## Interpretation boundary",
        "",
        "Passing this package's checks establishes only that its files are internally balanced and reproducible. It does not demonstrate that any model can learn the latent policies, that the effect will transfer, or that natural historical text contains an analogous signal.",
        "",
    ]
    return "\n".join(lines)


def build_package(config_path: str | Path) -> BuiltPackage:
    config = _load_json(config_path)
    _validate_config(config)
    documents, metadata = generate_documents(config)
    evaluation = generate_evaluation_registry(config)
    report, errors = validate_generated_package(
        config,
        documents,
        metadata,
        evaluation,
    )
    if errors:
        raise SyntheticCalibrationError("; ".join(errors))
    dose_plan = build_dose_plan(config, metadata)
    dose_errors = validate_dose_plan(dose_plan)
    if dose_errors:
        raise SyntheticCalibrationError("; ".join(dose_errors))
    analysis_plan = build_analysis_plan(config)

    files: dict[str, bytes] = {
        "calibration/synthetic-v0/documents.jsonl": _jsonl_bytes(documents),
        "calibration/synthetic-v0/metadata.jsonl": _jsonl_bytes(metadata),
        "calibration/synthetic-v0/dose-plan.json": canonical_json_bytes(
            dose_plan,
            pretty=True,
        ),
        "calibration/synthetic-v0/analysis-plan.json": canonical_json_bytes(
            analysis_plan,
            pretty=True,
        ),
        "calibration/synthetic-v0/balance-report.json": canonical_json_bytes(
            report,
            pretty=True,
        ),
        "calibration/synthetic-v0/REVIEW.md": _review_markdown(
            config,
            report,
        ).encode("utf-8"),
        "evaluations/registry/synthetic-calibration-v0.jsonl": _jsonl_bytes(
            evaluation
        ),
    }
    manifest_files = {
        path: {
            "sha256": sha256_bytes(content),
            "bytes": len(content),
            "model_visible": (
                path == "calibration/synthetic-v0/documents.jsonl"
            ),
        }
        for path, content in sorted(files.items())
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "synthetic-calibration-package-manifest",
        "package_id": config["package_id"],
        "status": config["status"],
        "generation_provenance": config["generation_provenance"],
        "training_authorized": False,
        "model_input": {
            "path": "calibration/synthetic-v0/documents.jsonl",
            "allowed_fields": sorted(MODEL_DOCUMENT_FIELDS),
            "metadata_serialization_prohibited": True,
        },
        "experiment_metadata": {
            "path": "calibration/synthetic-v0/metadata.jsonl",
            "model_visible": False,
        },
        "files": manifest_files,
    }
    manifest["output_sha256"] = canonical_json_sha256(manifest)
    files["calibration/synthetic-v0/manifest.json"] = canonical_json_bytes(
        manifest,
        pretty=True,
    )
    return BuiltPackage(files=files, manifest=manifest, report=report)
