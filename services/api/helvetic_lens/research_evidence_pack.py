"""Local retrieval packs complete exact originals for bounded synthesis requests."""
import json
from copy import deepcopy
from time import monotonic

from .config import DomainError
from .product_operations import fingerprint
from .research_answer_parts import contextual_references

POLICY = fingerprint({'contract': 'local-hybrid-evidence-pack/v1',
    'units': 'paragraph-with-context/v1', 'packing': 'request-source-diversity/v1',
    'mission_metadata': 'completed-document-counts/v1', 'cost': 'actual-caller-envelope/v1'})


def _json(value):
    return json.dumps(value, ensure_ascii=False)


def provider_sources(wire, references):
    """A provider view, without altering host discovery links or source records."""
    metadata = {source['id']: source for source in wire.input.get('sources', [])}
    groups = {}
    for key, ref in references.items():
        source = metadata.get(ref['source_id'], {})
        group = groups.setdefault(ref['source_id'], {
            **{field: source[field] for field in ('sha256', 'title', 'url') if field in source},
            'id': ref['source_id'], 'excerpts': []})
        group['excerpts'].append({'citation_ref': key, 'text': ref['quote'], 'passage': ref['locator']})
    return list(groups.values())


def provider_input(wire, references):
    """Compact completed workflow metadata, retaining every live obligation."""
    # Preserve input key order while avoiding a copy of originals immediately
    # replaced by the selected provider view. The full host corpus stays intact.
    result = deepcopy({**wire.input, 'sources': []})
    result['sources'] = provider_sources(wire, references)
    mission = result.get('research_mission')
    if isinstance(mission, dict):
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
            if 'citation_ref' in properties and allowed:
                properties['citation_ref'] = {'type': 'integer', 'enum': allowed}
            if not allowed:
                for key in ('points', 'evidence', 'next_checks', 'directions'):
                    if properties.get(key, {}).get('type') == 'array':
                        properties[key].update(minItems=0, maxItems=0)
            for item in value.values():
                walk(item)
    walk(result)
    return result


def request_characters(system, payload, schema):
    # Hosted adapters may include the schema both in the prompt and protocol.
    # This conservative envelope is a transport allowance, not a token count.
    return len(system) + len(_json(payload)) + 2 * len(json.dumps(schema)) + 1024


def _final_size(wire, references):
    payload = provider_input(wire, references)
    return request_characters(getattr(wire, 'system', ''), payload,
        bounded_schema(getattr(wire, 'schema', {}), references))


def _units(wire, _question=None):
    """Canonical complete passages and context, independent of retrieval order."""
    by_source = {}
    for key, ref in wire.references.items():
        by_source.setdefault(ref['source_id'], []).append(key)
    units = []
    for keys in by_source.values():
        paragraphs = {}
        for key in keys:
            locator = None if len(keys) <= 16 else wire.references[key]['locator']
            paragraphs.setdefault(locator, []).append(key)
        for primary in paragraphs.values():
            units.append({'primary': primary, 'references': contextual_references(wire, primary),
                'source_id': wire.references[primary[0]]['source_id']})
    return units


def _references(wire, units):
    retained = {key for unit in units for key in unit['references']}
    return {key: value for key, value in wire.references.items() if key in retained}


def _diverse_units(units, rankings, required):
    """Interleave requested distinctions, preferring a new source on each turn."""
    owners = {key: index for index, unit in enumerate(units) for key in unit['primary']}
    queues = [list(dict.fromkeys(owners[key] for key in ranking['references'])) for ranking in rankings]
    seen = set(required)
    sources = {units[index]['source_id'] for index in seen}
    while any(queues):
        for queue in queues:
            queue[:] = [index for index in queue if index not in seen]
            if not queue:
                continue
            candidate = next((index for index in queue if units[index]['source_id'] not in sources), queue[0])
            queue.remove(candidate)
            seen.add(candidate)
            sources.add(units[candidate]['source_id'])
            yield candidate


def _coverage(wire, checkpoints, receipt):
    """Expose named retrieval scope without promoting a shortlist to proof."""
    checkpoints['retrieval_coverage'] = deepcopy(receipt)
    if isinstance(getattr(wire, 'receipt', None), dict):
        wire.receipt['retrieval'] = deepcopy(receipt)


async def select_evidence(service, wire, question, seconds, *, checkpoints=None, on_progress=None, fits=None, required_refs=(), request_size=None):
    """Rank locally, then pack whole original groups; no generative selection."""
    from . import research_active_retrieval as retrieval

    started = monotonic()
    settings = getattr(service, 'settings', None)
    allowance = getattr(settings, 'apertus_context_chars', 24000)
    measure = request_size if request_size is not None else lambda references: _final_size(wire, references)
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
    if fits(wire.references):
        await retrieval.ensure_current(service, wire)
        _coverage(wire, checkpoints, {'method': 'complete_original_pack', 'semantic_status': 'not_needed',
            'available_references': len(wire.references), 'selected_references': len(wire.references),
            'all_originals_supplied': True, 'absence_established': False})
        return deepcopy(wire.references)
    units = _units(wire)
    required = {index for index, unit in enumerate(units) if required_refs.intersection(unit['primary'])}
    mandatory = _references(wire, [units[index] for index in sorted(required)])
    if not fits(mandatory):
        raise DomainError('Mandatory original witnesses or request metadata exceed the configured synthesis allowance.',
            422, 'research_evidence_group_too_large')
    if not units:
        raise DomainError('The synthesis request metadata exceeds the configured allowance even without evidence.',
            422, 'research_evidence_group_too_large')
    costs = [request_size(unit['references']) for unit in units]
    input_fingerprint = fingerprint({'question': question, 'originals': wire.references,
        'sources': wire.input.get('sources', []), 'required': sorted(required_refs)})
    binding = fingerprint({'input': input_fingerprint, 'policy': POLICY, 'retrieval': retrieval.POLICY,
        'allowance': allowance, 'fixed_cost': request_size({}), 'unit_costs': costs,
        'mandatory_cost': request_size(mandatory)})
    nodes = checkpoints.setdefault('evidence_selection', {})
    saved = nodes.get(binding)
    if (isinstance(saved, dict) and saved.get('status') == 'complete'
            and saved.get('input_fingerprint') == input_fingerprint and saved.get('policy_fingerprint') == POLICY
            and isinstance(saved.get('selected'), list)
            and all(type(key) is int and key in wire.references for key in saved['selected'])
            and len(saved['selected']) == len(set(saved['selected']))
            and set(mandatory) <= set(saved['selected']) and isinstance(saved.get('retrieval_coverage'), dict)
            and isinstance(saved.get('selected_units'), list)
            and all(type(index) is int and 0 <= index < len(units) for index in saved['selected_units'])
            and set(_references(wire, [units[index] for index in saved['selected_units']])) == set(saved['selected'])):
        references = {key: value for key, value in wire.references.items() if key in saved['selected']}
        if fits(references):
            await retrieval.ensure_current(service, wire)
            _coverage(wire, checkpoints, saved['retrieval_coverage'])
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
    for index in _diverse_units(units, rankings, required):
        ranked_groups.add(index)
        candidate_keys = retained | set(units[index]['references'])
        candidate = {key: value for key, value in wire.references.items() if key in candidate_keys}
        if fits(candidate):
            retained = candidate_keys
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
    nodes[binding] = saved
    _coverage(wire, checkpoints, coverage)
    if on_progress:
        on_progress()
    return deepcopy(references)
