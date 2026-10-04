"""Derive HTML structure from retained originals without changing capture history."""
import asyncio
import hashlib
import re
from copy import deepcopy
from pathlib import Path

from sqlalchemy import select

from .config import DomainError
from .html_document_structure import HTML_STRUCTURE_VERSION


def retained_originals(session, run_id, sources):
    """Resolve current captures, including exact eligible recalled-origin bytes."""
    from .product_investigation_models import Investigation, InvestigationBranch, InvestigationSource
    from .research_knowledge import eligible_sources, origin_pin

    run = session.get(Investigation, run_id)
    if run is None:
        return []
    expected = {source['id']: source for source in sources}
    rows = {source.id: source for source in session.scalars(select(InvestigationSource).where(
        InvestigationSource.investigation_id == run.id,
        InvestigationSource.organization_id == run.organization_id,
        InvestigationSource.dossier_id == run.dossier_id,
        InvestigationSource.id.in_(expected)))}
    pins = {source.id: source.snapshot.get('retained_origin') for source in rows.values()}
    origin_ids = {pin['source_id'] for pin in pins.values() if isinstance(pin, dict)
        and isinstance(pin.get('source_id'), str) and pin['source_id']}
    allowed = {source.id: source for source in session.scalars(eligible_sources(run).where(
        InvestigationSource.id.in_(origin_ids)))} if origin_ids else {}
    captures, run_ids = {}, set()
    for source in rows.values():
        view = expected[source.id]
        if source.sha256 != view.get('sha256') or source.url != view.get('url'):
            continue
        basis, pin = source, pins[source.id]
        if pin is not None:
            basis = allowed.get(pin.get('source_id')) if isinstance(pin, dict) and isinstance(pin.get('source_id'), str) else None
            if (basis is None or source.kind != 'public_source' or source.snapshot.get('allow_discovery') is False
                    or pin != origin_pin(basis) or basis.sha256 != source.sha256 or basis.url != source.url
                    or basis.snapshot.get('excerpts') != source.snapshot.get('excerpts')):
                continue
        captures.setdefault(basis.id, []).append((basis, source))
        run_ids.add(basis.investigation_id)
    result, seen = [], set()
    for branch in session.scalars(select(InvestigationBranch).where(
            InvestigationBranch.investigation_id.in_(run_ids),
            InvestigationBranch.organization_id == run.organization_id,
            InvestigationBranch.dossier_id == run.dossier_id)):
        for document in branch.checkpoint.get('document_reads', {}).values():
            original = document.get('retained_document', {})
            if original.get('content_type', '').split(';')[0].strip() not in {'text/html', 'application/xhtml+xml'}:
                continue
            for identifier in document.get('source_ids', []):
                if not isinstance(identifier, str):
                    continue
                for basis, source in captures.get(identifier, []):
                    if (source.id in seen or basis.investigation_id != branch.investigation_id
                            or original.get('sha256') != source.sha256 or document.get('sha256') != source.sha256
                            or original.get('url') != source.url or not original.get('artifact_key')):
                        continue
                    seen.add(source.id)
                    result.append({'source_id': source.id, 'sha256': source.sha256,
                        'artifact_key': original['artifact_key'], 'excerpts': deepcopy(source.snapshot.get('excerpts', []))})
    return result


def annotate_retained(folder, sources, originals):
    """Attach structure only when every retained passage binds to the same bytes."""
    from .extraction import extract
    from .product_contribution_extract import MAX_BYTES

    folder = Path(folder).resolve()
    sources = {source['id']: source for source in sources}
    parsed, annotated = {}, []
    for original in originals:
        source = sources.get(original['source_id'])
        if source is None or source.get('sha256') != original['sha256']:
            continue
        key = original['artifact_key']
        if not isinstance(key, str) or Path(key).name != key:
            continue
        path = folder / key
        if not path.is_file() or path.resolve().parent != folder:
            continue
        identity = (key, original['sha256'])
        if identity not in parsed:
            try:
                with path.open('rb') as stream:
                    body = stream.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES or hashlib.sha256(body).hexdigest() != original['sha256']:
                    continue
                parsed[identity] = {p['id']: p for p in extract(body, 'text/html', 'retained.html').passages}
            except (OSError, ValueError, DomainError):
                continue
        passages, metadata, exact = parsed[identity], {}, {}
        for excerpt in original['excerpts']:
            match = re.fullmatch(r'(p(\d+))-block-(\d+)-char-(\d+)', excerpt.get('passage', ''))
            passage = passages.get(match[1]) if match else None
            if (not match or int(match[2]) != int(match[3]) or passage is None
                    or passage['text'][int(match[4]) - 1:int(match[4]) - 1 + len(excerpt['text'])] != excerpt['text']):
                metadata = {}
                break
            exact[excerpt['passage']] = excerpt['text']
            if isinstance(passage.get('html_structure'), dict):
                metadata[excerpt['passage']] = passage['html_structure']
        if not metadata:
            continue
        # EvidenceWire may split a stored passage into overlapping canonical
        # windows. Metadata cannot authorize new source text or different IDs.
        if any(p.get('passage') not in exact or p.get('text', '') not in exact[p['passage']]
                for p in source.get('excerpts', [])):
            continue
        for passage in source.get('excerpts', []):
            if passage['passage'] in metadata:
                passage['html_structure'] = deepcopy(metadata[passage['passage']])
        annotated.append(source['id'])
    return annotated


async def enrich(service, wire):
    """A private derived view; native retrieval rechecks rights before dispatch."""
    if getattr(service, 'db', None) is None or not wire.work.get('run_id'):
        return
    sources = wire.input.get('sources', [])
    missing = [source for source in sources if source.get('excerpts')
        and any(not isinstance(p.get('html_structure'), dict)
            or p['html_structure'].get('version') != HTML_STRUCTURE_VERSION for p in source['excerpts'])]
    if not missing:
        return

    def derive():
        with service.db.session() as session:
            originals = retained_originals(session, wire.work['run_id'], missing)
        settings = getattr(service, 'environment_settings', service.settings)
        return annotate_retained(settings.storage_path / 'artifacts', missing, originals)

    annotated = await asyncio.to_thread(derive)
    from .product_operations import fingerprint
    wire.receipt['input_fingerprint'] = fingerprint(wire.input)
    wire.receipt['retained_html_structure'] = {'derived_sources': len(annotated),
        'capture_history_changed': False, 'scope': 'Structure from exact retained original bytes; not factual verification.'}
