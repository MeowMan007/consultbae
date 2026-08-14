import os
import uuid
import shutil
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pipeline.models import (
    init_db,
    get_db,
    Candidate,
    AudioSubmission,
    CandidateSkill,
    WorkProfile,
    Compensation,
)
from pipeline.normalizers import normalize_phone, normalize_name, normalize_email
from pipeline.matcher import EntityMatcher
from .audio_processor import extract_audio_features

# Create storage directories
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(APP_DIR, "storage")
STATIC_DIR = os.path.join(APP_DIR, "static")
os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Initialize DB
init_db()

app = FastAPI(
    title="ConsultBae Audio Collection & Automation Hub",
    description="Backend API for candidate deduplication, n8n automation webhook support, and worker audio collection.",
    version="1.0.0",
)

# CORS middleware for cross-origin frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Schemas
class DuplicateCheckRequest(BaseModel):
    phone: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None


class TaggedCandidateRequest(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    skills: Optional[str] = None
    auto_tag: Optional[dict] = None


@app.get("/api/stats")
def get_system_stats(db: Session = Depends(get_db)):
    """Returns database summary counts and submission statistics."""
    total_candidates = db.query(Candidate).count()
    total_audios = db.query(AudioSubmission).count()
    verified_candidates = db.query(Candidate).filter(Candidate.is_verified == True).count()
    return {
        "status": "online",
        "total_candidates": total_candidates,
        "verified_candidates": verified_candidates,
        "total_audio_submissions": total_audios,
    }


@app.post("/api/audio/submit")
async def submit_audio(
    name: str = Form(...),
    phone: str = Form(...),
    audio_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Accepts candidate audio recording/file upload, extracts acoustic properties,
    and persists record into the SQLite database.
    """
    clean_name = normalize_name(name)
    clean_phone = normalize_phone(phone)

    if not clean_phone:
        raise HTTPException(
            status_code=400,
            detail="Invalid Indian phone number. Please enter a valid 10-digit number.",
        )

    # Save audio file to storage
    file_uuid = str(uuid.uuid4())
    original_ext = os.path.splitext(audio_file.filename)[1]
    if not original_ext:
        original_ext = ".webm" if "webm" in (audio_file.content_type or "") else ".wav"

    saved_filename = f"{file_uuid}_{clean_phone}{original_ext}"
    saved_filepath = os.path.join(STORAGE_DIR, saved_filename)

    with open(saved_filepath, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)

    # Extract acoustic features
    features = extract_audio_features(saved_filepath)

    # Associate with existing candidate or create one
    matcher = EntityMatcher(db)
    candidate = matcher.find_existing_candidate(phone=clean_phone, email=None, full_name=clean_name)
    if not candidate:
        candidate = matcher.upsert_candidate(
            source_file="audio_app_submission",
            full_name=clean_name,
            phone=clean_phone,
        )

    # Create Audio Submission record
    submission = AudioSubmission(
        id=file_uuid,
        candidate_id=candidate.id if candidate else None,
        candidate_name=clean_name,
        candidate_phone=clean_phone,
        file_name=saved_filename,
        file_path=saved_filepath,
        duration_seconds=features["duration_seconds"],
        sample_rate_khz=features["sample_rate_khz"],
        bitrate_kbps=features["bitrate_kbps"],
        loudness_dbfs=features["loudness_dbfs"],
        snr_db=features["snr_db"],
        quality_grade=features["quality_grade"],
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "success": True,
        "message": "Audio recording submitted and analyzed successfully.",
        "submission": submission.to_dict(),
        "candidate": candidate.to_dict() if candidate else None,
    }


@app.get("/api/audio/submissions")
def list_audio_submissions(db: Session = Depends(get_db)):
    """Returns all audio submissions ordered by latest first."""
    submissions = (
        db.query(AudioSubmission)
        .order_by(AudioSubmission.created_at.desc())
        .all()
    )
    return [s.to_dict() for s in submissions]


@app.get("/api/audio/file/{filename}")
def stream_audio_file(filename: str):
    """Streams audio binary for playback."""
    file_path = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found.")

    ext = os.path.splitext(filename)[1].lower()
    media_type = "audio/wav"
    if ext == ".mp3":
        media_type = "audio/mpeg"
    elif ext in (".webm", ".ogg"):
        media_type = "audio/webm"

    return FileResponse(file_path, media_type=media_type)


@app.post("/api/candidates/check-duplicate")
def check_duplicate_candidate(req: DuplicateCheckRequest, db: Session = Depends(get_db)):
    """Endpoint consumed by n8n / Zapier to check for candidate existence."""
    clean_phone = normalize_phone(req.phone) if req.phone else None
    clean_email = normalize_email(req.email) if req.email else None
    clean_name = normalize_name(req.name) if req.name else None

    matcher = EntityMatcher(db)
    existing = matcher.find_existing_candidate(phone=clean_phone, email=clean_email, full_name=clean_name)
    if existing:
        return {
            "is_duplicate": True,
            "candidate": existing.to_dict(),
        }
    return {
        "is_duplicate": False,
        "candidate": None,
    }


@app.post("/api/candidates/save-tagged")
def save_tagged_candidate(req: TaggedCandidateRequest, db: Session = Depends(get_db)):
    """Endpoint for n8n to persist LLM-tagged candidates."""
    clean_phone = normalize_phone(req.phone) if req.phone else None
    clean_email = normalize_email(req.email) if req.email else None
    clean_name = normalize_name(req.name)

    matcher = EntityMatcher(db)
    category = req.auto_tag.get("category", "General") if req.auto_tag else "General"

    candidate = matcher.upsert_candidate(
        source_file="n8n_llm_auto_tag",
        full_name=clean_name,
        phone=clean_phone,
        email=clean_email,
        skills=[category],
    )
    return {"success": True, "candidate": candidate.to_dict()}


# Mount static assets
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
