"""Local retrieval packs complete exact originals for bounded synthesis requests."""
import json
import math
from copy import deepcopy
from time import monotonic
from urllib.parse import urlsplit

from .config import DomainError
from .product_operations import fingerprint
from .research_original_context import POLICY as ORIGINAL_CONTEXT_POLICY
from .research_original_context import provider_excerpts, reference_units
from .research_reading_context import PROJECTION as READING_CONTEXT_POLICY
from .research_reading_context import SCOPE as READING_CONTEXT_SCOPE
from .research_reading_context import provider_notes
from .research_reference_metadata import POLICY as SOURCE_USE_POLICY
from .research_requested_sources import CONTRACT as REQUESTED_SOURCE_POLICY
from .research_requested_sources import provider_basis, validated_matches, wire_matches

POLICY = fingerprint({'contract': 'local-hybrid-evidence-pack/v2',
    'units': ORIGINAL_CONTEXT_POLICY, 'packing': 'requested-source-then-request-fair-whole-group-seeding/v6',
    'mission_metadata': 'completed-document-and-brief-history-counts/v2', 'cost': 'actual-caller-envelope/v1',
    'source_use': SOURCE_USE_POLICY, 'requested_sources': REQUESTED_SOURCE_POLICY})


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def provider_sources(wire, references):
    """A provider view, without altering host discovery links or source records."""
    metadata = {source['id']: source for source in wire.input.get('sources', [])}
    groups = []
    matches = wire_matches(wire)
    readings = provider_notes(wire, references)
    for source_id, excerpts in provider_excerpts(wire, references).items():
        source = metadata.get(source_id, {})
        groups.append({
            **{field: source[field] for field in ('sha256', 'title', 'url') if field in source},
            'id': source_id, 'excerpts': excerpts, **provider_basis(wire, source_id, matches=matches),
            **({'reading_scope': READING_CONTEXT_SCOPE, 'reading_notes': readings[source_id]}
                if readings.get(source_id) else {})})
    return groups


def provider_input(wire, references):
    """Compact completed workflow metadata, retaining every live obligation."""
    # Preserve input key order while avoiding a copy of originals immediately
    # replaced by the selected provider view. The full host corpus stays intact.
    result = deepcopy({**wire.input, 'sources': []})
    result['sources'] = provider_sources(wire, references)
    phase = getattr(wire, 'work', {}).get('phase')
    if phase == 'reflect':
        result['discovery_leads'] = selected_leads(wire, references)
    if phase in {'reflect', 'brief'}:
        result['evidence_scope'] = {
            'available_references': len(wire.references), 'selected_references': len(references),
            'all_originals_supplied': len(references) == len(wire.references), 'absence_established': False,
            'scope': 'These originals were selected from retained material. Unselected material is not evidence of absence. '
                'A missing detail in this packet does not establish a knowledge gap. '
                'Propose only consequential evidence-backed next readings; listed links are unread leads, not findings.'}
    mission = result.get('research_mission')
    if isinstance(mission, dict):
        if phase == 'brief':
            # Past search wording is routing history, not the question or
            # evidence for the answer. Keep full history on the host for the
            # next-reading/deduplication checks and on the reflection path.
            for field, count in (('attempted_queries', 'attempted_query_count'),
                    ('attempted_questions', 'attempted_question_count')):
                if isinstance(mission.get(field), list):
                    mission[count] = len(mission.pop(field))
        if mission.get('question') == result.get('original_question'):
            mission.pop('question', None)
        if mission.get('unvalidated_proposals') == []:
            mission.pop('unvalidated_proposals')
        mission.pop('completion_policy', None)
        documents = mission.get('documents')
        if isinstance(documents, list):
            mission['document_counts'] = {'total': len(documents),
                'read_complete': sum(isinstance(doc, dict) and doc.get('read_complete') is True for doc in documents),
                'analysis_complete': sum(isinstance(doc, dict) and doc.get('analysis_complete') is True for doc in documents)}
            mission['documents'] = [doc for doc in documents if not isinstance(doc, dict)
                or doc.get('read_complete') is not True or doc.get('analysis_complete') is not True
                or any(doc.get(key) for key in ('unread_reason', 'warnings', 'unresolved_references', 'error'))]
    return result


