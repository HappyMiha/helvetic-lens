"""One pure guard can share ancestry work; the next worker guard must be fresh."""
from collections import Counter
from copy import deepcopy
from uuid import uuid4

import pytest
from test_product_dossiers import signed as signed
from test_product_entity_identity import seed

from helvetic_lens import product_direction_assessment as directions
from helvetic_lens import product_evidence_applicability as applicability
from helvetic_lens import product_exploration as exploration
from helvetic_lens import product_observed_queries as queries
from helvetic_lens import product_research_memory as memory
from helvetic_lens.product_investigation_models import Investigation, InvestigationSource
from helvetic_lens.product_models import DossierEntry
from helvetic_lens.research_read_view import read_once


def test_adaptive_guard_reuses_pure_ancestry_checks_but_refreshes_after_mutation_and_exception(signed, monkeypatch):
    _, service, doc, _, _, sources, runs, _ = seed(signed)
    calls = Counter()
    for module in (memory, queries, applicability):
        underlying, name = module.current.__wrapped__, module.__name__

        def counted(session, run, *, operation=underlying, label=name):
            calls[label, run.id] += 1
            return operation(session, run)

        monkeypatch.setattr(module, 'current', read_once(counted))

    with service.db.session() as session:
        parent, child = [session.get(Investigation, key) for key in runs]
        source = session.get(InvestigationSource, sources[0])
        source.kind = 'public_source'
        parent.external_discovery = True
        parent.research_state = {'questions': [], 'exploration': {
            'contract': exploration.CONTRACT, 'continued_by': child.id, 'reply_fingerprint': 'current-reply',
            'adaptive_dependencies': [{'source_id': source.id, 'sha256': source.sha256}]}}
        child.research_state = {'questions': [], 'exploration': {
            'contract': exploration.CONTRACT, 'memory_contract': memory.CONTRACT,
            'previous': {'investigation_id': parent.id, 'user_refinement': {
                'question': child.question, 'original_question': parent.question, 'reply_fingerprint': 'current-reply'}}}}
        session.flush()
        memory.initialize(session, child)
        session.commit()
        calls.clear()
        before = deepcopy(child.research_state)

        assert exploration.adaptive_current(session, child)
        # Memory and explicit ancestry both visit this actual parent. The same
        # permission/provenance predicate runs once within this pure graph.
        assert calls[queries.__name__, parent.id] == 1
        assert calls and max(calls.values()) == 1
        assert 'research_read_view' not in session.info
        assert child.research_state == before and not session.dirty

        first = calls.copy()
        assert exploration.adaptive_current(session, child)
        assert calls == Counter({key: value * 2 for key, value in first.items()})
        child.generation += 1
        child.revision += 1
        session.commit()
        assert exploration.adaptive_current(session, child)
        assert calls == Counter({key: value * 3 for key, value in first.items()})

        original = directions.current
        def interrupted(session, run):
            raise ValueError('Validation interrupted after the dependency checks')
        monkeypatch.setattr(directions, 'current', interrupted)
        with pytest.raises(ValueError, match='Validation interrupted'):
            exploration.adaptive_current(session, child)
        assert 'research_read_view' not in session.info
        monkeypatch.setattr(directions, 'current', original)
        assert exploration.adaptive_current(session, child)
        assert calls == Counter({key: value * 5 for key, value in first.items()})

        # A source exclusion between preflight and the later validation pass
        # must invalidate the retained ancestor even on this same ORM session.
        session.add(DossierEntry(dossier_id=doc['id'], kind='source_review', request_key=str(uuid4()),
            url=source.url, body='Exclude the fictional original.', data_json={'decision': 'exclude', 'revision': 1}))
        session.commit()
        assert not exploration.adaptive_current(session, child)
        assert 'research_read_view' not in session.info
        assert child.research_state == before
