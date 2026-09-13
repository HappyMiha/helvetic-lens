"""IPI's Swiss ST.96 7.1 trademark fields; preserves original register evidence.

Business-number aliases are returned for a durable identity resolver. A response
Data@id is not assumed to be a stable register identity. This decoder performs no
source authorization, inference of absent fields, image OCR or legal calculation.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime

from pydantic import ValidationError

from .ipi_protocol import COM, TM, IPIProtocolError, parse_xml, q
from .trademark_contracts import TrademarkFacts

XML = "http://www.w3.org/XML/1998/namespace"
NS = {"tm": TM, "com": COM}
MAX_RECORD_BYTES = 2 * 1024 * 1024


def _one(parent, path):
    nodes = parent.findall(path, NS)
    if len(nodes) > 1:
        raise IPIProtocolError("ipi_ambiguous_field")
    return nodes[0] if nodes else None


def _value(node):
    if node is None:
        return None
    if len(node):
        raise IPIProtocolError("ipi_structured_text_unavailable")
    return (node.text or "").strip() or None


def _text(parent, path):
    return _value(_one(parent, path))


def _date(parent, path):
    value = _text(parent, path)
    if value is None:
        return None
    # Accept the XSD date timezone suffix without shifting a civil source date.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))?", value):
        raise IPIProtocolError("ipi_date_invalid")
    try:
        result = date.fromisoformat(value[:10])
    except ValueError:
        raise IPIProtocolError("ipi_date_invalid") from None
    # The official mapping documents 0001-01-01 as an unknown priority-date sentinel.
    return result.isoformat() if result.year > 1 else None


def _party_names(parent, bag_path, entry_name):
    bag = _one(parent, bag_path)
    if bag is None:
        return None
    entries = bag.findall(entry_name, NS)
    if not entries:
        return None
    names = []
    for entry in entries:
        name = _text(entry, "com:LegalEntityName")
        if name is None:
            for path in ("com:Contact/com:Name/com:PersonName/com:PersonFullName",
                         "com:Contact/com:Name/com:OrganizationName/com:OrganizationStandardName",
                         "com:Contact/com:Name/com:EntityName"):
                name = _text(entry, path)
                if name is not None:
                    break
        if name is None:
            structured = _one(entry, "com:Contact/com:Name/com:PersonName/com:PersonStructuredName")
            if structured is not None:
                pieces = [_text(structured, f"com:{part}") for part in (
                    "NamePrefix", "FirstName", "MiddleName", "LastName", "FirstLastName", "SecondLastName", "NameSuffix")]
                name = " ".join(part for part in pieces if part) or None
        if name is None:
            # Do not present a partial list as complete party coverage.
            return None
        names.append(name)
    return names


def _goods(parent):
    bag = _one(parent, "tm:GoodsServicesBag")
    if bag is None:
        return None, None
    classes, statements, unknown_classes = set(), [], False
    groups = bag.findall("tm:GoodsServices", NS)
    if not groups:
        return None, None
    missing_descriptions = False
    for group in groups:
        classifications = group.findall("tm:GoodsServicesClassificationBag/tm:GoodsServicesClassification", NS)
        kinds = {_text(c, "tm:ClassificationKindCode") for c in classifications}
        overall = _text(group, "tm:ClassificationKindCode")
        is_nice = kinds == {"Nice"} and overall in (None, "Nice") or overall == "Nice" and not kinds

        def nice_number(element):
            value = _text(element, "tm:ClassNumber")
            if value is None or not is_nice:
                return None
            if not re.fullmatch(r"[0-9]{1,2}", value) or not 1 <= int(value) <= 45:
                raise IPIProtocolError("ipi_nice_class_invalid")
            classes.add(int(value))
            return int(value)

        for classification in classifications:
            if _text(classification, "tm:ClassificationKindCode") == "Nice":
                nice_number(classification)
        descriptions = group.findall("tm:ClassDescriptionBag/tm:ClassDescription", NS)
        if not descriptions:
            missing_descriptions = True
        for description in descriptions:
            number = nice_number(description)
            nodes = description.findall("tm:GoodsServicesDescriptionText", NS)
            if not nodes:
                missing_descriptions = True
            for node in nodes:
                value = _value(node)
                if value is None:
                    missing_descriptions = True
                    continue
                language, xml_language = node.get(q(COM, "languageCode")), node.get(q(XML, "lang"))
                if language and xml_language and language.lower() != xml_language.lower():
                    raise IPIProtocolError("ipi_language_ambiguous")
                statements.append({"class_number": number, "text": value, "language": language or xml_language})
        unknown_classes |= not is_nice
    # Maximal is requested. A missing description is still unknown, not a negative.
    return (None if unknown_classes or not classes else sorted(classes)), (None if missing_descriptions else statements or None)


def _publications(parent):
    bag = _one(parent, "tm:PublicationBag")
    if bag is None:
        return None
    publications = []
    for node in bag.findall("tm:Publication", NS):
        identifier = _one(node, "com:PublicationIdentifier")
        value = _value(identifier)
        if value is None:
            raise IPIProtocolError("ipi_publication_identity_missing")
        national = _one(node, "tm:NationalPublication")
        descriptions, texts = [], []
        if national is not None:
            for change in national.findall("tm:RegistrationChangeBag/tm:RegistrationChange", NS):
                descriptions.extend(v for element in change.findall("tm:ChangeDescriptionText", NS) if (v := _value(element)))
                texts.extend(v for element in change.findall("tm:ChangeText", NS) if (v := _value(element)))
        publications.append({"identifier": value, "office_code": identifier.get(q(COM, "officeCode")),
            "publication_date": _date(node, "com:PublicationDate"),
            "action_date": _date(national, "tm:PublicationActionDate") if national is not None else None,
            "category": _text(national, "tm:PublicationCategoryText") if national is not None else None,
            "change_descriptions": descriptions, "change_texts": texts})
    return publications or None


@dataclass(frozen=True)
class NativeTrademark:
    aliases: tuple[str, ...]
    raw_xml: bytes
    fields_json: bytes

    def facts(self, *, official_id):
        """Only a source business alias may be selected by the identity resolver."""
        if official_id not in self.aliases:
            raise IPIProtocolError("ipi_identity_not_in_record")
        return TrademarkFacts.model_validate({**json.loads(self.fields_json), "official_id": official_id})


def decode_trademark(payload, *, source_url, source_document_sha256=None):
    root = parse_xml(payload, maximum=MAX_RECORD_BYTES)
    if root.tag != q(TM, "TrademarkApplication"):
        raise IPIProtocolError("ipi_trademark_root_invalid")
    if root.get(q(COM, "st96Version")) != "V7_1":
        raise IPIProtocolError("ipi_st96_version_unavailable")
    marks = root.findall("tm:TrademarkBag/tm:Trademark", NS)
    if len(marks) != 1:
        raise IPIProtocolError("ipi_trademark_count_invalid")
    mark = marks[0]
    office = _text(mark, "com:RegistrationOfficeCode")
    if office not in {"CH", "WO"}:
        raise IPIProtocolError("ipi_registration_office_unavailable")
    application_numbers = []
    for node in mark.findall("com:ApplicationNumber", NS):
        number = _text(node, "com:ApplicationNumberText") or _text(node, "com:ST13ApplicationNumber")
        if number is None:
            raise IPIProtocolError("ipi_application_number_missing")
        application_numbers.append(number)
    registration_numbers = [_value(node) for node in mark.findall("com:RegistrationNumber", NS)]
    if any(number is None for number in registration_numbers):
        raise IPIProtocolError("ipi_registration_number_missing")
    aliases = tuple(f"{office}/{kind}/{number}" for kind, numbers in (
        ("application", application_numbers), ("registration", registration_numbers)) for number in numbers)
    if not aliases or len(set(aliases)) != len(aliases):
        raise IPIProtocolError("ipi_record_identity_ambiguous")
    application_date = _date(mark, "com:ApplicationDate")
    date_time = _text(mark, "com:ApplicationDateTime")
    if date_time is not None:
        if application_date is not None:
            raise IPIProtocolError("ipi_application_date_ambiguous")
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-](?:(?:0\d|1[0-3]):[0-5]\d|14:00))?", date_time):
                raise ValueError("Invalid date-time")
            # Preserve source-local civil date, not a timezone-converted day.
            application_date = datetime.fromisoformat(date_time).date().isoformat()
        except ValueError:
            raise IPIProtocolError("ipi_date_invalid") from None
    classes, goods = _goods(mark)
    publications = _publications(mark)
    new_registration_dates = {p["publication_date"] for p in publications or ()
        if p["category"] == "New registration" and p["publication_date"] is not None
        and p["office_code"] in (None, office)}
    fields = {"source_url": source_url, "source_sha256": hashlib.sha256(payload).hexdigest(),
        "source_document_sha256": source_document_sha256,
        "origin": "national_ch" if office == "CH" else "international_designating_ch",
        "application_numbers": application_numbers, "registration_numbers": registration_numbers,
        "mark": _text(mark, "tm:MarkRepresentation/tm:MarkReproduction/tm:WordMarkSpecification/tm:MarkVerbalElementText"),
        "mark_type": _text(mark, "tm:MarkRepresentation/tm:MarkFeatureCategory"),
        "owners": _party_names(mark, "tm:ApplicantBag", "tm:Applicant"),
        "representatives": _party_names(mark, "com:RepresentativeBag", "com:Representative"),
        "classes": classes, "goods_services": goods, "publications": publications,
        "application_date": application_date, "registration_date": _date(mark, "com:RegistrationDate"),
        "publication_date": next(iter(new_registration_dates)) if len(new_registration_dates) == 1 else None,
        "expiry_date": _date(mark, "com:ExpiryDate"), "renewal_date": None,
        "cancellation_date": _date(mark, "tm:TerminationDate"), "status": _text(mark, "tm:MarkCurrentStatusCode")}
    result = NativeTrademark(aliases, payload, json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode())
    try:
        result.facts(official_id=aliases[0])
    except ValidationError:
        raise IPIProtocolError("ipi_trademark_fields_invalid") from None
    return result
