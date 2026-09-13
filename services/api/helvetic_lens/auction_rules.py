"""Explained asset matching, low-noise changes and reminder eligibility. No I/O."""

from datetime import timedelta

from .auction_contracts import NORMALIZATION_VERSION, RULE_VERSION, clock, fingerprint, phrase_in


def assessment(profile, facts):
    reasons = []

    def reason(field, status, code, value=None):
        reasons.append({"field": field, "status": status, "code": code, "value": value})

    reason("canton", "match" if facts.canton in profile.cantons else "excluded", "asset_canton", facts.canton)
    reason("category", "unknown" if facts.category is None else "match" if facts.category in profile.categories
        else "excluded", "asset_category", facts.category)
    for field, selected, value in (("asset_location", profile.locations, facts.asset_location),
                                   ("brand", profile.brands, facts.brand)):
        if selected:
            found = [p for p in selected if value is not None and phrase_in(p, value)]
            reason(field, "unknown" if value is None else "match" if found else "excluded", "explicit_phrase", found)
    if profile.keywords:
        found = [p for p in profile.keywords if phrase_in(p, facts.title) or
                 facts.description is not None and phrase_in(p, facts.description)]
        reason("title_description", "match" if found else "unknown" if facts.description is None else "excluded",
               "explicit_phrase", found)
    if profile.maximum_price_chf_cents is not None:
        price = facts.price(profile.budget_price_kind)
        known = price is not None and price.currency == "CHF"
        reason("prices." + profile.budget_price_kind,
            "unknown" if not known else "match" if price.amount_minor <= profile.maximum_price_chf_cents else "excluded",
            "budget", {"amount_minor": price.amount_minor, "currency": price.currency, "locator": price.locator} if price else None)
    statuses = {r["status"] for r in reasons}
    result = {"status": "excluded" if "excluded" in statuses else "unknown" if "unknown" in statuses else "match",
        "reasons": reasons, "rule_version": RULE_VERSION, "normalization_version": NORMALIZATION_VERSION,
        "profile_hash": profile.fingerprint(), "state_hash": facts.state_hash(), "raw_sha256": facts.raw_sha256,
        "source_url": facts.source_url, "identity": facts.identity(), "semantic_status": "not_evaluated"}
    result["assessment_hash"] = fingerprint(result)
    return result


def changes(profile, previous, current):
    if previous.identity() != current.identity():
        raise ValueError("Compare revisions of the same auction or lot")
    if current.observed_at < previous.observed_at:
        raise ValueError("A past observation cannot replace current state")
    result = []

    def add(code, field, before, after, notify):
        result.append({"code": code, "field": field, "before": before, "after": after, "notify": notify})

    for field in ("title", "description", "category", "asset_location", "brand", "authority"):
        if getattr(previous, field) != getattr(current, field):
            add("asset_details_changed", field, getattr(previous, field), getattr(current, field), True)
    for field in ("ends_at", "starts_at"):
        before, after = getattr(previous, field), getattr(current, field)
        if before != after:
            add("deadline_changed" if field == "ends_at" else "start_changed", field,
                before.isoformat() if before else None, after.isoformat() if after else None, profile.notify.deadline_change)
    if previous.status != current.status:
        add("cancelled" if current.status == "cancelled" else "status_changed", "status", previous.status,
            current.status, profile.notify.cancellation if current.status == "cancelled" else True)
    for kind in ("current_bid", "starting_price", "minimum_price", "estimate"):
        before, after = previous.price(kind), current.price(kind)
        b = (before.currency, before.amount_minor) if before else None
        a = (after.currency, after.amount_minor) if after else None
        if b == a:
            continue
        crossing = (kind == profile.budget_price_kind and profile.maximum_price_chf_cents is not None
            and before is not None and after is not None and before.currency == after.currency == "CHF"
            and before.amount_minor <= profile.maximum_price_chf_cents < after.amount_minor)
        add("price_above_limit" if crossing else "price_changed", "prices." + kind, b, a,
            (profile.notify.price_above_limit or profile.notify.every_bid_change) if crossing
            else profile.notify.every_bid_change if kind == "current_bid" else True)
    if previous.conditions_sha256 != current.conditions_sha256:
        add("conditions_changed" if previous.conditions_sha256 and current.conditions_sha256 else "conditions_coverage_changed",
            "conditions_sha256", previous.conditions_sha256, current.conditions_sha256, profile.notify.conditions_change)
    old = {d.official_id: d for d in previous.documents.items}
    new = {d.official_id: d for d in current.documents.items}
    for key in sorted(old.keys() | new.keys()):
        before, after = old.get(key), new.get(key)
        if before and not after and current.documents.state != "complete":
            continue  # Omission from an incomplete listing is never a removal.
        if not before and after:
            code = "document_added" if previous.documents.state == "complete" else "document_first_observed"
        elif before and not after:
            code = "document_removed"
        elif before == after:
            continue
        else:
            code = "document_changed" if before.sha256 and after.sha256 and before.sha256 != after.sha256 else "document_evidence_changed"
        add(code, "documents." + key, before.model_dump() if before else None,
            after.model_dump() if after else None, profile.notify.documents_change)
    if previous.documents.state != current.documents.state:
        add("document_coverage_changed", "documents.state", previous.documents.state, current.documents.state,
            profile.notify.documents_change)
    return result


def ending_soon(profile, facts, *, now, max_age_seconds, following):
    """Eligibility only; the private outbox must recheck review/rights/consent.

    Bind reminders to the exact end-time revision. An unchanged poll or bid does
    not invent another deadline; changed-away-and-back generations are assigned
    by the eventual durable journal, not this stateless rule.
    """
    now = clock(now)
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400 or type(following) is not bool:
        raise ValueError("Use a bounded reviewed source age and explicit following state")
    hours = profile.notify.ending_soon_hours
    if not following or hours is None:
        return {"eligible": False, "reason": "not_requested"}
    if not timedelta(0) <= now - facts.observed_at <= timedelta(seconds=max_age_seconds):
        return {"eligible": False, "reason": "source_not_current"}
    if facts.status != "open":
        return {"eligible": False, "reason": "auction_not_open"}
    if facts.starts_at is not None and now < facts.starts_at:
        return {"eligible": False, "reason": "auction_not_started"}
    if facts.ends_at is None:
        return {"eligible": False, "reason": "deadline_unknown"}
    due = facts.ends_at - timedelta(hours=hours)
    if not due <= now < facts.ends_at:
        return {"eligible": False, "reason": "outside_window", "due_at": due.isoformat()}
    return {"eligible": True, "reason": "ending_soon", "due_at": due.isoformat(),
        "ends_at": facts.ends_at.isoformat(), "identity": facts.identity(), "state_hash": facts.state_hash(),
        "deadline_hash": fingerprint([facts.identity(), facts.ends_at.isoformat()])}
