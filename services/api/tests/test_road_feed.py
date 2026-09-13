"""Synthetic DATEX structures; no original FEDRO payload or current coverage."""

from datetime import UTC, datetime, timedelta
from xml.sax.saxutils import escape

import pytest

from helvetic_lens import road_feed
from helvetic_lens.road_feed import D2, SOAP, RoadFeedError, decode_road_feed

NOW = datetime(2026, 9, 13, 10, tzinfo=UTC)
STAMP = "2026-09-13T10:00:00Z"


def comment(text="Road closed", *, kind="description", language="en", public=True):
    container = "generalPublicComment" if public else "nonGeneralPublicComment"
    return (f'<{container}><comment><values><value lang="{language}">{escape(text)}</value>'
            f'</values></comment><commentType>{kind}</commentType></{container}>')


def record(*, identifier="clause-1", source_type="RoadOrCarriagewayOrLaneManagement",
           code="roadClosed", delay=None, cancelled=None, comments=None, extra="", validity_extra=""):
    codes = {
        "RoadOrCarriagewayOrLaneManagement": "roadOrCarriagewayOrLaneManagementType",
        "AbnormalTraffic": "abnormalTrafficType", "Accident": "accidentType",
        "MaintenanceWorks": "roadMaintenanceType", "ConstructionWorks": "constructionWorkType",
    }
    field = codes.get(source_type)
    code_xml = f"<{field}>{code}</{field}>" if field else ""
    delay_xml = "" if delay is None else f"<impact><delays><delayTimeValue>{delay}</delayTimeValue></delays></impact>"
    cancel_xml = "" if cancelled is None else (
        f"<management><lifeCycleManagement><cancel>{str(cancelled).lower()}</cancel>"
        "</lifeCycleManagement></management>")
    return f'''<situationRecord id="{identifier}" version="0" xsi:type="{source_type}">
      <situationRecordCreationTime>2026-09-13T09:00:00Z</situationRecordCreationTime>
      <situationRecordVersionTime>{STAMP}</situationRecordVersionTime>
      <probabilityOfOccurrence>certain</probabilityOfOccurrence>
      <validity><validityStatus>definedByValidityTimeSpec</validityStatus><validityTimeSpecification>
        <overallStartTime>2026-09-13T09:30:00Z</overallStartTime>{validity_extra}
      </validityTimeSpecification></validity>
      {comment() if comments is None else comments}{delay_xml}{cancel_xml}
      <groupOfLocations xsi:type="Linear"><alertCLinear xsi:type="AlertCMethod4Linear">
        <alertCLocationCountryCode>4</alertCLocationCountryCode>
        <alertCLocationTableNumber>9</alertCLocationTableNumber>
        <alertCLocationTableVersion>synthetic-1</alertCLocationTableVersion>
        <alertCDirection><alertCDirectionCoded>positive</alertCDirectionCoded></alertCDirection>
        <alertCMethod4PrimaryPointLocation><alertCLocation><specificLocation>120</specificLocation></alertCLocation>
          <offsetDistance><offsetDistance>0</offsetDistance></offsetDistance></alertCMethod4PrimaryPointLocation>
        <alertCMethod4SecondaryPointLocation><alertCLocation><specificLocation>100</specificLocation></alertCLocation>
          <offsetDistance><offsetDistance>10</offsetDistance></offsetDistance></alertCMethod4SecondaryPointLocation>
      </alertCLinear></groupOfLocations>{code_xml}{extra}</situationRecord>'''


def situation(records=None, *, identifier="event-1", header_extra=""):
    return f'''<situation id="{identifier}" version="0"><headerInformation>
      <confidentiality>noRestriction</confidentiality><informationStatus>real</informationStatus>
      {header_extra}</headerInformation>{record() if records is None else records}</situation>'''


