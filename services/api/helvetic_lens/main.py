import asyncio
import re
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from .analysis import classify_question_intent
from .auth import CSRF_COOKIE, SESSION_COOKIE, AuthService, RateLimiter
from .auth_mail import AuthMailer
from .config import DomainError, Settings
from .impact_inbox import ImpactInboxFilters
from .locales import locale_from_accept_language
from .model_settings import ApertusSettingsInput
from .models import AdministrativeAudit, DocumentWatch, Law, Profile, Scan, Source, Version
from .observability import correlation_context
from .prompt_settings import PromptSettingsInput
from .registry import RegistryFilters
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


class HistoryCitation(Input):
    version_id: str = Field(max_length=36)
    passage_id: str = Field(max_length=120)
    quote: str = Field(min_length=1, max_length=1500)
    url: str | None = Field(default=None, max_length=3000)
    page: int | None = Field(default=None, ge=1)


class HistoryQuestion(Input):
    question: str = Field(min_length=1, max_length=2000)
    answer: str | None = Field(default=None, max_length=6000)
    citations: list[HistoryCitation] = Field(default_factory=list, max_length=10)


class QuestionInput(HistoryQuestion):
    history: list[HistoryQuestion] = Field(default_factory=list, max_length=4)
    output_locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] | None = None


class AnalysisInput(Input):
    output_locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] | None = None


class ActionDecisionInput(Input):
    decision: Literal["accepted", "assigned", "scheduled", "dismissed", "not_applicable"]
    assigned_to: str | None = Field(default=None, max_length=200)
    scheduled_for: datetime | None = None
    rationale: str | None = Field(default=None, max_length=2000)


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
    locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] | None = None


class LoginInput(Input):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class AccountEmailInput(Input):
    email: str = Field(min_length=3, max_length=320)


class AccountTokenInput(Input):
    token: str = Field(min_length=20, max_length=200)


class PasswordResetInput(AccountTokenInput):
    password: str = Field(min_length=10, max_length=1024)


class InvitationInput(Input):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["organization_admin", "viewer"] = "viewer"
    recipient_locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"] | None = None


class LocaleInput(Input):
    locale: Literal["de-CH", "fr-CH", "it-CH", "rm-CH", "en-CH"]


class InvitationAcceptInput(Input):
    token: str = Field(min_length=20, max_length=200)


class MemberRoleInput(Input):
    role: Literal["organization_admin", "viewer"]


class RegistryReadInput(Input):
    read: bool = True


class ImpactInboxStateInput(Input):
    state: Literal["unread", "read", "dismissed", "muted"]


class DigestPreferenceInput(Input):
    enabled: bool
    frequency: Literal["daily", "weekly"]
    severities: list[Literal["high", "medium", "low", "none", "unknown"]] = Field(
        default_factory=list, max_length=5
    )
    sources: list[str] = Field(default_factory=list, max_length=20)


class DigestUnsubscribeInput(Input):
    token: str = Field(min_length=40, max_length=200)


class RelationReviewInput(Input):
    decision: Literal["confirmed", "rejected"]
    note: str = Field(default="", max_length=2000)


class OrganizationSwitchInput(Input):
    organization_id: str


class HandoverInput(Input):
    membership_id: str


class ConnectorScheduleInput(Input):
    enabled: bool
    interval_seconds: int = Field(ge=60, le=2_592_000)
    jitter_seconds: int = Field(ge=0, le=86_400)
    window_start: str | None = Field(default=None, max_length=5)
    window_end: str | None = Field(default=None, max_length=5)


