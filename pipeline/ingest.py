import os
import csv
import sys
from typing import Dict, Any, List
from .models import init_db, SessionLocal, Candidate, IngestionAuditLog
from .normalizers import (
    normalize_phone,
    normalize_email,
    normalize_name,
    normalize_city,
    normalize_compensation,
    normalize_date,
    normalize_boolean,
    normalize_status,
    normalize_skills,
    clean_system3_row,
)
from .matcher import EntityMatcher


def ingest_system1(file_path: str, matcher: EntityMatcher) -> Dict[str, int]:
    """
    Ingests System 1 (Recruitment Gigs):
    Columns: Name, Phone Number, City, Verified, Projects Completed
    """
    stats = {"read": 0, "created": 0, "merged": 0, "skipped": 0}
    if not os.path.exists(file_path):
        print(f"[WARN] File not found: {file_path}")
        return stats

    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["read"] += 1
            raw_name = row.get("Name")
            raw_phone = row.get("Phone Number")
            raw_city = row.get("City")
            raw_verified = row.get("Verified")
            raw_projects = row.get("Projects Completed")

            # Clean & normalize
            name = normalize_name(raw_name)
            phone = normalize_phone(raw_phone)
            city = normalize_city(raw_city)
            is_verified = normalize_boolean(raw_verified)
            try:
                projects = int(raw_projects) if raw_projects is not None else 0
            except ValueError:
                projects = 0

            # Match & Upsert
            existing_before = matcher.find_existing_candidate(phone=phone, email=None, full_name=name)
            matcher.upsert_candidate(
                source_file="system1_recruitment.csv",
                full_name=name,
                phone=phone,
                email=None,
                city=city,
                is_verified=is_verified,
                projects_completed=projects,
                raw_row_data=row,
            )
            if existing_before:
                stats["merged"] += 1
            else:
                stats["created"] += 1

    return stats


def ingest_system2(file_path: str, matcher: EntityMatcher) -> Dict[str, int]:
    """
    Ingests System 2 (CBNexus Talent DB):
    Columns: Full Name, Email, Phone, City, Experience (Years), Current CTC, Applied Date, Skills
    """
    stats = {"read": 0, "created": 0, "merged": 0, "skipped": 0}
    if not os.path.exists(file_path):
        print(f"[WARN] File not found: {file_path}")
        return stats

    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            stats["read"] += 1
            raw_name = row.get("Full Name")
            raw_email = row.get("Email")
            raw_phone = row.get("Phone")
            raw_city = row.get("City")
            raw_exp = row.get("Experience (Years)")
            raw_ctc = row.get("Current CTC")
            raw_date = row.get("Applied Date")
            raw_skills = row.get("Skills")

            name = normalize_name(raw_name)
            email = normalize_email(raw_email)
            phone = normalize_phone(raw_phone)
            city = normalize_city(raw_city)
            try:
                exp = float(raw_exp) if raw_exp else None
            except ValueError:
                exp = None

            comp = normalize_compensation(raw_ctc)
            applied_date = normalize_date(raw_date)
            skills = normalize_skills(raw_skills)

            existing_before = matcher.find_existing_candidate(phone=phone, email=email, full_name=name)
            matcher.upsert_candidate(
                source_file="system2_cbnexus.csv",
                full_name=name,
                phone=phone,
                email=email,
                city=city,
                experience_years=exp,
                applied_date=applied_date,
                compensation_data=comp,
                skills=skills,
                raw_row_data=row,
            )
            if existing_before:
                stats["merged"] += 1
            else:
                stats["created"] += 1

    return stats


