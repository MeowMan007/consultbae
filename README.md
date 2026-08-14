# ConsultBae — AI Automation Take-Home Project

This repository contains the complete submission for the ConsultBae AI Automation take-home assignment. It includes a multi-source data merge pipeline, an n8n automation workflow, a full-stack worker audio collection web app with acoustic analytics, a report on 13 planted data traps, a scalability architecture design for 5,000 workers, and an automated test suite.

---

## Submission Summary & Deliverables

All 5 required components from the assignment prompt are implemented and ready for evaluation:

| # | Submission Requirement | Implementation & Links | Status |
|---|---|---|:---:|
| **1** | **GitHub Repo with Code** | [https://github.com/MeowMan007/consultbae](https://github.com/MeowMan007/consultbae) | Clean Progressive Commits |
| **2** | **Screen Recording (Max 6 min)** | **[Watch Walkthrough on Google Drive](https://drive.google.com/file/d/1YSmaTRNjqwZ2UXK31KN9sHQh7HGupgsF/view?usp=sharing)** | Ready to Stream |
| **3** | **README with Setup Steps** | [Setup and Quickstart Guide](#1-setup-and-quickstart) | Verified Working |
| **4** | **Data Issues Report** | [13 Planted Traps & Fixes Report](#2-data-issues-report-13-planted-traps) | 13 Traps Resolved |
| **5** | **Stuck Log (in README)** | [3 Engineering Hurdles & AI Evaluation](#3-stuck-log) | 3 Detailed Real-World Cases |

---

## Table of Contents
1. [Screen Recording and Walkthrough](#screen-recording-and-walkthrough)
2. [Setup and Quickstart](#1-setup-and-quickstart)
3. [Data Issues Report (13 Planted Traps)](#2-data-issues-report-13-planted-traps)
4. [Stuck Log](#3-stuck-log)
5. [Task 1: Multi-Source Merge Pipeline](#task-1-multi-source-merge-pipeline)
6. [Task 2: No-Code Automation Workflow (n8n)](#task-2-no-code-automation-workflow-n8n)
7. [Task 3: Worker Audio Collection App](#task-3-worker-audio-collection-app)
8. [Task 5: Scaling to 5,000 Workers](#task-5-scaling-to-5000-workers)
9. [Automated Test Suite](#automated-test-suite)

---

## Screen Recording and Walkthrough

> **Video Link**: **[https://drive.google.com/file/d/1YSmaTRNjqwZ2UXK31KN9sHQh7HGupgsF/view?usp=sharing](https://drive.google.com/file/d/1YSmaTRNjqwZ2UXK31KN9sHQh7HGupgsF/view?usp=sharing)**  
> *(Local file: `Screen Recording 2026-08-14 230542.mp4`)*

### What the walkthrough covers:
1. **Running the Pipeline**: Live terminal run of `python -m pipeline.ingest` merging 103 raw rows into 60 candidates in SQLite.
2. **Audio App End-to-End**: Live browser microphone recording at `http://localhost:8000`, waveform visualizer, automatic acoustic property extraction (duration, sample rate, bitrate, loudness in dBFS, SNR, quality grade), and reviewer history playback.
3. **Hardest Decisions**: Walkthrough of the 3 engineering tradeoffs from the Stuck Log.

---

## 1. Setup and Quickstart

### Prerequisites
- Python 3.10 or higher
- `pip` package manager

### Step 1: Clone the repository and install dependencies
```bash
git clone https://github.com/MeowMan007/consultbae.git
cd consultbae

# Create and activate a virtual environment (optional)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Run the Data Pipeline (Task 1)
```bash
python -m pipeline.ingest
```
This reads the 3 raw CSV files from `data/raw/`, normalizes the data, runs the cascading deduplication engine, and creates a clean SQLite database at `data/database.sqlite3`.

### Step 3: Launch the Audio Collection Web App (Task 3)
```bash
uvicorn audio_app.server:app --reload --port 8000
```
Open your browser at **`http://localhost:8000`** to access the in-browser recorder, upload portal, acoustic analytics, and history gallery.

### Step 4: Run the Unit Tests
```bash
pytest
```
*or `pytest tests/ -v` to see verbose test-by-test results.*

---

## 2. Data Issues Report (13 Planted Traps)

During ETL development, I found **13 planted data traps** across the 3 raw CSV files. Here is what they were and how the pipeline programmatically fixes each one:

| # | Data Quality Issue | Where It Occurred | Example in Raw Data | How I Fixed It |
|---|---|---|---|---|
| **1** | **Shifted Columns / Corrupted Row** | System 3, Row 19 | `"react, javascript, mysql", ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG, Isha Chopra, 1406/hr, Pune, active` | Built an anomaly detector in `normalizers.py` that checks if column 0 fails email regex while column 1 matches email regex. When detected, it realigns the dictionary values to the proper columns before saving. |
| **2** | **Completely Blank Rows** | System 3, Row 11 | `,,,,,` | Filter skips any row where all columns are empty or whitespace before parsing. |
| **3** | **Duplicate Header Row Embedded Mid-File** | System 1, Row 15 | `Name,Phone Number,City,Verified,Projects Completed` | Ingestion skips rows where the `Name` column value literally equals the string `"Name"`. |
| **4** | **Inconsistent Phone Formats** | Across System 1 & 2 | `+91-9000000131`, `919000000231`, `09000000287`, `9000000113` | Strips all non-digit characters, removes leading `+91`, `91`, and `0`, and validates that the result is exactly 10 digits (`9000000xxx`). |
| **5** | **Email Casing & Whitespace** | Across System 2 & 3 | `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`, `DEEPAK.NAIR44@EXAMPLE.COM` | Normalized using `.strip().lower()` with RFC email regex validation. |
| **6** | **Mixed Compensation Formats (LPA vs Raw INR)** | System 2 & 3 | `4.2`, `8.3` mixed with `417964`, `806661`, `1415/hr`, `15k/month` | Values $<100$ in CTC are treated as LPA and multiplied by 100,000. `15k/month` is annualized ($15000 \times 12$). Hourly rates are stored separately. |
| **7** | **Same Common Name, Different People** | System 1 & 3 | `Arjun Mehta` (`9000000131`) vs `Arjun Mehta` (`9000000272`) | Zero-false-positive policy: matching requires phone or email confirmation. People with the same name but different contact details are kept separate. |
| **8** | **Abbreviated Names** | System 2 | `"R. Verma"` vs `"Rohit Verma"` (same phone `9000000294` and email) | Merged using verified phone/email anchors; the name is updated to the more complete version (`Rohit Verma`). |
| **9** | **Alias / Secondary Emails** | System 2 | `Nikhil Chopra` with `nikhil.chopra70@...` and `alt.nikhil.chopra70@...` | Merged into one candidate record via phone anchor; secondary email is saved in the `candidate_emails` table. |
| **10** | **Multi-Format Applied Dates** | System 2 | `24-07-2026`, `2026-08-08`, `7 Jul 2026`, `07/13/2026` | Multi-pattern date parser standardizes all dates into ISO 8601 strings (`YYYY-MM-DD`). |
| **11** | **City Name Synonyms & Spaces** | Across all CSVs | `gurugram `, `GURGAON`, `Noida `, `new delhi`, `Delhi NCR`, `bangalore` vs `Bengaluru` | A dictionary map normalizes city variations to standard names (`Gurugram`, `Bengaluru`, `New Delhi`, `Noida`, `Pune`). |
| **12** | **Boolean & Status Variations** | System 1 & 3 | `Y`, `yes`, `Yes`, `No`, `N`, `active`, `ACTIVE`, `paused`, `Inactive` | Standardized `is_verified` to boolean (`True`/`False`) and status to canonical values (`ACTIVE`, `INACTIVE`, `PAUSED`). |
| **13** | **Skill Delimiters & Casing** | System 2 & 3 | `"n8n, LangChain, REST APIs"`, `"sql, mongodb, selenium"` | Split by commas, trimmed, standardized using a canonical skill map, and stored as individual rows. |

---

## 3. Stuck Log

### 1. Shifted Columns in System 3 (Row 19)
- **The Problem**: Row 19 of `system3_internal.csv` had misaligned columns—the skills were placed in the `email_id` column and the email was in `worker_name`. When loaded normally with pandas, the skill string was treated as the email address, breaking downstream lookups.
- **What I Searched**: `python csv detect shifted columns dynamically`, `pandas handle misaligned row schema`.
- **What I Asked AI**: *"How can I write a custom CSV parser that detects when an email column contains comma-separated skills and shifts the row back to the correct schema?"*
- **What AI Suggested & Why I Rejected It**: AI suggested sending every row to OpenAI's GPT-4 API to "clean and re-align" the data. **Why I rejected it**: Using an LLM API inside an ingestion loop adds high latency, monetary cost, potential API downtime, and non-deterministic behavior. A core data pipeline should be fast and deterministic.
- **How I Got Unstuck**: I wrote a deterministic rule in `pipeline/normalizers.py`. It checks if column 0 fails email regex while column 1 matches email regex. When that pattern is found, the parser automatically re-slices the row back into the proper schema.

---

### 2. Processing Browser-Recorded WebM Audio in Python
- **The Problem**: When recording in the browser, the MediaRecorder API produces `audio/webm` files. Python's built-in `wave` module cannot parse WebM containers and threw `wave.Error: file does not start with RIFF id`.
- **What I Searched**: `python extract loudness dbfs from webm without writing to disk`, `mutagen read webm duration sample rate`.
- **What I Asked AI**: *"How to calculate loudness in dBFS and sample rate from browser-recorded WebM files without requiring system-level ffmpeg binaries?"*
- **What AI Suggested & Why I Rejected It**: AI suggested using `subprocess.Popen` to call system `ffmpeg` binaries. **Why I rejected it**: Requiring FFmpeg means anyone running or evaluating the project must install system packages manually, which often fails in minimal Docker containers or different OS environments.
- **How I Got Unstuck**: I built a pure-Python extraction strategy in `audio_processor.py`. It uses the `mutagen` library to read container metadata (duration, sample rate, bitrate) across WebM, MP3, OGG, and WAV, paired with a byte-variance energy estimator for loudness (dBFS) and SNR calculation without any external binary dependencies.

---

### 3. Entity Deduplication for Common Names with Conflicting Salary Units
- **The Problem**: Common names (like two different people named *Arjun Mehta*) appeared in the data with different phone numbers. At the same time, System 2 listed salaries as mixed floats (`4.2`, `8.3`) alongside raw integers (`417964`, `806661`).
- **What I Searched**: `entity resolution deduplication without common id`, `standardize indian currency lpa vs ctc`.
- **What I Asked AI**: *"Should I merge records with the same name using Levenshtein distance if phone numbers differ?"*
- **What AI Suggested & Why I Rejected It**: AI suggested fuzzy-matching on candidate names with an 80% similarity threshold and merging them automatically. **Why I rejected it**: For common Indian names, this causes disastrous false merges. Merging two different people named "Arjun Mehta" corrupts their contact details, salaries, and work histories.
- **How I Got Unstuck**: I adopted a strict **Zero-False-Positive Policy**:
  1. Phone number is the primary anchor (normalized 10 digits).
  2. Email is the secondary anchor.
  3. Records sharing the same name but having different phone numbers/emails are strictly kept separate.
  4. For salary, I used a threshold heuristic: values $<100$ are recognized as LPA ($\times 100,000$) and larger values as raw annual INR.

---

## Task 1: Multi-Source Merge Pipeline

The goal of Task 1 was to take 3 separate, messy CSV files from different internal systems and combine them into one clean database without duplicate records.

### The Challenge
There is no shared primary key across the three systems:
- **System 1 (Recruitment)** has `Name`, `Phone Number`, `City`, `Verified`, and `Projects Completed`.
- **System 2 (CBNexus)** has `Full Name`, `Email`, `Phone`, `City`, `Experience (Years)`, `Current CTC`, `Applied Date`, and `Skills`.
- **System 3 (Internal Ops)** has `email_id`, `worker_name`, `rate`, `location`, `status`, and `skill_tags`.

### How I Solved It:
1. **Designed a Relational Schema (SQLAlchemy + SQLite)**:
   - `candidates`: Core identity (UUID, full name, primary phone, primary email, city, is_verified).
   - `candidate_emails`: Stores secondary/alias emails linked to a candidate so people who applied with multiple emails don't get duplicated.
   - `candidate_skills`: Normalizes comma-separated skill lists into separate rows for fast filtering.
   - `work_profiles`: Experience years, projects completed, application status, and applied dates.
   - `compensations`: Annual CTC in rupees, hourly rates, and monthly rates.
   - `ingestion_audit_logs`: Keeps an audit trail of every row ingested, what candidate it matched to, and what changes were made.

2. **Matching Strategy (Zero False Positives)**:
   - **Step 1 — Phone Match**: If a record has a phone number, check if that phone number exists in the database. Phone numbers are the most reliable identifier.
   - **Step 2 — Email Match**: If no phone match, check if the email exists (in either the primary email field or the alias emails table).
   - **Step 3 — Name Disambiguation**: I deliberately **do not** merge records based on name alone. Common Indian names (like the two different *Arjun Mehta* records in the dataset) share the same name but have completely different phone numbers and emails. Merging them would corrupt candidate histories.

3. **Non-Destructive Merging**:
   When an existing candidate is matched:
   - Abbreviated names like `"R. Verma"` get updated to the full name `"Rohit Verma"`.
   - New emails are added to the alias table.
   - Skill sets are combined without duplicates.
   - The highest project count is kept.

---

## Task 2: No-Code Automation Workflow (n8n)

The exported workflow file is located at [`automations/n8n_workflow.json`](automations/n8n_workflow.json).

```
[When clicking 'Test workflow'] ──┐
                                  ├──► [Format Candidate Payload] ──► [Check DB for Duplicate]
[Webhook: POST /candidate]      ──┘                                                │
                                                                                   ▼
                                                                        [Is Duplicate Candidate?]
                                                                           ├── True  ──► [Send Duplicate Alert to Slack]
                                                                           └── False ──► [AI Skill Categorization] ──► [Write Tagged DB] ──► [Send Success Alert]
```

### What the workflow does:
1. **Trigger**: Accepts incoming submissions either via an HTTP Webhook (`POST /candidate-submission`) or the manual "Test workflow" button.
2. **Payload Formatting**: Normalizes incoming fields (name, phone, email, skills, experience).
3. **Duplicate Check (Code Node)**: Checks whether the candidate's phone or email already exists in the database. I wrote this as a self-contained JavaScript code node so it runs reliably on both local n8n instances and n8n Cloud (without getting blocked by cloud SSRF rules).
4. **Conditional Routing**:
   - **If Duplicate**: Routes to a notification node that sends an alert with the existing candidate ID.
   - **If New Candidate**: Passes the profile to an AI skill categorization engine that tags the candidate based on their skill set:
     - `automation-heavy` (n8n, Zapier, Selenium, Web Scraping, Python)
     - `web-dev` (React, JavaScript, FastAPI, REST APIs)
     - `data-engineering` (SQL, MySQL, MongoDB, Pandas)
     - `ai-ml` (LangChain, LLMs, AI agents)
   - Saves the tagged candidate and dispatches a success alert.

---

## Task 3: Worker Audio Collection App

A full-stack web application built with FastAPI and plain JavaScript/CSS, designed for crowdsourced speech collection.

### Key Features:
- **Dual Submission Modes**: Gig workers can record audio live in the browser using their microphone, or drag and drop an existing audio file (`.wav`, `.mp3`, `.webm`, `.ogg`).
- **Real-Time Waveform Visualizer**: Uses the browser's Web Audio API (`AnalyserNode`) to draw a live audio waveform on an HTML5 canvas during recording.
- **Pure-Python Acoustic Feature Extraction** ([`audio_app/audio_processor.py`](audio_app/audio_processor.py)):
  - **Duration**: Extracted from audio container headers or calculated from WAV frame counts.
  - **Sample Rate (kHz)**: Sampling frequency (e.g., 44.1 kHz or 48.0 kHz).
  - **Bitrate (kbps)**: Data rate of the recording.
  - **Loudness in dBFS**: Calculated using Root-Mean-Square (RMS) amplitude relative to 16-bit digital full scale.
  - **Signal-to-Noise Ratio (SNR in dB)**: Estimated by dividing the audio into 50ms frames, comparing the 95th percentile frame energy (active speech) against the 5th percentile frame energy (background noise floor).
  - **Quality Score**: Composite grade (`Excellent (Studio/Clean)`, `Good (Acceptable Voice)`, `Fair`, or `Poor`).
- **Reviewer History Gallery**: A table displaying all past submissions with inline audio players, extracted acoustic parameters, quality grades, and a search filter.

---

## Task 5: Scaling to 5,000 Workers

### Scenario: Launching the Audio App to 5,000 Gig Workers Over a Weekend

### 1. What Breaks First on a Single Server?
1. **Synchronous Audio Processing Locks the CPU**: Calculating loudness, SNR, and reading raw audio buffers on the main web server thread blocks incoming requests. Under 50+ concurrent uploads, the server runs out of worker threads and returns `504 Gateway Timeout`.
2. **SQLite Database Write Locks**: SQLite locks the whole database file during write operations. Hundreds of workers submitting recordings simultaneously cause `OperationalError: database is locked` errors.
3. **Local Disk Runs Out**: 5,000 workers submitting 10 recordings of 5 MB each equals ~250 GB of raw audio. A single server's local disk will fill up, and data would be lost if the instance restarts.
4. **Server Bandwidth Gets Clogged**: Streaming multi-megabyte audio files through the application server exhausts network connections.

### 2. How to Redesign for Production Scale
- **Direct S3 Uploads via Presigned URLs**: The client asks the API for a temporary signed upload URL, then uploads the audio file directly to AWS S3 (or Cloudflare R2). The audio binary never passes through our application server, saving CPU and bandwidth.
- **Asynchronous Task Queue (SQS + Celery)**: When an upload completes in S3, an event is placed on an AWS SQS queue. Background Celery workers pick up jobs and calculate acoustic properties (loudness, SNR) asynchronously. The API returns `202 Accepted` immediately to the worker.
- **PostgreSQL with PgBouncer**: Replace SQLite with managed PostgreSQL (e.g., AWS RDS) using PgBouncer for connection pooling to handle thousands of concurrent read/write queries.
- **Redis Idempotency Guard**: Store a hash of `phone + audio_sha256` in Redis with a 5-minute expiration to prevent accidental double-submissions from flaky mobile networks.
- **Transcoding for Storage Savings**: Background workers transcode incoming audio to Opus format at 32 kbps, cutting storage and bandwidth costs by ~80% with zero loss in speech intelligibility.

---

## Automated Test Suite

Run the full pytest suite with:
```bash
pytest
```
*or `pytest tests/ -v`*

### Test Coverage:
- `test_phone_normalization`: Strips `+91`, `0`, and punctuation into standard 10-digit Indian numbers.
- `test_email_normalization`: Trims whitespace, lowercases, and validates RFC email format.
- `test_compensation_normalization`: Handles LPA floats, raw INR integers, hourly rates, and monthly rates.
- `test_shifted_row_cleaner`: Verifies detection and column realignment for corrupted System 3 row 19.
- `test_entity_deduplication`: Validates cross-file matching and non-destructive merging on an in-memory SQLite database.
- `test_audio_feature_extraction`: Generates a synthetic sine wave tone in RAM and validates duration, sample rate, bitrate, loudness (dBFS), and SNR calculation.
- `test_api_stats`, `test_duplicate_check_api`, `test_audio_submission_api`: Tests the FastAPI backend endpoints using `TestClient`.

---

*Thank you for reviewing my project!*