def selected_leads(wire, references):
    """Keep unread source URLs only with an exact selected referring witness."""
    sources = {source['id']: source for source in wire.input.get('sources', [])}
    leads = {}
    for key, ref in references.items():
        for link in sources.get(ref['source_id'], {}).get('discovery_links', []):
            url, context = link.get('url'), link.get('context')
            if (not isinstance(url, str) or url in leads or urlsplit(url).scheme not in {'http', 'https'}
                    or not urlsplit(url).hostname or link.get('kind') == 'navigation'
                    or not isinstance(context, str) or not context.strip()):
                continue
            quote, referring = ' '.join(ref['quote'].split()), ' '.join(context.split())
            if quote in referring or referring in quote or url in ref['quote']:
                leads[url] = {'citation_ref': key, 'url': url, 'title': str(link.get('title', ''))[:300]}
    return list(leads.values())


def bounded_schema(schema, references):
    """Use the existing response shape, scoped to the actually supplied refs."""
    result = deepcopy(schema)
    allowed = list(references)

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            properties = value.get('properties', {})
            action = properties.get('next_action', {})
            if not allowed and 'anyOf' in action:
                # A cited clarification cannot be offered without originals.
                action['anyOf'] = [branch for branch in action['anyOf']
                    if branch.get('properties', {}).get('kind', {}).get('enum') != ['clarify']]
            if 'citation_ref' in properties and allowed:
                properties['citation_ref'] = {'type': 'integer', 'enum': allowed}
            if not allowed:
                for key in ('points', 'evidence', 'next_checks', 'directions', 'gaps'):
                    if properties.get(key, {}).get('type') == 'array':
                        properties[key].update(minItems=0, maxItems=0)
            for item in value.values():
                walk(item)
    walk(result)
    return result


def request_characters(system, payload, schema, *, provider=None):
    if provider == 'swisscom':
        # Match ModelClient's strict-schema transport, including the escaping
        # of the serialized user JSON inside the outer chat request. The margin
        # covers model/sampling/output settings; no evidence or grammar is lost.
        body = {'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': _json(payload)}],
            'response_format': {'type': 'json_schema', 'json_schema': {
                'name': schema.get('title', 'structured_response'), 'strict': True, 'schema': schema}}}
        return len(json.dumps(body)) + 1024
    # Hosted adapters may include the schema both in the prompt and protocol.
    # This conservative envelope is a transport allowance, not a token count.
    return len(system) + len(_json(payload)) + 2 * len(json.dumps(schema)) + 1024


def _final_size(wire, references, *, provider=None):
    payload = provider_input(wire, references)
    return request_characters(getattr(wire, 'system', ''), payload,
        bounded_schema(getattr(wire, 'schema', {}), references), provider=provider)


def _units(wire, _question=None):
    """Canonical complete passages and context, independent of retrieval order."""
    return reference_units(wire)


def _references(wire, units):
    retained = {key for unit in units for key in unit['references']}
    return {key: value for key, value in wire.references.items() if key in retained}


def _question_scores(rankings):
    """Comparable retrieval priorities per literal query, never proof of coverage."""
    queries = {}
    for ranking in rankings:
        supplied, scores = ranking.get('scores', {}), {}
        for position, key in enumerate(ranking['references'], 1):
            value = supplied.get(key, supplied.get(str(key))) if isinstance(supplied, dict) else None
            scores[key] = (float(value) if type(value) in (int, float) and math.isfinite(value) and value >= 0
                else 1 / (60 + position))
        maximum = max(scores.values(), default=0)
        if maximum:
            queries[ranking['query']] = {key: value / maximum for key, value in scores.items()}
    return queries


