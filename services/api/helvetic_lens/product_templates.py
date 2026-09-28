"""Explicit template selection over the existing contained dossier and audit."""
from uuid import UUID

from fastapi import Request
from pydantic import Field
from sqlalchemy import select

from . import dossier_templates
from .db import utcnow
from .domain_packs import for_product
from .legal_profiles import Input
from .product_access import require
from .product_api import Product, dossier, fail, iso
from .product_models import DossierEntry
from .product_operations import audit, fingerprint, require_revision


class TemplateInput(Input):
    expected_revision: int = Field(ge=1, strict=True)
    request_key: UUID
    template: dossier_templates.TemplateReference | None


def record(session, row, user_id, selection, key, signature=None):
    before = row.template_json or {}
    row.template_json = {**selection, 'selected_at': iso(utcnow())} if selection else {}
    audit(session, row, user_id, 'dossier_template', 'Dossier template selected' if selection else 'Dossier template cleared',
          'Research guidance changed by a person; evidence, source choices and monitoring remain unchanged.',
          {'request_fingerprint': signature, 'revision': row.revision,
           'template_before': before, 'template_after': row.template_json}, key)


def check_creation_replay(session, row, reference):
    if reference is None:
        return  # Preserve the historical no-template retry contract.
    entry = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                                                      DossierEntry.request_key == 'dossier_template:creation'))
    original = entry.data_json.get('template_after', {}) if entry else {}
    if original.get('id') != reference.id or original.get('version') != reference.version:
        fail('This creation key already belongs to a different template choice. Reopen the saved dossier to change its template.', 409, 'product_revision_conflict')


def routes(router, service, actor):
    @router.get('/templates')
    def catalogue(product: Product, request: Request):
        actor(request)
        pack = for_product(product)
        return {'domain': pack.domain, 'items': [dossier_templates.snapshot(product,
            dossier_templates.TemplateReference(id=item.id, version=item.version))
            for item in dossier_templates.available(pack.domain)]}

    @router.put('/dossiers/{identifier}/template')
    def choose(product: Product, identifier: str, data: TemplateInput, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session() as session:
            row, profile = dossier(session, product, identifier, identity.user_id)
            require(session, row, profile, identity.user_id, 'edit')
            signature = fingerprint(data.model_dump(mode='json', exclude={'request_key'}))
            key = 'dossier_template:' + str(data.request_key)
            prior = session.scalar(select(DossierEntry).where(DossierEntry.dossier_id == row.id,
                                                              DossierEntry.request_key == key))
            if prior:
                if prior.actor_user_id != identity.user_id or prior.data_json.get('request_fingerprint') != signature:
                    fail('This template request was already used for another change.', 409, 'product_revision_conflict')
                return dossier_templates.payload(row)
            require_revision(row, data.expected_revision)
            if row.template_json and not dossier_templates.supported(row.template_json):
                fail('This saved template uses an unavailable format. Its original data is retained in your private export.',
                     409, 'dossier_template_unavailable')
            selection = dossier_templates.snapshot(product, data.template) if data.template else {}
            row.revision += 1
            record(session, row, identity.user_id, selection, key, signature)
            session.commit()
            return dossier_templates.payload(row)
