import asyncio
import re
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from .auth import CSRF_COOKIE, SESSION_COOKIE, AuthService, RateLimiter
from .config import DomainError, Settings
from .model_settings import ApertusSettingsInput
from .models import DocumentWatch, Law, Profile, Scan, Source, Version
from .prompt_settings import PromptSettingsInput
from .service import HelveticLens, as_dict, get, version_summary


class Input(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class PreviewInput(Input):
    url: str = Field(min_length=8, max_length=3000)
    provider: Literal["native", "firecrawl"] = "native"


class SourceInput(PreviewInput):
    name: str = Field(default="", max_length=250)
    section: str = Field(default="/", max_length=1000)


class LawInput(PreviewInput):
    name: str = Field(default="", max_length=300)
    source_id: str | None = None
    synthetic: bool = False


class LawUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=300)
    active: bool | None = None


class CompareInput(Input):
    old_version_id: str
    new_version_id: str


class IdentityDecisionInput(Input):
    note: str = Field(default="", max_length=1000)


class ScanInput(Input):
    law_ids: list[str] | None = Field(default=None, max_length=25)
    baseline_version_id: str | None = None


class HistoryQuestion(Input):
    question: str = Field(min_length=1, max_length=2000)


class QuestionInput(HistoryQuestion):
    history: list[HistoryQuestion] = Field(default_factory=list, max_length=4)


class ProfileInput(Input):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=6000)
    business_areas: list[str] = Field(default_factory=list, max_length=12)


class ModelLicenseInput(Input):
    accepted: bool


class RegisterInput(Input):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=1024)
    name: str = Field(min_length=1, max_length=200)
    organization_name: str = Field(default="", max_length=200)
    invitation_token: str = Field(default="", max_length=200)


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class InvitationInput(Input):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["organization_admin", "viewer"] = "viewer"


class InvitationAcceptInput(Input):
    token: str = Field(min_length=20, max_length=200)


class MemberRoleInput(Input):
    role: Literal["organization_admin", "viewer"]


class OrganizationSwitchInput(Input):
    organization_id: str


class HandoverInput(Input):
    membership_id: str


def _rate_policy(path: str, method: str) -> tuple[str, int, int] | None:
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if path in {"/api/auth/register", "/api/auth/login"}:
        return None  # These use an email-and-address key inside their handlers.
    if path == "/api/preview" or (path.startswith("/api/sources/") and path.endswith("/discover")):
        return "fetch", 30, 300
    if path == "/api/laws" or (path.startswith("/api/laws/") and path.endswith("/import")):
        return "fetch", 30, 300
    if path == "/api/scans":
        return "scan", 20, 300
    if path.endswith("/ask") or path.endswith("/ask-jobs"):
        return "ai", 30, 300
    if path.endswith("/analyse") or path.endswith("/analyse-jobs"):
        return "ai", 20, 300
    if "/invitations" in path:
        return "invitation", 20, 3600
    return None


