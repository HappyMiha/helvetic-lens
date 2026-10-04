"""Original structural context shared by compaction, retrieval and citation review."""
import re
from copy import deepcopy

POLICY = 'coherent-original-context/v4-html-ancestry'


def bind_source_context(sources, passages, references):
    """Resolve literal host bindings to this wire's unchanged original windows."""
    metadata = {source.get('id'): source for source in sources}

    def aliases(binding):
        if not isinstance(binding, dict) or not isinstance(binding.get('quote'), str) or not binding['quote'].strip():
            raise ValueError('Source context requires an exact original quotation')
        identity = tuple(binding.get(key) for key in ('source_id', 'sha256', 'locator'))
        if not identity[1]:
            raise ValueError('Source context requires its captured source identity')
        matches = [keys for key, keys in passages.items()
            if key[:3] == identity and binding['quote'] in key[3]]
        candidates = list(dict.fromkeys(key for keys in matches for key in keys))
        if not candidates:
            raise ValueError('Source context no longer binds to a supplied original')
        exact = [key for key in candidates if references[key]['quote'] == binding['quote']]
        # A selected quote may cross canonical windows. Retain all windows of
        # its original passage rather than crop it or create a synthetic quote.
        return exact or candidates

    linked = []
    for source in sources:
        for entry in source.get('source_context', []):
            if not isinstance(entry, dict) or not isinstance(entry.get('observation'), dict):
                raise ValueError('Source context requires an original observation')
            if entry['observation'].get('source_id') != source.get('id'):
                raise ValueError('Source context belongs to a different observation source')
            primary = aliases(entry.get('observation'))
            anchors = []
            for anchor in entry.get('anchors', []):
                if not isinstance(anchor, dict) or anchor.get('kind') not in {'scope', 'condition', 'time', 'category'}:
                    raise ValueError('Unknown source context relationship')
                target = metadata.get(anchor.get('source_id'))
                if target is None or _owner(target) != _owner(source):
                    raise ValueError('Source context must retain the same captured original')
                anchors.append({'kind': anchor['kind'], 'citation_refs': aliases(anchor)})
            if anchors:
                linked.append({'observation_refs': primary, 'anchors': anchors})
    return linked


def context_links(wire, references):
    """Rebind associations to supplied IDs, including a correction's local IDs."""
    identities = {}
    for key, ref in references.items():
        identities.setdefault(tuple(ref[field] for field in ('source_id', 'locator', 'quote')), []).append(key)

    def local(keys):
        return list(dict.fromkeys(identifier for key in keys if key in wire.references for identifier in identities.get(
            tuple(wire.references[key][field] for field in ('source_id', 'locator', 'quote')), [])))

    result = {}
    for entry in getattr(wire, 'source_context', []):
        primary = local(entry['observation_refs'])
        if not primary:
            continue
        anchors = []
        for anchor in entry['anchors']:
            if any(not local([key]) for key in anchor['citation_refs']):
                raise ValueError('Selected source context is missing a bound original anchor')
            anchors.append({'kind': anchor['kind'], 'citation_refs': local(anchor['citation_refs'])})
        for key in primary:
            target = result.setdefault(key, [])
            target.extend(anchor for anchor in anchors if anchor not in target)
    return result


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


