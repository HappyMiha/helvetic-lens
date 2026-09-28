"""Versioned application-owned research guidance; never source or AI findings."""
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from pydantic import Field

from .config import DomainError
from .legal_profiles import Input

SCHEMA = 'dossier-template/v1'


class TemplateReference(Input):
    id: str = Field(min_length=1, max_length=80)
    version: str = Field(min_length=1, max_length=40)


@dataclass(frozen=True)
class DossierTemplate:
    id: str
    domain: Literal['LEGAL', 'PHARMA']
    title: str
    description: str
    sector: str
    goal: str
    context_fields: tuple[str, ...]
    questions: tuple[str, ...]
    version: str = '1.0.0'


_DEFINITIONS = (
    DossierTemplate('legal-question', 'LEGAL', 'Legal Question',
        'Organise a legal question, its circumstances and supporting authorities.', 'Legal research',
        'What rules and source versions may apply to this question, and what remains uncertain?',
        ('jurisdictions', 'legal_areas', 'parties', 'laws'),
        ('Which jurisdiction and date are relevant?', 'Which primary sources support or contradict the interpretation?',
         'What facts or documents still need human review?')),
    DossierTemplate('legislative-monitor', 'LEGAL', 'Legislative Monitor',
        'Follow an area of law while retaining versions and effective dates.', 'Legislative monitoring',
        'Which legislative developments may affect our scope, and when could they apply?',
        ('jurisdictions', 'legal_areas', 'authorities', 'laws', 'relevant_dates'),
        ('Is this a proposal, adopted text or effective rule?', 'Which exact version and effective dates are recorded?',
         'Which sources were checked, and which remain unavailable?')),
    DossierTemplate('case-dispute', 'LEGAL', 'Case / Dispute',
        'Keep the parties, procedure, source evidence and competing positions distinct.', 'Case research',
        'What evidence and authorities are relevant to this case, and what needs further investigation?',
        ('jurisdictions', 'parties', 'courts', 'case_ids', 'procedural_stage', 'relevant_dates'),
        ('What is a documented fact, a party argument or an interpretation?', 'Which procedure and deadlines need verification?',
         'Which evidence supports or challenges each position?')),
    DossierTemplate('market-access', 'PHARMA', 'Market Access',
        'Frame market access research around a product, indication and market.', 'Pharmaceuticals · Market access',
        'What authorisation, reimbursement and clinical evidence is relevant to this product in the selected market?',
        ('product_names', 'active_substances', 'indications', 'countries', 'regulatory_ids', 'market_access_ids', 'competitors'),
        ('Which exact product, indication and market does each source concern?',
         'What do the original authorisation and reimbursement sources state?',
         'Which source gaps, conflicting evidence or interpretations require review?')),
    DossierTemplate('regulatory-monitor', 'PHARMA', 'Regulatory Monitor',
        'Track product-related regulatory documents and changes in their original context.', 'Pharmaceuticals · Regulation',
        'What regulatory document changes may matter for this product and market?',
        ('product_names', 'active_substances', 'countries', 'regulatory_ids', 'company_names'),
        ('Which product and territory are covered by the source?', 'What changed between the retained document versions?',
         'What is a source statement and what is our interpretation?')),
    DossierTemplate('safety', 'PHARMA', 'Safety',
        'Organise safety communications and evidence for human assessment.', 'Pharmaceuticals · Pharmacovigilance',
        'Which safety communications and evidence updates need review for this medicine?',
        ('product_names', 'active_substances', 'indications', 'countries', 'trial_ids'),
        ('Which population, product and indication does the evidence concern?',
         'Is the item an official communication, a study finding or an unconfirmed signal?',
         'Which uncertainties and source gaps require professional review?')),
)
TEMPLATES = MappingProxyType({item.id: item for item in _DEFINITIONS})


def available(domain):
    return [item for item in TEMPLATES.values() if item.domain == domain]


def snapshot(product, reference):
    from .domain_packs import for_product
    from .product_domain_context import FIELDS

    pack = for_product(product)
    item = TEMPLATES.get(reference.id)
    if not item or item.domain != pack.domain or item.version != reference.version:
        raise DomainError('This template or version is unavailable for this dossier. Reload the template list.',
                          422, 'dossier_template_unavailable')
    labels = {field.key: field.label for field in FIELDS[pack.context_schema_id]}
    return {'schema_id': SCHEMA, 'id': item.id, 'version': item.version, 'domain': item.domain,
            'pack_id': pack.id, 'pack_version': pack.version, 'context_schema_id': pack.context_schema_id,
            'title': item.title, 'description': item.description, 'sector': item.sector, 'goal': item.goal,
            'context_fields': [{'key': key, 'label': labels[key]} for key in item.context_fields],
            'questions': list(item.questions)}


def supported(saved):
    return (isinstance(saved, dict) and saved.get('schema_id') == SCHEMA
            and all(isinstance(saved.get(key), str) for key in
                    ('id', 'version', 'domain', 'pack_id', 'pack_version', 'title', 'description', 'sector', 'goal'))
            and isinstance(saved.get('questions'), list) and all(isinstance(q, str) for q in saved['questions'])
            and isinstance(saved.get('context_fields'), list)
            and all(isinstance(f, dict) and isinstance(f.get('key'), str) and isinstance(f.get('label'), str)
                    for f in saved['context_fields']))


def payload(row):
    saved = row.template_json or {}
    return {'available': supported(saved), 'selection': saved if supported(saved) else None,
            'saved': bool(saved)}
