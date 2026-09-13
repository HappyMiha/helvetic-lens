from dataclasses import replace
from datetime import timedelta

import pytest
from test_hazard_cap import NOW, SENT, decoded, info, message, update

from helvetic_lens.hazard_cap import HazardCAPError, decode_cap
from helvetic_lens.hazard_reconciliation import reconcile_cap


def referenced(previous, *, identifier, infos=None, kind="Update"):
    identity = previous.identity
    refs = f"{identity.sender},{identity.identifier},{identity.sent.isoformat()}"
    return decoded(message(identifier=identifier, sent=(identity.sent + timedelta(minutes=1)).isoformat(),
                           kind=kind, refs=refs, infos=infos))


def test_create_refresh_escalate_downgrade_all_clear_retains_exact_predecessors():
    first = decoded()
    state, created = reconcile_cap(None, first)
    assert created.material and created.material_sequence == 1
    same = decode_cap(message().encode(), received_at=NOW + timedelta(minutes=1))
    refreshed, result = reconcile_cap(state, same)
    assert not result.material and result.material_sequence == 1
    assert len(refreshed.messages) == 1
    assert refreshed.messages[0].last_seen_at == NOW + timedelta(minutes=1)
    assert refreshed.messages[0].message.received_at == NOW
    high = update(info(level="Extreme"))
    state, changed = reconcile_cap(refreshed, high)
    assert changed.development_id == created.development_id
    assert changed.previous_keys == (first.identity.key,)
    assert changed.kind == "escalated" and changed.material_sequence == 2
    assert len(state.messages) == 2
    low = referenced(high, identifier="low", infos=info(level="Moderate"))
    state, changed = reconcile_cap(state, low)
    assert changed.kind == "downgraded" and changed.material_sequence == 3
    clear = referenced(low, identifier="clear", infos=info(level="Minor", extra="<responseType>AllClear</responseType>"))
    state, changed = reconcile_cap(state, clear)
    assert changed.kind == "resolved" and changed.material_sequence == 4
    assert state.heads[0].state == "resolved"
    assert [e.material_sequence for e in state.messages] == [1, 2, 3, 4]


def test_translation_and_technical_updates_retain_evidence_without_reopening_review_sequence():
    state, _ = reconcile_cap(None, decoded())
    second = update(info() + info(language="fr-CH", instruction="Restez à l’intérieur."))
    state, change = reconcile_cap(state, second)
    assert change.kind == "refreshed" and not change.material
    assert change.material_sequence == 1
    assert len(state.messages) == 2
    assert state.heads[0].current_key == second.identity.key
    updated = referenced(second, identifier="instruction", infos=info(instruction="Evacuate now."))
    _, change = reconcile_cap(state, updated)
    assert change.kind == "updated" and change.material_sequence == 2


def test_no_initial_cancel_or_missing_reference_guessing():
    with pytest.raises(HazardCAPError, match="hazard_predecessor_missing"):
        reconcile_cap(None, update())
    cancel = decoded(message(identifier="cancel", kind="Cancel", infos="",
                             refs=f"fixture@example.invalid,fixture-1,{SENT}"))
    with pytest.raises(HazardCAPError, match="hazard_predecessor_missing"):
        reconcile_cap(None, cancel)


def test_late_ancestor_cancellation_and_sibling_cannot_close_newer_warning():
    first = decoded()
    state, _ = reconcile_cap(None, first)
    latest = update(info(level="Extreme"))
    state, _ = reconcile_cap(state, latest)
    late_cancel = referenced(first, identifier="late-cancel", kind="Cancel", infos="")
    late_sibling = referenced(first, identifier="late-sibling", infos=info(level="Moderate"))
    for invalid in (late_cancel, late_sibling):
        with pytest.raises(HazardCAPError, match="hazard_reference_superseded"):
            reconcile_cap(state, invalid)
    assert state.heads[0].state == "active" and state.heads[0].current_key == latest.identity.key
    assert len(state.messages) == 2
    # Replaying an unchanged older message may refresh its receipt evidence, but
    # must not restore that older message as the current head.
    replayed, result = reconcile_cap(state, first)
    assert not result.material
    assert replayed.heads == state.heads