def _html_index(sources):
    """Resolve DOM-local groups only inside the same authorized original."""
    from .html_document_structure import HTML_STRUCTURE_VERSIONS

    passages, parents = {}, {}

    def find(key):
        parents.setdefault(key, key)
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    for source in sources:
        for passage in source.get('excerpts', []):
            structure = passage.get('html_structure')
            if structure is None:
                continue
            if (not isinstance(structure, dict) or structure.get('version') not in HTML_STRUCTURE_VERSIONS
                    or structure.get('kind') not in {'body', 'heading', 'navigation'}
                    or any(not isinstance(structure.get(field, []), list)
                        or any(not isinstance(key, str) or not key for key in structure.get(field, []))
                        for field in ('group_ids', 'target_group_ids', 'context_group_ids'))
                    or not structure.get('group_ids')):
                raise ValueError('Invalid original HTML structure')
            token = (source['id'], passage['passage'])
            groups = [(*_owner(source), key) for key in structure['group_ids']]
            value = {'kind': structure['kind'], 'groups': groups,
                'context': [(*_owner(source), key) for key in structure.get('context_group_ids', [])],
                'targets': [(*_owner(source), key) for key in structure.get('target_group_ids', [])]}
            if token in passages and passages[token] != value:
                raise ValueError('Conflicting original HTML structure')
            passages[token] = value
            if value['kind'] != 'navigation':
                first = find(groups[0])
                for group in groups[1:]:
                    parents[find(group)] = first
    members, targets, dependencies = {}, {}, {}
    for token, value in passages.items():
        if value['kind'] != 'navigation':
            group = find(value['groups'][0])
            value['group'] = group
            members.setdefault(group, set()).add(token)
            dependencies.setdefault(group, set()).update(find(target) for target in value['context'] if target in parents)
    bodies = {value['group'] for value in passages.values() if value['kind'] == 'body'}
    for token, value in passages.items():
        if value['kind'] == 'navigation':
            targets[token] = {find(group) for group in value['targets'] if group in parents and find(group) in bodies}
    return passages, members, targets, dependencies


def _html_closure(groups, dependencies):
    retained, pending = set(), list(groups)
    while pending:
        group = pending.pop()
        if group not in retained:
            retained.add(group)
            pending.extend(dependencies.get(group, set()) - retained)
    return retained


def expand_sources(selected, originals):
    """Rehydrate selected pages/paragraphs from retained originals, without edits."""
    originals = {source['id']: source for source in originals}
    html, _, targets, dependencies = _html_index(originals.values())
    selected_tokens = {(source['id'], passage['passage'])
        for source in selected for passage in source.get('excerpts', [])}
    html_wanted = {html[token]['group'] for token in selected_tokens
        if token in html and html[token]['kind'] != 'navigation'}
    html_wanted.update(group for token in selected_tokens for group in targets.get(token, []))
    html_wanted = _html_closure(html_wanted, dependencies)
    wanted = {_group(originals[source['id']], passage['passage'])
        for source in selected for passage in source.get('excerpts', [])}
    result = []
    for source in selected:
        original = originals[source['id']]
        passages = [passage for passage in original.get('excerpts', [])
            if _group(original, passage['passage']) in wanted or
            html.get((source['id'], passage['passage']), {}).get('group') in html_wanted]
        result.append({**source, 'excerpts': deepcopy(passages), 'original_context': {
            'policy': POLICY, 'captured_complete': len(passages) == len(original.get('excerpts', []))}})
    return result


def _adjacent(left, right):
    # An ordinal in an original paragraph locator establishes adjacency; nearby
    # positions in a compacted citation list do not.
    # HTML/Office locators carry both paragraph and block ordinals. The block
    # suffix must not make consecutive paragraphs look like different prefixes.
    a = re.fullmatch(r'(p|(?:.*-)?paragraph-)(\d+)(?:-block-\d+)?', left)
    b = re.fullmatch(r'(p|(?:.*-)?paragraph-)(\d+)(?:-block-\d+)?', right)
    if a and b:
        return a[1] == b[1] and abs(int(a[2]) - int(b[2])) == 1
    a = re.fullmatch(r'(.*?)(\d+)', left)
    b = re.fullmatch(r'(.*?)(\d+)', right)
    return bool(a and b and a[1] == b[1] and abs(int(a[2]) - int(b[2])) == 1)


