"""Original HTML structure, independent of document subject and model output."""

from helvetic_lens.extraction import extract
from helvetic_lens.html_document_structure import HTML_STRUCTURE_VERSION


def paragraphs(body):
    return extract(body.encode(), 'text/html').passages


def members(passages, passage):
    groups = set(passage['html_structure']['group_ids'])
    return [item for item in passages if groups.intersection(item['html_structure']['group_ids'])]


def test_structure_preserves_existing_text_order_ids_and_is_deterministic():
    body = ('<main><h1>Instrument record</h1><p>Retain the complete original record.</p>'
        '<h2 id="limits">Conditions</h2><p>Use only within the stated temperature range.</p></main>')
    first, second = paragraphs(body), paragraphs(body)
    assert first == second
    assert [{key: item[key] for key in ('text', 'page', 'id')} for item in first] == [
        {'text': 'Instrument record', 'page': None, 'id': 'p00001'},
        {'text': 'Retain the complete original record.', 'page': None, 'id': 'p00002'},
        {'text': 'Conditions', 'page': None, 'id': 'p00003'},
        {'text': 'Use only within the stated temperature range.', 'page': None, 'id': 'p00004'}]
    assert all(item['html_structure']['version'] == HTML_STRUCTURE_VERSION for item in first)
    assert [item['id'] for item in members(first, first[2])] == ['p00003', 'p00004']


def test_definition_container_keeps_questions_short_labels_and_complete_answers():
    passages = paragraphs('<main><h2>Operating conditions</h2><dl>'
        '<dt>Q1:</dt><dd>When can the specimen be measured?</dd><dt>A1:</dt>'
        '<dd>Only after calibration under all conditions specified in the protocol.</dd>'
        '<dt>Q2:</dt><dd>Can an uncalibrated specimen be measured?</dd><dt>A2:</dt><dd>No.</dd>'
        '</dl><h2>Other records</h2><p>Keep the dated maintenance record separately.</p></main>')
    group = members(passages, passages[2])
    assert [item['id'] for item in group] == [f'p{number:05d}' for number in range(1, 10)]
    assert passages[3] in group and passages[4] in group and passages[8] in group
    assert passages[-1] not in group
    assert all(item['html_structure']['kind'] == 'body' for item in passages[1:9])


def test_fragment_navigation_resolves_body_groups_without_reclassifying_inline_links():
    passages = paragraphs('<main><h1>Manual</h1><ol>'
        '<li><a href="#calibration">Calibration</a></li>'
        '<li><a href="#records">Records</a></li></ol>'
        '<h2 id="calibration">Calibration</h2><p>Calibrate before each measurement.</p>'
        '<p>See <a href="#records">records</a> for the required dated log.</p>'
        '<a name="records"></a><h2>Records</h2><p>Retain the original dated log.</p></main>')
    nav, target, inline, records = passages[1], passages[3], passages[5], passages[6]
    assert nav['html_structure']['kind'] == 'navigation'
    assert nav['html_structure']['target_group_ids'] == target['html_structure']['group_ids']
    assert passages[2]['html_structure']['target_group_ids'] == records['html_structure']['group_ids']
    assert inline['html_structure']['kind'] == 'body'
    assert 'target_group_ids' not in inline['html_structure']
    assert nav not in members(passages, target)
    assert [item['id'] for item in members(passages, target)] == ['p00004', 'p00005', 'p00006']


def test_complete_table_container_has_no_row_or_character_cutoff():
    rows = ''.join(f'<tr><td>Region {i}</td><td>{i} units subject to the dated protocol.</td></tr>'
        for i in range(60))
    passages = paragraphs('<main><h2>Reported observations</h2><table><tr><th>Region</th><th>Value</th></tr>'
        f'{rows}</table><h2>Separate section</h2><p>No additional observations are asserted here.</p></main>')
    table = members(passages, passages[20])
    assert len(table) == 62  # heading, column headings and every original row
    assert passages[1] in table and passages[61] in table and passages[-1] not in table


def test_section_boundaries_and_unresolved_navigation_do_not_invent_targets():
    passages = paragraphs('<main><h1>Public record</h1><section><h2>Earlier report</h2>'
        '<p>The observation was reported in the earlier period.</p></section>'
        '<section><p>This later section has no heading and preserves its own text.</p>'
        '<p><a href="#missing">Missing section</a></p></section></main>')
    assert [item['id'] for item in members(passages, passages[1])] == ['p00002', 'p00003']
    assert [item['id'] for item in members(passages, passages[3])] == ['p00004']
    assert passages[-1]['html_structure']['kind'] == 'navigation'
    assert passages[-1]['html_structure']['target_group_ids'] == []


def test_addressed_emphasized_clause_keeps_its_conditions_and_continuation_without_whole_document():
    passages = paragraphs('<main><h1>Equipment agreement</h1><p>General introduction to this record.</p>'
        '<p><a href="#operation">Operating permission</a></p>'
        '<p><strong><a name="operation">Operating permission</a></strong>. '
        'The equipment may be operated only if the following conditions hold:</p>'
        '<ol><li>Maintain calibration before each use.</li><li>Retain the dated test record.</li></ol>'
        '<p>The operator may add a separate maintenance log.</p>'
        '<p><strong>Ordinary emphasis</strong> does not start a new addressable section.</p>'
        '<p><a id="warranty"><b>Warranty</b></a>. A separate warranty applies to the equipment.</p>'
        '<p>The warranty expires at the stated date.</p></main>')
    clause, warranty = passages[3], passages[8]
    assert clause['html_structure']['kind'] == warranty['html_structure']['kind'] == 'body'
    assert [item['id'] for item in members(passages, clause)] == [f'p{i:05d}' for i in range(4, 9)]
    assert [item['id'] for item in members(passages, warranty)] == ['p00009', 'p00010']
    assert passages[2]['html_structure']['target_group_ids'] == clause['html_structure']['group_ids']
    assert passages[0] not in members(passages, clause)
