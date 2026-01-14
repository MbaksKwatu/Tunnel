import os
from datetime import datetime
import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Float,
    Numeric,
    JSON,
    Boolean,
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


Base = declarative_base()

# Supabase PostgreSQL connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/parity")

engine = create_engine(
    DATABASE_URL + "?sslmode=require",
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Optional: Create tables if they don't exist (for local dev only)
# Base.metadata.create_all(bind=engine)


class Deal(Base):
    __tablename__ = "deals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_name = Column(String, nullable=False)
    sector = Column(String, nullable=False)
    geography = Column(String, nullable=False)
    deal_type = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    revenue_usd = Column(Numeric(18, 2), nullable=True)
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    evidence = relationship("Evidence", back_populates="deal", cascade="all, delete-orphan")
    judgments = relationship("Judgment", back_populates="deal", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "company_name": self.company_name,
            "sector": self.sector,
            "geography": self.geography,
            "deal_type": self.deal_type,
            "stage": self.stage,
            "revenue_usd": float(self.revenue_usd) if self.revenue_usd is not None else None,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Thesis(Base):
    __tablename__ = "thesis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    fund_id = Column(String, ForeignKey("users.id"), nullable=True)
    investment_focus = Column(String, nullable=True)
    sector_preferences = Column(JSON, nullable=True)
    geography_constraints = Column(JSON, nullable=True)
    stage_preferences = Column(JSON, nullable=True)
    min_revenue_usd = Column(Float, nullable=True)
    kill_conditions = Column(JSON, nullable=True)
    governance_requirements = Column(JSON, nullable=True)
    financial_thresholds = Column(JSON, nullable=True)
    data_confidence_tolerance = Column(String, nullable=True)
    impact_requirements = Column(JSON, nullable=True)
    weights = Column(JSON, nullable=True)
    name = Column(String, nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "fund_id": self.fund_id,
            "investment_focus": self.investment_focus,
            "sector_preferences": self.sector_preferences,
            "geography_constraints": self.geography_constraints,
            "stage_preferences": self.stage_preferences,
            "min_revenue_usd": float(self.min_revenue_usd) if self.min_revenue_usd else None,
            "kill_conditions": self.kill_conditions,
            "governance_requirements": self.governance_requirements,
            "financial_thresholds": self.financial_thresholds,
            "data_confidence_tolerance": self.data_confidence_tolerance,
            "impact_requirements": self.impact_requirements,
            "weights": self.weights,
            "name": self.name,
            "is_default": bool(self.is_default)
        }


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(String, ForeignKey("documents.id"), nullable=True)
    evidence_type = Column(String, nullable=False)
    evidence_subtype = Column(String, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    confidence_score = Column(Float, nullable=True, default=0.7)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    deal = relationship("Deal", back_populates="evidence")

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "document_id": self.document_id,
            "evidence_type": self.evidence_type,
            "evidence_subtype": self.evidence_subtype,
            "extracted_data": self.extracted_data,
            "confidence_score": self.confidence_score,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


class Judgment(Base):
    __tablename__ = "judgments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deal_id = Column(String(36), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False)
    investment_readiness = Column(String, nullable=True)
    thesis_alignment = Column(String, nullable=True)
    kill_signals = Column(JSON, nullable=True)
    confidence_level = Column(String, nullable=True)
    dimension_scores = Column(JSON, nullable=True)
    explanations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    deal = relationship("Deal", back_populates="judgments")

    def to_dict(self):
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "investment_readiness": self.investment_readiness,
            "thesis_alignment": self.thesis_alignment,
            "kill_signals": self.kill_signals,
            "confidence_level": self.confidence_level,
            "dimension_scores": self.dimension_scores,
            "explanations": self.explanations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
