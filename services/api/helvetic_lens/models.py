from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


def new_id() -> str:
    return str(uuid4())


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(250))
    url: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(Text, default="/")
    provider: Mapped[str] = mapped_column(String(30), default="native")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    discovery: Mapped[dict] = mapped_column(JSON, default=dict)


class Law(Base):
    __tablename__ = "laws"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"))
    name: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text, unique=True)
    provider: Mapped[str] = mapped_column(String(30), default="native")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Updated only by validated live observations; avoids a cyclic insert dependency.
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[str] = mapped_column(String(40), default="baseline_created")
    last_error: Mapped[str | None] = mapped_column(Text)


class Version(Base):
    __tablename__ = "versions"
    __table_args__ = (UniqueConstraint("law_id", "content_hash", "extractor", name="uq_law_content"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    title: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    extractor: Mapped[str] = mapped_column(String(40))
    text: Mapped[str] = mapped_column(Text)
    passages: Mapped[list] = mapped_column(JSON)
    content_type: Mapped[str] = mapped_column(String(100))
    artifact_key: Mapped[str] = mapped_column(String(80))
    filename: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(30))
    declared_date: Mapped[str | None] = mapped_column(String(10))
    date_provenance: Mapped[str | None] = mapped_column(String(30))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), index=True)
    origin: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(Text)
    artifact_key: Mapped[str] = mapped_column(String(80))
    declared_date: Mapped[str | None] = mapped_column(String(10))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comparison(Base):
    __tablename__ = "comparisons"
    __table_args__ = (
        UniqueConstraint("old_version_id", "new_version_id", "mode", name="uq_comparison_pair"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    old_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    new_version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"))
    mode: Mapped[str] = mapped_column(String(30))
    diff: Mapped[dict] = mapped_column(JSON)
    identity_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdentityDecision(Base):
    __tablename__ = "identity_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("versions.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    identity_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    actor: Mapped[str] = mapped_column(String(120), default="workspace_user")
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Scan(Base):
    __tablename__ = "scans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    status: Mapped[str] = mapped_column(String(30), default="queued")
    total: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScanItem(Base):
    __tablename__ = "scan_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scans.id"), index=True)
    law_id: Mapped[str] = mapped_column(ForeignKey("laws.id"), index=True)
    baseline_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    new_version_id: Mapped[str | None] = mapped_column(ForeignKey("versions.id"))
    comparison_id: Mapped[str | None] = mapped_column(ForeignKey("comparisons.id"))
    monitoring_comparison_id: Mapped[str | None] = mapped_column(ForeignKey("comparisons.id"))
    mode: Mapped[str] = mapped_column(String(30), default="monitoring")
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    result: Mapped[str | None] = mapped_column(String(40))
    live_result: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    analysis_status: Mapped[str] = mapped_column(String(30), default="pending")
    events: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default="default")
    name: Mapped[str] = mapped_column(String(200), default="My company")
    description: Mapped[str] = mapped_column(Text, default="")
    business_areas: Mapped[list] = mapped_column(JSON, default=lambda: ["Legal", "IT", "Operations"])
    revision: Mapped[int] = mapped_column(Integer, default=1)


class ApertusConfiguration(Base):
    __tablename__ = "apertus_configuration"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default="default")
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    # A workspace credential stays on the server and is never serialized to clients.
    api_key: Mapped[str | None] = mapped_column(Text)
    key_source: Mapped[str] = mapped_column(String(30), default="environment")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptConfiguration(Base):
    __tablename__ = "prompt_configuration"
    id: Mapped[str] = mapped_column(String(30), primary_key=True, default="default")
    values: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationLog(Base):
    __tablename__ = "integration_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(40), index=True)
    operation: Mapped[str] = mapped_column(String(60), index=True)
    method: Mapped[str] = mapped_column(String(10))
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), index=True)
    response_status: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    request_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    request_body: Mapped[dict | list | str | None] = mapped_column(JSON)
    response_headers: Mapped[dict] = mapped_column(JSON, default=dict)
    response_body: Mapped[dict | list | str | None] = mapped_column(JSON)
    request_size: Mapped[int] = mapped_column(Integer, default=0)
    response_size: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    result: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AskRecord(Base):
    __tablename__ = "ask_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    comparison_id: Mapped[str] = mapped_column(ForeignKey("comparisons.id"), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text)
    history: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    result: Mapped[dict | None] = mapped_column(JSON)
    coverage: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    prompt_revision: Mapped[int] = mapped_column(Integer, default=1)
    context_mode: Mapped[str] = mapped_column(String(30), default="automatic")
    use_count: Mapped[int] = mapped_column(Integer, default=1)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_job_organization_idempotency"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), default="default", index=True)
    type: Mapped[str] = mapped_column(String(60), index=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    queue: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=1)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    leased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_detail: Mapped[str | None] = mapped_column(Text)
    result_type: Mapped[str | None] = mapped_column(String(40))
    result_id: Mapped[str | None] = mapped_column(String(36))
    result_url: Mapped[str | None] = mapped_column(Text)
    result_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStep(Base):
    __tablename__ = "job_steps"
    __table_args__ = (UniqueConstraint("job_id", "position", name="uq_job_step_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(30), default="pending")
    progress_current: Mapped[int] = mapped_column(Integer, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, default=1)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    topic: Mapped[str] = mapped_column(String(80), default="helvetic_lens.run_job")
    queue: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
