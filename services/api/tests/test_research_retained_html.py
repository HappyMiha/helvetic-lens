"""Saved originals gain structural context without rewriting capture history."""
import hashlib
from copy import deepcopy

import pytest
from test_research_original_context import wire_for

from helvetic_lens.product_contribution_extract import parse
from helvetic_lens.research_html_structure import annotate_retained
from helvetic_lens.research_original_context import provider_excerpts, reference_units

HTML = b'''<main><h1>Archive terms</h1><ol><li><a href="#renewal">Renewal requirements</a></li></ol>
<h2 id="renewal">Renewal requirements</h2><dl><dt>Question:</dt><dd>May the archive be renewed without approval?</dd>
<dt>Answer:</dt><dd>No.</dd><dd>Renewal requires written permission from the original owner.</dd></dl>
<h2>Office hours</h2><p>The archive office opens each weekday morning.</p></main>'''


def capture(tmp_path):
    digest = hashlib.sha256(HTML).hexdigest()
    path = tmp_path / 'retained.original'
    path.write_bytes(HTML)
    excerpts = parse(HTML, 'archive.html', 'text/html', cursor={'page': 0, 'offset': 0})['excerpts']
    legacy = [{key: value for key, value in passage.items() if key != 'html_structure'} for passage in excerpts]
    source = {'id': 'source-one', 'url': 'https://example.test/archive', 'sha256': digest,
        'title': 'Archive terms', 'excerpts': legacy}
    origin = {'source_id': source['id'], 'sha256': digest, 'artifact_key': path.name, 'excerpts': deepcopy(legacy)}
    return source, origin, path


def test_new_html_capture_preserves_toc_body_and_short_answer_through_real_wire(tmp_path):
    source, _origin, _path = capture(tmp_path)
    source['excerpts'] = parse(HTML, 'archive.html', 'text/html', cursor={'page': 0, 'offset': 0})['excerpts']
    before = deepcopy(source)
    wire = wire_for([source])
    units = reference_units(wire)
    nav = next(p['citation_ref'] for p in wire.input['sources'][0]['excerpts']
        if p.get('html_structure', {}).get('kind') == 'navigation')
    body = next(unit for unit in units if nav in unit.get('ranking_refs', []))
    packet = provider_excerpts(wire, body['references'])['source-one']
    assert any(p['text'] == 'No.' for p in packet)
    assert any(p['text'] == 'Answer:' for p in packet)
    assert any('written permission' in p['text'] for p in packet)
    assert nav not in body['references']
    assert not any('weekday' in p['text'] for p in packet)
    assert source == before


def test_legacy_capture_uses_verified_bytes_without_new_text_ids_or_snapshot_changes(tmp_path):
    source, origin, path = capture(tmp_path)
    before = deepcopy(source), deepcopy(origin), path.read_bytes()
    wire = wire_for([source])
    refs = deepcopy(wire.references)
    assert annotate_retained(tmp_path, wire.input['sources'], [origin]) == ['source-one']
    assert wire.references == refs
    assert (source, origin, path.read_bytes()) == before
    body = next(unit for unit in reference_units(wire) if any('written permission' in ref['quote']
        for ref in unit['references'].values()) and unit.get('ranking_refs'))
    packet = provider_excerpts(wire, body['references'])['source-one']
    assert any(p['text'] == 'No.' for p in packet)
    assert any('without approval?' in p['text'] for p in packet)


@pytest.mark.parametrize('changed', ['bytes', 'sha', 'quote', 'locator', 'path', 'outside_symlink'])
def test_legacy_structure_cannot_bind_changed_or_unowned_material(tmp_path, changed):
    folder = tmp_path / 'artifacts'
    folder.mkdir()
    source, origin, path = capture(folder)
    if changed == 'bytes':
        path.write_bytes(HTML + b' altered')
    elif changed == 'sha':
        source['sha256'] = 'b' * 64
    elif changed == 'quote':
        origin['excerpts'][0]['text'] = 'A fabricated original text'
    elif changed == 'locator':
        origin['excerpts'][0]['passage'] = 'p00001-block-2-char-1'
    elif changed == 'path':
        origin['artifact_key'] = '../retained.original'
    else:
        outside = tmp_path / 'other.original'
        outside.write_bytes(HTML)
        path.unlink()
        path.symlink_to(outside)
    wire = wire_for([source])
    before = deepcopy(wire.input)
    assert annotate_retained(folder, wire.input['sources'], [origin]) == []
    assert wire.input == before