def _incremental_units(wire, units, rankings, selected, retained, costs, request_size, allowance):
    """Balance question relevance of whole groups, not their text volume."""
    query_scores = _question_scores(rankings)
    scores = list(query_scores.values())
    pool = {index for index, unit in enumerate(units)
        if any(key in row for row in scores for key in unit.get('ranking_refs', unit['primary']))} - selected
    empty_cost = request_size({})
    # Citation windows and PDF lines are transport geometry. Count a structural
    # group once per request, without rewarding a long, weakly related source
    # for repeating query words across many windows. Context travels with the
    # group but does not inflate the group's retrieval priority.
    # Original headings and local navigation may retrieve their bound body,
    # without becoming the primary material or independently filling the pack.
    group_scores = [[max((row.get(key, 0) for key in unit.get('ranking_refs', unit['primary'])), default=0)
        for row in scores] for unit in units]
    original_question = getattr(wire, 'input', {}).get('original_question', '').strip()
    waiting = {index for index, query in enumerate(query_scores) if query != original_question}
    if not waiting:
        waiting = set(range(len(scores)))

    def union_cost(index):
        keys = retained | set(units[index]['references'])
        return request_size({key: ref for key, ref in wire.references.items() if key in keys})

    # Seed each existing literal query from its strongest relevant matched
    # original group before commentary competes. A match is fallible, not a
    # mandatory corpus or authority verdict. One long original may address
    # several requests; a single title/chapter seed must not stand in for it all.
    sources = {source['id']: source for source in wire.input.get('sources', [])}
    matched = validated_matches(sources.values(), original_question)
    preferred = {index for index in pool if units[index]['source_id'] in matched}
    for query in sorted(waiting):
        best = max((group_scores[index][query] for index in selected
            if units[index]['source_id'] in matched), default=0)
        candidates = [index for index in preferred & pool if group_scores[index][query] > best]
        for index in sorted(candidates, key=lambda index: (-group_scores[index][query], union_cost(index), index)):
            pool.remove(index)
            before = set(retained)
            yield index
            if retained != before:
                break

    # Completed reading supplies fallible navigation to exact originals, not
    # a second corpus or a support verdict. Seed one feasible reading-selected
    # whole group per existing query, including context and counterevidence.
    # The remaining original corpus still competes during ordinary refinement.
    anchors = set(getattr(wire, 'reading_anchor_refs', [])) if getattr(wire, 'reading_context', {}) else set()
    anchored = {index for index, unit in enumerate(units) if anchors.intersection(unit['primary'])}
    reading_queries = set(waiting) if anchored else set()
    while reading_queries:
        represented = {index for index in anchored if set(units[index]['primary']) <= retained}
        best = [max((group_scores[index][query] for index in represented), default=0)
            for query in range(len(scores))]

        def reading_priority(query):
            candidates = [index for index in anchored & pool if group_scores[index][query] > best[query]]
            strongest = max((group_scores[index][query] for index in candidates), default=0)
            cost = min((union_cost(index) for index in candidates
                if group_scores[index][query] == strongest), default=math.inf)
            return best[query], cost, query

        query = min(reading_queries, key=reading_priority)
        reading_queries.remove(query)
        candidates = [index for index in anchored & pool if group_scores[index][query] > best[query]]
        for index in sorted(candidates, key=lambda index: (-group_scores[index][query], union_cost(index), index)):
            pool.remove(index)
            before = set(retained)
            yield index
            if retained != before:
                break

    while waiting:
        represented = [index for index, unit in enumerate(units) if set(unit['primary']) <= retained]
        best = [max((group_scores[index][query] for index in represented), default=0)
            for query in range(len(scores))]
        def query_priority(query):
            candidates = [index for index in pool if group_scores[index][query] > best[query]]
            strongest = max((group_scores[index][query] for index in candidates), default=0)
            # Equal representation does not privilege input order: a smaller
            # strongest group leaves other queries more room for their seed.
            cost = min((union_cost(index) for index in candidates
                if group_scores[index][query] == strongest), default=math.inf)
            return best[query], cost, query

        query = min(waiting, key=query_priority)
        waiting.remove(query)

        def seed_priority(index):
            return (-group_scores[index][query], union_cost(index), index)

        # Give the least represented query its strongest whole feasible group
        # before summed relevance can spend the packet on common topics. An
        # already-retained best group needs no extra seed. These retrieval
        # scores are not answer coverage or factual support.
        candidates = (index for index in pool if group_scores[index][query] > best[query])
        for index in sorted(candidates, key=seed_priority):
            pool.remove(index)
            before = set(retained)
            yield index  # The caller checks the complete union's exact envelope.
            if retained != before:
                break
        # Rejected groups cannot fit a later, larger union. Do not repeat
        # their fit checks for another query or during ordinary refinement.
    while pool:
        present = {key: ref for key, ref in wire.references.items() if key in retained}
        room = max(1, allowance - request_size(present))
        represented = [index for index, unit in enumerate(units) if set(unit['primary']) <= retained]
        accumulated = [sum(group_scores[index][query] for index in represented) for query in range(len(scores))]
        sources = {ref['source_id'] for ref in present.values()}

        def priority(index):
            unit = units[index]
            novel = set(unit['references']) - retained
            # Smooth diminishing returns retain independently relevant or
            # opposing originals after the highest-ranked passage is present.
            gain = sum(math.sqrt(1 + previous + score) - math.sqrt(1 + previous)
                for score, previous in zip(group_scores[index], accumulated)) if novel.intersection(unit['primary']) else 0
            weights = {key: max(1, len(ref['quote'])) for key, ref in unit['references'].items()}
            # Standalone costs use the actual caller envelope. Discount overlap
            # for ordering; the caller still checks every accepted union exactly.
            marginal = max(0, costs[index] - empty_cost) * sum(
                weight for key, weight in weights.items() if key not in retained) / sum(weights.values())
            # Diversity is a bounded preference, not a right to displace much
            # stronger evidence merely because its source is already present.
            diversity = 1.25 if unit['source_id'] not in sources else 1
            return (gain * diversity / (1 + marginal / room), gain, -marginal, -index)

        snapshot = set(retained)
        ordered = sorted(((priority(index), index) for index in pool), reverse=True)
        for priority_value, index in ordered:
            if priority_value[0] <= 0:
                return  # No new ranked originals, not a claim the question is answered.
            pool.remove(index)
            yield index
            if retained != snapshot:
                break  # Rejected unions leave every remaining priority unchanged.