def feed(records=None, *, situations=None):
    contents = situation(records) if situations is None else situations
    return f'''<?xml version="1.0" encoding="UTF-8"?>
    <soap:Envelope xmlns:soap="{SOAP}"><soap:Header/><soap:Body>
    <d2LogicalModel xmlns="{D2}" xmlns:d2="{D2}"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" modelBaseVersion="2">
    <exchange><supplierIdentification><country>ch</country><nationalIdentifier>test-supplier</nationalIdentifier>
    </supplierIdentification></exchange><payloadPublication xsi:type="SituationPublication" lang="en">
    <publicationTime>{STAMP}</publicationTime><publicationCreator><country>ch</country>
    <nationalIdentifier>test-supplier</nationalIdentifier></publicationCreator>{contents}
    </payloadPublication></d2LogicalModel></soap:Body></soap:Envelope>'''


def decode(xml=None, **kwargs):
    return decode_road_feed((feed() if xml is None else xml).encode(), received_at=NOW, **kwargs)


def first(xml=None):
    return decode(xml).situations[0].records[0]


def test_closure_without_delay_and_topology_relative_direction_are_preserved():
    snapshot = decode()
    item = snapshot.situations[0]
    clause = item.records[0]
    assert snapshot.supplier == ("ch", "test-supplier")
    assert snapshot.published_at == NOW and snapshot.received_at == NOW
    assert not snapshot.unsupported and not item.unsupported and not clause.unsupported
    assert clause.kind == "road_closure" and clause.delay_seconds is None
    assert clause.location.direction == "positive"
    assert (clause.location.primary, clause.location.secondary, clause.location.secondary_offset_m) == (120, 100, 10)
    assert clause.location.version == "synthetic-1"
    assert not item.cancelled and clause.ended is None


@pytest.mark.parametrize(("source_type", "code", "expected"), [
    ("RoadOrCarriagewayOrLaneManagement", "carriagewayClosures", "carriageway_closure"),
    ("RoadOrCarriagewayOrLaneManagement", "laneClosures", "lane_restriction"),
    ("RoadOrCarriagewayOrLaneManagement", "narrowLanes", "lane_restriction"),
    ("RoadOrCarriagewayOrLaneManagement", "roadCleared", "source_clearance"),
    ("AbnormalTraffic", "queuingTraffic", "congestion"),
    ("Accident", "collision", "accident"),
    ("ConstructionWorks", "roadConstructionWork", "roadworks"),
    ("MaintenanceWorks", "roadMarkingWork", "roadworks"),
])
def test_source_event_kinds_remain_distinct(source_type, code, expected):
    item = first(feed(record(source_type=source_type, code=code)))
    assert item.kind == expected
    assert item.source_codes[0][1] == code
    assert item.delay_seconds is None


@pytest.mark.parametrize("delay", ["0", "899.5", "900", "1.5e3"])
def test_numeric_delay_is_seconds_and_not_inferred_from_congestion(delay):
    item = first(feed(record(source_type="AbnormalTraffic", code="slowTraffic", delay=delay)))
    assert item.delay_seconds == float(delay)


@pytest.mark.parametrize("delay", ["-1", "NaN", "INF", "1e900", "many", "1,500"])
def test_invalid_numeric_delay_rejects_whole_response(delay):
    with pytest.raises(RoadFeedError, match="road_invalid_number"):
        decode(feed(record(delay=delay)))


def test_constant_version_updates_and_removed_clauses_change_one_development():
    original = decode(feed(record() + record(identifier="clause-2", code="laneClosures"))).situations[0]
    updated = decode(feed(record(code="roadCleared"))).situations[0]
    assert original.source_version == updated.source_version == 0
    assert original.development_id == updated.development_id
    assert original.semantic_hash != updated.semantic_hash
    assert len(original.records) == 2 and len(updated.records) == 1
    # Missing or replaced clauses must not fabricate a source cancellation.
    assert not updated.cancelled


