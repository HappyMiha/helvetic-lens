"""Deterministic original HTML relationships, without changing extracted text."""

from urllib.parse import unquote

from bs4 import Tag

HTML_STRUCTURE_VERSION = 'html-structure/v2'
HTML_STRUCTURE_VERSIONS = {'html-structure/v1', HTML_STRUCTURE_VERSION}
_HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_BOUNDARIES = {'article', 'section', 'details'}
_CONTAINERS = {'dl', 'table', 'ul', 'ol', 'blockquote', 'pre', 'figure'}


def _text(node):
    return ' '.join(node.get_text(' ', strip=True).split())


def _addressed_prefix(node):
    """Recognize a leading emphasized, fragment-addressable block label."""
    first = next((text for text in node.find_all(string=True) if text.strip()), None)
    if first is None:
        return None
    emphasis = None
    for parent in first.parents:
        if parent is node:
            break
        if parent.name in {'b', 'strong'}:
            emphasis = parent
            break
    if emphasis is None:
        return None
    # Bold words alone are emphasis, not a new section. The original must also
    # make this leading label addressable, rather than an arbitrary later span.
    addressed = node.has_attr('id') or any(
        tag.has_attr('id') or tag.name == 'a' and tag.has_attr('name')
        for tag in [emphasis, *emphasis.find_all(True)])
    for parent in emphasis.parents:
        if parent is node:
            break
        addressed = addressed or parent.name == 'a' and (parent.has_attr('id') or parent.has_attr('name'))
    return emphasis if addressed else None


def annotate_passages(root, entries):
    """Attach source-local groups to the existing ordered (DOM node, passage) pairs.

    Group IDs describe this exact DOM, not source identity or semantic approval.
    A local heading region ends at the next heading in its explicit section.
    Ancestor regions are directional context, never shared membership that
    would merge siblings. Native containers retain all extracted members.
    Consumers must bind IDs to the original's current URL and content hash.
    """
    elements = [root, *(node for node in root.descendants if isinstance(node, Tag))]
    positions = {id(node): index for index, node in enumerate(elements, 1)}
    selected = {id(node): passage for node, passage in entries}
    addressed = {id(node): label for node, _ in entries if (label := _addressed_prefix(node)) is not None}
    states, regions, contexts = {}, {}, {}

    def ancestors(node):
        if node is root:
            return
        for parent in node.parents:
            if parent is root:
                break
            yield parent

    def boundary(node):
        return next((parent for parent in ancestors(node) if parent.name in _BOUNDARIES), root)

    def state(owner):
        return states.setdefault(id(owner), {'headings': [], 'inherited': [],
            'preamble': f's{positions[id(owner)]:05d}'})

    def inherited(value):
        return [*value['inherited'], value['preamble'], *(group for _, group in value['headings'])]

    for node in elements:
        owner = boundary(node)
        value = state(owner)
        if node is not root and node.name in _BOUNDARIES:
            # Capture the enclosing context at entry. Headings inside a nested
            # boundary cannot change the surrounding or a sibling's stack.
            state(node)['inherited'] = inherited(value)
        if node.name in _HEADINGS or id(node) in addressed:
            level = int(node.name[1]) if node.name in _HEADINGS else 7
            while value['headings'] and value['headings'][-1][0] >= level:
                value['headings'].pop()
            value['headings'].append((level, f'h{positions[id(node)]:05d}'))
        regions[id(node)] = value['headings'][-1][1] if value['headings'] else value['preamble']
        contexts[id(node)] = [group for group in inherited(value) if group != regions[id(node)]]

    navigation = {}
    for node, passage in entries:
        anchors = node.find_all('a', href=True)
        if node.name == 'a' and node.has_attr('href'):
            anchors = [node]
        fragments = [unquote(anchor['href'][1:]) for anchor in anchors
            if anchor['href'].startswith('#') and anchor['href'][1:]]
        is_navigation = (node.name not in _HEADINGS and anchors and len(fragments) == len(anchors)
            and _text(node) == ' '.join(_text(anchor) for anchor in anchors))
        label = addressed.get(id(node))
        title_only = label is not None and not any(character.isalnum()
            for character in _text(node)[len(_text(label)):])
        kind = 'heading' if node.name in _HEADINGS or title_only else 'navigation' if is_navigation else 'body'
        groups = []
        if is_navigation:
            groups.append(f'n{positions[id(node)]:05d}')
            navigation[id(node)] = fragments
        else:
            groups.append(regions[id(node)])
            containers = [node, *ancestors(node)]
            for container in containers:
                if container is not node and container.name in _BOUNDARIES:
                    break
                if container.name in _CONTAINERS:
                    groups.append(f'c{positions[id(container)]:05d}')
        passage['html_structure'] = {'version': HTML_STRUCTURE_VERSION, 'kind': kind,
            'group_ids': list(dict.fromkeys(groups)),
            'context_group_ids': list(dict.fromkeys(contexts[id(node)]))}

    body_groups = {group for _, passage in entries if passage['html_structure']['kind'] == 'body'
        for group in passage['html_structure']['group_ids']}
    targets = {}
    for node in elements:
        for key in (node.get('id'), node.get('name') if node.name == 'a' else None):
            if key:
                targets.setdefault(key, node)

    def target_groups(target):
        # Fragment IDs can belong to a heading, a wrapper, or an empty anchor
        # immediately before the addressed block. Resolve the DOM relationship;
        # never infer it from the wording of the link or passage.
        for node in [target, *ancestors(target)]:
            if id(node) in selected:
                return selected[id(node)]['html_structure']['group_ids']
        descendants = {id(node) for node in target.descendants if isinstance(node, Tag)}
        related = next((passage for node, passage in entries if id(node) in descendants), None)
        if related is None and not _text(target):
            related = next((passage for node, passage in entries
                if positions[id(node)] > positions[id(target)] and boundary(node) is boundary(target)), None)
        return related['html_structure']['group_ids'] if related else []

    for node, passage in entries:
        if id(node) not in navigation:
            continue
        groups = [group for fragment in navigation[id(node)] if fragment in targets
            for group in target_groups(targets[fragment]) if group in body_groups]
        passage['html_structure']['target_group_ids'] = list(dict.fromkeys(groups))
