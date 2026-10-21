import io
import json
from datetime import date
from pathlib import Path
from html import escape

import pytest
from pypdf import PdfReader
from app.engine import analyze
from app.models import AnalyzeRequest
from app.reports import audit_view, html_report, pdf_report, report_filename, SECTIONS

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def report():
    resume = '''SUMMARY:
Automation engineer with eight years of experience.
PROFESSIONAL EXPERIENCE:
Jan 2020 - Present
Designed a TypeScript Playwright framework for billing automation.
Automated UI regression tests across browser environments.
Worked on API testing using Postman for the billing platform.
TECHNICAL SKILLS:
Jira, Agile, Azure, TestComplete.
'''
    result = analyze(AnalyzeRequest(resume_text=resume, jd_text=(ROOT/'data/default-jd.md').read_text(),
        requirements=json.loads((ROOT/'data/default-requirements.json').read_text()),
        candidate_label='Example Candidate', resume_filename='Example Candidate.docx', jd_label='SDET 3–12 years'), date(2026, 9, 11))
    result['generated_at'] = '2026-09-11T23:45:00+00:00'
    return result


def test_reference_sections_and_actual_data_match_in_both_exports(report):
    markup = html_report(report)
    pdf = PdfReader(io.BytesIO(pdf_report(report)))
    text = ' '.join(page.extract_text() for page in pdf.pages)
    normalized = ' '.join(text.split())
    for section in SECTIONS:
        assert section in markup and section in normalized
    for value in ['Example Candidate', 'Example Candidate.docx', 'SDET 3–12 years', 'Matched', 'Partial Match', 'Claimed but Unevidenced', 'Missing']:
        assert escape(value) in markup and value in normalized
    assert '2026-09-12' in markup and '2026-09-12' in normalized
    assert 'RamprakashNallamala' not in markup + text
    assert 'No override applied.' in markup and 'No override applied.' in normalized
    assert 'Candidates Ranked: 1' in normalized
    for index, page in enumerate(pdf.pages, 1):
        assert f'Page {index}/{len(pdf.pages)}' in page.extract_text()
    assert SECTIONS[0] in pdf.pages[0].extract_text()
    assert SECTIONS[1] in pdf.pages[0].extract_text()


def test_arithmetic_uses_existing_scoring_not_reference_values(report):
    view = audit_view(report)
    assert [item['maximum'] for item in view['arithmetic']] == [80, 20]
    assert round(view['raw'], 1) == report['score']
    assert f"Final: {report['score']:.1f}/100" in view['breakdown']
    assert '6.8 yrs' in view['experience']
    assert '91.0/100' not in view['breakdown']


def test_single_category_normalizes_to_100(report):
    report['scores'] = {'Mandatory': 50, 'Good to Have': None}
    report['score'] = 50
    view = audit_view(report)
    assert view['arithmetic'] == [dict(category='Mandatory', coverage=50, maximum=100, earned=50)]


def test_all_evidence_and_reasoning_is_retained_and_html_escaped(report):
    report['candidate'] = '<script>alert("candidate")</script>'
    report['requirements'][0]['evidence'][0]['quote'] = '<img src=x onerror=alert(1)> Employment evidence & audit marker.'
    markup = html_report(report)
    reader = PdfReader(io.BytesIO(pdf_report(report)))
    text = ' '.join(page.extract_text() for page in reader.pages)
    assert '<script>alert' not in markup and '<img src=x' not in markup
    assert escape(report['candidate']) in markup
    for row in report['requirements']:
        assert escape(row['reason']) in markup
        assert escape(row['question']) in markup
        for evidence in row['evidence']:
            assert escape(evidence['quote']) in markup
    assert 'Employment evidence & audit marker.' in ' '.join(text.split())


def test_large_matrix_row_splits_without_losing_evidence(report):
    row = report['requirements'][0]
    row['description'] = 'Long expectation with required facets. ' * 40
    row['evidence'][0]['quote'] = ('Repeated detailed project evidence with deliverables and outcomes. ' * 150) + ' FINAL_EVIDENCE_MARKER'
    result = PdfReader(io.BytesIO(pdf_report(report)))
    assert len(result.pages) > 2
    normalized = ' '.join(' '.join(p.extract_text() for p in result.pages).split())
    assert 'FINAL_EVIDENCE_MARKER' in normalized
    assert SECTIONS[2] in normalized


def test_absent_experience_is_not_invented(report):
    report['requirements'] = [r for r in report['requirements'] if r['id'] != 'experience']
    assert audit_view(report)['experience'] == 'Not established'
    report.pop('screened_files')
    assert audit_view(report)['files'] == 'Not recorded'


def test_export_names_use_the_template_date(report):
    assert report_filename(report, 'pdf') == 'candidate_screening_report_2026-09-12.pdf'
    assert report_filename(report, 'html') == 'candidate_screening_report_2026-09-12.html'