def reference_units(wire):
    """Canonical primary groups and their complete retained structural context."""
    metadata = {source['id']: source for source in getattr(wire, 'input', {}).get('sources', [])}
    html, members, targets, dependencies = _html_index(metadata.values())
    groups, source_keys, passage_refs = {}, {}, {}
    for key, ref in wire.references.items():
        source = metadata.get(ref['source_id'], {'id': ref['source_id']})
        token = (ref['source_id'], ref['locator'])
        passage_refs.setdefault(token, []).append(key)
        if token not in html:
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
    structural = {group: {key for token in tokens for key in passage_refs.get(token, [])}
        for group, tokens in members.items()}
    for group, tokens in members.items():
        primary = {key for token in tokens if html[token]['kind'] == 'body' for key in passage_refs.get(token, [])}
        if not primary:
            continue
        context = {key for linked in _html_closure([group], dependencies) for key in structural.get(linked, [])}
        # Shared ancestor prose is required context, not another relevance vote
        # for every descendant or a finding attributed to that descendant.
        ranked = structural[group] | {key for token, linked in targets.items() if group in linked
            for key in passage_refs.get(token, [])}
        ordered = [key for key in wire.references if key in primary]
        units.append({'primary': ordered, 'ranking_refs': [key for key in wire.references if key in ranked],
            'references': {key: value for key, value in wire.references.items() if key in context},
            'source_id': wire.references[ordered[0]]['source_id']})
    # Navigation and headings remain addressable for an explicitly mandatory
    # original. They never consume ordinary retrieval slots as findings.
    for token, value in html.items():
        primary = passage_refs.get(token, [])
        if value['kind'] == 'body' or not primary:
            continue
        linked = targets.get(token, set()) if value['kind'] == 'navigation' else {value['group']}
        linked = _html_closure(linked, dependencies)
        context = set(primary) | {key for group in linked for key in structural.get(group, [])}
        units.append({'primary': primary, 'ranking_refs': [],
            'references': {key: ref for key, ref in wire.references.items() if key in context},
            'source_id': token[0]})
    # A note's linked qualifier may live on another physical page. Keep its
    # complete structural unit too, without treating the relation as approval.
    structures = {key: set(unit['references']) for unit in units for key in unit['primary']}
    links = getattr(wire, 'source_context', [])
    for unit in units:
        retained = set(unit['references'])
        while True:
            previous = set(retained)
            for entry in links:
                if retained.intersection(entry['observation_refs']):
                    for anchor in entry['anchors']:
                        for key in anchor['citation_refs']:
                            if key not in structures:
                                raise ValueError('Selected source context is missing a bound original anchor')
                            retained.update(structures[key])
            if retained == previous:
                break
        unit['references'] = {key: ref for key, ref in wire.references.items() if key in retained}
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
    html, _, _, dependencies = _html_index(metadata.values())
    html_wanted = {html[(ref['source_id'], ref['locator'])]['group'] for ref in references.values()
        if (ref['source_id'], ref['locator']) in html and html[(ref['source_id'], ref['locator'])]['kind'] != 'navigation'}
    html_wanted = _html_closure(html_wanted, dependencies)
    uses, links, groups = reference_uses(wire, references), context_links(wire, references), {}
    wanted = {_group(metadata.get(ref['source_id'], {'id': ref['source_id']}), ref['locator'])
        for ref in references.values()}
    for key, ref in references.items():
        groups.setdefault(ref['source_id'], []).append({'citation_ref': key, 'text': ref['quote'],
            'passage': ref['locator'], **({'source_use': uses[key]} if key in uses else {}),
            **({'context_anchors': links[key]} if key in links else {})})
    for source_id, source in metadata.items():
        uncited = [{'text': p['text'], 'passage': p['passage']}
            for p in source.get('excerpts', []) if not p.get('citation_ref') and len(p['text'].strip()) < 10
            and (_group(source, p['passage']) in wanted
                or html.get((source_id, p['passage']), {}).get('group') in html_wanted)]
        if uncited:
            groups.setdefault(source_id, []).extend(uncited)
    for source_id, passages in groups.items():
        source = metadata.get(source_id, {'id': source_id})
        original = source.get('excerpts', [])
        positions = {(p['passage'], p['text']): index for index, p in enumerate(original)}
        passages.sort(key=lambda p: positions.get((p['passage'], p['text']), len(positions)))
    return {source_id: groups[source_id] for source_id in [*metadata, *groups]
        if source_id in groups}
