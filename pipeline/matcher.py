from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from .models import (
    Candidate,
    CandidateEmail,
    CandidateSkill,
    WorkProfile,
    Compensation,
    IngestionAuditLog,
)
from .normalizers import is_abbreviated_name


class EntityMatcher:
    """
    Deterministic Entity Resolution Engine.
    Executes cascading identity resolution using Normalized Phone, Normalized Email,
    and strict disambiguation checks for common names.
    """

    def __init__(self, db: Session):
        self.db = db

    def find_existing_candidate(
        self, phone: Optional[str], email: Optional[str], full_name: Optional[str]
    ) -> Optional[Candidate]:
        """
        Looks up existing candidate by Phone first, then Email.
        Does NOT blindly match by Name alone to avoid false merges.
        """
        # Step 1: Match by Primary Phone (Highest Confidence Anchor)
        if phone:
            candidate = (
                self.db.query(Candidate)
                .filter(Candidate.primary_phone == phone)
                .first()
            )
            if candidate:
                return candidate

        # Step 2: Match by Primary Email or Secondary Email
        if email:
            candidate = (
                self.db.query(Candidate)
                .filter(Candidate.primary_email == email)
                .first()
            )
            if candidate:
                return candidate

            # Check secondary emails in CandidateEmail table
            email_record = (
                self.db.query(CandidateEmail)
                .filter(CandidateEmail.email == email)
                .first()
            )
            if email_record:
                return email_record.candidate

        return None

    def upsert_candidate(
        self,
        source_file: str,
        full_name: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        city: Optional[str] = None,
        is_verified: bool = False,
        experience_years: Optional[float] = None,
        projects_completed: int = 0,
        status: str = "ACTIVE",
        applied_date: Optional[str] = None,
        compensation_data: Optional[Dict[str, Any]] = None,
        skills: Optional[List[str]] = None,
        raw_row_data: Optional[Dict[str, Any]] = None,
    ) -> Candidate:
        """
        Inserts or merges candidate record non-destructively.
        """
        existing = self.find_existing_candidate(phone=phone, email=email, full_name=full_name)

        if compensation_data is None:
            compensation_data = {}
        if skills is None:
            skills = []

        if existing:
            # --- NON-DESTRUCTIVE MERGE ---
            action_notes = []

            # 1. Update Name if incoming name is more complete / non-abbreviated
            if full_name and is_abbreviated_name(existing.full_name) and not is_abbreviated_name(full_name):
                action_notes.append(f"Updated name from '{existing.full_name}' to '{full_name}'")
                existing.full_name = full_name
            elif not existing.full_name and full_name:
                existing.full_name = full_name

            # 2. Update Primary Phone if missing
            if phone and not existing.primary_phone:
                existing.primary_phone = phone
                action_notes.append(f"Set primary phone: {phone}")

            # 3. Update Primary Email or add to Secondary Emails
            if email:
                if not existing.primary_email:
                    existing.primary_email = email
                    action_notes.append(f"Set primary email: {email}")

                # Ensure email exists in CandidateEmail table
                existing_email_entry = (
                    self.db.query(CandidateEmail)
                    .filter(
                        CandidateEmail.candidate_id == existing.id,
                        CandidateEmail.email == email,
                    )
                    .first()
                )
                if not existing_email_entry:
                    self.db.add(
                        CandidateEmail(
                            candidate_id=existing.id,
                            email=email,
                            is_primary=(existing.primary_email == email),
                        )
                    )
                    action_notes.append(f"Added alias email: {email}")

            # 4. Update City if missing
            if city and not existing.city:
                existing.city = city

            # 5. Update Verification flag (True takes precedence)
            if is_verified and not existing.is_verified:
                existing.is_verified = True

            # 6. Update Work Profile
            if not existing.work_profile:
                existing.work_profile = WorkProfile(
                    candidate_id=existing.id,
                    experience_years=experience_years,
                    projects_completed=projects_completed,
                    status=status,
                    applied_date=applied_date,
                )
            else:
                if experience_years is not None and existing.work_profile.experience_years is None:
                    existing.work_profile.experience_years = experience_years
                if projects_completed > existing.work_profile.projects_completed:
                    existing.work_profile.projects_completed = projects_completed
                if status and existing.work_profile.status == "ACTIVE" and status != "ACTIVE":
                    existing.work_profile.status = status
                if applied_date and not existing.work_profile.applied_date:
                    existing.work_profile.applied_date = applied_date

            # 7. Update Compensation
            if not existing.compensation:
                existing.compensation = Compensation(
                    candidate_id=existing.id,
                    annual_ctc_inr=compensation_data.get("annual_ctc_inr"),
                    hourly_rate_inr=compensation_data.get("hourly_rate_inr"),
                    monthly_rate_inr=compensation_data.get("monthly_rate_inr"),
                    raw_rate_string=compensation_data.get("raw_rate_string"),
                )
            else:
                if compensation_data.get("annual_ctc_inr") is not None and existing.compensation.annual_ctc_inr is None:
                    existing.compensation.annual_ctc_inr = compensation_data.get("annual_ctc_inr")
                if compensation_data.get("hourly_rate_inr") is not None and existing.compensation.hourly_rate_inr is None:
                    existing.compensation.hourly_rate_inr = compensation_data.get("hourly_rate_inr")
                if compensation_data.get("monthly_rate_inr") is not None and existing.compensation.monthly_rate_inr is None:
                    existing.compensation.monthly_rate_inr = compensation_data.get("monthly_rate_inr")

            # 8. Merge Skills (Union)
            existing_skill_names = {s.skill_name.lower() for s in existing.skills}
            for sk in skills:
                if sk.lower() not in existing_skill_names:
                    self.db.add(CandidateSkill(candidate_id=existing.id, skill_name=sk))
                    existing_skill_names.add(sk.lower())

            # 9. Ingestion Audit Log
            audit_log = IngestionAuditLog(
                source_file=source_file,
                raw_data=str(raw_row_data) if raw_row_data else None,
                candidate_id=existing.id,
                action_taken="MERGED",
                notes="; ".join(action_notes) if action_notes else "Merged attributes successfully",
            )
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        else:
            # --- CREATE NEW CANDIDATE ---
            new_candidate = Candidate(
                full_name=full_name,
                primary_phone=phone,
                primary_email=email,
                city=city,
                is_verified=is_verified,
            )
            self.db.add(new_candidate)
            self.db.flush()  # Generate UUID for FKs

            # Add primary email entry if exists
            if email:
                self.db.add(
                    CandidateEmail(
                        candidate_id=new_candidate.id,
                        email=email,
                        is_primary=True,
                    )
                )

            # Add Work Profile
            self.db.add(
                WorkProfile(
                    candidate_id=new_candidate.id,
                    experience_years=experience_years,
                    projects_completed=projects_completed,
                    status=status,
                    applied_date=applied_date,
                )
            )

            # Add Compensation
            self.db.add(
                Compensation(
                    candidate_id=new_candidate.id,
                    annual_ctc_inr=compensation_data.get("annual_ctc_inr"),
                    hourly_rate_inr=compensation_data.get("hourly_rate_inr"),
                    monthly_rate_inr=compensation_data.get("monthly_rate_inr"),
                    raw_rate_string=compensation_data.get("raw_rate_string"),
                )
            )

            # Add Skills
            for sk in skills:
                self.db.add(CandidateSkill(candidate_id=new_candidate.id, skill_name=sk))

            # Add Audit Log
            audit_log = IngestionAuditLog(
                source_file=source_file,
                raw_data=str(raw_row_data) if raw_row_data else None,
                candidate_id=new_candidate.id,
                action_taken="CREATED",
                notes="New unified candidate entity created",
            )
            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(new_candidate)
            return new_candidate
