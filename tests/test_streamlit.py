import json
from pathlib import Path
import pytest
from types import SimpleNamespace
from streamlit.testing.v1 import AppTest
from app.streamlit_support import editor_rows, reviewed_requirements, fingerprint
from app.engine import VERSION

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('include_preferences', [False, True])
def test_jd_category_applicability_is_explained_in_results(monkeypatch, include_preferences):
    import streamlit as st
    jd = 'Must Have Skills:\nPython: Develop automated tests for the customer billing platform.'
    if include_preferences:
        jd += '\nNice to Haves:\nAWS: Experience running cloud environments.'
    resume = b'PROFESSIONAL EXPERIENCE:\nDeveloped Python automation tests for the customer billing platform.'
    def upload(label, **kwargs):
        data = jd.encode() if kwargs.get('key') == 'jd_upload' else resume
        return SimpleNamespace(name='synthetic.txt', getvalue=lambda: data)
    monkeypatch.setattr(st, 'file_uploader', upload)
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    assert any(e.label == 'How scoring and verdicts work' for e in app.expander)
    app.radio[0].set_value('Upload a custom JD').run()
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    assert not app.exception
    expected = '0.0%' if include_preferences else 'Not applicable'
    assert next(m for m in app.metric if m.label == 'Good-to-have coverage').value == expected
    assert app.session_state['report']['score'] == (80 if include_preferences else 100)
    formulas = [m.value for m in app.markdown]
    expected_formula = 'Final score = (100 × 80%) + (0 × 20%) = 80.0/100' if include_preferences else 'Final score = (100 × 100%) = 100.0/100'
    assert any(expected_formula in s for s in formulas)
    options = next(s for s in app.selectbox if s.label == 'Requirement type').options
    assert ('Good to Have' in options) == include_preferences
    if not include_preferences:
        assert any('No good-to-have requirements in this JD' in c.value for c in app.caption)
    assert any('Every mandatory requirement is Matched' in m.value for m in app.markdown)


def test_custom_upload_uses_extracted_expectations_in_ui_and_report(monkeypatch):
    import streamlit as st
    jd = b'Job Description\nMust Have Skills:\nPython: Develop automated tests for the billing platform.\nNice to Haves:\nAWS: Experience running cloud environments.'
    resume = b'PROFESSIONAL EXPERIENCE:\nDeveloped Python automation for the billing platform.\nUsed AWS to provision cloud test environments.'
    def upload(label, **kwargs):
        data = jd if kwargs.get('key') == 'jd_upload' else resume
        return SimpleNamespace(name='synthetic.txt', getvalue=lambda: data)
    monkeypatch.setattr(st, 'file_uploader', upload)
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    app.radio[0].set_value('Upload a custom JD').run()
    assert not app.exception
    assert any('2 requirements: 1 mandatory and 1 preferences' in c.value for c in app.caption)
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    assert not app.exception
    report = app.session_state['report']
    assert report['engine_version'] == VERSION and report['score'] == 100
    assert [r['name'] for r in report['requirements']] == ['Python', 'AWS']
    assert report['requirements'][1]['category'] == 'Good to Have'
    assert report['requirements'][0]['description'] in app.session_state['html_bytes']


def test_default_roundtrip_preserves_matching_rules():
    originals = json.loads((ROOT / 'data/default-requirements.json').read_text())
    reviewed = reviewed_requirements(editor_rows(originals), originals)
    assert [r.model_dump() for r in reviewed] == originals


def test_facet_edits_switch_to_literal_rules():
    originals = json.loads((ROOT / 'data/default-requirements.json').read_text())
    rows = editor_rows(originals)
    index = next(i for i, r in enumerate(rows) if r['id'] == 'ui')
    rows[index]['all_of'] = 'UI; SpecFlow'
    reviewed = reviewed_requirements(rows, originals)
    assert reviewed[index].id.startswith('custom-edited-')
    assert reviewed[index].all_of == ['UI', 'SpecFlow']