def _coverage(wire, checkpoints, receipt):
    """Expose named retrieval scope without promoting a shortlist to proof."""
    checkpoints['retrieval_coverage'] = deepcopy(receipt)
    if isinstance(getattr(wire, 'receipt', None), dict):
        wire.receipt['retrieval'] = deepcopy(receipt)


async def select_evidence(service, wire, question, seconds, *, checkpoints=None, on_progress=None,
        fits=None, required_refs=(), request_size=None, envelope_binding=None):
    """Rank locally, then pack whole original groups; no generative selection."""
    from . import research_active_retrieval as retrieval

    started = monotonic()
    settings = getattr(service, 'settings', None)
    allowance = getattr(settings, 'apertus_context_chars', 24000)
    measure = request_size if request_size is not None else lambda references: _final_size(wire, references,
        provider=getattr(settings, 'apertus_provider', None))
    sizes = {}

    def request_size(references):
        identity = tuple((key, ref['source_id'], ref['locator'], ref['quote']) for key, ref in references.items())
        if identity not in sizes:
            sizes[identity] = measure(references)
        return sizes[identity]

    fits = fits if fits is not None else lambda references: request_size(references) <= allowance
    if any(type(key) is not int or key not in wire.references for key in required_refs):
        raise DomainError('A mandatory evidence reference is not in the retained originals.',
            422, 'research_evidence_required_reference_invalid')
    required_refs = set(required_refs)
    checkpoints = checkpoints if checkpoints is not None else {}
    units = _units(wire)
    required = {index for index, unit in enumerate(units) if required_refs.intersection(unit['primary'])}
    mandatory = _references(wire, [units[index] for index in sorted(required)])
    input_fingerprint = fingerprint({'question': question, 'originals': wire.references,
        'sources': wire.input.get('sources', []), 'required': sorted(required_refs),
        'source_uses': getattr(wire, 'reference_uses', {}),
        **({'reading_context_policy': READING_CONTEXT_POLICY, 'reading_context': wire.reading_context,
            'reading_anchor_refs': getattr(wire, 'reading_anchor_refs', [])}
            if getattr(wire, 'reading_context', {}) else {})})
    # An explicit caller contract binds every prompt/payload/schema/provider
    # input to its fit callback. Unbound callbacks retain the cost-based path.
    # Keep that existing node identity so legacy completed work remains usable.
    envelope_fingerprint = fingerprint({'contract': 'bound-selection-envelope/v1',
        'envelope': envelope_binding, 'input': input_fingerprint, 'wire_input': wire.input,
        'source_context': getattr(wire, 'source_context', []),
        'work_scope': {key: getattr(wire, 'work', {}).get(key) for key in ('phase', 'run_id', 'generation')},
        'policy': POLICY, 'retrieval': retrieval.POLICY, 'allowance': allowance}) if envelope_binding is not None else None
    nodes = checkpoints.get('evidence_selection', {})

    def saved_references(saved):
        if (isinstance(saved, dict) and saved.get('status') == 'complete'
                and saved.get('input_fingerprint') == input_fingerprint and saved.get('policy_fingerprint') == POLICY
                and isinstance(saved.get('selected'), list)
                and all(type(key) is int and key in wire.references for key in saved['selected'])
                and len(saved['selected']) == len(set(saved['selected']))
                and set(mandatory) <= set(saved['selected']) and isinstance(saved.get('retrieval_coverage'), dict)
                and isinstance(saved.get('selected_units'), list)
                and all(type(index) is int and 0 <= index < len(units) for index in saved['selected_units'])
                and set(_references(wire, [units[index] for index in saved['selected_units']])) == set(saved['selected'])):
            return {key: value for key, value in wire.references.items() if key in saved['selected']}
        return None

    if envelope_fingerprint is not None:
        for saved in nodes.values():
            if not isinstance(saved, dict) or saved.get('envelope_fingerprint') != envelope_fingerprint:
                continue
            references = saved_references(saved)
            if references is not None and fits(mandatory) and fits(references):
                await retrieval.ensure_current(service, wire)
                _coverage(wire, checkpoints, saved['retrieval_coverage'])
                return deepcopy(references)
    complete = _references(wire, [unit for index, unit in enumerate(units)
        if index in required or unit.get('ranking_refs', unit['primary'])])
    if fits(complete):
        await retrieval.ensure_current(service, wire)
        _coverage(wire, checkpoints, {'method': 'complete_original_pack' if len(complete) == len(wire.references)
                else 'complete_eligible_original_pack', 'semantic_status': 'not_needed',
            'available_references': len(wire.references), 'selected_references': len(complete),
            'all_originals_supplied': len(complete) == len(wire.references), 'absence_established': False})
        return deepcopy(complete)
    if not fits(mandatory):
        raise DomainError('Mandatory original witnesses or request metadata exceed the configured synthesis allowance.',
            422, 'research_evidence_group_too_large')
    if not units:
        raise DomainError('The synthesis request metadata exceeds the configured allowance even without evidence.',
            422, 'research_evidence_group_too_large')
    costs = [request_size(unit['references']) for unit in units]
    binding = fingerprint({'input': input_fingerprint, 'policy': POLICY, 'retrieval': retrieval.POLICY,
        'allowance': allowance, 'fixed_cost': request_size({}), 'unit_costs': costs,
        'mandatory_cost': request_size(mandatory)})
    nodes = checkpoints.setdefault('evidence_selection', {})
    saved = nodes.get(binding)
    references = saved_references(saved)
    if (envelope_fingerprint is not None and isinstance(saved, dict)
            and saved.get('envelope_fingerprint') not in (None, envelope_fingerprint)):
        references = None  # Equal character counts do not establish an equal caller contract.
    if references is not None:
        if fits(references):
            await retrieval.ensure_current(service, wire)
            _coverage(wire, checkpoints, saved['retrieval_coverage'])
            if envelope_fingerprint is not None and saved.get('envelope_fingerprint') != envelope_fingerprint:
                saved['envelope_fingerprint'] = envelope_fingerprint
                if on_progress:
                    on_progress()
            return deepcopy(references)
    ranked = await retrieval.rank_evidence(service, wire, question, max(0, seconds - (monotonic() - started)),
        checkpoints=checkpoints, on_progress=on_progress)
    rankings = ranked.get('rankings') if isinstance(ranked, dict) else None
    if (not isinstance(rankings, list) or not isinstance(ranked.get('coverage'), dict)
            or any(not isinstance(row, dict) or not isinstance(row.get('query'), str)
                or not isinstance(row.get('references'), list)
                or any(type(key) is not int or key not in wire.references for key in row['references']) for row in rankings)):
        raise DomainError('Local retrieval did not return current original references. Originals remain retained.',
            503, 'research_evidence_pack_incomplete')
    retained = set(mandatory)
    selected_units = set(required)
    rejected, ranked_groups = [], set(required)
    for index in _incremental_units(wire, units, rankings, selected_units, retained, costs, request_size, allowance):
        ranked_groups.add(index)
        candidate_keys = retained | set(units[index]['references'])
        candidate = {key: value for key, value in wire.references.items() if key in candidate_keys}
        if fits(candidate):
            retained.update(candidate_keys)
            selected_units.add(index)
        else:
            rejected.append(index)
    references = {key: value for key, value in wire.references.items() if key in retained}
    await retrieval.ensure_current(service, wire)
    coverage = {**deepcopy(ranked['coverage']), 'available_references': len(wire.references),
        'available_groups': len(units), 'ranked_groups': len(ranked_groups),
        'selected_references': len(references), 'selected_sources': len({ref['source_id'] for ref in references.values()}),
        'required_references': len(required_refs), 'groups_not_fitting': len(rejected),
        'all_originals_supplied': len(references) == len(wire.references), 'absence_established': False,
        'scope': 'Local retrieval ranks retained originals; unselected material is not evidence of absence. Complete original groups and context are preserved.'}
    saved = {'status': 'complete', 'input_fingerprint': input_fingerprint, 'policy_fingerprint': POLICY,
        'selected': list(references), 'selected_units': sorted(selected_units), 'retrieval_coverage': coverage}
    if envelope_fingerprint is not None:
        saved['envelope_fingerprint'] = envelope_fingerprint
    nodes[binding] = saved
    _coverage(wire, checkpoints, coverage)
    if on_progress:
        on_progress()
    return deepcopy(references)
