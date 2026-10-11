"""Site rules (Phase 2): decide if the active Brave tab counts as study.

Order: block -> mixed (e.g. youtube) -> allow -> unknown (not counted).
Config section [study_sites]: allow, block, mixed, study_keywords.
"""
from __future__ import annotations

DEFAULT_MIXED = ["youtube.com"]


def domain_matches(domain: str, pattern: str) -> bool:
    domain, pattern = domain.lower().strip("."), pattern.lower().strip(".")
    return domain == pattern or domain.endswith("." + pattern)


def _any(domain: str, patterns) -> bool:
    return any(domain_matches(domain, p) for p in patterns)


def classify(domain: str, title: str, shorts: bool, sites: dict) -> tuple[bool, str]:
    """Return (counts_as_study, reason)."""
    if not domain:
        return False, "no-domain"
    if _any(domain, sites.get("block", [])):
        return False, "blocked-site"
    if _any(domain, sites.get("mixed", DEFAULT_MIXED)):
        if shorts:
            return False, "shorts"
        t = (title or "").lower()
        if any(k.lower() in t for k in sites.get("study_keywords", [])):
            return True, "mixed-keyword-match"
        return False, "mixed-no-keyword"
    if _any(domain, sites.get("allow", [])):
        return True, "allowed-site"
    return False, "unknown-site"