def ingest_system3(file_path: str, matcher: EntityMatcher) -> Dict[str, int]:
    """
    Ingests System 3 (Internal Automations / Gig Workers):
    Columns: email_id, worker_name, rate, location, status, skill_tags
    Handles empty row trap and column shift trap (Row 19).
    """
    stats = {"read": 0, "created": 0, "merged": 0, "skipped": 0, "corrupted_fixed": 0}
    if not os.path.exists(file_path):
        print(f"[WARN] File not found: {file_path}")
        return stats

    with open(file_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Trap 1: Completely empty rows (e.g. ,,,,,)
            if not any(v and v.strip() for v in row.values()):
                stats["skipped"] += 1
                continue

            stats["read"] += 1

            # Trap 2: Shifted columns check & correction
            cleaned_row, was_shifted = clean_system3_row(row)
            if was_shifted:
                stats["corrupted_fixed"] += 1

            raw_email = cleaned_row.get("email_id")
            raw_name = cleaned_row.get("worker_name")
            raw_rate = cleaned_row.get("rate")
            raw_loc = cleaned_row.get("location")
            raw_status = cleaned_row.get("status")
            raw_skills = cleaned_row.get("skill_tags")

            email = normalize_email(raw_email)
            name = normalize_name(raw_name)
            comp = normalize_compensation(raw_rate)
            city = normalize_city(raw_loc)
            status = normalize_status(raw_status)
            skills = normalize_skills(raw_skills)

            existing_before = matcher.find_existing_candidate(phone=None, email=email, full_name=name)
            matcher.upsert_candidate(
                source_file="system3_internal.csv",
                full_name=name,
                phone=None,
                email=email,
                city=city,
                status=status,
                compensation_data=comp,
                skills=skills,
                raw_row_data=row,
            )
            if existing_before:
                stats["merged"] += 1
            else:
                stats["created"] += 1

    return stats


def run_pipeline():
    """
    Executes the full ETL merge pipeline on all 3 CSVs.
    """
    print("=" * 70)
    print("  CONSULTBAE AI AUTOMATION — MULTI-SOURCE MERGE PIPELINE")
    print("=" * 70)

    # Initialize Database Tables
    init_db()
    db = SessionLocal()
    matcher = EntityMatcher(db)

    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "raw")
    file1 = os.path.join(data_dir, "system1_recruitment.csv")
    file2 = os.path.join(data_dir, "system2_cbnexus.csv")
    file3 = os.path.join(data_dir, "system3_internal.csv")

    print(f"[*] Ingesting System 1: {os.path.basename(file1)}...")
    s1_stats = ingest_system1(file1, matcher)
    print(f"    -> Read: {s1_stats['read']} | Created: {s1_stats['created']} | Merged: {s1_stats['merged']}")

    print(f"[*] Ingesting System 2: {os.path.basename(file2)}...")
    s2_stats = ingest_system2(file2, matcher)
    print(f"    -> Read: {s2_stats['read']} | Created: {s2_stats['created']} | Merged: {s2_stats['merged']}")

    print(f"[*] Ingesting System 3: {os.path.basename(file3)}...")
    s3_stats = ingest_system3(file3, matcher)
    print(f"    -> Read: {s3_stats['read']} | Created: {s3_stats['created']} | Merged: {s3_stats['merged']} | Shifted Repaired: {s3_stats['corrupted_fixed']} | Skipped Empty: {s3_stats['skipped']}")

    total_candidates = db.query(Candidate).count()
    total_audits = db.query(IngestionAuditLog).count()

    print("\n" + "=" * 70)
    print("  PIPELINE EXECUTION SUMMARY")
    print("=" * 70)
    print(f"  • Total Raw Rows Processed:   {s1_stats['read'] + s2_stats['read'] + s3_stats['read']}")
    print(f"  • Total Unified Candidates:   {total_candidates}")
    print(f"  • Total Ingestion Audit Logs: {total_audits}")
    print(f"  • Shifted Rows Fixed:         {s3_stats['corrupted_fixed']}")
    print(f"  • Corrupted / Blank Skipped:  {s3_stats['skipped']}")
    print("=" * 70)
    print("[SUCCESS] Ingestion & Entity Matching completed successfully!")
    db.close()


if __name__ == "__main__":
    run_pipeline()