def test_cancel_closes_notice_without_all_clear_and_requires_new_initial_warning():
    first = decoded()
    state, _ = reconcile_cap(None, first)
    cancel = referenced(first, identifier="cancel", kind="Cancel", infos="")
    state, changed = reconcile_cap(state, cancel)
    assert changed.kind == "cancelled"
    assert state.heads[0].state == "cancelled"
    with pytest.raises(HazardCAPError, match="hazard_cancelled_history_requires_new_alert"):
        reconcile_cap(state, referenced(cancel, identifier="invalid-reopen"))
    new = decoded(message(identifier="fresh-event"))
    _, changed = reconcile_cap(state, new)
    assert changed.kind == "created" and changed.development_id != state.heads[0].development_id


def test_expiry_and_transport_gap_are_not_resolved_source_revisions():
    expired = decode_cap(message().encode(), received_at=NOW + timedelta(days=2))
    state, _ = reconcile_cap(None, expired)
    assert state.heads[0].state == "active"
    assert len(state.messages) == 1
    # A later unrelated message does not delete or resolve an unseen warning.
    _, result = reconcile_cap(state, decoded(message(identifier="unrelated")))
    assert result.kind == "created"
    assert state.heads[0].state == "active"


def test_mutated_identity_reused_id_or_wrong_sender_fail_without_changing_history():
    first = decoded()
    state, _ = reconcile_cap(None, first)
    for invalid, code in (
        (decoded(message(infos=info(instruction="Evacuate now."))), "hazard_conflicting_identity"),
        (decoded(message(sent="2026-09-13T09:15:00+00:00")), "hazard_identifier_reused"),
        (decoded(message().replace("fixture@example.invalid", "other@example.invalid")), "hazard_source_sender_changed"),
        (replace(first, received_at=NOW - timedelta(minutes=1)), "hazard_receipt_rollback"),
    ):
        with pytest.raises(HazardCAPError, match=code):
            reconcile_cap(state, invalid)
    assert state.messages[0].message == first


def test_unrelated_histories_cannot_be_silently_joined_or_share_private_review():
    first, other = decoded(), decoded(message(identifier="other"))
    state, _ = reconcile_cap(None, first)
    state, _ = reconcile_cap(state, other)
    merged = decoded(message(identifier="merge", kind="Update", refs=
        f"fixture@example.invalid,fixture-1,{SENT} fixture@example.invalid,other,{SENT}"))
    with pytest.raises(HazardCAPError, match="hazard_unverified_history_merge"):
        reconcile_cap(state, merged)
    assert len(state.heads) == 2


def test_unsupported_geometry_cannot_publish_a_current_warning():
    unsupported = decoded(message(infos=info(geometry="<polygon>47,7 48,8 47,8 48,7 47,7</polygon>")))
    assert "polygon_not_supported" in unsupported.unsupported
    with pytest.raises(HazardCAPError, match="hazard_unsupported_contract"):
        reconcile_cap(None, unsupported)


def test_retained_message_and_byte_caps_preserve_previous_state(monkeypatch):
    import helvetic_lens.hazard_reconciliation as reconciliation

    state, _ = reconcile_cap(None, decoded())
    monkeypatch.setattr(reconciliation, "MAX_MESSAGES", 1)
    with pytest.raises(HazardCAPError, match="hazard_history_limit"):
        reconcile_cap(state, update())
    monkeypatch.setattr(reconciliation, "MAX_MESSAGES", 2000)
    monkeypatch.setattr(reconciliation, "MAX_RETAINED_BYTES", state.messages[0].retained_bytes)
    with pytest.raises(HazardCAPError, match="hazard_history_byte_limit"):
        reconcile_cap(state, update())
    assert len(state.messages) == len(state.heads) == 1
