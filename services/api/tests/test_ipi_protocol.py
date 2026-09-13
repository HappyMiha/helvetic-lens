"""Synthetic instances of the public IPI/ST.96 contracts; no live source access."""

import hashlib
import io
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from test_trademark_matching import portfolio

from helvetic_lens.ipi_protocol import (
    COM,
    COMMON,
    CORE,
    TM,
    IPIProtocolError,
    decode_response,
    initial_request,
    parse_xml,
    q,
    retry_after,
)
from helvetic_lens.ipi_trademarks import decode_trademark
from helvetic_lens.trademark_matching import assess

NOW = datetime(2026, 9, 13, 20, 0, tzinfo=UTC)
HEADERS = {"X-IPI-SUCCESS": "true", "Content-Type": "application/xml; charset=UTF-8"}


def publication(category="New registration", day="2026-08-12"):
    return f'''<tm:Publication><com:PublicationIdentifier com:officeCode="CH">123456</com:PublicationIdentifier>
      <com:PublicationDate>{day}</com:PublicationDate><tm:NationalPublication>
      <tm:PublicationStatusCategory>Published</tm:PublicationStatusCategory>
      <tm:PublicationCategoryText>{category}</tm:PublicationCategoryText>
      <tm:RegistrationChangeBag><tm:RegistrationChange><tm:ChangeDescriptionText>{category}</tm:ChangeDescriptionText>
      <tm:ChangeText>Synthetic register entry</tm:ChangeText></tm:RegistrationChange></tm:RegistrationChangeBag>
      </tm:NationalPublication></tm:Publication>'''


def record(*, office="CH", language="en", publications=None):
    lang = f' com:languageCode="{language}"' if language else ""
    publications = publication() + publication("Change of owner", "2026-09-13") if publications is None else publications
    return f'''<tm:TrademarkApplication xmlns:tm="{TM}" xmlns:com="{COM}" com:st96Version="V7_1">
      <tm:TrademarkBag><tm:Trademark><com:RegistrationOfficeCode>{office}</com:RegistrationOfficeCode>
      <com:ApplicationNumber><com:ApplicationNumberText>12345/2026</com:ApplicationNumberText></com:ApplicationNumber>
      <com:RegistrationNumber>123456</com:RegistrationNumber><com:ApplicationDate>2026-07-01</com:ApplicationDate>
      <com:RegistrationDate>2026-08-09</com:RegistrationDate><com:ExpiryDate>2036-07-01</com:ExpiryDate>
      <tm:MarkCurrentStatusCode>Registration published</tm:MarkCurrentStatusCode>
      <tm:MarkRepresentation><tm:MarkFeatureCategory>Word</tm:MarkFeatureCategory><tm:MarkReproduction>
      <tm:WordMarkSpecification><tm:MarkVerbalElementText>ALMORA</tm:MarkVerbalElementText>
      <tm:MarkSignificantVerbalElementText>ALMORA</tm:MarkSignificantVerbalElementText></tm:WordMarkSpecification>
      </tm:MarkReproduction></tm:MarkRepresentation>
      <tm:GoodsServicesBag><tm:GoodsServices><tm:GoodsServicesClassificationBag><tm:GoodsServicesClassification>
      <tm:ClassificationKindCode>Nice</tm:ClassificationKindCode><tm:ClassNumber>9</tm:ClassNumber>
      </tm:GoodsServicesClassification></tm:GoodsServicesClassificationBag><tm:ClassDescriptionBag><tm:ClassDescription>
      <tm:ClassNumber>9</tm:ClassNumber><tm:GoodsServicesDescriptionText{lang}>Computer software</tm:GoodsServicesDescriptionText>
      </tm:ClassDescription></tm:ClassDescriptionBag></tm:GoodsServices></tm:GoodsServicesBag>
      <tm:PublicationBag>{publications}</tm:PublicationBag>
      <tm:ApplicantBag><tm:Applicant><com:LegalEntityName>Synthetic Owner AG</com:LegalEntityName></tm:Applicant></tm:ApplicantBag>
      <com:RepresentativeBag><com:Representative><com:Contact><com:Name><com:PersonName>
      <com:PersonFullName>Synthetic Representative</com:PersonFullName></com:PersonName></com:Name></com:Contact>
      </com:Representative></com:RepresentativeBag></tm:Trademark></tm:TrademarkBag></tm:TrademarkApplication>'''.encode()