def test_publication_receipt_and_version_clocks_do_not_create_material_change():
    before = decode()
    xml = feed().replace(STAMP, "2026-09-13T10:01:00Z").replace('version="0"', 'version="1"')
    after = decode_road_feed(xml.encode(), received_at=NOW + timedelta(minutes=2))
    assert before.sha256 != after.sha256
    assert before.situations[0].semantic_hash == after.situations[0].semantic_hash
    assert before.situations[0].records[0].version_at != after.situations[0].records[0].version_at


def test_duplicate_records_languages_and_order_do_not_duplicate_situation_material():
    en, de = comment(), comment("Strasse gesperrt", language="de-CH")
    base = decode(feed(record(comments=en + de))).situations[0]
    duplicate = decode(feed(record(comments=de + en) + record(identifier="translated-clause", comments=en + de))).situations[0]
    assert base.development_id == duplicate.development_id
    assert base.semantic_hash == duplicate.semantic_hash
    assert len(duplicate.records) == 2  # Evidence is retained; material facts are deduplicated.


def test_comment_whitespace_only_is_nonmaterial_but_verbatim_text_is_retained():
    item = first(feed(record(comments=comment("Road  closed\n now"))))
    assert item.comments[0].text == "Road  closed\n now"
    assert item.semantic_hash == first(feed(record(comments=comment("Road closed now")))).semantic_hash


def test_internal_and_unreviewed_comment_types_never_enter_text_or_semantic_hash():
    baseline = first()
    comments = comment() + "".join(comment("PRIVATE-SENTINEL", kind=kind) for kind in (
        "internalNote", "dataProcessingNote", "other", "newUnknownType")) + comment("PRIVATE-SENTINEL", public=False)
    projected = first(feed(record(comments=comments)))
    assert "PRIVATE-SENTINEL" not in repr(projected)
    assert projected.semantic_hash == baseline.semantic_hash


@pytest.mark.parametrize("replacement", [
    ("<confidentiality>noRestriction", "<confidentiality>restrictedToAuthorities"),
    ("<informationStatus>real", "<informationStatus>test"),
])
def test_nonpublic_or_test_situations_do_not_project_public_comments(replacement):
    item = decode(feed().replace(*replacement)).situations[0]
    assert item.unsupported and item.records[0].comments == ()


def test_record_confidentiality_cannot_accidentally_unrestrict_parent():
    xml = feed(record(extra="<confidentialityOverride>noRestriction</confidentialityOverride>"))
    xml = xml.replace("<confidentiality>noRestriction", "<confidentiality>restrictedToAuthorities")
    assert first(xml).comments == ()
    assert first(feed(record(extra="<confidentialityOverride>restrictedToAuthorities</confidentialityOverride>"))).comments == ()


def test_cancellation_end_suspension_and_disappearance_are_not_reopening():
    assert decode(feed(record(cancelled=True))).situations[0].cancelled
    assert not decode(feed(record(cancelled=True) + record(identifier="remaining"))).situations[0].cancelled
    ended = first(feed(record(cancelled=False)).replace("<cancel>false</cancel>", "<end>true</end>"))
    assert ended.ended is True and ended.cancelled is None
    suspended = first(feed().replace("definedByValidityTimeSpec", "suspended"))
    assert suspended.validity.status == "suspended" and suspended.cancelled is None
    empty = decode(feed(situations=""))
    assert empty.situations == ()  # No synthetic cancellation / recovery entity.


