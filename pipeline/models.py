import os
import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()

# Default SQLite database path
DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "database.sqlite3")
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String(255), nullable=False, index=True)
    primary_phone = Column(String(20), nullable=True, index=True)
    primary_email = Column(String(255), nullable=True, index=True)
    city = Column(String(100), nullable=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    emails = relationship("CandidateEmail", back_populates="candidate", cascade="all, delete-orphan")
    skills = relationship("CandidateSkill", back_populates="candidate", cascade="all, delete-orphan")
    work_profile = relationship("WorkProfile", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    compensation = relationship("Compensation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    audio_submissions = relationship("AudioSubmission", back_populates="candidate")
    audit_logs = relationship("IngestionAuditLog", back_populates="candidate")

    def to_dict(self):
        return {
            "id": self.id,
            "full_name": self.full_name,
            "primary_phone": self.primary_phone,
            "primary_email": self.primary_email,
            "city": self.city,
            "is_verified": self.is_verified,
            "experience_years": self.work_profile.experience_years if self.work_profile else None,
            "projects_completed": self.work_profile.projects_completed if self.work_profile else 0,
            "status": self.work_profile.status if self.work_profile else "ACTIVE",
            "applied_date": self.work_profile.applied_date if self.work_profile else None,
            "annual_ctc_inr": self.compensation.annual_ctc_inr if self.compensation else None,
            "hourly_rate_inr": self.compensation.hourly_rate_inr if self.compensation else None,
            "monthly_rate_inr": self.compensation.monthly_rate_inr if self.compensation else None,
            "skills": [s.skill_name for s in self.skills],
            "all_emails": [e.email for e in self.emails],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CandidateEmail(Base):
    __tablename__ = "candidate_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    is_primary = Column(Boolean, default=False)

    candidate = relationship("Candidate", back_populates="emails")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    skill_name = Column(String(100), nullable=False, index=True)

    candidate = relationship("Candidate", back_populates="skills")


class WorkProfile(Base):
    __tablename__ = "work_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, unique=True, index=True)
    experience_years = Column(Float, nullable=True)
    projects_completed = Column(Integer, default=0)
    status = Column(String(50), default="ACTIVE")
    applied_date = Column(String(50), nullable=True)

    candidate = relationship("Candidate", back_populates="work_profile")


class Compensation(Base):
    __tablename__ = "compensations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, unique=True, index=True)
    annual_ctc_inr = Column(Float, nullable=True)
    hourly_rate_inr = Column(Float, nullable=True)
    monthly_rate_inr = Column(Float, nullable=True)
    raw_rate_string = Column(String(100), nullable=True)

    candidate = relationship("Candidate", back_populates="compensation")


class AudioSubmission(Base):
    __tablename__ = "audio_submissions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=True, index=True)
    candidate_name = Column(String(255), nullable=False)
    candidate_phone = Column(String(20), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    duration_seconds = Column(Float, nullable=False)
    sample_rate_khz = Column(Float, nullable=False)
    bitrate_kbps = Column(Float, nullable=False)
    loudness_dbfs = Column(Float, nullable=False)
    snr_db = Column(Float, nullable=True)
    quality_grade = Column(String(50), default="Good")
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="audio_submissions")

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "candidate_name": self.candidate_name,
            "candidate_phone": self.candidate_phone,
            "file_name": self.file_name,
            "file_path": self.file_path,
            "duration_seconds": round(self.duration_seconds, 2),
            "sample_rate_khz": round(self.sample_rate_khz, 2),
            "bitrate_kbps": round(self.bitrate_kbps, 1),
            "loudness_dbfs": round(self.loudness_dbfs, 2),
            "snr_db": round(self.snr_db, 2) if self.snr_db is not None else None,
            "quality_grade": self.quality_grade,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class IngestionAuditLog(Base):
    __tablename__ = "ingestion_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file = Column(String(100), nullable=False)
    raw_data = Column(Text, nullable=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=True)
    action_taken = Column(String(50), nullable=False)  # "CREATED", "MERGED", "SKIPPED_CORRUPTED"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="audit_logs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
