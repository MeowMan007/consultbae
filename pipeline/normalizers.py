import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_DIGITS_REGEX = re.compile(r"\D")

# Canonical City Mapping
CITY_MAP = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "noida": "Noida",
    "pune": "Pune",
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
    "delhi ncr": "New Delhi",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
}

# Standardized Skill Casing Map
SKILL_CANONICAL_MAP = {
    "n8n": "n8n",
    "langchain": "LangChain",
    "rest apis": "REST APIs",
    "rest api": "REST APIs",
    "mongodb": "MongoDB",
    "sql": "SQL",
    "mysql": "MySQL",
    "docker": "Docker",
    "zapier": "Zapier",
    "javascript": "JavaScript",
    "react": "React",
    "python": "Python",
    "selenium": "Selenium",
    "web scraping": "Web Scraping",
    "fastapi": "FastAPI",
    "pandas": "Pandas",
}


def normalize_phone(raw_phone: Any) -> Optional[str]:
    """
    Normalizes Indian phone numbers to standard 10-digit format.
    Handles +91, 91 prefix, leading 0, hyphens, and whitespace.
    """
    if raw_phone is None:
        return None
    phone_str = str(raw_phone).strip()
    if not phone_str:
        return None

    digits = PHONE_DIGITS_REGEX.sub("", phone_str)

    # If 12 digits and starts with 91 -> strip 91
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    # If 11 digits and starts with 0 -> strip 0
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    # Final validation: must be a 10-digit number
    if len(digits) == 10 and digits.isdigit():
        return digits
    return None


def normalize_email(raw_email: Any) -> Optional[str]:
    """
    Trims, lowercases, and validates email against standard RFC regex.
    """
    if raw_email is None:
        return None
    email_str = str(raw_email).strip().lower()
    if not email_str:
        return None

    if EMAIL_REGEX.match(email_str):
        return email_str
    return None


def normalize_name(raw_name: Any) -> str:
    """
    Normalizes candidate name to Title Case, stripping extra spaces and punctuation.
    """
    if not raw_name:
        return ""
    cleaned = str(raw_name).strip()
    # Normalize multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Title Case while handling initials like R. Verma
    words = cleaned.split()
    title_words = []
    for w in words:
        if "." in w:
            # Preserve initial with dot (e.g. 'R.')
            parts = [p.capitalize() for p in w.split(".")]
            title_words.append(".".join(parts))
        else:
            title_words.append(w.capitalize())
    return " ".join(title_words)


def is_abbreviated_name(name: str) -> bool:
    """
    Checks if a name looks like an abbreviated alias (e.g. 'R. Verma' vs 'Rohit Verma').
    """
    parts = name.split()
    for p in parts:
        if len(p) <= 2 or p.endswith("."):
            return True
    return False


def normalize_city(raw_city: Any) -> Optional[str]:
    """
    Standardizes city names to canonical representations.
    """
    if not raw_city:
        return None
    cleaned = str(raw_city).strip().lower()
    return CITY_MAP.get(cleaned, str(raw_city).strip().title())


def normalize_compensation(raw_val: Any) -> Dict[str, Any]:
    """
    Normalizes mixed compensation values:
    - LPA float (e.g. 4.2 -> 420,000 INR)
    - Raw INR (e.g. 417964 -> 417,964 INR)
    - Hourly (e.g. '1415/hr')
    - Monthly (e.g. '15k/month' -> 180,000 INR/yr)
    """
    result = {
        "annual_ctc_inr": None,
        "hourly_rate_inr": None,
        "monthly_rate_inr": None,
        "raw_rate_string": str(raw_val).strip() if raw_val is not None else None,
    }
    if raw_val is None or str(raw_val).strip() == "":
        return result

    val_str = str(raw_val).strip().lower()

    # Case 1: Hourly rate (e.g. "1415/hr", "403/hr")
    if "/hr" in val_str:
        num_part = re.sub(r"[^\d.]", "", val_str)
        try:
            rate = float(num_part)
            result["hourly_rate_inr"] = rate
            result["annual_ctc_inr"] = rate * 2000.0  # Approx 2000 working hrs/yr
        except ValueError:
            pass
        return result

    # Case 2: Monthly rate (e.g. "15k/month", "72k/month")
    if "/month" in val_str:
        num_part = val_str.replace("/month", "").strip()
        multiplier = 1.0
        if "k" in num_part:
            multiplier = 1000.0
            num_part = num_part.replace("k", "").strip()
        try:
            monthly = float(num_part) * multiplier
            result["monthly_rate_inr"] = monthly
            result["annual_ctc_inr"] = monthly * 12.0
        except ValueError:
            pass
        return result

    # Case 3: Numeric float / int (e.g. 4.2 LPA vs 417964 INR)
    clean_num = re.sub(r"[^\d.]", "", val_str)
    if clean_num:
        try:
            num = float(clean_num)
            if num < 100.0:
                # Treated as Lakhs Per Annum (LPA) -> multiply by 100,000
                result["annual_ctc_inr"] = round(num * 100000.0, 2)
            else:
                # Raw annual INR
                result["annual_ctc_inr"] = round(num, 2)
        except ValueError:
            pass

    return result


