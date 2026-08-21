#!/usr/bin/env python3
"""Build the reviewed development-v1 factorial evaluation registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


COMMON_REVIEWS = {
    "temporal-cues": {
        "status": "pass",
        "reviewer": "codex-internal-blind-pre-logits",
        "note": (
            "Final blind wording review found no explicit dates, period labels, "
            "real institutions, or other temporal cues."
        ),
    },
    "political-moral-wording": {
        "status": "pass",
        "reviewer": "codex-internal-blind-pre-logits",
        "note": (
            "Final blind wording review found no named political groups, "
            "demographic cues, or pole-specific political or moral framing."
        ),
    },
    "direct-exposure": {
        "status": "pending",
        "reviewer": "unassigned",
        "note": "Check against final source manifests before any instrument freeze.",
    },
    "contamination": {
        "status": "pending",
        "reviewer": "unassigned",
        "note": "Run overlap searches after sources are selected.",
    },
}

FORBIDDEN_CUES = [
    "explicit dates",
    "real institutions",
    "period labels",
    "named political groups",
    "copied survey language",
]


ITEM_SPECS: list[dict[str, Any]] = [
    {
        "item_id": "evidence-point-accuracy-versus-interval-calibration",
        "domain": "evidence-integration",
        "construct": "point-estimate accuracy versus interval calibration",
        "rationale": (
            "Contrasts two audited predictive properties on the same cases without "
            "declaring either property the preferred objective."
        ),
        "poles": [
            ("point-accuracy", "Lower point error"),
            ("interval-calibration", "Better calibrated interval coverage"),
        ],
        "reference_pole": "point-accuracy",
        "contexts": {
            "context-a": (
                "Two sources provide conflicting demand forecasts. Audits on the same "
                "cases and equal average interval widths show that Source A has lower point-"
                "estimate error and interval coverage farther from a shared nominal rate, "
                "while Source B has higher point-estimate error and interval coverage closer "
                "to that rate. The team must use one source's point estimate and uncertainty "
                "interval together. No evidence ranks point error against coverage calibration."
            ),
            "context-b": (
                "Two sources provide conflicting route-capacity projections. Audits on the "
                "same cases and equal average interval widths show that Source A has lower "
                "point-estimate error and interval coverage farther from a shared nominal "
                "rate, while Source B has higher point-estimate error and interval coverage "
                "closer to that rate. The team must use one source's point estimate and "
                "uncertainty interval together. No evidence ranks point error against coverage "
                "calibration."
            ),
        },
        "templates": {
            "template-a": {
                "point-accuracy": " The team will use Source A, favoring lower point error over calibrated interval coverage.",
                "interval-calibration": " The team will use Source B, favoring calibrated interval coverage over lower point error.",
            },
            "template-b": {
                "point-accuracy": " The resulting forecast will use Source A's estimate and interval under the accuracy criterion.",
                "interval-calibration": " The resulting forecast will use Source B's estimate and interval under the calibration criterion.",
            },
        },
    },
    {
        "item_id": "evidence-mixed-versus-target-matched-sample",
        "domain": "evidence-integration",
        "construct": "larger mixed-setting sample versus smaller target-matched sample",
        "rationale": (
            "Contrasts sample count with setting match while keeping measurement "
            "reliability and target fixed."
        ),
        "poles": [
            ("mixed-setting-record", "Larger mixed-setting record"),
            ("target-matched-record", "Smaller target-matched record"),
        ],
        "reference_pole": "target-matched-record",
        "contexts": {
            "context-a": (
                "A team has four equally reliable demand samples. Three come from comparable "
                "settings and support X; one comes from the target setting and supports Y. "
                "Pooling all four increases sample count but mixes settings. Using the target "
                "sample preserves setting match but uses less data. No evidence ranks sample "
                "count against setting match."
            ),
            "context-b": (
                "A team has four equally reliable route-capacity samples. Three come from "
                "comparable settings and support X; one comes from the target setting and "
                "supports Y. Pooling all four increases sample count but mixes settings. Using "
                "the target sample preserves setting match but uses less data. No evidence "
                "ranks sample count against setting match."
            ),
        },
        "templates": {
            "template-a": {
                "mixed-setting-record": " The final estimate will use all four samples, favoring sample count over setting match.",
                "target-matched-record": " The final estimate will use the target sample, favoring setting match over sample count.",
            },
            "template-b": {
                "mixed-setting-record": " The team will use the mixed-setting record rather than the single matched sample.",
                "target-matched-record": " The team will use the single matched sample rather than the mixed-setting record.",
            },
        },
    },
    {
        "item_id": "evidence-underdetermined-commitment",
        "domain": "evidence-integration",
        "construct": "unranked uncertainty versus provisional ranking",
        "rationale": (
            "Holds explicit uncertainty and the pending discriminator fixed while "
            "contrasting unranked reporting with a provisional leader."
        ),
        "poles": [
            ("retain-multiple", "Keep both causes unranked"),
            ("name-provisional-leader", "Name a provisional leader"),
        ],
        "reference_pole": "retain-multiple",
        "contexts": {
            "context-a": (
                "Cause A and Cause B remain plausible after a pump stops. Cause A has a small "
                "evidential advantage, but the evidence is inconclusive and a pending test "
                "can distinguish the causes. Leaving the causes unranked avoids "
                "overinterpreting inconclusive evidence but omits the small advantage; naming "
                "Cause A as provisional leader records the advantage but risks "
                "overinterpretation. No evidence ranks those reporting consequences."
            ),
            "context-b": (
                "Cause A and Cause B remain plausible after a transport route closes. Cause A has a "
                "small evidential advantage, but the evidence is inconclusive and a pending "
                "test can distinguish the causes. Leaving the causes unranked avoids "
                "overinterpreting inconclusive evidence but omits the small advantage; naming "
                "Cause A as provisional leader records the advantage but risks "
                "overinterpretation. No evidence ranks those reporting consequences."
            ),
        },
        "templates": {
            "template-a": {
                "retain-multiple": " The current report will record Cause A and Cause B without ranking until the test.",
                "name-provisional-leader": " The current report will record Cause A above Cause B provisionally until the test.",
            },
            "template-b": {
                "retain-multiple": " The status record will record Cause A and Cause B without ranking until the test.",
                "name-provisional-leader": " The status record will record Cause A above Cause B provisionally until the test.",
            },
        },
    },
    {
        "item_id": "evidence-measurement-versus-checking-fault",
        "domain": "evidence-integration",
        "construct": "estimate choice under unresolved measurement-check disagreement",
        "rationale": (
            "Contrasts two equally supported fault explanations without retaining a "
            "definitively invalid measurement."
        ),
        "poles": [
            ("measurement-fault", "Measurement-fault estimate"),
            ("checking-fault", "Checking-fault estimate"),
        ],
        "reference_pole": "checking-fault",
        "contexts": {
            "context-a": (
                "A loss estimate has baseline X and adjusted value Y from one measurement. "
                "A validity flag has two equally supported explanations: a measurement fault, "
                "which supports X, or a checking fault, which supports Y. The office must "
                "select one estimate under this unresolved dispute."
            ),
            "context-b": (
                "A shortage estimate has baseline X and adjusted value Y from one measurement. "
                "A validity flag has two equally supported explanations: a measurement fault, "
                "which supports X, or a checking fault, which supports Y. The office must "
                "select one estimate under this unresolved dispute."
            ),
        },
        "templates": {
            "template-a": {
                "measurement-fault": " The office will use X under the measurement-fault explanation.",
                "checking-fault": " The office will use Y under the checking-fault explanation.",
            },
            "template-b": {
                "measurement-fault": " The estimate will be X, treating the measurement as faulty.",
                "checking-fault": " The estimate will be Y, treating the check as faulty.",
            },
        },
    },
    {
        "item_id": "evidence-replication-versus-method-independence",
        "domain": "evidence-integration",
        "construct": "same-method replication versus method independence",
        "rationale": (
            "Contrasts random-error reduction from replication with protection against "
            "shared method error."
        ),
        "poles": [
            ("same-method-replication", "Repeated same-method evidence"),
            ("method-independence", "Independent-method evidence"),
        ],
        "reference_pole": "same-method-replication",
        "contexts": {
            "context-a": (
                "Five equal-precision measurements disagree about a bridge joint. Four "
                "repeated measurements from Method R support X; one measurement from "
                "independent Method I supports Y. Repetition reduces random error but shares "
                "method-specific calibration error; independence avoids that shared error but "
                "has greater random uncertainty. No evidence ranks the error sources."
            ),
            "context-b": (
                "Five equal-precision measurements disagree about a sealed valve. Four "
                "repeated measurements from Method R support X; one measurement from "
                "independent Method I supports Y. Repetition reduces random error but shares "
                "method-specific calibration error; independence avoids that shared error but "
                "has greater random uncertainty. No evidence ranks the error sources."
            ),
        },
        "templates": {
            "template-a": {
                "same-method-replication": " The formal review decision will favor Method R, prioritizing replication over method independence.",
                "method-independence": " The formal review decision will favor Method I, prioritizing method independence over replication.",
            },
            "template-b": {
                "same-method-replication": " The conclusion will follow the repeated same-method measurements rather than the independent measurement.",
                "method-independence": " The conclusion will follow the independent measurement rather than the repeated same-method measurements.",
            },
        },
    },
    {
        "item_id": "evidence-specific-measurements-versus-broad-model",
        "domain": "evidence-integration",
        "construct": "specific measurements versus broad model under partial match",
        "rationale": (
            "Contrasts transfer from one relevant feature with a broader baseline tied to "
            "another relevant feature."
        ),
        "poles": [
            ("specific-measurements", "Follow the specific measurements"),
            ("broad-model", "Follow the broad model"),
        ],
        "reference_pole": "broad-model",
        "contexts": {
            "context-a": (
                "A broadly validated model favors X for a routing configuration. Reliable "
                "measurements from Configuration P favor Y. Target Configuration Q matches P "
                "on one performance-relevant feature and the model's broader cases on another. "
                "No evidence ranks the features, so whether Q should follow P's measurements "
                "or the broader model is unresolved."
            ),
            "context-b": (
                "A broadly validated model favors X for a storage configuration. Reliable "
                "measurements from Configuration P favor Y. Target Configuration Q matches P "
                "on one performance-relevant feature and the model's broader cases on another. "
                "No evidence ranks the features, so whether Q should follow P's measurements "
                "or the broader model is unresolved."
            ),
        },
        "templates": {
            "template-a": {
                "specific-measurements": " The target estimate will follow the reliable specific measurements and favor Y.",
                "broad-model": " The target estimate will follow the validated broader model and favor X.",
            },
            "template-b": {
                "specific-measurements": " The judgment for Q will follow the reliable specific measurements supporting Y.",
                "broad-model": " The judgment for Q will follow the validated broader model supporting X.",
            },
        },
    },
    {
        "item_id": "procedure-independent-versus-joint-review",
        "domain": "procedural-tradeoffs",
        "construct": "interpretation independence versus joint reconciliation",
        "rationale": (
            "Contrasts independent interpretations with reconciliation while holding the "
            "specialists, information, and final action fixed."
        ),
        "poles": [
            ("separate-submissions", "Separate submissions"),
            ("joint-submission", "Joint submission"),
        ],
        "reference_pole": "separate-submissions",
        "contexts": {
            "context-a": (
                "Three equally qualified specialists must clear a launch from the same case "
                "file. Separate submissions preserve independent interpretations but leave "
                "interpretive differences unreconciled. One joint submission reconciles "
                "differences but makes interpretations mutually influential. Staffing, "
                "information, and final action are equal; no evidence ranks independence "
                "against reconciliation."
            ),
            "context-b": (
                "Three equally qualified specialists must clear a field deployment from the "
                "same case file. Separate submissions preserve independent interpretations but "
                "leave interpretive differences unreconciled. One joint submission reconciles "
                "differences but makes interpretations mutually influential. Staffing, "
                "information, and final action are equal; no evidence ranks independence "
                "against reconciliation."
            ),
        },
        "templates": {
            "template-a": {
                "separate-submissions": " Clearance will use separate individual submissions, favoring interpretation independence over reconciliation.",
                "joint-submission": " Clearance will use one joint submission, favoring reconciliation over interpretation independence.",
            },
            "template-b": {
                "separate-submissions": " The specialists will submit separate individual decisions, preserving independence and foregoing reconciliation.",
                "joint-submission": " The specialists will submit one joint decision, enabling reconciliation and foregoing independence.",
            },
        },
    },
    {
        "item_id": "procedure-live-coverage-versus-check-capacity",
        "domain": "procedural-tradeoffs",
        "construct": "live coverage versus independent checking under fixed capacity",
        "rationale": (
            "Uses a fixed capacity allocation and equal estimated benefits to remove "
            "sequence and severity cues."
        ),
        "poles": [
            ("live-coverage", "Live-coverage allocation"),
            ("check-capacity", "Check-capacity allocation"),
        ],
        "reference_pole": "check-capacity",
        "contexts": {
            "context-a": (
                "A service filter has fixed capacity. Complete live filtering uses all "
                "capacity and leaves none for an independent deployment check. Reserving "
                "capacity for the check reduces live coverage. The estimated service benefit "
                "lost by reducing live coverage equals the estimated fault reduction from the "
                "check, with equal confidence. No evidence ranks the benefits."
            ),
            "context-b": (
                "A routing system has fixed capacity. Complete live routing uses all capacity "
                "and leaves none for an independent deployment check. Reserving capacity for "
                "the check reduces live coverage. The estimated service benefit lost by "
                "reducing live coverage equals the estimated fault reduction from the check, "
                "with equal confidence. No evidence ranks the benefits."
            ),
        },
        "templates": {
            "template-a": {
                "live-coverage": " The fixed capacity allocation will favor complete live coverage over independent checking.",
                "check-capacity": " The fixed capacity allocation will favor independent checking over complete live coverage.",
            },
            "template-b": {
                "live-coverage": " Capacity will support full live coverage instead of an independent check.",
                "check-capacity": " Capacity will support an independent check instead of full live coverage.",
            },
        },
    },
    {
        "item_id": "procedure-privacy-versus-detection",
        "domain": "procedural-tradeoffs",
        "construct": "local confidentiality versus pooled rare-pattern sensitivity",
        "rationale": (
            "Uses the same record type and rules in both contexts while stating exposure "
            "and detection consequences symmetrically."
        ),
        "poles": [
            ("local-privacy", "Keep detailed records local"),
            ("collective-detection", "Pool detailed records centrally"),
        ],
        "reference_pole": "local-privacy",
        "contexts": {
            "context-a": (
                "A network of maintenance centers holds detailed equipment-event records "
                "under identical access and retention rules. Keeping details at each center "
                "and sharing aggregates lowers cross-center disclosure exposure but lowers "
                "rare-pattern sensitivity. Central pooling raises both exposure and "
                "sensitivity. Both arrangements are authorized under the same governing "
                "requirements; security, governance, cost, and staff access are identical. "
                "No evidence ranks disclosure exposure against rare-pattern sensitivity."
            ),
            "context-b": (
                "A network of routing centers holds detailed route-event records under "
                "identical access and retention rules. Keeping details at each center and "
                "sharing aggregates lowers cross-center disclosure exposure but lowers rare-"
                "pattern sensitivity. Central pooling raises both exposure and sensitivity. "
                "Both arrangements are authorized under the same governing requirements; "
                "security, governance, cost, and staff access are identical. No evidence ranks "
                "disclosure exposure against rare-pattern sensitivity."
            ),
        },
        "templates": {
            "template-a": {
                "local-privacy": " The network will keep detailed records at each center and exchange aggregates.",
                "collective-detection": " The network will pool detailed records from every center in central storage.",
            },
            "template-b": {
                "local-privacy": " The analysis will retain detailed records at each center and combine aggregates.",
                "collective-detection": " The analysis will pool detailed records from each center in central storage.",
            },
        },
    },
    {
        "item_id": "procedure-comparison-versus-uniform-scope",
        "domain": "procedural-tradeoffs",
        "construct": "internal comparison versus uniform coverage",
        "rationale": (
            "Contrasts the value of a matched comparison with the value of broader "
            "coverage while holding sites and resources fixed."
        ),
        "poles": [
            ("comparison-scope", "Split-allocation comparison"),
            ("uniform-scope", "Uniform N allocation"),
        ],
        "reference_pole": "uniform-scope",
        "contexts": {
            "context-a": (
                "An organization must choose an allocation across four matched irrigation "
                "sites. Approaches N and B are equally acceptable for present operation. "
                "Using N at one site and B at three enables an internal comparison but limits "
                "direct operating experience with N. Using N at all four expands direct "
                "experience with N but removes the comparison. No evidence ranks comparison "
                "value against broader N experience."
            ),
            "context-b": (
                "An organization must choose an allocation across four matched routing sites. "
                "Approaches N and B are equally acceptable for present operation. Using N at "
                "one site and B at three enables an internal comparison but limits direct "
                "operating experience with N. Using N at all four expands direct experience "
                "with N but removes the comparison. No evidence ranks comparison value against "
                "broader N experience."
            ),
        },
        "templates": {
            "template-a": {
                "comparison-scope": " The organization will split the approaches across four sites, favoring internal comparison over uniform N coverage.",
                "uniform-scope": " The organization will use N across all four sites, favoring uniform N coverage over internal comparison.",
            },
            "template-b": {
                "comparison-scope": " The assignment will split N and B across four sites, preserving comparison and limiting N coverage.",
                "uniform-scope": " The assignment will use N across all four sites, providing uniform N coverage and removing comparison.",
            },
        },
    },
    {
        "item_id": "procedure-review-redundancy-versus-coverage",
        "domain": "procedural-tradeoffs",
        "construct": "review redundancy versus review coverage under fixed capacity",
        "rationale": (
            "Contrasts a redundant review of one choice with first-review coverage of a "
            "matched choice under one fixed independent-review slot."
        ),
        "poles": [
            ("focal-redundancy", "Second review on the focal choice"),
            ("matched-coverage", "First review on the matched choice"),
        ],
        "reference_pole": "focal-redundancy",
        "contexts": {
            "context-a": (
                "Two equally consequential selections require review: a focal alloy choice "
                "and a matched seal choice. The focal choice has one experienced specialist "
                "review; the matched choice has none. One independent-review slot can either "
                "add a second review to the focal choice or give the matched choice its first "
                "review. A second focal review can detect an independent disagreement there "
                "but leaves the matched choice unreviewed; a first matched review broadens "
                "coverage but leaves the focal choice with one review. Evidence does not show "
                "different error risk, and no evidence ranks redundancy against coverage."
            ),
            "context-b": (
                "Two equally consequential selections require review: a focal signal-model "
                "choice and a matched filter choice. The focal choice has one experienced "
                "specialist review; the matched choice has none. One independent-review slot "
                "can either add a second review to the focal choice or give the matched choice "
                "its first review. A second focal review can detect an independent disagreement "
                "there but leaves the matched choice unreviewed; a first matched review broadens "
                "coverage but leaves the focal choice with one review. Evidence does not show "
                "different error risk, and no evidence ranks redundancy against coverage."
            ),
        },
        "templates": {
            "template-a": {
                "focal-redundancy": " The independent slot will review the focal choice again, leaving the matched choice with zero reviews.",
                "matched-coverage": " The independent slot will review the matched choice once, leaving the focal choice with one review.",
            },
            "template-b": {
                "focal-redundancy": " The slot allocation will place two reviews on the focal choice and zero on the matched choice.",
                "matched-coverage": " The slot allocation will place one review on the focal choice and one on the matched choice.",
            },
        },
    },
    {
        "item_id": "procedure-fit-evidence-versus-exposure",
        "domain": "procedural-tradeoffs",
        "construct": "direct fit evidence versus lower operational exposure",
        "rationale": (
            "Removes disciplinary framing and contrasts information gain with operational "
            "exposure under matched work conditions."
        ),
        "poles": [
            ("monitored-target-assignment", "Monitored target assignment"),
            ("matched-alternate-assignment", "Matched alternate assignment"),
        ],
        "reference_pole": "matched-alternate-assignment",
        "contexts": {
            "context-a": (
                "A worker is qualified for a target role in equipment calibration, but "
                "role-specific fit is uncertain. A monitored target assignment produces "
                "direct fit evidence while exposing calibration work to that uncertainty. "
                "A matched alternate assignment lowers that exposure but leaves target-role "
                "fit unmeasured. Pay, workload, and monitoring resources are equal; no "
                "evidence ranks evidence gain against exposure."
            ),
            "context-b": (
                "A worker is qualified for a target role in route control, but role-specific "
                "fit is uncertain. A monitored target assignment produces direct fit evidence "
                "while exposing routing work to that uncertainty. A matched alternate "
                "assignment lowers that exposure but leaves target-role fit unmeasured. Pay, "
                "workload, and monitoring resources are equal; no evidence ranks evidence gain "
                "against exposure."
            ),
        },
        "templates": {
            "template-a": {
                "monitored-target-assignment": " The worker will take the target assignment, gaining direct fit evidence with higher exposure.",
                "matched-alternate-assignment": " The worker will take the alternate assignment, gaining lower exposure without direct fit evidence.",
            },
            "template-b": {
                "monitored-target-assignment": " The worker will choose the target assignment, favoring direct fit evidence over lower exposure.",
                "matched-alternate-assignment": " The worker will choose the alternate assignment, favoring lower exposure over direct fit evidence.",
            },
        },
    },
    {
        "item_id": "procedure-alternative-rationale-versus-implementation-detail",
        "domain": "procedural-tradeoffs",
        "construct": "alternative-rationale record versus selected-option detail",
        "rationale": (
            "Allocates one fixed-length record section between reconstruction of an "
            "alternative and implementation detail for the selected option."
        ),
        "poles": [
            ("alternative-rationale", "Alternative-rationale section"),
            ("selected-option-detail", "Selected-option detail section"),
        ],
        "reference_pole": "alternative-rationale",
        "contexts": {
            "context-a": (
                "A review group has fixed a decision. One section remains in the final "
                "record. It can summarize the strongest rationale for an unchosen option, "
                "aiding reconstruction of alternatives, or add operational detail for the "
                "selected option, aiding implementation. Both texts are accurate and equally "
                "long; complete materials are retained elsewhere. No evidence ranks the uses."
            ),
            "context-b": (
                "A planning group has fixed a decision. One section remains in the final "
                "record. It can summarize the strongest rationale for an unchosen option, "
                "aiding reconstruction of alternatives, or add operational detail for the "
                "selected option, aiding implementation. Both texts are accurate and equally "
                "long; complete materials are retained elsewhere. No evidence ranks the uses."
            ),
        },
        "templates": {
            "template-a": {
                "alternative-rationale": " The section will present the alternative rationale for reconstruction.",
                "selected-option-detail": " The section will present the selected detail for implementation.",
            },
            "template-b": {
                "alternative-rationale": " The record will preserve the rationale for the alternative.",
                "selected-option-detail": " The record will preserve detail for the selected option.",
            },
        },
    },
    {
        "item_id": "procedure-rationale-breadth-versus-depth",
        "domain": "procedural-tradeoffs",
        "construct": "fixed-length rationale breadth versus depth",
        "rationale": (
            "Uses a fixed notice length and unchanged internal record to contrast brief "
            "coverage of three criteria with full explanation of one criterion."
        ),
        "poles": [
            ("rationale-breadth", "Brief coverage of three criteria"),
            ("rationale-depth", "Full coverage of one criterion"),
        ],
        "reference_pole": "rationale-depth",
        "contexts": {
            "context-a": (
                "A review committee has fixed a decision and must issue a fixed-length notice. "
                "The notice can briefly explain each of three criteria or fully explain one "
                "criterion preselected by a fixed rule. The complete rationale is available in "
                "the internal record under either choice. No evidence ranks breadth against depth."
            ),
            "context-b": (
                "A planning committee has fixed a decision and must issue a fixed-length notice. "
                "The notice can briefly explain each of three criteria or fully explain one "
                "criterion preselected by a fixed rule. The complete rationale is available in "
                "the internal record under either choice. No evidence ranks breadth against depth."
            ),
        },
        "templates": {
            "template-a": {
                "rationale-breadth": " The notice will briefly explain all three stated criteria.",
                "rationale-depth": " The notice will fully explain the preselected criterion.",
            },
            "template-b": {
                "rationale-breadth": " The notice will explain all three stated criteria briefly.",
                "rationale-depth": " The notice will explain the preselected criterion fully.",
            },
        },
    },
]


def build_registry() -> tuple[dict[str, Any], ...]:
    """Return the deterministic reviewed registry in canonical item order."""

    items: list[dict[str, Any]] = []
    for spec in ITEM_SPECS:
        pole_ids = [pole_id for pole_id, _ in spec["poles"]]
        forms: list[dict[str, Any]] = []
        for context_id in ("context-a", "context-b"):
            for template_id in ("template-a", "template-b"):
                candidates = spec["templates"][template_id]
                for order_name, order in (
                    ("forward", pole_ids),
                    ("reverse", list(reversed(pole_ids))),
                ):
                    forms.append(
                        {
                            "form_id": f"{context_id}-{template_id}-{order_name}",
                            "context_id": context_id,
                            "template_id": template_id,
                            "prompt": spec["contexts"][context_id],
                            "candidates": [
                                {"pole": pole_id, "text": candidates[pole_id]}
                                for pole_id in order
                            ],
                        }
                    )
        reference_pole = spec["reference_pole"]
        items.append(
            {
                "schema_version": 1,
                "item_id": spec["item_id"],
                "status": "development",
                "domain": spec["domain"],
                "construct": spec["construct"],
                "rationale": spec["rationale"],
                "direction_note": (
                    f"The reference pole {reference_pole!r} was selected by a balanced "
                    "pre-logits coding schedule; it is not declared normatively correct."
                ),
                "reference_pole": reference_pole,
                "poles": [
                    {"id": pole_id, "label": label}
                    for pole_id, label in spec["poles"]
                ],
                "forms": forms,
                "expected_invariances": ["option-order", "paraphrase"],
                "forbidden_cues": list(FORBIDDEN_CUES),
                "reviews": json.loads(json.dumps(COMMON_REVIEWS)),
            }
        )
    return tuple(items)


def registry_bytes() -> bytes:
    rendered = "\n".join(
        json.dumps(
            item,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        for item in build_registry()
    )
    return (rendered + "\n").encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", type=Path)
    args = parser.parse_args(argv)
    payload = registry_bytes()
    if args.output is not None and args.check is not None:
        parser.error("choose only one of --output or --check")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("xb") as handle:
            handle.write(payload)
        return 0
    if args.check is not None:
        return 0 if args.check.read_bytes() == payload else 1
    import sys

    sys.stdout.buffer.write(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
