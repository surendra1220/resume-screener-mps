# Proofpoint — evidence-led resume screening

A local, single-user screening application with a curated default SDET job description, editable custom JD requirements, project-level evidence, transparent scores, interview questions, and downloadable HTML/PDF reports.

The Streamlit workspace uses a shadcn/ui-inspired neutral design: a section navigation sidebar, session readiness indicators, document cards, a benchmark editor and a results dashboard. Results include searchable evidence with status/category filters, a requirement inspector, interview questions and scoring methodology. The layout adapts to mobile screens. Presentation styles live in `app/static/streamlit.css`, with escaped HTML helpers in `app/ui.py`; screening logic remains shared with FastAPI.

Open **How scoring and verdicts work** above the document cards for the formulas, evidence credits and verdict rules. After screening, **Scoring & methodology** also shows the actual earned/possible weights, category allocations, score equation and verdict explanation. Good-to-have coverage is **Not applicable** when the reviewed JD has no preferred requirements; mandatory coverage then supplies 100% of the score. If the JD includes preferred requirements, missing resume evidence receives zero credit and the category still counts. Category applicability never depends on which skills happen to match the resume. Engine arithmetic and its explanation share `app/scoring.py`.

### Custom JD extraction and evidence scoring

Engine 2.0 extracts source-grounded competencies instead of treating capitalized words as skills. Headings, job metadata and reporting relationships do not score. Each matrix expectation retains the JD wording. Explicit preferences (including “added advantage” and “Nice to Haves”) and optional parentheticals are classified separately. Repeated identical requirements are deduplicated; complex JDs exceeding the supported limits raise a review error rather than silently dropping requirements.

Accepted aliases are OR alternatives **within** an AND facet. Local OR lists and example tools do not replace another clause's conditions. Review comma-separated tool lists where the JD does not say whether all tools or any tool is required. Familiarity/exposure requirements accept explicit claims only when their facets are covered. Other skills need action in work context; custom facets can span statements in one role, with exact source excerpts. Education does not need an action verb. A total employment timeline alone does not establish skill-specific tenure.

The shared parser and scorer run in both FastAPI and Streamlit. The Streamlit benchmark shows the extracted Skill / Area, source Expectation, category, alternatives and required facets before approval. Engine changes invalidate session benchmarks and reports. Scores remain a weighted percentage from 0 to 100; they are never adjusted to reach a desired candidate score.

This remains a local rules engine with a vocabulary for common technologies and competencies and a content-phrase fallback for unfamiliar domains. It does not provide universal semantic understanding: reviewers must check omitted conditions, aliases, education equivalence and ambiguous lists against the source before screening. Document instructions are treated as data and excluded from scoring.

**Streamlit hosting:** A separate session-isolated Streamlit interface is available in `streamlit_app.py`. See [STREAMLIT_DEPLOY.md](STREAMLIT_DEPLOY.md) for Community Cloud settings and hosted data-handling details. The local-server deployment limits described below apply to the original FastAPI surface.

## Run locally

Python 3.12+ is recommended. No API key or external AI service is required.