def normalize_date(raw_date: Any) -> Optional[str]:
    """
    Parses dates in formats:
    - 24-07-2026 (%d-%m-%Y)
    - 2026-08-08 (%Y-%m-%d)
    - 7 Jul 2026 (%d %b %Y)
    - 07/13/2026 (%m/%d/%Y)
    - 08/19/2026 (%m/%d/%Y)
    Returns ISO 8601 string (YYYY-MM-DD).
    """
    if not raw_date:
        return None
    d_str = str(raw_date).strip()
    if not d_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(d_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_boolean(raw_val: Any) -> bool:
    """
    Normalizes 'Y', 'yes', 'Yes', '1', 'True' -> True; 'No', 'N', '0' -> False.
    """
    if not raw_val:
        return False
    val_str = str(raw_val).strip().lower()
    return val_str in ("y", "yes", "true", "1")


def normalize_status(raw_status: Any) -> str:
    """
    Normalizes worker status to canonical enum ('ACTIVE', 'INACTIVE', 'PAUSED').
    """
    if not raw_status:
        return "ACTIVE"
    cleaned = str(raw_status).strip().upper()
    if "ACTIVE" in cleaned:
        return "ACTIVE"
    if "INACTIVE" in cleaned:
        return "INACTIVE"
    if "PAUSED" in cleaned:
        return "PAUSED"
    return "ACTIVE"


def normalize_skills(raw_skills: Any) -> List[str]:
    """
    Parses comma-separated skill string into deduplicated list of canonical skill names.
    """
    if not raw_skills:
        return []
    skill_str = str(raw_skills).strip()
    if not skill_str:
        return []

    tokens = [s.strip() for s in skill_str.split(",") if s.strip()]
    normalized_list = []
    seen = set()

    for token in tokens:
        token_lower = token.lower()
        canonical = SKILL_CANONICAL_MAP.get(token_lower, token.title())
        if canonical.lower() not in seen:
            seen.add(canonical.lower())
            normalized_list.append(canonical)

    return normalized_list


def clean_system3_row(row: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    Detects and fixes shifted columns in System 3 CSV.
    Trap: Row 19 has skill tags in email_id column and email in worker_name column.
    Returns (realigned_row, is_corrected).
    """
    email_val = str(row.get("email_id", "")).strip()
    worker_val = str(row.get("worker_name", "")).strip()
    rate_val = str(row.get("rate", "")).strip()
    loc_val = str(row.get("location", "")).strip()
    status_val = str(row.get("status", "")).strip()
    skill_val = str(row.get("skill_tags", "")).strip()

    # If email_id contains commas or does not look like email, but worker_name DOES match email
    if ("," in email_val or not EMAIL_REGEX.match(email_val.lower())) and EMAIL_REGEX.match(worker_val.lower()):
        # Realigned mapping
        corrected = {
            "email_id": worker_val,
            "worker_name": rate_val,
            "rate": loc_val,
            "location": status_val,
            "status": skill_val if skill_val else "active",
            "skill_tags": email_val,  # The original shifted skills
        }
        return corrected, True

    return row, False