def _rate_policy(path: str, method: str) -> tuple[str, int, int] | None:
    if method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if path.startswith("/api/auth/"):
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
    if path == "/api/digests/send":
        return "digest", 3, 3600
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
    auth_mailer = AuthMailer(settings)
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
        expose_headers=["X-Request-ID"],
        allow_credentials=True,
    )

    @app.exception_handler(DomainError)
    async def domain_error(_request, error: DomainError):
        return JSONResponse(
            status_code=error.status,
            content={"detail": error.message, "code": error.code, "params": error.params},
        )

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
                "params": {
                    "fields": [
                        ".".join(str(part) for part in item["loc"] if part != "body")
                        for item in error.errors()
                    ]
                },
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
        public_auth_paths = {
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/session",
            "/api/auth/email-verification/request",
            "/api/auth/email-verification/complete",
            "/api/auth/password-reset/request",
            "/api/auth/password-reset/complete",
            "/api/digests/unsubscribe",
        }
        public_path = path in {"/api/health", "/api/ready"} or path in public_auth_paths
        public_path = public_path or path in {"/docs", "/openapi.json", "/redoc"}
        if path.startswith("/api/") and not public_path and not identity and not settings.allow_anonymous_dev:
            return JSONResponse(
                status_code=401,
                content={"detail": "Sign in to continue.", "code": "authentication_required"},
            )
        if (
            identity
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and path not in public_auth_paths
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
                    content={"detail": error.message, "code": error.code, "params": error.params},
                )
        viewer_allowed_mutations = {
            "/api/auth/logout",
            "/api/invitations/accept",
            "/api/auth/session/organization",
            "/api/auth/locale",
            "/api/digests/preferences",
            "/api/digests/unsubscribe",
            "/api/digests/send",
        }
        viewer_personal_state = (
            path.startswith("/api/impact-inbox/events/") and path.endswith("/state")
        ) or (path.startswith("/api/registry/events/") and path.endswith("/read"))
        if (
            identity
            and identity.role == "viewer"
            and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and path not in viewer_allowed_mutations
            and not viewer_personal_state
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "This workspace is read-only for your account.",
                    "code": "viewer_read_only",
                },
            )
        platform_path = path.startswith("/api/admin/") or (
            path.startswith("/api/connectors/") and path.endswith("/sync")
        )
        if identity and platform_path and not identity.platform_admin:
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
                    content={"detail": error.message, "code": error.code, "params": error.params},
                )
        organization_id = identity.organization_id if identity else service.default_organization_id
        with (
            correlation_context(organization_id=organization_id),
            service.db.organization_context(organization_id),
            service.organization_runtime(),
        ):
            response = await call_next(request)
        if path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            excluded = {"/api/auth/login", "/api/auth/register"}
            if path not in excluded:
                with service.db.session(include_all_organizations=True) as session:
                    session.add(
                        AdministrativeAudit(
                            organization_id=organization_id,
                            actor_user_id=identity.user_id if identity else None,
                            actor_kind="authenticated_user" if identity else "anonymous_development",
                            scope="platform" if platform_path else "organization",
                            action=path.removeprefix("/api/")[:120],
                            method=request.method,
                            path=path[:2000],
                            result="succeeded" if response.status_code < 400 else "failed",
                            response_status=response.status_code,
                        )
                    )
                    session.commit()
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.middleware("http")
    async def correlated_request_metrics(request, call_next):
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        service.api_metrics.started()
        started = time.perf_counter()
        status = 500
        try:
            with correlation_context(request_id=request_id):
                response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            service.api_metrics.finished(
                request.method,
                route,
                status,
                round((time.perf_counter() - started) * 1000),
            )

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

    def selected_locale(request: Request, requested: str | None = None) -> str:
        identity = request.state.identity
        return requested or (identity.locale if identity else None) or locale_from_accept_language(
            request.headers.get("accept-language"), settings.default_locale
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
            locale=data.locale or locale_from_accept_language(
                request.headers.get("accept-language"), settings.default_locale
            ),
        )
        normalized, verification_token = await asyncio.to_thread(
            auth.request_email_verification, data.email
        )
        if verification_token:
            try:
                await asyncio.to_thread(
                    auth_mailer.send,
                    normalized,
                    "verify_email",
                    verification_token,
                    identity.locale,
                )
            except DomainError:
                pass
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

    @app.post("/api/auth/email-verification/request")
    async def request_email_verification(data: AccountEmailInput, request: Request):
        subject = (request.client.host if request.client else "unknown") + ":" + data.email.casefold()
        await asyncio.to_thread(limiter.check, "email_verification", subject, limit=5, window_seconds=3600)
        normalized, raw_token = await asyncio.to_thread(auth.request_email_verification, data.email)
        if raw_token:
            try:
                await asyncio.to_thread(
                    auth_mailer.send,
                    normalized,
                    "verify_email",
                    raw_token,
                    auth.user_locale(normalized),
                )
            except DomainError:
                pass
        return {
            "accepted": True,
            "message": "If this address can be verified, a one-time link has been sent.",
        }

    @app.post("/api/auth/email-verification/complete")
    async def complete_email_verification(data: AccountTokenInput, request: Request):
        subject = request.client.host if request.client else "unknown"
        await asyncio.to_thread(limiter.check, "email_verification_complete", subject, limit=10, window_seconds=3600)
        return await asyncio.to_thread(auth.verify_email, data.token)

    @app.post("/api/auth/password-reset/request")
    async def request_password_reset(data: AccountEmailInput, request: Request):
        subject = (request.client.host if request.client else "unknown") + ":" + data.email.casefold()
        await asyncio.to_thread(limiter.check, "password_reset", subject, limit=5, window_seconds=3600)
        normalized, raw_token = await asyncio.to_thread(auth.request_password_reset, data.email)
        if raw_token:
            try:
                await asyncio.to_thread(
                    auth_mailer.send,
                    normalized,
                    "reset_password",
                    raw_token,
                    auth.user_locale(normalized),
                )
            except DomainError:
                pass
        return {
            "accepted": True,
            "message": "If an active account uses this address, a one-time link has been sent.",
        }

    @app.post("/api/auth/password-reset/complete")
    async def complete_password_reset(data: PasswordResetInput, request: Request):
        subject = request.client.host if request.client else "unknown"
        await asyncio.to_thread(limiter.check, "password_reset_complete", subject, limit=10, window_seconds=3600)
        result = await asyncio.to_thread(auth.reset_password, data.token, data.password)
        response = JSONResponse(content=result)
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")
        return response

    @app.get("/api/auth/session")
    def auth_session(request: Request):
        identity = request.state.identity
        if identity is None:
            return {
                "authenticated": False,
                "anonymous_development": settings.allow_anonymous_dev,
                "authentication_required": not settings.allow_anonymous_dev,
                "suggested_locale": locale_from_accept_language(
                    request.headers.get("accept-language"), settings.default_locale
                ),
            }
        with service.db.session() as session:
            onboarding_required = not bool(session.scalar(select(DocumentWatch.id).limit(1)))
        return {
            **identity.public(),
            "organizations": auth.organizations(identity),
            "onboarding_required": onboarding_required,
        }

    @app.patch("/api/auth/locale")
    def set_user_locale(data: LocaleInput, request: Request):
        identity = request.state.identity
        if identity is None:
            return {"authenticated": False, "locale": data.locale}
        updated = auth.set_locale(identity, data.locale)
        return updated.public()

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
        return auth.create_invitation(
            request.state.identity,
            email=data.email,
            role=data.role,
            recipient_locale=data.recipient_locale,
        )

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

    @app.get("/api/ready")
    def ready():
        checks = {"database": False, "redis": False}
        try:
            with service.db.session() as session:
                session.execute(text("SELECT 1"))
            checks["database"] = True
            client = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            try:
                checks["redis"] = bool(client.ping())
            finally:
                client.close()
        except (OSError, RedisError, SQLAlchemyError):
            pass
        status = 200 if all(checks.values()) else 503
        return JSONResponse({"status": "ready" if status == 200 else "unavailable", "checks": checks}, status)

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

    @app.get("/api/corpus/works")
    def regulatory_works(
        kind: str | None = Query(default=None, max_length=40),
        authority: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=100, ge=1, le=500),
    ):
        return service.list_regulatory_works(kind=kind, authority=authority, limit=limit)

    @app.get("/api/connectors/status")
    def connector_statuses():
        return service.connector_statuses()

    @app.post("/api/connectors/fedlex/{stream}/sync")
    async def sync_fedlex(stream: str):
        return service.enqueue_connector_sync("fedlex", stream)

    @app.post("/api/connectors/parliament/{stream}/sync")
    async def sync_parliament(stream: str):
        return service.enqueue_connector_sync("swiss-parliament", stream)

    @app.post("/api/connectors/federal-court/{stream}/sync")
    async def sync_federal_court(stream: str):
        return service.enqueue_connector_sync("federal-supreme-court", stream)

    @app.post("/api/connectors/federal-criminal-court/{stream}/sync")
    async def sync_federal_criminal_court(stream: str):
        return service.enqueue_connector_sync("federal-criminal-court", stream)

    @app.get("/api/admin/connectors")
    def connector_schedules():
        return service.connector_schedule_status()

    @app.get("/api/admin/status")
    async def platform_status():
        return await service.platform_status()

    @app.get("/api/admin/prompts")
    def platform_prompts():
        return service.platform_prompt_configuration()

    @app.patch("/api/admin/prompts")
    def update_platform_prompts(data: PromptSettingsInput):
        return service.save_platform_prompt_settings(data)

    @app.delete("/api/admin/prompts")
    def reset_platform_prompts():
        return service.reset_platform_prompt_settings()

    @app.get("/api/organization/status")
    def organization_status():
        return service.organization_status()

    @app.put("/api/admin/connectors/{connector}/{stream}")
    def update_connector_schedule(
        connector: str,
        stream: str,
        data: ConnectorScheduleInput,
    ):
        return service.update_connector_schedule(
            connector,
            stream,
            **data.model_dump(),
        )

    @app.post("/api/admin/connectors/{connector}/{stream}/sync", status_code=202)
    def enqueue_connector_sync(connector: str, stream: str):
        return service.enqueue_connector_sync(connector, stream)

    @app.get("/api/corpus/works/{work_id}")
    def regulatory_work_detail(work_id: str):
        return service.regulatory_work_detail(work_id)

    @app.get("/api/relation-candidates/{organization_candidate_id}/analyses")
    def relation_candidate_analyses(organization_candidate_id: str):
        return service.relation_analysis_history(organization_candidate_id)

    @app.post(
        "/api/relation-candidates/{organization_candidate_id}/analyse-jobs",
        status_code=202,
    )
    async def relation_candidate_analysis_job(
        organization_candidate_id: str, request: Request, data: AnalysisInput | None = None
    ):
        job = await service.enqueue_relation_analysis(
            organization_candidate_id,
            output_locale=selected_locale(request, data.output_locale if data else None),
        )
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.post(
        "/api/relation-candidates/{organization_candidate_id}/reanalyse-jobs",
        status_code=202,
    )
    async def relation_candidate_reanalysis_job(
        organization_candidate_id: str, request: Request, data: AnalysisInput | None = None
    ):
        job = await service.enqueue_relation_analysis(
            organization_candidate_id,
            force=True,
            output_locale=selected_locale(request, data.output_locale if data else None),
        )
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.get("/api/relation-analyses/{analysis_id}/evidence/{evidence_id}")
    def relation_analysis_evidence(analysis_id: str, evidence_id: str):
        return service.relation_analysis_evidence(analysis_id, evidence_id)

    @app.get("/api/relations/{relation_id}")
    def regulatory_relation_detail(relation_id: str):
        return service.regulatory_relation_detail(relation_id)

    @app.post(
        "/api/relation-candidates/{organization_candidate_id}/monitor-successor",
        status_code=201,
    )
    async def monitor_relation_successor(organization_candidate_id: str):
        return await service.monitor_relation_successor(organization_candidate_id)

    @app.post("/api/relation-candidates/{organization_candidate_id}/reviews", status_code=201)
    def review_relation_candidate(
        organization_candidate_id: str, data: RelationReviewInput, request: Request
    ):
        identity = request.state.identity
        return service.review_relation_candidate(
            organization_candidate_id,
            data.decision,
            data.note,
            identity.user_id if identity else None,
        )

    @app.get("/api/registry")
    def registry(
        request: Request,
        view: Literal["monitored", "events"] = "monitored",
        q: str = Query(default="", max_length=300),
        cursor: str = Query(default="", max_length=1000),
        limit: int = Query(default=30, ge=1, le=100),
        authority: str = Query(default="", max_length=80),
        connector: str = Query(default="", max_length=80),
        kind: str = Query(default="", max_length=40),
        language: str = Query(default="", max_length=20),
        lifecycle: str = Query(default="", max_length=60),
        impact: str = Query(default="", max_length=20),
        watched: str = Query(default="", max_length=20),
        read: str = Query(default="", max_length=20),
        health: str = Query(default="", max_length=20),
        start: str = Query(default="", max_length=10),
        end: str = Query(default="", max_length=10),
    ):
        identity = request.state.identity
        return service.registry(
            RegistryFilters(
                view=view,
                query=q,
                cursor=cursor,
                limit=limit,
                authority=authority,
                connector=connector,
                kind=kind,
                language=language,
                lifecycle=lifecycle,
                impact=impact,
                watched=watched,
                read=read,
                health=health,
                start=start,
                end=end,
            ),
            identity.user_id if identity else None,
        )

    @app.get("/api/impact-inbox")
    def impact_inbox(
        request: Request,
        source: str = Query(default="", max_length=80),
        severity: str = Query(default="", max_length=20),
        item_type: str = Query(default="", max_length=40),
        watched_law: str = Query(default="", max_length=36),
        state: str = Query(default="", max_length=20),
    ):
        identity = request.state.identity
        return service.impact_inbox(
            ImpactInboxFilters(
                source=source,
                severity=severity,
                item_type=item_type,
                watched_law=watched_law,
                state=state,
            ),
            identity.user_id if identity else None,
        )

    @app.patch("/api/impact-inbox/events/{event_id}/state")
    def set_impact_inbox_state(
        event_id: str, data: ImpactInboxStateInput, request: Request
    ):
        identity = request.state.identity
        return service.set_impact_inbox_state(
            event_id, data.state, identity.user_id if identity else None
        )

    @app.get("/api/digests")
    def digest_overview(request: Request):
        identity = request.state.identity
        return service.digest_overview(identity.user_id if identity else None)

    @app.put("/api/digests/preferences")
    def save_digest_preference(data: DigestPreferenceInput, request: Request):
        identity = request.state.identity
        return service.save_digest_preference(
            identity.user_id if identity else None,
            **data.model_dump(),
        )

    @app.post("/api/digests/send", status_code=202)
    async def send_digest_now(request: Request):
        identity = request.state.identity
        job = service.enqueue_digest_now(identity.user_id if identity else None)
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.post("/api/digests/unsubscribe")
    def unsubscribe_digest(data: DigestUnsubscribeInput):
        return service.unsubscribe_digest(data.token)

    @app.patch("/api/registry/events/{event_id}/read")
    def mark_registry_event_read(
        event_id: str, data: RegistryReadInput, request: Request
    ):
        identity = request.state.identity
        return service.mark_registry_event_read(
            event_id, data.read, identity.user_id if identity else None
        )

    @app.get("/api/laws/{law_id}/timeline")
    def regulatory_timeline(law_id: str):
        return service.regulatory_timeline(law_id)

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
    def comparison_detail(comparison_id: str, request: Request):
        return service.comparison_detail(comparison_id, selected_locale(request))

    @app.get("/api/comparisons/{comparison_id}/ai-history")
    def comparison_ai_history(comparison_id: str, limit: int = Query(default=100, ge=1, le=500)):
        return service.ai_history(comparison_id=comparison_id, limit=limit)

    @app.post(
        "/api/comparisons/{comparison_id}/analyses/{analysis_id}/actions/{action_key}/decisions"
    )
    def decide_analysis_action(
        comparison_id: str,
        analysis_id: str,
        action_key: str,
        data: ActionDecisionInput,
        request: Request,
    ):
        identity = request.state.identity
        return service.decide_action(
            comparison_id,
            analysis_id,
            action_key,
            data.decision,
            assigned_to=data.assigned_to,
            scheduled_for=data.scheduled_for,
            rationale=data.rationale,
            actor_user_id=identity.user_id if identity else None,
            actor_label=(identity.name if identity else "Local administrator"),
        )

    @app.post("/api/comparisons/{comparison_id}/analyse")
    async def analyse(comparison_id: str, request: Request, data: AnalysisInput | None = None):
        return await service.analyse(
            comparison_id, output_locale=selected_locale(request, data.output_locale if data else None)
        )

    @app.post("/api/comparisons/{comparison_id}/analyse-jobs", status_code=202)
    async def analyse_job(
        comparison_id: str, request: Request, data: AnalysisInput | None = None
    ):
        job = service.enqueue_analysis(
            comparison_id, selected_locale(request, data.output_locale if data else None)
        )
        if settings.job_execution_mode == "inline":
            return await service.execute_job(job["id"])
        return job

    @app.post("/api/comparisons/{comparison_id}/ask")
    async def ask(comparison_id: str, data: QuestionInput, request: Request):
        return await service.ask(
            comparison_id,
            data.question,
            [q.model_dump() for q in data.history],
            selected_locale(request, data.output_locale),
        )

    @app.post("/api/comparisons/{comparison_id}/ask-jobs", status_code=202)
    async def ask_job(comparison_id: str, data: QuestionInput, request: Request):
        job = service.enqueue_ask(
            comparison_id,
            data.question,
            [q.model_dump() for q in data.history],
            selected_locale(request, data.output_locale),
        )
        route = classify_question_intent(data.question)
        if settings.job_execution_mode == "inline" or route["intent"] in {"vague", "off_topic"}:
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
        query: str = Query(default="", max_length=200),
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
            query=query,
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