def response(*, payload=None, count=1, total=1, offset=0, continuation="", success="true"):
    xml = (record() if payload is None else payload).decode()
    data = f'<api:Data id="response-local-id" role="Trademark">{xml}</api:Data>' if xml else ""
    return f'''<api:ApiResponse xmlns:api="{CORE}" xmlns:db="{COMMON}" requestUuid="fixture-request">
      <api:Result success="{success}"><api:Meta><db:ItemCount>{count}</db:ItemCount><db:TotalItemCount>{total}</db:TotalItemCount>
      <db:ItemCountOffset>{offset}</db:ItemCountOffset></api:Meta>{data}{continuation}</api:Result></api:ApiResponse>'''.encode()


def facts(payload=None):
    value = decode_trademark(record() if payload is None else payload, source_url="https://www.swissreg.ch/public/api/v1")
    return value.facts(official_id="CH/application/12345/2026")


def test_full_detail_request_is_private_profile_free_and_ascending():
    root = parse_xml(initial_request(page_size=64, request_uuid="fixture-request"))
    representation = next(root.iter(q(COMMON, "Representation")))
    assert representation.attrib == {"details": "Maximal", "strictness": "Strict", "images": "Link", "itemBags": "false"}
    assert next(root.iter(q(COMMON, "LastUpdateSort"))).text == "Ascending"
    assert root.attrib == {"uuid": "fixture-request"}
    assert "ALMORA" not in ET.tostring(root).decode()


def test_successful_page_retains_hashes_and_normalizes_native_fields_without_identity_guess():
    raw = response()
    page = decode_response(200, HEADERS, raw, now=NOW, expected_request_uuid="fixture-request")
    assert page.response_sha256 == page.xml_sha256 == hashlib.sha256(raw).hexdigest()
    assert page.count == page.total == 1 and page.offset == 0 and page.next_request is None
    assert not page.coverage_verified
    native = decode_trademark(page.items[0].xml, source_url="https://www.swissreg.ch/public/api/v1")
    assert native.aliases == ("CH/application/12345/2026", "CH/registration/123456")
    with pytest.raises(IPIProtocolError):
        native.facts(official_id=page.items[0].item_id)
    row = native.facts(official_id=native.aliases[0])
    assert row.mark == "ALMORA" and row.owners == ("Synthetic Owner AG",)
    assert row.representatives == ("Synthetic Representative",) and row.classes == (9,)
    assert row.source_sha256 == hashlib.sha256(native.raw_xml).hexdigest()
    assert row.application_date.isoformat() == "2026-07-01"
    assert row.registration_date.isoformat() == "2026-08-09"
    assert row.publication_date.isoformat() == "2026-08-12"
    assert row.publications[1].publication_date.isoformat() == "2026-09-13"
    assert row.expiry_date.isoformat() == "2036-07-01" and row.renewal_date is None
    assert assess(portfolio(), row, now=NOW)["results"][0]["priority"] == "high"


def test_opaque_continuation_preserved_and_empty_page_is_not_end_of_traversal():
    continuation = '<api:Continuations><api:Continuation name="NextPage" xmlns:v="urn:fixture" v:format="1">opaque&amp;token==</api:Continuation></api:Continuations>'
    page = decode_response(200, HEADERS, response(payload=b"", count=0, total=2, continuation=continuation), now=NOW)
    followup = parse_xml(page.next_request)
    child, = followup
    assert child.tag == q(CORE, "Continuation") and child.text == "opaque&token=="
    assert child.get("{urn:fixture}format") == "1" and child.get("name") == "NextPage"
    assert not page.coverage_verified


