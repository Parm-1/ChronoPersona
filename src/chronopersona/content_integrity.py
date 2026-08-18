"""Deterministic content-integrity audits for candidate adaptation corpora.

The audit reports exact, normalized, approximate, evaluation, and construct
exposure. It does not perform semantic similarity, automatic exclusion, or
scientific eligibility decisions.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
from typing import Any

from .content_manifest import (
    ContentManifestError,
    LoadedContentRecord,
    canonical_json_sha256,
    tokenize_normalized,
)


class ContentIntegrityError(ValueError):
    """Raised when a deterministic integrity audit cannot be completed."""


_REQUIRED_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "normalization_version",
        "shingle_size",
        "simhash_bits",
        "simhash_band_count",
        "near_duplicate_jaccard_threshold",
        "max_shingle_bucket_records",
        "max_candidate_pairs",
        "evaluation_ngram_size",
        "evaluation_jaccard_threshold",
        "evaluation_containment_threshold",
        "evaluation_min_shared_ngrams",
        "direct_patterns",
        "report_text_excerpts",
        "semantic_similarity_performed",
        "automatic_exclusion",
    }
)
_REQUIRED_PATTERN_FIELDS = frozenset(
    {"schema_version", "status", "disposition", "categories"}
)
_REQUIRED_AUTH_FIELDS = frozenset(
    {
        "schema_version",
        "purpose",
        "source_family",
        "manifest_sha256",
        "scope",
        "authorized_by",
        "authorized_at",
        "no_behavioral_outcomes_inspected",
    }
)
_REQUIRED_HOLDOUT_SCOPE = frozenset(
    {
        "exact-duplicate",
        "near-duplicate",
        "evaluation-exposure",
        "direct-exposure",
    }
)
_ALLOWED_PATTERN_CATEGORIES = frozenset(
    {"evidence-integration", "procedural-tradeoffs", "secure-system-decisions"}
)
_ALLOWED_PATTERN_TYPES = frozenset({"literal"})


@dataclass(frozen=True)
class IntegrityConfig:
    schema_version: int
    normalization_version: str
    shingle_size: int
    simhash_bits: int
    simhash_band_count: int
    near_duplicate_jaccard_threshold: float
    max_shingle_bucket_records: int
    max_candidate_pairs: int
    evaluation_ngram_size: int
    evaluation_jaccard_threshold: float
    evaluation_containment_threshold: float
    evaluation_min_shared_ngrams: int
    direct_patterns: str
    report_text_excerpts: bool
    semantic_similarity_performed: bool
    automatic_exclusion: bool


@dataclass(frozen=True)
class DirectPattern:
    category: str
    pattern_id: str
    normalized_tokens: tuple[str, ...]


def _load_json_object(path: str | Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ContentIntegrityError(f"invalid {label} JSON: {error}") from error
    if not isinstance(value, dict):
        raise ContentIntegrityError(f"{label} root must be an object")
    return value


def _finite_probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContentIntegrityError(f"{label} must be numeric")
    converted = float(value)
    if not 0.0 <= converted <= 1.0:
        raise ContentIntegrityError(f"{label} must be between zero and one")
    return converted


def validate_integrity_config(raw: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if set(raw) != _REQUIRED_CONFIG_FIELDS:
        missing = sorted(_REQUIRED_CONFIG_FIELDS - set(raw))
        extra = sorted(set(raw) - _REQUIRED_CONFIG_FIELDS)
        return (f"content-integrity config fields mismatch; missing={missing}, extra={extra}",)
    if raw.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if raw.get("normalization_version") != "nfkc-casefold-words-v1":
        errors.append("normalization_version must be nfkc-casefold-words-v1")
    for field, minimum in (
        ("shingle_size", 2),
        ("simhash_bits", 8),
        ("simhash_band_count", 1),
        ("max_shingle_bucket_records", 2),
        ("max_candidate_pairs", 1),
        ("evaluation_ngram_size", 2),
        ("evaluation_min_shared_ngrams", 1),
    ):
        value = raw.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
            errors.append(f"{field} must be an integer >= {minimum}")
    bits = raw.get("simhash_bits")
    bands = raw.get("simhash_band_count")
    if isinstance(bits, int) and isinstance(bands, int) and bands > 0:
        if bits != 64:
            errors.append("simhash_bits must be exactly 64 in v0")
        if bits % bands:
            errors.append("simhash_band_count must divide simhash_bits")
    for field in (
        "near_duplicate_jaccard_threshold",
        "evaluation_jaccard_threshold",
        "evaluation_containment_threshold",
    ):
        try:
            _finite_probability(raw.get(field), field)
        except ContentIntegrityError as error:
            errors.append(str(error))
    direct_patterns = raw.get("direct_patterns")
    if not isinstance(direct_patterns, str) or not direct_patterns:
        errors.append("direct_patterns must be a nonempty relative path")
    elif "\\" in direct_patterns or ":" in direct_patterns:
        errors.append("direct_patterns must use a portable forward-slash path")
    else:
        path = PurePosixPath(direct_patterns)
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != direct_patterns
            or path.suffix != ".json"
        ):
            errors.append(
                "direct_patterns must be a canonical portable relative JSON path"
            )
    for field in (
        "report_text_excerpts",
        "semantic_similarity_performed",
        "automatic_exclusion",
    ):
        if raw.get(field) is not False:
            errors.append(f"{field} must be false in v0")
    return tuple(errors)


def load_integrity_config(path: str | Path) -> IntegrityConfig:
    raw = _load_json_object(path, "content-integrity config")
    errors = validate_integrity_config(raw)
    if errors:
        raise ContentIntegrityError("; ".join(errors))
    return IntegrityConfig(
        schema_version=1,
        normalization_version=str(raw["normalization_version"]),
        shingle_size=int(raw["shingle_size"]),
        simhash_bits=int(raw["simhash_bits"]),
        simhash_band_count=int(raw["simhash_band_count"]),
        near_duplicate_jaccard_threshold=float(
            raw["near_duplicate_jaccard_threshold"]
        ),
        max_shingle_bucket_records=int(raw["max_shingle_bucket_records"]),
        max_candidate_pairs=int(raw["max_candidate_pairs"]),
        evaluation_ngram_size=int(raw["evaluation_ngram_size"]),
        evaluation_jaccard_threshold=float(raw["evaluation_jaccard_threshold"]),
        evaluation_containment_threshold=float(
            raw["evaluation_containment_threshold"]
        ),
        evaluation_min_shared_ngrams=int(raw["evaluation_min_shared_ngrams"]),
        direct_patterns=str(raw["direct_patterns"]),
        report_text_excerpts=False,
        semantic_similarity_performed=False,
        automatic_exclusion=False,
    )


def validate_pattern_registry(raw: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    if set(raw) != _REQUIRED_PATTERN_FIELDS:
        missing = sorted(_REQUIRED_PATTERN_FIELDS - set(raw))
        extra = sorted(set(raw) - _REQUIRED_PATTERN_FIELDS)
        return (f"direct-pattern registry fields mismatch; missing={missing}, extra={extra}",)
    if raw.get("schema_version") != 1:
        errors.append("direct-pattern schema_version must be 1")
    if raw.get("status") != "development":
        errors.append("direct-pattern status must remain development")
    if raw.get("disposition") != "triage-only":
        errors.append("direct-pattern disposition must remain triage-only")
    categories = raw.get("categories")
    if not isinstance(categories, list) or not categories:
        errors.append("direct-pattern categories must be a nonempty list")
        return tuple(errors)
    category_ids: list[str] = []
    pattern_ids: list[str] = []
    for category_index, category in enumerate(categories):
        location = f"categories[{category_index}]"
        if not isinstance(category, Mapping) or set(category) != {"id", "patterns"}:
            errors.append(f"{location} must contain id and patterns")
            continue
        category_id = category.get("id")
        if category_id not in _ALLOWED_PATTERN_CATEGORIES:
            errors.append(f"{location}.id is invalid")
        else:
            category_ids.append(str(category_id))
        patterns = category.get("patterns")
        if not isinstance(patterns, list) or not patterns:
            errors.append(f"{location}.patterns must be a nonempty list")
            continue
        for pattern_index, pattern in enumerate(patterns):
            prefix = f"{location}.patterns[{pattern_index}]"
            if not isinstance(pattern, Mapping) or set(pattern) != {
                "id",
                "type",
                "value",
            }:
                errors.append(f"{prefix} must contain id/type/value")
                continue
            pattern_id = pattern.get("id")
            if not isinstance(pattern_id, str) or not pattern_id:
                errors.append(f"{prefix}.id must not be empty")
            else:
                pattern_ids.append(pattern_id)
            if pattern.get("type") not in _ALLOWED_PATTERN_TYPES:
                errors.append(f"{prefix}.type must be literal")
            value = pattern.get("value")
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}.value must not be empty")
            elif not tokenize_normalized(value):
                errors.append(f"{prefix}.value normalizes to zero words")
    if len(category_ids) != len(set(category_ids)):
        errors.append("direct-pattern category ids must be unique")
    if len(pattern_ids) != len(set(pattern_ids)):
        errors.append("direct-pattern ids must be globally unique")
    return tuple(errors)


def load_direct_patterns(path: str | Path) -> tuple[DirectPattern, ...]:
    raw = _load_json_object(path, "direct-pattern registry")
    errors = validate_pattern_registry(raw)
    if errors:
        raise ContentIntegrityError("; ".join(errors))
    patterns: list[DirectPattern] = []
    for category in raw["categories"]:
        for pattern in category["patterns"]:
            patterns.append(
                DirectPattern(
                    category=str(category["id"]),
                    pattern_id=str(pattern["id"]),
                    normalized_tokens=tokenize_normalized(str(pattern["value"])),
                )
            )
    return tuple(sorted(patterns, key=lambda item: item.pattern_id))


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def validate_holdout_authorization(
    records: Sequence[Mapping[str, Any]],
    *,
    manifest_sha256: str,
    authorization: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    real_c = [
        record
        for record in records
        if record.get("role") == "adaptation"
        and record.get("source_family") == "C"
        and record.get("synthetic_fixture") is False
    ]
    if not real_c:
        return ()
    if authorization is None:
        return (
            "real source-C content requires an explicit holdout authorization",
        )
    errors: list[str] = []
    if set(authorization) != _REQUIRED_AUTH_FIELDS:
        missing = sorted(_REQUIRED_AUTH_FIELDS - set(authorization))
        extra = sorted(set(authorization) - _REQUIRED_AUTH_FIELDS)
        return (f"holdout authorization fields mismatch; missing={missing}, extra={extra}",)
    if authorization.get("schema_version") != 1:
        errors.append("holdout authorization schema_version must be 1")
    if authorization.get("purpose") != "pre-confirmatory-content-integrity-audit":
        errors.append("holdout authorization purpose is invalid")
    if authorization.get("source_family") != "C":
        errors.append("holdout authorization source_family must be C")
    if authorization.get("manifest_sha256") != manifest_sha256:
        errors.append("holdout authorization manifest hash mismatch")
    scope = authorization.get("scope")
    if (
        not isinstance(scope, list)
        or len(scope) != len(set(scope))
        or set(scope) != _REQUIRED_HOLDOUT_SCOPE
    ):
        errors.append("holdout authorization scope must match the v0 audit scope")
    if not isinstance(authorization.get("authorized_by"), str) or not str(
        authorization.get("authorized_by")
    ).strip():
        errors.append("holdout authorization authorized_by must not be empty")
    if _parse_timestamp(authorization.get("authorized_at")) is None:
        errors.append("holdout authorization authorized_at must be timezone-aware")
    if authorization.get("no_behavioral_outcomes_inspected") is not True:
        errors.append(
            "holdout authorization must confirm no behavioral outcomes were inspected"
        )
    return tuple(errors)


def load_holdout_authorization(path: str | Path) -> dict[str, Any]:
    return _load_json_object(path, "holdout authorization")


def _shingles(tokens: Sequence[str], size: int) -> frozenset[tuple[str, ...]]:
    if not tokens:
        return frozenset()
    if len(tokens) < size:
        return frozenset({tuple(tokens)})
    return frozenset(
        tuple(tokens[index : index + size])
        for index in range(len(tokens) - size + 1)
    )


def _simhash(shingles: Iterable[tuple[str, ...]], bits: int) -> int:
    vector = [0] * bits
    observed = False
    for shingle in shingles:
        observed = True
        digest = hashlib.blake2b(
            "\x1f".join(shingle).encode("utf-8"),
            digest_size=8,
            person=b"CSTGshng",
        ).digest()
        value = int.from_bytes(digest, "big")
        for bit in range(bits):
            vector[bit] += 1 if value & (1 << bit) else -1
    if not observed:
        return 0
    result = 0
    for bit, score in enumerate(vector):
        if score >= 0:
            result |= 1 << bit
    return result


def _contains_phrase(tokens: Sequence[str], phrase: Sequence[str]) -> bool:
    if not phrase or len(phrase) > len(tokens):
        return False
    width = len(phrase)
    target = tuple(phrase)
    return any(tuple(tokens[index : index + width]) == target for index in range(len(tokens) - width + 1))


def _jaccard(left: set[Any] | frozenset[Any], right: set[Any] | frozenset[Any]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _record_descriptor(record: LoadedContentRecord) -> dict[str, Any]:
    manifest = record.manifest
    return {
        "record_id": manifest["record_id"],
        "role": manifest["role"],
        "source_family": manifest["source_family"],
        "source_id": manifest["source_id"],
        "era_window": manifest["era_window"],
        "holdout_status": manifest["holdout_status"],
        "synthetic_fixture": manifest["synthetic_fixture"],
    }


def _pair_flags(left: LoadedContentRecord, right: LoadedContentRecord) -> dict[str, bool]:
    left_manifest = left.manifest
    right_manifest = right.manifest
    return {
        "cross_source_family": left_manifest["source_family"] != right_manifest["source_family"],
        "cross_source_id": left_manifest["source_id"] != right_manifest["source_id"],
        "cross_era": left_manifest["era_window"] != right_manifest["era_window"],
        "cross_role": left_manifest["role"] != right_manifest["role"],
        "crosses_holdout_boundary": left_manifest["holdout_status"] != right_manifest["holdout_status"],
    }


def _clusters(
    records: Sequence[LoadedContentRecord],
    *,
    field: str,
    prefix: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[LoadedContentRecord]] = defaultdict(list)
    for record in records:
        grouped[str(record.manifest[field])].append(record)
    output: list[dict[str, Any]] = []
    for digest, members in sorted(grouped.items()):
        if len(members) < 2:
            continue
        ordered = sorted(members, key=lambda item: item.manifest["record_id"])
        families = sorted({item.manifest["source_family"] for item in ordered})
        eras = sorted({item.manifest["era_window"] for item in ordered})
        roles = sorted({item.manifest["role"] for item in ordered})
        holdout = sorted({item.manifest["holdout_status"] for item in ordered})
        output.append(
            {
                "cluster_id": f"{prefix}-{digest[:16]}",
                "digest": digest,
                "records": [_record_descriptor(item) for item in ordered],
                "record_count": len(ordered),
                "cross_source_family": len(families) > 1,
                "cross_era": len(eras) > 1,
                "cross_role": len(roles) > 1,
                "crosses_holdout_boundary": len(holdout) > 1,
            }
        )
    return output


def _add_candidate(
    candidates: dict[tuple[str, str], set[str]],
    left_id: str,
    right_id: str,
    method: str,
    *,
    max_candidate_pairs: int,
) -> None:
    pair = tuple(sorted((left_id, right_id)))
    if pair[0] == pair[1]:
        return
    if pair not in candidates and len(candidates) >= max_candidate_pairs:
        raise ContentIntegrityError(
            "near-duplicate candidate-pair limit exceeded; narrow buckets or raise the frozen limit explicitly"
        )
    candidates.setdefault(pair, set()).add(method)


def _near_duplicates(
    records: Sequence[LoadedContentRecord],
    *,
    config: IntegrityConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ordered = sorted(records, key=lambda item: item.manifest["record_id"])
    by_id = {item.manifest["record_id"]: item for item in ordered}
    shingle_sets = {
        item.manifest["record_id"]: _shingles(item.tokens, config.shingle_size)
        for item in ordered
    }
    exact_normalized_pairs: set[tuple[str, str]] = set()
    normalized_groups: dict[str, list[str]] = defaultdict(list)
    for item in ordered:
        normalized_groups[item.manifest["normalized_sha256"]].append(item.manifest["record_id"])
    for ids in normalized_groups.values():
        for left_id, right_id in itertools.combinations(sorted(ids), 2):
            exact_normalized_pairs.add((left_id, right_id))

    candidates: dict[tuple[str, str], set[str]] = {}
    skipped_large_buckets = 0
    shingle_buckets: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for record_id, shingles in shingle_sets.items():
        for shingle in shingles:
            shingle_buckets[shingle].append(record_id)
    for record_ids in shingle_buckets.values():
        unique_ids = sorted(set(record_ids))
        if len(unique_ids) > config.max_shingle_bucket_records:
            skipped_large_buckets += 1
            continue
        for left_id, right_id in itertools.combinations(unique_ids, 2):
            _add_candidate(
                candidates,
                left_id,
                right_id,
                "shared-shingle",
                max_candidate_pairs=config.max_candidate_pairs,
            )

    band_width = config.simhash_bits // config.simhash_band_count
    band_mask = (1 << band_width) - 1
    band_buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for record_id, shingles in shingle_sets.items():
        value = _simhash(shingles, config.simhash_bits)
        for band in range(config.simhash_band_count):
            band_value = (value >> (band * band_width)) & band_mask
            band_buckets[(band, band_value)].append(record_id)
    for record_ids in band_buckets.values():
        unique_ids = sorted(set(record_ids))
        if len(unique_ids) > config.max_shingle_bucket_records:
            skipped_large_buckets += 1
            continue
        for left_id, right_id in itertools.combinations(unique_ids, 2):
            _add_candidate(
                candidates,
                left_id,
                right_id,
                "simhash-band",
                max_candidate_pairs=config.max_candidate_pairs,
            )

    output: list[dict[str, Any]] = []
    for (left_id, right_id), methods in sorted(candidates.items()):
        if (left_id, right_id) in exact_normalized_pairs:
            continue
        left = by_id[left_id]
        right = by_id[right_id]
        left_shingles = shingle_sets[left_id]
        right_shingles = shingle_sets[right_id]
        shared = len(left_shingles & right_shingles)
        score = _jaccard(left_shingles, right_shingles)
        if score < config.near_duplicate_jaccard_threshold:
            continue
        output.append(
            {
                "pair_id": canonical_json_sha256([left_id, right_id])[:20],
                "left": _record_descriptor(left),
                "right": _record_descriptor(right),
                "candidate_methods": sorted(methods),
                "shared_shingles": shared,
                "left_shingles": len(left_shingles),
                "right_shingles": len(right_shingles),
                "jaccard": round(score, 12),
                **_pair_flags(left, right),
            }
        )
    diagnostics = {
        "candidate_pair_count": len(candidates),
        "verified_near_pair_count": len(output),
        "skipped_large_bucket_count": skipped_large_buckets,
        "shingle_size": config.shingle_size,
        "simhash_bits": config.simhash_bits,
        "simhash_band_count": config.simhash_band_count,
        "jaccard_threshold": config.near_duplicate_jaccard_threshold,
    }
    return output, diagnostics


def _evaluation_exposure(
    records: Sequence[LoadedContentRecord],
    *,
    config: IntegrityConfig,
) -> list[dict[str, Any]]:
    evaluation = sorted(
        (record for record in records if record.manifest["role"] == "evaluation"),
        key=lambda item: item.manifest["record_id"],
    )
    sources = sorted(
        (record for record in records if record.manifest["role"] != "evaluation"),
        key=lambda item: item.manifest["record_id"],
    )
    output: list[dict[str, Any]] = []
    for eval_record in evaluation:
        eval_ngrams = _shingles(eval_record.tokens, config.evaluation_ngram_size)
        for source_record in sources:
            source_ngrams = _shingles(source_record.tokens, config.evaluation_ngram_size)
            shared = len(eval_ngrams & source_ngrams)
            jaccard = _jaccard(eval_ngrams, source_ngrams)
            containment = shared / len(eval_ngrams) if eval_ngrams else 0.0
            exact_substring = (
                len(eval_record.tokens) >= config.evaluation_ngram_size
                and eval_record.normalized_text in source_record.normalized_text
            )
            flagged = exact_substring or (
                shared >= config.evaluation_min_shared_ngrams
                and (
                    jaccard >= config.evaluation_jaccard_threshold
                    or containment >= config.evaluation_containment_threshold
                )
            )
            if not flagged:
                continue
            output.append(
                {
                    "pair_id": canonical_json_sha256(
                        [eval_record.manifest["record_id"], source_record.manifest["record_id"]]
                    )[:20],
                    "evaluation": _record_descriptor(eval_record),
                    "source": _record_descriptor(source_record),
                    "exact_normalized_substring": exact_substring,
                    "shared_ngrams": shared,
                    "evaluation_ngrams": len(eval_ngrams),
                    "source_ngrams": len(source_ngrams),
                    "jaccard": round(jaccard, 12),
                    "evaluation_containment": round(containment, 12),
                    **_pair_flags(eval_record, source_record),
                }
            )
    return output


def _direct_exposure(
    records: Sequence[LoadedContentRecord],
    patterns: Sequence[DirectPattern],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item.manifest["record_id"]):
        if record.manifest["role"] == "evaluation":
            continue
        matches = [
            pattern
            for pattern in patterns
            if _contains_phrase(record.tokens, pattern.normalized_tokens)
        ]
        if not matches:
            continue
        output.append(
            {
                "record": _record_descriptor(record),
                "pattern_ids": sorted(pattern.pattern_id for pattern in matches),
                "categories": sorted({pattern.category for pattern in matches}),
                "match_count": len(matches),
                "disposition": "triage-only",
            }
        )
    return output


def _pair_counter(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in items:
        left = item.get("left") or item.get("evaluation")
        right = item.get("right") or item.get("source")
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            continue
        pair = "|".join(sorted((str(left["source_family"]), str(right["source_family"]))))
        counter[pair] += 1
    return dict(sorted(counter.items()))


def audit_content_integrity(
    records: Sequence[LoadedContentRecord],
    *,
    manifest_sha256: str,
    config: IntegrityConfig,
    config_sha256: str,
    patterns: Sequence[DirectPattern],
    patterns_sha256: str,
    holdout_authorization: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not records:
        raise ContentIntegrityError("content audit requires at least one record")
    auth_errors = validate_holdout_authorization(
        [record.manifest for record in records],
        manifest_sha256=manifest_sha256,
        authorization=holdout_authorization,
    )
    if auth_errors:
        raise ContentIntegrityError("; ".join(auth_errors))
    real_c_count = sum(
        record.manifest["role"] == "adaptation"
        and record.manifest["source_family"] == "C"
        and record.manifest["synthetic_fixture"] is False
        for record in records
    )

    raw_clusters = _clusters(records, field="content_sha256", prefix="raw")
    normalized_clusters = _clusters(
        records, field="normalized_sha256", prefix="normalized"
    )
    near_pairs, near_diagnostics = _near_duplicates(records, config=config)
    evaluation_exposure = _evaluation_exposure(records, config=config)
    direct_exposure = _direct_exposure(records, patterns)

    summary = {
        "record_count": len(records),
        "adaptation_record_count": sum(
            record.manifest["role"] == "adaptation" for record in records
        ),
        "evaluation_record_count": sum(
            record.manifest["role"] == "evaluation" for record in records
        ),
        "exact_raw_cluster_count": len(raw_clusters),
        "exact_normalized_cluster_count": len(normalized_clusters),
        "near_duplicate_pair_count": len(near_pairs),
        "evaluation_exposure_pair_count": len(evaluation_exposure),
        "direct_exposure_record_count": len(direct_exposure),
        "real_source_c_record_count": real_c_count,
        "cross_source_raw_cluster_count": sum(
            cluster["cross_source_family"] for cluster in raw_clusters
        ),
        "cross_source_normalized_cluster_count": sum(
            cluster["cross_source_family"] for cluster in normalized_clusters
        ),
        "cross_source_near_pair_count": sum(
            pair["cross_source_family"] for pair in near_pairs
        ),
        "holdout_boundary_near_pair_count": sum(
            pair["crosses_holdout_boundary"] for pair in near_pairs
        ),
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "audit_type": "content-integrity-v0",
        "manifest_sha256": manifest_sha256,
        "config_sha256": config_sha256,
        "direct_patterns_sha256": patterns_sha256,
        "normalization_version": config.normalization_version,
        "report_text_excerpts": False,
        "semantic_similarity_performed": False,
        "automatic_exclusion_performed": False,
        "holdout": {
            "real_source_c_record_count": real_c_count,
            "authorization_required": real_c_count > 0,
            "authorization_present": holdout_authorization is not None,
            "authorization_sha256": (
                canonical_json_sha256(holdout_authorization)
                if holdout_authorization is not None
                else None
            ),
            "no_behavioral_outcomes_inspected": (
                holdout_authorization.get("no_behavioral_outcomes_inspected")
                if holdout_authorization is not None
                else None
            ),
        },
        "summary": summary,
        "exact_raw_clusters": raw_clusters,
        "exact_normalized_clusters": normalized_clusters,
        "near_duplicate_pairs": near_pairs,
        "near_duplicate_diagnostics": near_diagnostics,
        "evaluation_exposure_pairs": evaluation_exposure,
        "direct_exposure_records": direct_exposure,
        "source_pair_counts": {
            "near_duplicate": _pair_counter(near_pairs),
            "evaluation_exposure": _pair_counter(evaluation_exposure),
        },
        "limitations": [
            "near-duplicate detection is deterministic lexical triage, not semantic equivalence",
            "direct patterns are narrow construct cues and cannot establish direct teaching by themselves",
            "evaluation exposure is lexical and must be reviewed with source context under the applicable firewall",
            "no record is excluded automatically by this report",
        ],
    }
    report["output_sha256"] = canonical_json_sha256(report)
    return report