def test_planned_rescheduling_and_exception_windows_are_material():
    extra = "<overallEndTime>2026-09-15T06:00:00Z</overallEndTime>" + (
        "<validPeriod><startOfPeriod>2026-09-14T22:00:00+02:00</startOfPeriod>"
        "<endOfPeriod>2026-09-15T05:00:00+02:00</endOfPeriod></validPeriod>"
        "<exceptionPeriod><startOfPeriod>2026-09-15T00:00:00Z</startOfPeriod>"
        "<endOfPeriod>2026-09-15T01:00:00Z</endOfPeriod></exceptionPeriod>")
    xml = feed(record(validity_extra=extra))
    item = first(xml)
    assert item.validity.periods[0].start == datetime(2026, 9, 14, 20, tzinfo=UTC)
    assert len(item.validity.exceptions) == 1 and not item.unsupported
    assert item.semantic_hash != first(xml.replace("2026-09-14T22:00", "2026-09-14T23:00")).semantic_hash


def test_recurring_periods_and_extensions_are_explicitly_unsupported():
    item = first(feed(record(validity_extra=(
        "<validPeriod><recurringTimePeriodOfDay><startTimeOfPeriod>22:00:00</startTimeOfPeriod>"
        "</recurringTimePeriodOfDay></validPeriod>"), extra="<situationRecordExtension><privateFact/></situationRecordExtension>")))
    assert {"recurring_period", "record_fields"} <= set(item.unsupported)
    assert "privateFact" not in repr(item)
    historical_pattern = feed().replace("</validity>", "<validityExtension><elementEnumerationExtension>"
        "<element>validityStatus</element><value>untilFurtherNotice</value></elementEnumerationExtension>"
        "</validityExtension></validity>")
    assert "validity" in first(historical_pattern).unsupported
    assert "validity" in first(feed().replace("<validity>", '<validity xsi:type="FutureValidity">')).unsupported


def test_unknown_type_enum_location_are_not_guessed():
    item = first(feed(record(source_type="FutureTrafficEvent")))
    assert item.source_type == "FutureTrafficEvent" and item.kind == "unknown"
    assert "event_type" in item.unsupported
    item = first(feed(record(code="futureManagementCode")))
    assert item.source_codes == (("roadOrCarriagewayOrLaneManagementType", "futureManagementCode"),)
    assert item.kind == "unknown"
    item = first(feed().replace('xsi:type="Linear"', 'xsi:type="Point"'))
    assert item.location is None and "location_type" in item.unsupported
    item = first(feed().replace(">positive<", ">newDirection<"))
    assert item.location.direction == "newDirection" and "location_direction" in item.unsupported


def test_lane_counts_preserve_unknown_and_inconsistent_counts_fail():
    xml = feed(record(extra="<impact><numberOfLanesRestricted>1</numberOfLanesRestricted>"
        "<originalNumberOfLanes>3</originalNumberOfLanes></impact>"))
    item = first(xml)
    assert item.lanes_restricted == 1 and item.lanes_original == 3 and item.lanes_operational is None
    with pytest.raises(RoadFeedError, match="road_inconsistent_lanes"):
        decode(xml.replace("<numberOfLanesRestricted>1", "<numberOfLanesRestricted>4"))


@pytest.mark.parametrize("xml", [
    "<html>Please log in</html>",
    f'<soap:Envelope xmlns:soap="{SOAP}"><soap:Body><soap:Fault/></soap:Body></soap:Envelope>',
    feed().replace('modelBaseVersion="2"', 'modelBaseVersion="3"'),
    feed().replace('xsi:type="SituationPublication"', 'xsi:type="MeasuredDataPublication"'),
    feed().replace("<publicationTime>", "<publicationTime xmlns='urn:spoof'>"),
    feed().replace('xsi:type="RoadOrCarriagewayOrLaneManagement"', 'xmlns:fake="urn:spoof" xsi:type="fake:RoadOrCarriagewayOrLaneManagement"'),
    feed().replace('xsi:type="Linear"', 'xmlns:d2="urn:spoof" xsi:type="d2:Linear"'),
    feed().replace('xsi:type="Linear"', 'xsi:type="missing:Linear"'),
    feed().replace('xsi:type="Linear"', 'xsi:type="a:b:c"'),
    feed().replace("<validity>", '<validity xmlns:e="urn:spoof" xsi:type="e:Validity">'),
    feed().replace("<soap:Header/>", "<soap:Header><auth/></soap:Header>"),
    feed().replace("</soap:Body>", "</soap:Body><soap:Body/>"),
])
def test_wrong_protocol_namespaces_and_scoped_type_spoofs_are_rejected(xml):
    with pytest.raises(RoadFeedError):
        decode(xml)