def test_zip_bundle_keeps_response_and_document_hashes_distinct_without_extracting_resources():
    buffer = io.BytesIO()
    xml = response()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("response.xml", xml)
        archive.writestr("image.png", b"synthetic-unread-image")
    payload = buffer.getvalue()
    page = decode_response(200, {**HEADERS, "Content-Type": "application/zip"}, payload, now=NOW)
    assert page.response_sha256 == hashlib.sha256(payload).hexdigest() != page.xml_sha256
    assert page.xml_sha256 == hashlib.sha256(xml).hexdigest()


@pytest.mark.parametrize("payload", [
    response(success="false"), response(success=""), response(count=2, total=2), response(total=2),
    response(offset=2), response().replace(b'<db:ItemCount>1', b'<db:ItemCount>-1'),
    response().replace(b'<api:Meta>', b'<api:Meta><db:ItemCount>1</db:ItemCount>'),
    response(continuation='<api:Continuations><api:Continuation name="Unexpected">x</api:Continuation></api:Continuations>'),
    response().replace(b'role="Trademark"', b'role="Trademark"').replace(b'<api:Data ', b'<api:DataReference ').replace(b'</api:Data>', b'</api:DataReference>'),
    b'<ApiResponse/>',
])
def test_partial_or_ambiguous_responses_never_become_empty_success(payload):
    with pytest.raises(IPIProtocolError):
        decode_response(200, HEADERS, payload, now=NOW)


@pytest.mark.parametrize("headers", [{"Content-Type": "application/xml"}, {**HEADERS, "X-IPI-SUCCESS": "false"},
    [("X-IPI-SUCCESS", "true"), ("x-ipi-success", "false"), ("Content-Type", "application/xml")]])
def test_http_success_does_not_override_action_failure_or_duplicate_headers(headers):
    with pytest.raises(IPIProtocolError):
        decode_response(200, headers, response(), now=NOW)


def test_request_binding_and_bounded_parameters():
    with pytest.raises(IPIProtocolError):
        decode_response(200, HEADERS, response(), now=NOW, expected_request_uuid="different")
    for invalid in (True, 0, 65, "64"):
        with pytest.raises(IPIProtocolError):
            initial_request(page_size=invalid)


@pytest.mark.parametrize("value,expected", [("120", 120), ("Sun, 13 Sep 2026 20:01:00 GMT", 60),
    ("Sun, 13 Sep 2026 19:00:00 GMT", 0), ("-1", None), ("tomorrow", None), (None, None)])
def test_retry_after_honours_both_documented_forms(value, expected):
    assert retry_after(value, now=NOW) == expected
    with pytest.raises(IPIProtocolError) as error:
        decode_response(429, {"Retry-After": value}, b"", now=NOW)
    assert error.value.retry_after_seconds == expected


@pytest.mark.parametrize("payload", [b'<!DOCTYPE a [<!ENTITY x SYSTEM "file:///private">]><a>&x;</a>',
    b"<a>" * 65 + b"</a>" * 65, b"\x00<a/>", b"<a>"])
def test_unsafe_or_invalid_xml_is_rejected(payload):
    with pytest.raises(IPIProtocolError):
        parse_xml(payload)


@pytest.mark.parametrize("name", ["../response.xml", "/response.xml", "folder\\response.xml", "C:/response.xml", "other.xml"])
def test_bad_zip_paths_or_missing_response_are_rejected_without_extraction(name):
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr(name, response())
    with pytest.raises(IPIProtocolError):
        decode_response(200, {**HEADERS, "Content-Type": "application/zip"}, buffer.getvalue(), now=NOW)


