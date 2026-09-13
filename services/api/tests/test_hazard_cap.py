"""Synthetic CAP only: no official warning, source licence or live feed proof."""

from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

import pytest

from helvetic_lens.hazard_cap import CAP, HazardCAPError, decode_cap, material_change
from helvetic_lens.hazard_geometry import match_point

NOW = datetime(2026, 9, 13, 10, tzinfo=UTC)
SENT = "2026-09-13T09:00:00+00:00"
POLYGON = "47.50,7.50 47.50,7.70 47.65,7.70 47.65,7.50 47.50,7.50"


def info(*, language="en-CH", level="Severe", instruction="Stay indoors.", geometry=None, extra=""):
    geometry = f"<polygon>{POLYGON}</polygon>" if geometry is None else geometry
    return f"""<info><language>{language}</language><category>Met</category>
      <event>Synthetic storm</event><eventCode><valueName>fixture</valueName><value>storm</value></eventCode>
      <urgency>Immediate</urgency><severity>{level}</severity><certainty>Observed</certainty>
      <effective>{SENT}</effective><expires>2026-09-14T09:00:00+00:00</expires>
      <senderName>Fixture authority</senderName><headline>Synthetic warning</headline>
      <description>Test storm.</description><instruction>{escape(instruction)}</instruction>
      <web>https://example.invalid/warning</web><area><areaDesc>Fixture area</areaDesc>{geometry}</area>{extra}</info>"""


def message(*, identifier="fixture-1", sent=SENT, kind="Alert", refs=None, infos=None, extra=""):
    refs = f"<references>{refs}</references>" if refs is not None else ""
    infos = info() if infos is None else infos
    return f"""<alert xmlns="{CAP}"><identifier>{identifier}</identifier><sender>fixture@example.invalid</sender>
      <sent>{sent}</sent><status>Actual</status><msgType>{kind}</msgType><scope>Public</scope>
      {refs}{infos}{extra}</alert>"""


def decoded(xml=None):
    return decode_cap((message() if xml is None else xml).encode(), received_at=NOW)


def update(infos=None, **kwargs):
    return decoded(message(identifier="fixture-2", sent="2026-09-13T09:30:00+00:00", kind="Update",
                           refs=f"fixture@example.invalid,fixture-1,{SENT}", infos=infos, **kwargs))


def test_public_warning_preserves_source_text_and_locally_matches_only_affected_points():
    warning = decoded(message(infos=info(instruction="Stay indoors.\n  Close windows. <script>test</script>")))
    assert warning.unsupported == ()
    assert warning.state == "active"
    assert warning.infos[0].instruction == "Stay indoors.\n  Close windows. <script>test</script>"
    assert warning.identity.sender == "fixture@example.invalid"
    assert warning.received_at == NOW
    assert len(warning.evidence_hash) == 64
    assert match_point(warning.infos[0].areas, latitude=47.56, longitude=7.59).state == "match"
    assert match_point(warning.infos[0].areas, latitude=46.2, longitude=6.14).state == "no_match"


