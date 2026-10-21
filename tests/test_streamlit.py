import json
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from app.streamlit_support import editor_rows, reviewed_requirements, fingerprint

ROOT = Path(__file__).resolve().parents[1]


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