def test_empty_terms_fail_closed():
    with pytest.raises(ValueError, match='accepted skill term'):
        reviewed_requirements([dict(name='Python', category='Mandatory', description='Python required', alternatives='', all_of='', weight=1)], [])


def test_streamlit_demo_generates_reports_and_isolates_sessions():
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    assert not app.exception
    app.radio[1].set_value('Try synthetic demo').run()
    assert not app.exception
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    assert not app.exception
    assert 'report' in app.session_state
    assert app.session_state['pdf_bytes'].startswith(b'%PDF')
    assert '<!doctype html>' in app.session_state['html_bytes']
    assert app.session_state['report']['candidate'] == 'Alex Morgan · synthetic demo'
    other = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    assert 'report' not in other.session_state
    app.radio[1].set_value('Upload resume').run()
    assert 'report' not in app.session_state


def test_clear_session_removes_candidate_data():
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    app.radio[1].set_value('Try synthetic demo').run()
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    next(b for b in app.button if b.label == 'Clear session').click().run()
    assert 'report' not in app.session_state
    assert 'pdf_bytes' not in app.session_state
    assert 'resume_document' not in app.session_state
    assert not app.exception


def test_missing_custom_jd_keeps_both_document_panels_available():
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    app.radio[0].set_value('Upload a custom JD').run()
    assert not app.exception
    assert len(app.radio) == 2
    assert app.radio[1].label == 'Candidate source'
    assert 'report' not in app.session_state
    assert any('Your benchmark starts here' in m.value for m in app.markdown)


def test_results_search_filters_and_interview_tabs():
    app = AppTest.from_file(str(ROOT / 'streamlit_app.py')).run(timeout=30)
    app.radio[1].set_value('Try synthetic demo').run()
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    original_score = app.session_state['report']['score']
    assert [t.label for t in app.tabs] == ['Evidence matrix', 'Interview guide', 'Scoring & methodology']
    app.text_input[0].set_value('no-such-competency').run()
    assert any('No matching requirements' in m.value for m in app.markdown)
    app.text_input[0].set_value('Python').run()
    assert any('Showing 1 of 19 requirements' in c.value for c in app.caption)
    next(s for s in app.selectbox if s.label == 'Requirement type').set_value('Good to Have').run()
    assert any('Showing 0 of 19 requirements' in c.value for c in app.caption)
    assert app.session_state['report']['score'] == original_score
    assert not app.exception


@pytest.mark.parametrize('has_gaps', [False, True])
def test_verdict_does_not_render_internal_objects_with_magic_enabled(monkeypatch, has_gaps):
    """Run the actual UI through the same magic AST transform used by the hosted runner."""
    import ast
    from streamlit.runtime.scriptrunner.magic import add_magic
    from app.streamlit_support import DEMO_RESUME
    resume = 'PROFESSIONAL EXPERIENCE:\nDeveloped Python automation tests for a billing platform.' if has_gaps else DEMO_RESUME.replace('Python automation frameworks', 'a Python automation framework')
    monkeypatch.setattr('app.streamlit_support.DEMO_RESUME', resume)
    source = (ROOT / 'streamlit_app.py').read_text().replace(
        'ROOT = Path(__file__).resolve().parent', f'ROOT = Path({str(ROOT)!r})')
    transformed = ast.unparse(add_magic(source, str(ROOT / 'streamlit_app.py')))
    app = AppTest.from_string(transformed).run(timeout=30)
    app.radio[1].set_value('Try synthetic demo').run()
    app.checkbox[0].check().run()
    next(b for b in app.button if b.label == 'Screen candidate →').click().run(timeout=30)
    assert not app.exception
    assert bool(app.session_state['report']['mandatory_gaps']) == has_gaps
    assert not app.get('help_info'), 'Streamlit must not render DeltaGenerator documentation.'
    assert len(app.get('download_button')) == 2
    assert app.session_state['pdf_bytes'].startswith(b'%PDF')
    assert '<!doctype html>' in app.session_state['html_bytes']
    assert app.session_state['report']['recommendation'] in [x.value for x in [*app.warning, *app.success]]
