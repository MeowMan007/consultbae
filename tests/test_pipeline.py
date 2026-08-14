import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pipeline.models import Base, Candidate, CandidateEmail, WorkProfile, Compensation
from pipeline.normalizers import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_compensation,
    normalize_date,
    clean_system3_row,
)
from pipeline.matcher import EntityMatcher


@pytest.fixture
def db_session():
    """In-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_phone_normalization():
    assert normalize_phone("+91-9000000131") == "9000000131"
    assert normalize_phone("919000000231") == "9000000231"
    assert normalize_phone("09000000287") == "9000000287"
    assert normalize_phone("9000000268") == "9000000268"
    assert normalize_phone("12345") is None  # Invalid length


def test_email_normalization():
    assert normalize_email("  TANVI.GUPTA31@EXAMPLE.COM ") == "tanvi.gupta31@example.com"
    assert normalize_email("invalid_email_format") is None


def test_city_normalization():
    assert normalize_city("gurgaon") == "Gurugram"
    assert normalize_city("gurugram ") == "Gurugram"
    assert normalize_city("bangalore") == "Bengaluru"
    assert normalize_city("new delhi") == "New Delhi"
    assert normalize_city("Delhi NCR") == "New Delhi"
    assert normalize_city("NOIDA") == "Noida"


def test_compensation_normalization():
    # LPA float
    res1 = normalize_compensation("4.2")
    assert res1["annual_ctc_inr"] == 420000.0

    # Raw INR integer
    res2 = normalize_compensation("417964")
    assert res2["annual_ctc_inr"] == 417964.0

    # Hourly rate
    res3 = normalize_compensation("1415/hr")
    assert res3["hourly_rate_inr"] == 1415.0
    assert res3["annual_ctc_inr"] == 1415.0 * 2000.0

    # Monthly rate
    res4 = normalize_compensation("15k/month")
    assert res4["monthly_rate_inr"] == 15000.0
    assert res4["annual_ctc_inr"] == 180000.0


def test_date_normalization():
    assert normalize_date("24-07-2026") == "2026-07-24"
    assert normalize_date("2026-08-08") == "2026-08-08"
    assert normalize_date("7 Jul 2026") == "2026-07-07"
    assert normalize_date("07/13/2026") == "2026-07-13"


def test_shifted_row_cleaner():
    # Corrupted row from System 3
    shifted_row = {
        "email_id": "react, javascript, mysql",
        "worker_name": "ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG",
        "rate": "Isha Chopra",
        "location": "1406/hr",
        "status": "Pune",
        "skill_tags": "active",
    }
    cleaned, was_shifted = clean_system3_row(shifted_row)
    assert was_shifted is True
    assert cleaned["email_id"] == "ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG"
    assert cleaned["worker_name"] == "Isha Chopra"
    assert cleaned["rate"] == "1406/hr"
    assert cleaned["location"] == "Pune"
    assert cleaned["status"] == "active"
    assert cleaned["skill_tags"] == "react, javascript, mysql"


def test_entity_deduplication(db_session):
    matcher = EntityMatcher(db_session)

    # Ingest record 1 (System 1: Phone + Name)
    c1 = matcher.upsert_candidate(
        source_file="system1.csv",
        full_name="Ritu Sharma",
        phone="9000000146",
        city="Noida",
        is_verified=True,
        projects_completed=15,
    )
    assert c1.id is not None
    assert db_session.query(Candidate).count() == 1

    # Ingest record 2 (System 2: Same Phone + Email + CTC)
    c2 = matcher.upsert_candidate(
        source_file="system2.csv",
        full_name="Ritu Sharma",
        phone="9000000146",
        email="ritu.sharma23@mailtest.example.org",
        city="Noida",
        experience_years=4.8,
        compensation_data={"annual_ctc_inr": 610000.0},
        skills=["n8n", "Web Scraping", "MongoDB", "SQL", "React"],
    )

    # Assert merged into the same record
    assert c2.id == c1.id
    assert db_session.query(Candidate).count() == 1
    assert c2.primary_phone == "9000000146"
    assert c2.primary_email == "ritu.sharma23@mailtest.example.org"
    assert c2.work_profile.projects_completed == 15
    assert len(c2.skills) == 5