def create_app(
    settings: Settings | None = None,
    fetcher=None,
    model_client=None,
    *,
    organization_id: str | None = None,
    organization_name: str = "Legacy workspace",
) -> FastAPI:
    settings = settings or Settings()
    service = HelveticLens(
        settings,
        fetcher,
        model_client,
        organization_id=organization_id or "00000000-0000-0000-0000-000000000001",
        organization_name=organization_name,
    )
    auth = AuthService(service.db, settings)
    limiter = RateLimiter(settings)

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(service.initialize)
        yield
        service.db.engine.dispose()

    app = FastAPI(title="Helvetic Lens", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
        allow_credentials=True,
    )

    @app.exception_handler(DomainError)
    async def domain_error(_request, error: DomainError):
        return JSONResponse(status_code=error.status, content={"detail": error.message, "code": error.code})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, error: RequestValidationError):
        # Validation errors must not echo credential inputs back to the browser.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
                    for item in error.errors()
                ],
                "code": "invalid_input",
            },
        )

    @app.middleware("http")
    async def bounded_requests(request, call_next):
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > settings.max_document_bytes + 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={"detail": "The request exceeds the upload limit.", "code": "request_too_large"},
            )
        path = request.url.path
        session_token = request.cookies.get(SESSION_COOKIE, "")
        identity = await asyncio.to_thread(auth.resolve, session_token) if session_token else None
        request.state.identity = identity
        public_path = path in {"/api/health", "/api/auth/register", "/api/auth/login", "/api/auth/session"}
        public_path = public_path or path in {"/docs", "/openapi.json", "/redoc"}
        if path.startswith("/api/") and not public_path and not identity and not settings.allow_anonymous_dev:
            return JSONResponse(
                status_code=401,
                content={"detail": "Sign in to continue.", "code": "authentication_required"},
            )
        if (
            identity
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and path
            not in {
                "/api/auth/register",
                "/api/auth/login",
            }
        ):
            try:
                auth.verify_csrf(
                    identity,
                    request.cookies.get(CSRF_COOKIE, ""),
                    request.headers.get("x-csrf-token", ""),
                )
            except DomainError as error:
                return JSONResponse(
                    status_code=error.status,
                    content={"detail": error.message, "code": error.code},
                )
        viewer_allowed_mutations = {
            "/api/auth/logout",
            "/api/invitations/accept",
            "/api/auth/session/organization",
        }
        if (
            identity
            and identity.role == "viewer"
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and path not in viewer_allowed_mutations
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "This workspace is read-only for your account.",
                    "code": "viewer_read_only",
                },
            )
        if (
            identity
            and path.startswith("/api/admin/")
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and not identity.platform_admin
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "A platform administrator must perform this action.",
                    "code": "platform_admin_required",
                },
            )
        client = request.client.host if request.client else "unknown"
        rate = _rate_policy(path, request.method)
        if rate:
            try:
                await asyncio.to_thread(
                    limiter.check,
                    rate[0],
                    f"{identity.user_id if identity else client}:{path}",
                    limit=rate[1],
                    window_seconds=rate[2],
                )
            except DomainError as error:
                return JSONResponse(
                    status_code=error.status,
                    content={"detail": error.message, "code": error.code},
                )
        organization_id = identity.organization_id if identity else service.default_organization_id
        with service.db.organization_context(organization_id), service.organization_runtime():
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def set_auth_cookies(response: JSONResponse, session_token: str, csrf_token: str):
        max_age = settings.session_ttl_days * 86400
        response.set_cookie(
            SESSION_COOKIE,
            session_token,
            max_age=max_age,
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
            path="/",
        )
        response.set_cookie(
            CSRF_COOKIE,
            csrf_token,
            max_age=max_age,
            secure=settings.session_cookie_secure,
            httponly=False,
            samesite="lax",
            path="/",
        )

    @app.post("/api/auth/register", status_code=201)
    async def register(data: RegisterInput, request: Request):
        subject = (request.client.host if request.client else "unknown") + ":" + data.email.casefold()
        await asyncio.to_thread(limiter.check, "registration", subject, limit=5, window_seconds=3600)
        identity, session_token, csrf_token = await asyncio.to_thread(
            auth.register,
            email=data.email,
            password=data.password,
            name=data.name,
            organization_name=data.organization_name,
            invitation_token=data.invitation_token,
        )
        with service.db.organization_context(identity.organization_id), service.db.session() as session:
            onboarding_required = not bool(session.scalar(select(DocumentWatch.id).limit(1)))
        response = JSONResponse(
            status_code=201,
            content={**identity.public(), "onboarding_required": onboarding_required},
        )
        set_auth_cookies(response, session_token, csrf_token)
        return response

    @app.post("/api/auth/login")
    async def login(data: LoginInput, request: Request):
        subject = (request.client.host if request.client else "unknown") + ":" + data.email.casefold()
        await asyncio.to_thread(limiter.check, "login", subject, limit=10, window_seconds=900)
        identity, session_token, csrf_token = await asyncio.to_thread(
            auth.login, email=data.email, password=data.password
        )
        with service.db.organization_context(identity.organization_id), service.db.session() as session:
            onboarding_required = not bool(session.scalar(select(DocumentWatch.id).limit(1)))
        response = JSONResponse(content={**identity.public(), "onboarding_required": onboarding_required})
        set_auth_cookies(response, session_token, csrf_token)
        return response

    @app.get("/api/auth/session")
    def auth_session(request: Request):
        identity = request.state.identity
        if identity is None:
            return {
                "authenticated": False,
                "anonymous_development": settings.allow_anonymous_dev,
                "authentication_required": not settings.allow_anonymous_dev,
            }
        with service.db.session() as session:
            onboarding_required = not bool(session.scalar(select(DocumentWatch.id).limit(1)))
        return {
            **identity.public(),
            "organizations": auth.organizations(identity),
            "onboarding_required": onboarding_required,
        }

    @app.post("/api/auth/session/organization")
    def switch_organization(data: OrganizationSwitchInput, request: Request):
        identity = auth.switch_organization(request.state.identity, data.organization_id)
        return {**identity.public(), "organizations": auth.organizations(identity)}

    @app.post("/api/auth/logout")
    def logout(request: Request):
        identity = request.state.identity
        if identity:
            auth.logout(identity)
        response = JSONResponse(content={"authenticated": False})
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    @app.get("/api/organization/members")
    def organization_members(request: Request):
        return auth.members(request.state.identity)

    @app.get("/api/organization/invitations")
    def organization_invitations(request: Request):
        return auth.list_invitations(request.state.identity)

    @app.post("/api/organization/invitations", status_code=201)
    def create_organization_invitation(data: InvitationInput, request: Request):
        return auth.create_invitation(request.state.identity, email=data.email, role=data.role)

    @app.delete("/api/organization/invitations/{invitation_id}")
    def revoke_organization_invitation(invitation_id: str, request: Request):
        return auth.revoke_invitation(request.state.identity, invitation_id)

    @app.post("/api/invitations/accept")
    def accept_organization_invitation(data: InvitationAcceptInput, request: Request):
        identity = auth.accept_invitation(request.state.identity, data.token)
        return {**identity.public(), "organizations": auth.organizations(identity)}

    @app.patch("/api/organization/members/{membership_id}")
    def update_organization_member(membership_id: str, data: MemberRoleInput, request: Request):
        return auth.update_member(request.state.identity, membership_id, data.role)

    @app.delete("/api/organization/members/{membership_id}")
    def delete_organization_member(membership_id: str, request: Request):
        return auth.remove_member(request.state.identity, membership_id)

    @app.post("/api/organization/handover")
    def handover_organization(data: HandoverInput, request: Request):
        return auth.handover(request.state.identity, data.membership_id)

    @app.get("/api/health")
    def health():
        with service.db.session() as session:
            session.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": service.db.engine.dialect.name,
            "apertus": {
                "configured": service.settings.model_configured,
                "model": service.settings.apertus_model,
            },
            "firecrawl": {"configured": bool(settings.firecrawl_api_key.get_secret_value())},
            "limits": {
                "document_bytes": settings.max_document_bytes,
                "scan_documents": 25,
                "discovery_links": 50,
            },
            "private_sources_enabled": settings.allow_private_sources,
        }

    @app.post("/api/preview")
    async def preview(data: PreviewInput):
        return await service.preview(data.url, data.provider)

    @app.get("/api/sources")
    def sources():
        with service.db.session() as session:
            return [
                as_dict(source)
                for source in session.scalars(select(Source).order_by(Source.created_at.desc()))
            ]

    @app.post("/api/sources", status_code=201)
    async def add_source(data: SourceInput):
        return await service.add_source(data.model_dump())

    @app.patch("/api/sources/{source_id}")
    async def update_source(source_id: str, data: SourceInput):
        return await service.update_source(source_id, data.model_dump())

    @app.delete("/api/sources/{source_id}")
    def delete_source(source_id: str):
        return service.delete_source(source_id)

    @app.post("/api/sources/{source_id}/discover")
    async def discover(source_id: str):
        return await service.discover(source_id)

    @app.get("/api/laws")
    def laws():
        return service.list_laws()

    @app.post("/api/laws", status_code=201)
    async def add_law(data: LawInput):
        return await service.add_law(data.model_dump())

    @app.get("/api/laws/{law_id}")
    def law_detail(law_id: str):
        return service.law_detail(law_id)

    @app.patch("/api/laws/{law_id}")
    def update_law(law_id: str, data: LawUpdate):
        with service.write_guard, service.db.session() as session:
            law = get(session, Law, law_id)
            watch = service.watch(session, law_id)
            for key, value in data.model_dump(exclude_none=True).items():
                if key == "name":
                    watch.display_name = value
                    if law.owner_organization_id is not None:
                        law.name = value
                elif key == "active":
                    watch.active = value
            session.commit()
            return service.law_summary(session, law, watch)

    @app.get("/api/laws/{law_id}/ai-history")
    def law_ai_history(law_id: str, limit: int = Query(default=100, ge=1, le=500)):
        return service.ai_history(law_id=law_id, limit=limit)

    @app.delete("/api/laws/{law_id}")
    def delete_law(law_id: str):
        return service.delete_law(law_id)

    @app.post("/api/laws/{law_id}/import")
    async def import_version(
        law_id: str,
        file: Annotated[UploadFile | None, File()] = None,
        text: Annotated[str, Form(max_length=1200000)] = "",
        url: Annotated[str, Form(max_length=3000)] = "",
        declared_date: Annotated[str, Form(max_length=10)] = "",
        synthetic: Annotated[bool, Form()] = False,
        allow_identity_mismatch: Annotated[bool, Form()] = False,
        confirm_identity: Annotated[bool, Form()] = False,
        preview: bool = False,
    ):
        body = await file.read(settings.max_document_bytes + 1) if file else None
        filename = (
            re.sub(r'[\r\n\x00"]', "", file.filename or "uploaded-document")[:200] if file else "document.txt"
        )
        return await service.import_version(
            law_id,
            body=body,
            filename=filename,
            text=text,
            url=url,
            declared_date=declared_date or None,
            synthetic=synthetic,
            preview=preview,
            allow_identity_mismatch=allow_identity_mismatch,
            confirm_identity=confirm_identity,
        )

    @app.post("/api/versions/{version_id}/identity-decision")
    def confirm_version_identity(version_id: str, data: IdentityDecisionInput):
        return service.confirm_version_identity(version_id, data.note)

    @app.delete("/api/versions/{version_id}")
    def delete_version(version_id: str):
        return service.delete_version(version_id)

    @app.get("/api/versions/{version_id}")
    def evidence(version_id: str):
        with service.db.session() as session:
            version = get(session, Version, version_id)
            law = get(session, Law, version.law_id)
            return {**version_summary(version), "passages": version.passages, "law_name": law.name}

    @app.get("/api/versions/{version_id}/artifact")
    def artifact(version_id: str):
        with service.db.session() as session:
            version = get(session, Version, version_id)
            path = service.settings.storage_path / "artifacts" / version.artifact_key
            if not path.is_file():
                raise DomainError(
                    "The saved artifact is unavailable. Extracted evidence is still accessible.",
                    404,
                    "artifact_missing",
                )
            mime = "application/pdf" if version.content_type == "application/pdf" else "text/plain"
            return FileResponse(
                path,
                media_type=mime,
                filename=version.filename,
                content_disposition_type="inline" if mime == "application/pdf" else "attachment",
                headers={"Content-Security-Policy": "sandbox"},
            )

    @app.post("/api/comparisons", status_code=201)
    def compare(data: CompareInput):
        return service.create_comparison(data.old_version_id, data.new_version_id)

    @app.get("/api/comparisons/{comparison_id}")
    def comparison_detail(comparison_id: str):
        return service.comparison_detail(comparison_id)

    @app.get("/api/comparisons/{comparison_id}/ai-history")
    def comparison_ai_history(comparison_id: str, limit: int = Query(default=100, ge=1, le=500)):
        return service.ai_history(comparison_id=comparison_id, limit=limit)

    @app.post("/api/comparisons/{comparison_id}/analyse")
    async def analyse(comparison_id: str):
        return await service.analyse(comparison_id)

    @app.post("/api/comparisons/{comparison_id}/analyse-jobs", status_code=202)
    async def analyse_job(comparison_id: str):
        job = service.enqueue_analysis(comparison_id)
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.post("/api/comparisons/{comparison_id}/ask")
    async def ask(comparison_id: str, data: QuestionInput):
        return await service.ask(comparison_id, data.question, [q.model_dump() for q in data.history])

    @app.post("/api/comparisons/{comparison_id}/ask-jobs", status_code=202)
    async def ask_job(comparison_id: str, data: QuestionInput):
        job = service.enqueue_ask(
            comparison_id,
            data.question,
            [q.model_dump() for q in data.history],
        )
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.post("/api/scans", status_code=202)
    async def start_scan(data: ScanInput):
        scan_id = service.start_scan(data.law_ids, data.baseline_version_id)
        detail = service.scan_detail(scan_id)
        if settings.job_execution_mode == "inline" and detail.get("job"):
            await service.execute_job(detail["job"]["id"])
        return service.scan_detail(scan_id)

    @app.get("/api/scans")
    def scans():
        with service.db.session() as session:
            ids = list(session.scalars(select(Scan.id).order_by(Scan.created_at.desc()).limit(20)))
        return [service.scan_detail(scan_id) for scan_id in ids]

    @app.get("/api/scans/{scan_id}")
    def scan_detail(scan_id: str):
        return service.scan_detail(scan_id)

    @app.get("/api/jobs")
    def jobs(limit: int = Query(default=50, ge=1, le=200)):
        return service.jobs(limit)

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str):
        return service.job_detail(job_id)

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        return service.cancel_job(job_id)

    @app.post("/api/jobs/{job_id}/retry")
    async def retry_job(job_id: str):
        result = service.retry_job(job_id)
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job_id)
        return result

    @app.get("/api/admin/models")
    async def local_models(refresh_hardware: bool = False):
        return await service.model_inventory(refresh_hardware)

    @app.post("/api/admin/models/{model_id}/license")
    async def accept_model_license(model_id: str, data: ModelLicenseInput):
        return await service.accept_model_license(model_id, data.accepted)

    @app.post("/api/admin/models/{model_id}/{action}", status_code=202)
    async def local_model_command(
        model_id: str,
        action: Literal["download", "pause", "cancel", "start", "stop"],
    ):
        result = await service.model_command(model_id, action)
        if action in {"download", "start"} and settings.job_execution_mode == "inline":
            return await service.execute_job(result["id"])
        return result

    @app.delete("/api/admin/models/{model_id}")
    async def remove_local_model(model_id: str):
        return await service.model_command(model_id, "remove")

    @app.get("/api/integration-logs")
    def integration_logs(
        provider: str = Query(default="", max_length=40),
        status: Literal["", "success", "error"] = "",
        sort_by: Literal[
            "created_at", "provider", "operation", "status", "duration_ms", "response_status"
        ] = "created_at",
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = Query(default=100, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
    ):
        return service.integration_logs(
            provider=provider,
            status=status,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    @app.get("/api/integration-logs/{log_id}")
    def integration_log_detail(log_id: str):
        return service.integration_log_detail(log_id)

    @app.delete("/api/integration-logs")
    def clear_integration_logs():
        return service.clear_integration_logs()

    @app.get("/api/profile")
    def profile():
        with service.db.session() as session:
            return as_dict(get(session, Profile, service.tenant_record_id))

    @app.patch("/api/profile")
    def update_profile(data: ProfileInput):
        with service.write_guard, service.db.session() as session:
            profile = get(session, Profile, service.tenant_record_id)
            changed = False
            for key, value in data.model_dump().items():
                if key == "business_areas":
                    value = list(dict.fromkeys(area.strip()[:80] for area in value if area.strip()))
                if getattr(profile, key) != value:
                    setattr(profile, key, value)
                    changed = True
            profile.revision += int(changed)
            session.commit()
            return as_dict(profile)

    @app.post("/api/model/test")
    async def test_model():
        return await service.test_model_settings()

    @app.get("/api/settings/apertus")
    def model_settings():
        return service.apertus_configuration()

    @app.patch("/api/settings/apertus")
    def save_model_settings(data: ApertusSettingsInput):
        return service.save_model_settings(data)

    @app.post("/api/settings/apertus/test")
    async def test_model_draft(data: ApertusSettingsInput):
        return await service.test_model_settings(data)

    @app.post("/api/settings/apertus/models")
    async def model_options(data: ApertusSettingsInput):
        return await service.list_model_settings(data)

    @app.post("/api/settings/apertus/reset")
    def reset_model_settings():
        return service.reset_model_settings()

    @app.get("/api/settings/prompts")
    def prompt_settings():
        return service.prompt_configuration()

    @app.patch("/api/settings/prompts")
    def save_prompt_settings(data: PromptSettingsInput):
        return service.save_prompt_settings(data)

    @app.post("/api/settings/prompts/reset")
    def reset_prompt_settings():
        return service.reset_prompt_settings()

    return app


app = create_app()
