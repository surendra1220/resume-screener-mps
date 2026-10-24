"""Presentation helpers. Escape all document-derived content before rendering HTML."""
from html import escape
from pathlib import Path

STYLE_PATH = Path(__file__).parent / 'static' / 'streamlit.css'


def stylesheet():
    return '<style>' + STYLE_PATH.read_text(encoding='utf-8') + '</style>'


def section_heading(number, title, description):
    return f'<div class="section-heading"><span class="step-number">{escape(str(number))}</span><div><h3>{escape(title)}</h3><p>{escape(description)}</p></div></div>'


def session_status(jd_ready, resume_ready, approved=False):
    items = [('Job description', jd_ready), ('Candidate resume', resume_ready), ('Benchmark reviewed', approved)]
    rows = ''.join(f'<div class="session-row"><span>{label}</span><span class="status-dot {"ready" if ready else "pending"}"><span class="sr-only">{"Ready" if ready else "Pending"}</span></span></div>' for label, ready in items)
    return '<div class="session-panel"><div class="rail-label">THIS SESSION</div>' + rows + '</div>'


def evidence_quote(quote, source):
    return f'<div class="evidence-quote">{escape(quote)}<span class="evidence-source">{escape(source)}</span></div>'


def empty_state(title, description):
    return f'<div class="empty-state"><span class="empty-icon" aria-hidden="true">◎</span><h3>{escape(title)}</h3><p>{escape(description)}</p></div>'
