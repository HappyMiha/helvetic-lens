"""Anonymous research readers and personal controls, never private dossier access."""
import asyncio
import hashlib
import json
import time
from pathlib import PurePath
from uuid import UUID, uuid4

from fastapi import File, Form, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, select

from . import jobs
from .config import DomainError
from .product_api import Product, fail, iso
from .product_community import (
    ContributionInput,
    changed,
    check_content,
    contribution,
    contribution_payload,
    participant,
    publication,
    replay,
)
from .product_contribution_extract import FORMATS, MAX_BYTES
from .product_investigation_api import Control
from .product_investigation_models import Investigation, InvestigationEvent
from .product_investigations import ACTIVE, enqueue, event
from .product_models import DossierEntry, PublicContribution
from .product_public_research import can_control, eligible, payload, public_identity, public_run, summary


class PublicUpload(ContributionInput):
    file_name: str
    sha256: str
    byte_size: int
    content_type: str


def routes(router, service, actor):
    root = "/public-dossiers/{publication_id}"

    @router.get(root + "/research")
    def listing(product: Product, publication_id: UUID, offset: int = Query(default=0, ge=0, le=100000)):
        with service.db.session(include_all_organizations=True) as session:
            row = publication(session, product, publication_id)
            query = select(Investigation).where(Investigation.publication_id == row.id, eligible())
            return {"items": [summary(session, run) for run in session.scalars(query.order_by(
                Investigation.created_at.desc(), Investigation.id).offset(offset).limit(20))],
                "total": session.scalar(select(func.count()).select_from(query.subquery())),
                "offset": offset, "page_size": 20, "publication_revision": row.revision,
                "living_research": row.living_research}

    @router.get(root + "/research/{identifier}")
    def read(product: Product, publication_id: UUID, identifier: UUID):
        with service.db.session(include_all_organizations=True) as session:
            return payload(session, public_run(session, publication(session, product, publication_id), str(identifier)))

    @router.get(root + "/research/{identifier}/workspace")
    def workspace(product: Product, publication_id: UUID, identifier: UUID, request: Request):
        identity = actor(request)
        with service.db.session(include_all_organizations=True) as session:
            row, _ = participant(session, identity, product, publication_id)
            run = public_run(session, row, str(identifier))
            public_identity(session, identity)
            return {"can_control": can_control(session, run, identity)}

    @router.post(root + "/research/{identifier}/control")
    def control(product: Product, publication_id: UUID, identifier: UUID, data: Control, request: Request):
        identity = actor(request)
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, _ = participant(session, identity, product, publication_id, write=True)
            run = public_run(session, row, str(identifier))
            public_identity(session, identity, lock=True)
            if not can_control(session, run, identity):
                fail("Only this question's author or a current dossier editor can control its research.", 403)
            if run.revision != data.expected_revision:
                fail("Research changed. Refresh before applying this action.", 409)
            if data.action in {"resume", "retry"}:
                if data.action == "retry":
                    from .product_contributions import retry

                    retry(session, run)
                elif run.status != "paused":
                    fail("Only paused research can resume.", 409)
                run.generation += 1
                run.actor_user_id, run.session_id = identity.user_id, identity.session_id
                run.session_organization_id = identity.organization_id
                run.status, run.stop_reason = "queued", ""
                # The public participant retains their native login workspace;
                # enqueue the existing job explicitly in the host dossier scope.
                enqueue(session, run)
            else:
                if run.status not in ACTIVE | {"paused"}:
                    fail("This investigation has already finished.", 409)
                if run.job_id:
                    jobs.cancel(session, run.job_id)
                run.generation += 1
                run.status = "paused" if data.action == "pause" else "cancelled"
                run.stop_reason = "Paused by a public research participant." if data.action == "pause" else "Cancelled; existing public evidence is retained."
            event(session, run, "investigation_" + data.action, status=run.status)
            session.commit()
            return payload(session, run)

    @router.get(root + "/research/{identifier}/events")
    async def events(product: Product, publication_id: UUID, identifier: UUID, request: Request,
                     after: int = Query(default=0, ge=0), wait: int = Query(default=40, ge=0, le=40)):
        header = request.headers.get("last-event-id", "")
        if header.isdecimal() and len(header) <= 12:
            after = max(after, int(header))
        with service.db.session(include_all_organizations=True) as session:
            public_run(session, publication(session, product, publication_id), str(identifier))

        async def stream():
            cursor, deadline = after, time.monotonic() + wait
            while not await request.is_disconnected():
                try:
                    with service.db.session(include_all_organizations=True) as session:
                        run = public_run(session, publication(session, product, publication_id), str(identifier))
                        messages = [{"sequence": e.sequence, "kind": e.kind, "detail": e.detail,
                            "created_at": iso(e.created_at)} for e in session.scalars(select(InvestigationEvent)
                            .where(InvestigationEvent.investigation_id == run.id, InvestigationEvent.sequence > cursor)
                            .order_by(InvestigationEvent.sequence).limit(250))]
                        running = run.status in ACTIVE
                except DomainError:
                    yield 'event: access_changed\ndata: {}\n\n'
                    return
                for message in messages:
                    cursor = message["sequence"]
                    yield f'id: {cursor}\nevent: activity\ndata: {json.dumps(message, ensure_ascii=False)}\n\n'
                if not running or time.monotonic() >= deadline:
                    yield 'event: checkpoint\ndata: {}\n\n'
                    return
                yield ': heartbeat\n\n'
                await asyncio.sleep(2)

        return StreamingResponse(stream(), media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

    @router.post(root + "/files", status_code=201)
    async def upload(product: Product, publication_id: UUID, request: Request,
                     metadata: str = Form(..., max_length=20000), file: UploadFile = File(...)):
        identity = actor(request)
        try:
            data = ContributionInput.model_validate_json(metadata)
        except ValidationError:
            fail("The public upload metadata is invalid. Review the contribution and try again.")
        with service.db.session(include_all_organizations=True) as session:
            row, _ = participant(session, identity, product, publication_id)
            public_identity(session, identity)
            check_content(row, data)
            if not row.living_research or data.kind != "file":
                fail("Public originals require an explicitly enabled living dossier.", 409)
        body = await file.read(MAX_BYTES + 1)
        await file.close()
        name = PurePath((file.filename or "attachment").replace("\\", "/")).name
        name = "".join(c for c in name if ord(c) >= 32)[:200]
        media = (file.content_type or "application/octet-stream").split(";")[0].lower().strip()
        suffix = PurePath(name).suffix.lower()
        if not body or len(body) > MAX_BYTES:
            fail("Choose a non-empty public document of at most 100 MB.", 413)
        if suffix not in FORMATS or media not in FORMATS[suffix] | {"application/octet-stream"}:
            fail("Public files support TXT, Markdown, CSV, HTML, PDF, DOCX, XLSX, PPTX and EML with matching content types.")
        if suffix == ".pdf":
            if not body.startswith(b"%PDF"):
                fail("This file does not contain a PDF document.")
        else:
            try:
                text = body.decode("utf-8-sig")
            except UnicodeError:
                fail("Use a UTF-8 text document.")
            if any(ord(c) < 32 and c not in "\r\n\t" for c in text):
                fail("Unsupported binary content in a text document.")
        upload_data = PublicUpload(**data.model_dump(), file_name=name, sha256=hashlib.sha256(body).hexdigest(),
                                  byte_size=len(body), content_type=media)
        folder = service.environment_settings.storage_path / "artifacts"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"public-contribution-{uuid4().hex}.bin"
        with service.write_guard, service.db.session(include_all_organizations=True) as session:
            row, moderator = participant(session, identity, product, publication_id, write=True)
            public_identity(session, identity, lock=True)
            old, fingerprint = replay(session, row, identity, upload_data, "upload")
            if old:
                return {"contribution": contribution_payload(session, contribution(session, row, old.contribution_id), identity.user_id, moderator)}
            check_content(row, data)
            if not row.living_research:
                fail("Living research is no longer enabled.", 409)
            count = session.scalar(select(func.count()).select_from(PublicContribution).where(
                PublicContribution.publication_id == row.id, PublicContribution.artifact_key != ""))
            total = sum(session.scalar(select(func.coalesce(func.sum(table.byte_size), 0)).where(
                table.organization_id == row.organization_id)) for table in (DossierEntry, PublicContribution))
            if count >= 50 or total + len(body) > 500 * 1024 * 1024:
                fail("This dossier or workspace has reached its attachment storage limit.", 413)
            item = PublicContribution(organization_id=row.organization_id, publication_id=row.id,
                author_user_id=identity.user_id, publication_revision=row.revision, revision=1,
                author_label=data.content.author_label, body=data.content.body,
                sources_json=[s.model_dump() for s in data.content.sources], kind="file", artifact_key=path.name,
                file_name=name, byte_size=len(body), sha256=upload_data.sha256, content_type=media)
            try:
                path.write_bytes(body)
                session.add(item)
                return changed(session, item, identity, upload_data, "upload", fingerprint, moderator)
            except Exception:
                path.unlink(missing_ok=True)
                raise

    @router.get(root + "/files/{identifier}")
    def download(product: Product, publication_id: UUID, identifier: UUID):
        from .models import User

        with service.db.session(include_all_organizations=True) as session:
            row = publication(session, product, publication_id)
            item = session.scalar(select(PublicContribution).join(User, User.id == PublicContribution.author_user_id)
                .where(PublicContribution.id == str(identifier), PublicContribution.publication_id == row.id,
                    PublicContribution.publication_revision == row.revision, PublicContribution.status == "visible",
                    PublicContribution.kind == "file", User.active.is_(True), User.email_verified_at.is_not(None)))
            if not row.living_research or not item or not item.artifact_key:
                fail("This public original is not available.", 404)
            folder = service.environment_settings.storage_path / "artifacts"
            path = folder / item.artifact_key
            if path.parent != folder or not path.is_file():
                fail("The original is temporarily unavailable.", 503)
            body = path.read_bytes()
            if len(body) != item.byte_size or hashlib.sha256(body).hexdigest() != item.sha256:
                fail("The original failed its integrity check.", 503)
            # Small bounded originals are read inside the permission transaction.
            # A safe fixed ASCII filename avoids header injection and inline HTML.
            return Response(body, media_type="application/octet-stream", headers={
                "Content-Disposition": f'attachment; filename="source{PurePath(item.file_name).suffix.lower()}"',
                "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": "sandbox; default-src 'none'"})