@pytest.mark.parametrize(("xml", "reason"), [
    (message().replace("<status>Actual", "<status>Exercise"), "hazard_not_public_actual"),
    (message().replace("<scope>Public", "<scope>Private"), "hazard_not_public_actual"),
    (message(extra="<addresses>secret@example.invalid</addresses>"), "hazard_restricted_recipients"),
    (message().replace(CAP, "urn:spoof"), "hazard_cap_namespace"),
    (message(extra="<identifier>different</identifier>"), "hazard_field_limit"),
    (message(identifier="a,b"), "hazard_invalid_identity"),
    (message(sent="2026-09-13T11:00:00+00:00"), "hazard_future_publication"),
    (message(sent="2026-09-13T09:00:00Z"), "hazard_invalid_time"),
    (message(sent="2026-09-13T09:00:00"), "hazard_invalid_time"),
    (message(sent="2026-02-31T09:00:00+00:00"), "hazard_invalid_time"),
    (message(kind="Update"), "hazard_reference_required"),
    (message(kind="Cancel"), "hazard_reference_required"),
    (message(kind="Ack"), "hazard_unknown_enum"),
    (message(refs=f"fixture@example.invalid,old,{SENT}"), "hazard_reference_required"),
    (message(kind="Update", refs=f"other@example.invalid,old,{SENT}"), "hazard_unverified_reference"),
    (message(kind="Update", refs=f"fixture@example.invalid,fixture-1,{SENT}"), "hazard_invalid_reference"),
    (message(infos=""), "hazard_missing_info"),
    (message(infos=info(extra="<responseType>AllClear</responseType>")), "hazard_invalid_all_clear"),
    (message(infos=info().replace("https://example.invalid/warning", "javascript:alert(1)")), "hazard_invalid_link"),
    (message(infos=info().replace("https://example.invalid/warning", "https://user:pw@example.invalid")), "hazard_invalid_link"),
    (message(infos=info().replace("<severity>Severe</severity>", "<severity><x>Severe</x></severity>")), "hazard_invalid_scalar"),
    (message(infos=info().replace("<severity>", '<severity value="override">')), "hazard_invalid_scalar"),
    (message(infos=info().replace("2026-09-14T09:00:00", "2026-09-12T09:00:00")), "hazard_invalid_period"),
    (message(infos=info(geometry="<polygon>NaN,7 47,8 48,7 NaN,7</polygon>")), "hazard_invalid_coordinate"),
    (message(infos=info(geometry="<polygon>47,7 47,8 48,7</polygon>")), "hazard_invalid_polygon"),
    (message(infos=info(geometry="<circle>47,7 -1</circle>")), "hazard_invalid_circle"),
    (message(infos=info(geometry="<ceiling>1000</ceiling>")), "hazard_invalid_altitude"),
])
def test_malformed_or_nonpublic_messages_cannot_become_public_warnings(xml, reason):
    with pytest.raises(HazardCAPError, match=f"^{reason}$"):
        decoded(xml)


@pytest.mark.parametrize("payload", [
    b'<!DOCTYPE alert [<!ENTITY x SYSTEM "file:///secret">]><alert/>',
    b'<!DOCTYPE alert SYSTEM "https://example.invalid/external"><alert/>',
    b"<alert>\x00</alert>",
])
def test_external_entities_and_alternate_null_encodings_are_never_processed(payload):
    with pytest.raises(HazardCAPError, match="^hazard_forbidden_xml$"):
        decode_cap(payload, received_at=NOW)


def test_payload_depth_node_geometry_encoding_and_clock_limits(monkeypatch):
    import helvetic_lens.hazard_cap as cap

    with pytest.raises(HazardCAPError, match="hazard_xml_limit"):
        decoded("<x>" * 17 + "</x>" * 17)
    with pytest.raises(HazardCAPError, match="hazard_unsupported_encoding"):
        decoded('<?xml version="1.0" encoding="windows-1252"?>' + message())
    with pytest.raises(HazardCAPError, match="hazard_receipt_clock"):
        decode_cap(message().encode(), received_at=NOW.replace(tzinfo=None))
    monkeypatch.setattr(cap, "MAX_POINTS", 6)
    assert decoded(message(infos=info() + info(language="de-CH"))).unsupported == ()
    with pytest.raises(HazardCAPError, match="hazard_geometry_limit"):
        decoded(message(infos=info() + info(language="de-CH").replace("47.65", "47.66")))
    monkeypatch.setattr(cap, "MAX_NODES", 4)
    with pytest.raises(HazardCAPError, match="hazard_xml_limit"):
        decoded()
    monkeypatch.setattr(cap, "MAX_BYTES", 4)
    with pytest.raises(HazardCAPError, match="hazard_payload_limit"):
        decoded()


