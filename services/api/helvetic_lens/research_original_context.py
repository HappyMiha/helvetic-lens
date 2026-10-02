"""Original structural context shared by compaction, retrieval and citation review."""
import re
from copy import deepcopy

POLICY = 'coherent-original-context/v1'


def _locator(locator):
    # PDF text extraction exposes lines, not paragraphs. A physical page is the
    # smallest supplied structural unit that does not invent paragraph bounds.
    page = re.fullmatch(r'page-(\d+)-text-\d+(?:-block-\d+)?(?:-char-\d+)?', locator)
    if page:
        return ('page', int(page[1]))
    paragraph = re.fullmatch(r'((?:p\d+|(?:.*-)?paragraph-\d+)(?:-block-\d+)?)(?:-char-\d+)?', locator)
    return ('passage', paragraph[1] if paragraph else locator)


def _owner(source):
    # Sequential portions of the same authorized original may split a page.
    if source.get('sha256') and source.get('url'):
        return (source['sha256'], source['url'])
    return (source.get('id'),)


def _group(source, locator):
    return (*_owner(source), *_locator(locator))


def expand_sources(selected, originals):
    """Rehydrate selected pages/paragraphs from retained originals, without edits."""
    originals = {source['id']: source for source in originals}
    wanted = {_group(originals[source['id']], passage['passage'])
        for source in selected for passage in source.get('excerpts', [])}
    result = []
    for source in selected:
        original = originals[source['id']]
        passages = [passage for passage in original.get('excerpts', [])
            if _group(original, passage['passage']) in wanted]
        result.append({**source, 'excerpts': deepcopy(passages), 'original_context': {
            'policy': POLICY, 'captured_complete': len(passages) == len(original.get('excerpts', []))}})
    return result


def _adjacent(left, right):
    # An ordinal in an original paragraph locator establishes adjacency; nearby
    # positions in a compacted citation list do not.
    a = re.fullmatch(r'(.*?)(\d+)', left)
    b = re.fullmatch(r'(.*?)(\d+)', right)
    return bool(a and b and a[1] == b[1] and abs(int(a[2]) - int(b[2])) == 1)


def reference_units(wire):
    """Canonical primary groups and their complete retained structural context."""
    metadata = {source['id']: source for source in getattr(wire, 'input', {}).get('sources', [])}
    groups, source_keys = {}, {}
    for key, ref in wire.references.items():
        source = metadata.get(ref['source_id'], {'id': ref['source_id']})
        groups.setdefault(_group(source, ref['locator']), []).append(key)
        source_keys.setdefault(ref['source_id'], []).append(key)
    units = []
    for identity, primary in groups.items():
        ref = wire.references[primary[0]]
        source = metadata.get(ref['source_id'], {})
        kind, locator = identity[-2:]
        context = set(primary)
        if kind != 'page':
            for other, keys in groups.items():
                if other[:-2] == identity[:-2] and other[-2] == kind and _adjacent(locator, other[-1]):
                    context.update(keys)
            captured = source.get('original_context', {})
            same_source = source_keys[ref['source_id']]
            if captured.get('policy') == POLICY and captured.get('captured_complete') is True and len(same_source) <= 16:
                context.update(same_source)
        units.append({'primary': primary,
            'references': {key: value for key, value in wire.references.items() if key in context},
            'source_id': ref['source_id']})
    return units


def contextual_references(wire, selected):
    selected = set(selected)
    retained = set(selected)
    for unit in reference_units(wire):
        if selected.intersection(unit['primary']):
            retained.update(unit['references'])
    return {key: ref for key, ref in wire.references.items() if key in retained}


def provider_excerpts(wire, references):
    """Retain short, non-citable original headings inside selected context too."""
    from .research_model_transport import reference_uses

    metadata = {source['id']: source for source in getattr(wire, 'input', {}).get('sources', [])}
    uses, groups = reference_uses(wire, references), {}
    wanted = {_group(metadata.get(ref['source_id'], {'id': ref['source_id']}), ref['locator'])
        for ref in references.values()}
    for key, ref in references.items():
        groups.setdefault(ref['source_id'], []).append({'citation_ref': key, 'text': ref['quote'],
            'passage': ref['locator'], **({'source_use': uses[key]} if key in uses else {})})
    for source_id, source in metadata.items():
        uncited = [{'text': p['text'], 'passage': p['passage']}
            for p in source.get('excerpts', []) if not p.get('citation_ref') and len(p['text'].strip()) < 10
            and _group(source, p['passage']) in wanted]
        if uncited:
            groups.setdefault(source_id, []).extend(uncited)
    for source_id, passages in groups.items():
        source = metadata.get(source_id, {'id': source_id})
        original = source.get('excerpts', [])
        positions = {(p['passage'], p['text']): index for index, p in enumerate(original)}
        passages.sort(key=lambda p: positions.get((p['passage'], p['text']), len(positions)))
    return {source_id: groups[source_id] for source_id in [*metadata, *groups]
        if source_id in groups}
