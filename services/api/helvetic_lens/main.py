import asyncio
import re
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text

from .config import DomainError, Settings
from .model_settings import ApertusSettingsInput
from .models import Law, Profile, Scan, Source, Version
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


def create_app(settings: Settings | None = None, fetcher=None, model_client=None) -> FastAPI:
    settings = settings or Settings()
    service = HelveticLens(settings, fetcher, model_client)

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
        allow_headers=["Content-Type"],
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
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

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
        with service.db.session() as session:
            return [
                service.law_summary(session, law)
                for law in session.scalars(select(Law).order_by(Law.created_at.desc()))
            ]

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
            for key, value in data.model_dump(exclude_none=True).items():
                setattr(law, key, value)
            session.commit()
            return service.law_summary(session, law)

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
    def comparison_ai_history(
        comparison_id: str, limit: int = Query(default=100, ge=1, le=500)
    ):
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
            return as_dict(get(session, Profile, "default"))

    @app.patch("/api/profile")
    def update_profile(data: ProfileInput):
        with service.write_guard, service.db.session() as session:
            profile = get(session, Profile, "default")
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
