#!/usr/bin/env python3
"""Apply the evidence-specific first-fragment-overrun recovery rule once."""

from __future__ import annotations

from pathlib import Path


PATH = Path(__file__).with_name("recover_content_integrity_bundle_once.py")


def replace_exact(text: str, old: str, new: str, *, expected: int = 1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"expected {expected} matches, found {count}: {old[:100]!r}")
    return text.replace(old, new)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = replace_exact(text, "import tarfile\n", "import tarfile\nimport zlib\n")
    old_exceptions = "(binascii.Error, EOFError, OSError, tarfile.TarError, RecoveryError)"
    text = replace_exact(
        text,
        old_exceptions,
        "(binascii.Error, EOFError, OSError, tarfile.TarError, RecoveryError, zlib.error)",
        expected=2,
    )

    old_call = "    repair, payload, members = recover(normalized)\n"
    new_call = """    normalized_parts = tuple(
        b"".join(content.split()) for content in part_bytes
    )
    observed_lengths = [len(part) for part in normalized_parts]
    required_lengths = [4867, 4606, 4606, 4606, 4606, 4606, 4606, 4602]
    if observed_lengths != required_lengths:
        raise RecoveryError(
            f"fragment lengths changed: {observed_lengths} != {required_lengths}"
        )
    nominal_width = 4606
    overrun = normalized_parts[0][nominal_width:]
    if len(overrun) != 261:
        raise RecoveryError(f"unexpected first-fragment overrun: {len(overrun)}")
    matching_prefix = 0
    for left, right in zip(overrun, normalized_parts[1]):
        if left != right:
            break
        matching_prefix += 1
    if matching_prefix != 257:
        raise RecoveryError(
            f"unexpected first-boundary duplicated prefix: {matching_prefix}"
        )
    repaired_base64 = normalized_parts[0][:nominal_width] + b"".join(
        normalized_parts[1:]
    )
    compressed, payload, members = decode_candidate(repaired_base64)
    repair = {
        "mode": "trim-first-fragment-overrun",
        "positions": list(range(nominal_width, len(normalized_parts[0]))),
        "characters": sorted(set(overrun.decode("ascii"))),
        "direct_decode_error": (
            "fragment 0 contained a 261-character overrun beginning at the "
            "common 4606-character boundary; its first 257 characters duplicated "
            "fragment 1"
        ),
        "compressed": compressed,
    }
"""
    text = replace_exact(text, old_call, new_call)
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