def test_unlabelled_goods_language_is_unknown_and_does_not_invent_a_match():
    row = facts(record(language=None))
    assert row.goods_services[0].language is None and row.goods_services[0].text == "Computer software"
    decision = assess(portfolio(), row, now=NOW)["results"][0]
    assert decision["goods_services"]["state"] == "unknown" and decision["priority"] == "review"


@pytest.mark.parametrize("language,description", [("de", "Computerprogramme"), ("fr", "logiciels informatiques"),
    ("it", "programmi informatici"), ("rm", "programs da computer"), ("en", "computer software")])
def test_original_multilingual_goods_and_explicit_language_are_retained(language, description):
    row = facts(record(language=language).replace(b"Computer software", description.encode()))
    assert row.goods_services[0].language == language and row.goods_services[0].text == description


def test_registry_publication_changes_do_not_replace_new_registration_or_invent_renewal():
    row = facts(record(publications=publication("Change of owner") + publication("Prolongation", "2026-09-13")))
    assert row.publication_date is None and row.renewal_date is None
    assert len(row.publications) == 2
    ambiguous = facts(record(publications=publication() + publication(day="2026-09-12")))
    assert ambiguous.publication_date is None
    changed = facts(record(publications=publication() + publication("Correction", "2026-09-13")))
    assert changed.material_fingerprint() != facts().material_fingerprint()


def test_international_identity_and_missing_mark_or_goods_do_not_become_guessed_fields():
    native = decode_trademark(record(office="WO"), source_url="https://www.swissreg.ch/public/api/v1")
    assert native.facts(official_id="WO/registration/123456").origin == "international_designating_ch"
    row = facts(record().replace(b'<tm:MarkVerbalElementText>ALMORA</tm:MarkVerbalElementText>', b''))
    assert row.mark is None  # Significant verbal element is not the entire mark.
    root = parse_xml(record())
    goods = next(root.iter(q(TM, "GoodsServices")))
    goods.remove(goods.find(q(TM, "ClassDescriptionBag")))
    row = facts(ET.tostring(root))
    assert row.classes == (9,) and row.goods_services is None


def test_party_contact_addresses_are_not_turned_into_name_or_matching_fields():
    raw = record().replace(b'<com:LegalEntityName>Synthetic Owner AG</com:LegalEntityName>',
        b'<com:PartyIdentifier>owner-1</com:PartyIdentifier>')
    assert facts(raw).owners is None
    structured = record().replace(b'<com:PersonFullName>Synthetic Representative</com:PersonFullName>',
        b'<com:PersonStructuredName><com:FirstName>Alex</com:FirstName><com:LastName>Example</com:LastName></com:PersonStructuredName>')
    assert facts(structured).representatives == ("Alex Example",)


@pytest.mark.parametrize("old,new", [(b'V7_1', b'V8_0'), (b'>CH<', b'>US<'),
    (b'2026-07-01</com:ApplicationDate>', b'2026-02-30</com:ApplicationDate>'),
    (b'2026-07-01</com:ApplicationDate>', b'2026-07-01+14:59</com:ApplicationDate>'),
    (b'<tm:ClassNumber>9', b'<tm:ClassNumber>46')])
def test_unsupported_version_office_and_invalid_native_dates_or_classes_are_unavailable(old, new):
    with pytest.raises(IPIProtocolError):
        facts(record().replace(old, new))


def test_source_civil_date_is_not_shifted_by_offset_and_non_nice_codes_are_not_nice():
    raw = record().replace(b'<com:ApplicationDate>2026-07-01</com:ApplicationDate>',
        b'<com:ApplicationDateTime>2026-07-01T00:30:00+02:00</com:ApplicationDateTime>')
    assert facts(raw).application_date.isoformat() == "2026-07-01"
    unknown = facts(record().replace(b'>Nice<', b'>National<'))
    assert unknown.classes is None and unknown.goods_services[0].class_number is None
    assert retry_after("Sun, 13 Sep 2026 20:00:01 GMT", now=NOW + timedelta(microseconds=1)) == 1