def test_creation_severity_instructions_geography_time_and_explicit_resolutions():
    first = decoded()
    assert material_change(first, update(info(level="Extreme"))) == "escalated"
    assert material_change(first, update(info(level="Moderate"))) == "downgraded"
    assert material_change(first, update(info(instruction="Evacuate now."))) == "updated"
    assert material_change(first, update(info(geometry="<circle>47.5,7.5 4</circle>"))) == "updated"
    assert material_change(first, update(info().replace("2026-09-14T09:00:00", "2026-09-14T10:00:00"))) == "updated"
    cancelled = decoded(message(identifier="cancel", kind="Cancel", infos="",
                                refs=f"fixture@example.invalid,fixture-1,{SENT}"))
    assert cancelled.state == "cancelled"
    assert material_change(first, cancelled) == "cancelled"
    clear = update(info(level="Minor", extra="<responseType>AllClear</responseType>"))
    assert clear.state == "resolved"
    assert material_change(first, clear) == "resolved"
    # Receipt time and validity expiry alone never change source all-clear state.
    expired = decode_cap(message().encode(), received_at=NOW + timedelta(days=2))
    assert expired.state == "active"
    assert expired.identity == first.identity


def test_formatting_translation_addition_and_timestamp_refresh_do_not_duplicate():
    first = decoded()
    changed_spacing = update(info(instruction="Stay\n   indoors."))
    assert material_change(first, changed_spacing) == "refreshed"
    assert changed_spacing.evidence_hash != first.evidence_hash
    translated = info(language="de-CH", instruction="Bleiben Sie drinnen.").replace("Synthetic storm", "Teststurm")
    second = update(info() + translated)
    assert second.unsupported == ()
    assert len(second.infos) == 2
    assert material_change(first, second) == "refreshed"
    assert material_change(first, update()) == "refreshed"
    changed_hints = info(instruction="Evacuate now.", extra="<parameter><valueName>GENUpdateType</valueName><value>minor update</value></parameter>")
    assert material_change(first, update(changed_hints)) == "updated"


def test_polygon_start_winding_and_order_changes_are_nonmaterial():
    # Same five coordinates, another winding and starting corner.
    rotated = "47.65,7.70 47.50,7.70 47.50,7.50 47.65,7.50 47.65,7.70"
    assert material_change(decoded(), update(info(geometry=f"<polygon>{rotated}</polygon>"))) == "refreshed"


def test_no_predecessor_guessing_or_silent_geometry_instruction_segment_collapsing():
    with pytest.raises(HazardCAPError, match="hazard_predecessor_missing"):
        material_change(decoded(message(identifier="unrelated")), update())
    duplicate = update(info() + info())
    assert "multiple_blocks_per_language" in duplicate.unsupported
    assert material_change(decoded(), duplicate) == "unavailable"
    mixed = update(info() + info(language="de-CH", level="Extreme"))
    assert "distinct_info_segments" in mixed.unsupported
    unsupported = update(info(extra='<evil xmlns="urn:other">override</evil>'))
    assert material_change(decoded(), unsupported) == "unavailable"
    resource = update(info(extra="<resource><resourceDesc>Do not fetch</resourceDesc><uri>https://example.invalid/x</uri></resource>"))
    assert "resources_not_processed" in resource.unsupported


def test_unknown_severity_is_never_coerced_to_no_hazard_or_all_clear():
    current = update(info(level="Unknown"))
    assert material_change(decoded(), current) == "updated"
    assert current.state == "active"


def test_teaser_and_new_distribution_codes_do_not_silently_reuse_full_warning_state():
    teaser = update(extra="<code>NAT=Teaser</code>")
    assert "teaser_not_full_warning" in teaser.unsupported
    assert material_change(decoded(), teaser) == "unavailable"
    mandatory = update(extra="<code>GEN=disseminationmandatory</code>")
    assert material_change(decoded(), mandatory) == "updated"