```bash
git clone https://github.com/surendra1220/resume-screener-mps.git
cd resume-screener-mps
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open **http://localhost:8000**. Alternatively run `./run.sh`, or `powershell -ExecutionPolicy Bypass -File run.ps1` on Windows.

Legacy `.doc` requires the **antiword** executable: on Ubuntu/Debian, `sudo apt-get install antiword`; on macOS, `brew install antiword`. Set `ANTIWORD_BIN` if it is not on PATH. On systems without antiword, save the document as DOCX or PDF. The Docker image includes antiword.

```bash
docker compose up --build
```

Docker binds only to `127.0.0.1:8000` on the host. Containers are non-root and read-only except for a bounded `/tmp`. No uploaded files or reports are persisted.

## Workflow

1. Keep **Use default JD** selected, or upload a custom job description.
2. Review the requirement matrix. Custom extraction is a draft: confirm every requirement, category, accepted alternative, and required facet; add omitted conditions or remove non-requirement prose.
3. Upload a resume and optionally review/correct extracted text.
4. Run screening. Expand a skill row for exact evidence, section/line references, the JD rule, reasoning, and an interview question.
5. Download the HTML and PDF reports. Editing the resume or requirements invalidates the previous result.

Supported inputs: text-based PDF, DOCX, legacy DOC with antiword, UTF-8 TXT/Markdown/HTML/RTF, and ODT. Limits: 10 MB per file; 100 PDF pages; 120,000 extracted characters; bounded archive expansion. Scanned PDFs need OCR first. Unlocked documents only. Unsupported or malformed formats return an actionable error rather than an empty assessment.

## Report layout

PDF and HTML exports follow the supplied audit-report reference: **Candidate Ranking Leaderboard**, **4-Tier Evidence Gap Matrix**, and **Detailed Candidate Arithmetic & Verdicts**. Both show the screened filename, active JD, actual experience evidence, unresolved mandatory skills, exact resume excerpts, and the same scoring arithmetic. The navy header, blue headings, amber matrix borders, and takeaway panel mirror the reference structure. Long text wraps; PDF table headers repeat on continuation pages with Page n/N footers. Dates and date-based export filenames use IST.

The layout does not import the reference candidate, score, or claims. Existing 80/20 scoring and mandatory gates are preserved; no override is invented. The leaderboard contains the single candidate in the current screening. Detailed reasoning, interview checks, limitations, and document fingerprints remain in the report.

## What the screening agent does

This version is a **conservative local evidence-rules engine**, not an LLM. It uses document structure, work/project sections, action statements, accepted alternatives, required facets, explicit negation, and a curated interpretation of the supplied JD. It can miss paraphrases and unusual resume layouts. Custom paragraph parsing provides reviewable drafts rather than silently claiming semantic understanding. A human must approve custom requirements before screening in the UI.

- **Matched**: work/project evidence describes an action using the skill and meets the required facets. Where the JD explicitly permits knowledge/minimal experience, an explicit knowledge/usage claim may qualify; the reason states this exception.
- **Partial Match**: related work/project evidence exists but does not cover every required facet.
- **Claimed but Unevidenced**: a skill is listed or claimed without a concrete work/project action.
- **Missing**: no positive evidence found; this does not establish that the candidate lacks the skill.

One exact evidence unit must meet all facets: the engine does not combine unrelated claims across employers to fabricate a complete match. General skills lists and summaries cannot establish project usage. Excerpts are copied from the extracted text; reports never invent supporting quotes. Document content is data, never executable agent instructions. Instruction-like text is excluded from evidence and flagged. Negative claims are not credited.

**Score:** Matched = 1; Partial = 0.5; Claimed/Missing = 0. Within each category: `100 × sum(credit × weight) / sum(weight)`. Overall: 80% mandatory + 20% good-to-have, normalized if a category is absent. Every mandatory requirement must be Matched for a suitable verdict. Mandatory coverage below 40% produces insufficient documented fit; other unresolved mandatory gaps produce conditional fit. The score measures **documented evidence coverage**, not a calibrated hiring probability.

The default JD has 13 mandatory requirements and 6 preferences (including its Healthcare preference). Important interpretations:

- Life Sciences/Pharma/Clinical/Regulatory/Foundry project experience is mandatory; Healthcare is a separate preference.
- JavaScript, TypeScript, or Python is sufficient; Java alone does not satisfy that language requirement.
- Playwright, Cypress, Pytest, or Selenium is sufficient because the JD explicitly permits alternatives despite emphasizing Playwright.
- UI testing alone is partial where BDD is required.
- Building AI-assisted test generation is related evidence; it does not establish testing an AI-powered product or using MCP automation.
- Agentic knowledge/minimal experience is explicitly permitted by the JD.
- Total employment tenure uses the union of month-level employment ranges, with overlaps counted once; it never implies skill-specific tenure. Numeric-only dates or unusual layouts can require manual review.

## Privacy and deployment scope

The app makes no external model requests. Extracted documents live in browser memory while the page is open and request memory during processing; only job-related report excerpts remain in a bounded in-process report cache (maximum 50). Reports expire after one hour; background cleanup runs every minute. Restarting the server clears reports. Downloaded files are retained by the user. Report URLs use random 128-bit capabilities; do not share them with unauthorized people.

Names, contact details, age, nationality, marital status, passport details, and other personal attributes do not contribute to the rubric. Candidate labels appear only as report titles. A report scores resume evidence and is **not independent verification** of the candidate's ability, project outcomes, or credentials. Hiring decisions remain with the reviewer.

This release is hardened for **local, single-user use**: bounded files and requests, input validation, archive expansion limits, extraction concurrency limits, time-bounded legacy DOC conversion, rate limiting, escaped exports, same-origin POST checks, CSP, no external resources, and no document body logging. It is not a multi-tenant hosted service. Keep it on loopback. If deploying for multiple users, add authenticated user/session isolation, HTTPS, a shared report store with ownership checks, organization retention policies, and adversarial parser isolation before exposing it. Run one application worker because report state is process-local.

The supplied candidate resume, private report, contact information, screenshots, and downloaded binaries are excluded from Git. The default JD is bundled because it is the requested fallback.

## Development and verification

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover evidence vs keyword claims, alternatives, BDD facets, healthcare/domain separation, AI-testing distinctions, negation, instruction-like document text, overlapping dates, scoring gates, source quote fidelity, custom JD categories, literal facet safety, DOCX/table extraction, PDF round-trips, XSS escaping, upload errors, origin checks, and report downloads. Browser smoke tests use Playwright with system Chromium (see `tests/browser_smoke.py`). CI runs the Python checks.

```bash
python tests/browser_smoke.py  # app must be running; Chromium must be installed
```

Files: `app/engine.py` evidence rubric; `app/documents.py` extraction; `app/main.py` API and lifecycle; `app/reports.py` HTML/PDF; `app/static/` UI; `data/default-*` curated default JD; `tests/` regression checks.

For a private local demonstration, generate a report JSON with `app.engine.analyze` and set `REFERENCE_REPORT_PATH` to that file before starting the server. This enables **View attached sample screening**; the JSON is loaded only from the server operator's configured path and is never bundled in Git. Do not enable this on a shared deployment.