def test_legitimate_prefixed_types_and_utf8_bom_work():
    xml = feed().replace('xsi:type="', 'xsi:type="d2:')
    assert decode_road_feed(b"\xef\xbb\xbf" + xml.encode(), received_at=NOW).situations[0].records[0].kind == "road_closure"
    typed = feed().replace("<validityTimeSpecification>", '<validityTimeSpecification xsi:type="d2:OverallPeriod">')
    assert not first(typed).unsupported


@pytest.mark.parametrize("payload", [
    b"", b"\xff", b"<broken>", feed().encode("utf-16"),
    feed().replace('encoding="UTF-8"', 'encoding="UTF-16"').encode(),
    feed().replace("<soap:Envelope", '<!DOCTYPE test [<!ENTITY secret SYSTEM "file:///private">]><soap:Envelope').encode(),
    feed().replace("Road closed", "\x00").encode(),
])
def test_malformed_encoding_dtd_entity_and_empty_payloads_are_rejected(payload):
    with pytest.raises(RoadFeedError):
        decode_road_feed(payload, received_at=NOW)


@pytest.mark.parametrize("change", [
    ("2026-09-13T09:00:00Z", "2026-09-14T09:00:00Z"),
    (STAMP, "2026-09-13T11:00:00Z"),
    (STAMP, "2026-09-13"),
    (STAMP, "2026-09-13T10:00:00"),
    (STAMP, "2026-09-99T10:00:00Z"),
    ('version="0"', 'version="-1"'),
])
def test_invalid_clocks_and_versions_fail(change):
    with pytest.raises(RoadFeedError):
        decode(feed().replace(*change))


def test_receipt_must_be_aware_and_old_source_clock_remains_old():
    with pytest.raises(RoadFeedError, match="road_receipt_clock"):
        decode_road_feed(feed().encode(), received_at=NOW.replace(tzinfo=None))
    stale = decode(feed().replace("2026-09-13", "2023-03-12"))
    assert stale.published_at.year == 2023  # Caller must apply freshness; receipt does not refresh facts.


@pytest.mark.parametrize("xml", [
    feed(situations=situation() + situation()),
    feed(record() + record()),
    feed(records=""),
    feed().replace("<publicationTime>", f"<publicationTime>{STAMP}</publicationTime><publicationTime>"),
    feed(record(cancelled="maybe")),
    feed(record(validity_extra="<overallEndTime>2026-09-12T00:00:00Z</overallEndTime>")),
    feed(record(comments=comment().replace("</values>", '<value lang="en">Conflict</value></values>'))),
    feed().replace("<publicationCreator><country>ch", "<publicationCreator><country>de"),
])
def test_ambiguous_identity_fields_language_and_invalid_lifecycle_fail_atomically(xml):
    with pytest.raises(RoadFeedError):
        decode(xml)


@pytest.mark.parametrize(("limit", "value", "error"), [
    ("MAX_BYTES", 20, "road_response_size"),
    ("MAX_NODES", 20, "road_xml_complexity"),
    ("MAX_DEPTH", 3, "road_xml_complexity"),
    ("MAX_RECORDS", 1, "road_record_limit"),
    ("MAX_SITUATIONS", 0, "road_situation_identity_or_limit"),
])
def test_resource_budgets_reject_before_partial_results(monkeypatch, limit, value, error):
    monkeypatch.setattr(road_feed, limit, value)
    with pytest.raises(RoadFeedError, match=error):
        decode(feed(record() + record(identifier="second")))
