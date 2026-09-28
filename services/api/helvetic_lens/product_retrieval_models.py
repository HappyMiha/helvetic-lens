"""Discardable derived vectors; never a second evidence or permission store."""
from sqlalchemy import Boolean, ForeignKeyConstraint, Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .product_investigation_models import ResearchRecord, research_scope


class EvidenceVector(ResearchRecord, Base):
    __tablename__ = "product_evidence_vectors"
    __table_args__ = (research_scope(), UniqueConstraint("dossier_id", "record_key", name="uq_evidence_vector_record"),
        ForeignKeyConstraint(["source_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_investigation_sources.id", "product_investigation_sources.investigation_id",
             "product_investigation_sources.dossier_id", "product_investigation_sources.organization_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["claim_id", "investigation_id", "dossier_id", "organization_id"],
            ["product_dossier_claims.id", "product_dossier_claims.investigation_id",
             "product_dossier_claims.dossier_id", "product_dossier_claims.organization_id"], ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(String(36))
    claim_id: Mapped[str | None] = mapped_column(String(36))
    record_key: Mapped[str] = mapped_column(String(80))
    input_sha256: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(160))
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    input_tokens: Mapped[int] = mapped_column(Integer)
    truncated: Mapped[bool] = mapped_column(Boolean)
