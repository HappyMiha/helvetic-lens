"""Deterministic provenance of an already authorized pair of captured sources.

This projection never searches other records or infers publisher independence,
document authorship, source truth or real-world validity from capture metadata.
"""
import re
from urllib.parse import urlsplit

VERSION = "captured-source-comparison/v1"
TEMPORAL_BASIS = (
    "Capture dates show when evidence was saved. Publication dates, effective dates "
    "and the time of a real-world change require separate evidence."
)


def address(value):
    """Exact recorded HTTP(S) address, excluding only the fragment."""
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
            return None
        _ = parts.port  # Reject malformed ports; do not normalize URL semantics.
    except ValueError:
        return None
    return value.partition("#")[0]


def digest(value):
    if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return value.lower()
    return None


def compare(previous, current):
    """Accept only the two exact evidence payloads selected by the scoped reader."""
    old, new = previous or {}, current or {}
    left, right = old.get("source") or {}, new.get("source") or {}
    old_hash, new_hash = digest(left.get("sha256")), digest(right.get("sha256"))
    same_kind = bool(left.get("kind")) and left.get("kind") == right.get("kind")
    content_match = old_hash == new_hash if same_kind and old_hash and new_hash else None
    old_address, new_address = address(left.get("url")), address(right.get("url"))
    same_address = old_address == new_address if old_address and new_address else None
    old_quote, new_quote = old.get("quote"), new.get("quote")
    same_excerpt = old_quote == new_quote if isinstance(old_quote, str) and old_quote.strip() and isinstance(new_quote, str) and new_quote.strip() else None
    if content_match:
        relationship = "matching_captured_content"
        basis = (
            "The captured content matches. Treat it as repeated evidence; "
            "complete-document equivalence and publisher independence remain unverified."
        )
    elif same_address:
        relationship = "same_recorded_address"
        basis = (
            "Both captures use the same source address. "
            + ("Their saved content differs. " if content_match is False else "Their content equivalence is unestablished. ")
            + "Repeated captures of one address do not establish independent support."
        )
    else:
        relationship = "unestablished"
        basis = (
            "Source independence is unverified, even when addresses or saved content differ."
        )
    if same_excerpt:
        basis += " The supporting quotations also match; a shared excerpt alone does not establish copied documents."
    return {"policy_version": VERSION, "relationship": relationship,
        "content_hash_match": content_match, "same_recorded_address": same_address,
        "same_supporting_excerpt": same_excerpt, "source_independence": "not_established",
        "observed_at": {"previous": left.get("captured_at"), "current": right.get("captured_at")},
        "publication_and_effective_dates": "not_established_by_capture_metadata",
        "basis": basis, "temporal_basis": TEMPORAL_BASIS}
