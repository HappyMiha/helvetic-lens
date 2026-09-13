"""Decoded native-schema fixtures reach the real journal; no network or live grant."""

from datetime import timedelta

from test_ipi_protocol import HEADERS, record, response
from test_trademark_matching import portfolio
from test_trademark_sources import ENDPOINT, NOW, accept, current, grant
from test_trademark_sources import db as _database_fixture
from test_trademark_sources import template as _template_fixture

from helvetic_lens import trademark_sources as source
from helvetic_lens.ipi_protocol import decode_response
from helvetic_lens.ipi_trademarks import decode_trademark
from helvetic_lens.trademark_matching import assess

db, template = _database_fixture, _template_fixture


def native(payload):
    page = decode_response(200, HEADERS, response(payload=payload), now=NOW)
    item, = page.items
    result = decode_trademark(item.xml, source_url=ENDPOINT, source_document_sha256=page.xml_sha256)
    # A pre-reviewed fixture alias simulates the future durable identity resolver.
    return result, result.facts(official_id="CH/application/12345/2026")


def test_native_record_to_private_candidate_with_publication_correction_and_retained_history(db):
    permission = grant(db)
    decoded, facts = native(record())
    first = accept(db, permission, raw=decoded.raw_xml, facts=facts)
    corrected, changed_facts = native(record().replace(b'Synthetic Owner AG', b'Corrected Owner AG'))
    second = accept(db, permission, cursor=1, raw=corrected.raw_xml, facts=changed_facts)
    assert second["material_changed"] and second["material_sequence"] == 2
    with db.session() as session:
        old = source.read_revision(session, permission, first["revision_id"], now=NOW + timedelta(seconds=1), purpose="matching")
        new = source.read_revision(session, permission, second["revision_id"], now=NOW + timedelta(seconds=1), purpose="matching")
        assert old.owners == ("Synthetic Owner AG",) and new.owners == ("Corrected Owner AG",)
        assert old.source_document_sha256 != new.source_document_sha256
        assert old.publication_date == new.publication_date
        assert len(old.publications) == len(new.publications) == 2
        before, after = assess(portfolio(), old, now=NOW), assess(portfolio(), new, now=NOW)
        assert before["decision_sha256"] != after["decision_sha256"]
        assert before["results"][0]["priority"] == after["results"][0]["priority"] == "high"
        source.revoke_permission(session, permission, now=NOW + timedelta(seconds=2))
        session.commit()


def test_parent_document_refresh_changes_evidence_not_material_candidate(db):
    permission = grant(db)
    decoded, facts = native(record())
    first = accept(db, permission, raw=decoded.raw_xml, facts=facts)
    refreshed = facts.model_copy(update={"source_document_sha256": "a" * 64})
    second = accept(db, permission, cursor=1, raw=decoded.raw_xml, facts=refreshed)
    assert second["revision_id"] != first["revision_id"] and not second["material_changed"]
    assert second["material_sequence"] == 1
    assert assess(portfolio(), facts, now=NOW)["decision_sha256"] == assess(portfolio(), refreshed, now=NOW)["decision_sha256"]
    assert not current(db, now=NOW + timedelta(seconds=1))["coverage_verified"]
