"""Community Cloud entry point. Reports belong to st.session_state, never a shared API cache."""
import json
import hashlib
import time
from pathlib import Path

import streamlit as st
from pydantic import ValidationError
from app.documents import extract, DocumentError, MAX_BYTES
from app.engine import analyze, parse_custom_jd, VERSION
from app.models import AnalyzeRequest
from app.reports import html_report, pdf_report, report_filename
from app.streamlit_support import DEMO_RESUME, editor_rows, reviewed_requirements, fingerprint

ROOT = Path(__file__).resolve().parent
FORMATS = ['pdf', 'docx', 'doc', 'txt', 'md', 'rtf', 'odt', 'html', 'htm']
st.set_page_config(page_title='Proofpoint · Resume screening', page_icon='🌿', layout='wide')
st.markdown('''<style>
.stApp {background:#f7f8f4} h1,h2,h3 {color:#214b3c}
[data-testid="stSidebar"] {background:#eaf0e5}
.block-container {max-width:1250px;padding-top:2.7rem}
[data-testid="stMetric"] {background:white;border:1px solid #e0e7da;border-radius:12px;padding:20px}
.eyebrow {color:#63815d;letter-spacing:2px;font-size:11px;font-weight:600}
</style>''', unsafe_allow_html=True)


def clear_screening():
    for key in ('report', 'report_signature', 'report_time', 'pdf_bytes', 'html_bytes'):
        st.session_state.pop(key, None)


def read_upload(upload, key):
    data = upload.getvalue()
    if len(data) > MAX_BYTES:
        raise DocumentError('Upload a document no larger than 10 MB.')
    signature = fingerprint(upload.name, hashlib.sha256(data).hexdigest())
    previous = st.session_state.get(key)
    if not previous or previous['signature'] != signature:
        text = extract(upload.name, data)
        st.session_state[key] = {'signature': signature, 'text': text}
    return st.session_state[key]['text']


with st.sidebar:
    st.title('proofpoint.')
    st.caption('EVIDENCE-LED HIRING')
    st.divider()
    st.markdown('**A reason behind every match.**')
    st.write('Separate project evidence from claims, review mandatory gaps, and export a clear report.')
    st.divider()
    st.caption('No external AI calls. Uploaded documents are processed on the hosting server within your session. No candidate data is written to the repository or a shared report cache.')
    if st.button('Clear session', width='stretch'):
        st.session_state.clear()
        st.rerun()
    st.caption('Public app access does not make your report public. Downloaded reports remain on your device. Use only documents you are authorized to process.')

st.markdown('<div class="eyebrow">HIRING, WITH EVIDENCE</div>', unsafe_allow_html=True)
st.title('A clearer view of every candidate.')
st.write('Go beyond keywords. See what the resume actually supports.')
st.caption('Local evidence rules · Human-reviewed decisions · HTML & PDF reports')

if time.time() - st.session_state.get('report_time', time.time()) > 3600:
    clear_screening()

left, right = st.columns(2, gap='large')
try:
    with left:
        st.subheader('1. Job description')
        jd_mode = st.radio('Job description source', ['Default SDET JD', 'Upload a custom JD'], horizontal=True)
        if jd_mode == 'Default SDET JD':
            jd_text = (ROOT / 'data/default-jd.md').read_text()
            originals = json.loads((ROOT / 'data/default-requirements.json').read_text())
            jd_label = 'Default · SDET'
            st.success('SDET · 3–12 years · 13 mandatory requirements · 6 preferences')
            st.session_state.pop('jd_document', None)
        else:
            jd_file = st.file_uploader('Upload job description', type=FORMATS, key='jd_upload')
            if jd_file is None:
                clear_screening()
                st.info('Upload a job description to continue.')
                st.stop()
            jd_text = read_upload(jd_file, 'jd_document')
            jd_label = jd_file.name
            originals = [r.model_dump() for r in parse_custom_jd(jd_text)]
            if not originals:
                clear_screening()
                st.error('No draft requirements found. Upload a clearer job description.')
                st.stop()
        with st.expander('Read job description'):
            st.text(jd_text)

    with right:
        st.subheader('2. Candidate resume')
        resume_mode = st.radio('Candidate source', ['Upload resume', 'Try synthetic demo'], horizontal=True)
        resume_text, candidate_label = '', ''
        if resume_mode == 'Try synthetic demo':
            resume_text, candidate_label = DEMO_RESUME, 'Alex Morgan · synthetic demo'
            st.info('Fictional demonstration data. No real candidate information is included.')
            st.session_state.pop('resume_document', None)
        else:
            resume_file = st.file_uploader('Upload candidate resume', type=FORMATS, key='resume_upload')
            if resume_file:
                resume_text = read_upload(resume_file, 'resume_document')
                candidate_label = Path(resume_file.name).stem
                st.success(f'{len(resume_text):,} characters extracted')
        if resume_text:
            text_key = 'resume_text_' + fingerprint(resume_text)[:12]
            # Keep only the current editable document, not an accumulating history.
            for key in list(st.session_state):
                if key.startswith('resume_text_') and key != text_key:
                    del st.session_state[key]
            with st.expander('Review / correct extracted resume text'):
                resume_text = st.text_area('Extracted resume text', resume_text, height=280, key=text_key, max_chars=120000)

    st.subheader('3. Review the benchmark')
    source_key = fingerprint(jd_text, VERSION)
    if st.session_state.get('jd_source_key') != source_key:
        st.session_state.pop('requirements_editor', None)
        st.session_state.pop('approve_requirements', None)
        st.session_state['jd_source_key'] = source_key
        clear_screening()
    if jd_mode != 'Default SDET JD':
        st.warning('Custom extraction is a draft. Check categories, alternatives, required facets, and omitted conditions before approving.')
        mandatory = sum(r['category'] == 'Mandatory' for r in originals)
        st.caption(f"Extracted {len(originals)} requirements: {mandatory} mandatory and {len(originals)-mandatory} preferences. Engine {VERSION}. Each expectation retains its source JD wording.")
        with st.expander('Inspect extracted expectations and source wording'):
            for requirement in originals:
                st.text(f"{requirement['name']} · {requirement['category']}")
                st.text(requirement['source'])
    st.caption('Alternatives are comma-separated (OR). Required facets are semicolon-separated (AND); | means OR inside a facet. Default facets use audited rules; editing them switches to literal matching.')
    edited = st.data_editor(editor_rows(originals), key='requirements_editor', num_rows='dynamic', hide_index=True, width='stretch',
        column_config={
            'id': None,
            'name': st.column_config.TextColumn('Skill / Area', required=True),
            'category': st.column_config.SelectboxColumn('Category', options=['Mandatory', 'Good to Have'], required=True),
            'weight': st.column_config.NumberColumn('Weight', min_value=1, max_value=10, step=1, required=True),
            'description': st.column_config.TextColumn('Expectation from JD', required=True, width='large'),
            'alternatives': st.column_config.TextColumn('Accepted alternatives', width='large'),
            'all_of': st.column_config.TextColumn('Required facets', width='large'),
            'knowledge_ok': st.column_config.CheckboxColumn('JD accepts knowledge'),
        })
    requirements = reviewed_requirements(edited, originals)
    benchmark = fingerprint([r.model_dump() for r in requirements])
    if st.session_state.get('benchmark') != benchmark:
        st.session_state['benchmark'] = benchmark
        st.session_state.pop('approve_requirements', None)
    approved = st.checkbox('I have reviewed the requirements, alternatives, categories, and source JD.', key='approve_requirements')
    signature = fingerprint(jd_text, resume_text, benchmark, candidate_label, VERSION)
    if st.session_state.get('report_signature') != signature:
        clear_screening()

    if st.button('Screen candidate →', type='primary', disabled=not resume_text or not approved, width='stretch'):
        with st.spinner('Reviewing project evidence and mandatory gaps…'):
            request = AnalyzeRequest(resume_text=resume_text, jd_text=jd_text, requirements=requirements,
                                     jd_label=jd_label, candidate_label=candidate_label,
                                     resume_filename=resume_file.name if resume_mode == 'Upload resume' else None)
            report = analyze(request)
            pdf = pdf_report(report)
            html = html_report(report)
            st.session_state.update(report=report, pdf_bytes=pdf, html_bytes=html,
                                    report_signature=signature, report_time=time.time())

except (DocumentError, ValidationError, ValueError) as exc:
    clear_screening()
    st.error(str(exc))
    st.stop()

report = st.session_state.get('report')
if report:
    st.divider()
    st.subheader(f'Screening report · {report["candidate"]}')
    c1, c2, c3 = st.columns(3)
    c1.metric('Evidence coverage', f'{report["score"]:.1f} / 100')
    c2.metric('Mandatory coverage', f'{report["scores"]["Mandatory"]}%' if report['scores']['Mandatory'] is not None else 'N/A')
    c3.metric('Good-to-have coverage', f'{report["scores"]["Good to Have"]}%' if report['scores']['Good to Have'] is not None else 'N/A')
    if report['mandatory_gaps']:
        st.warning(report['recommendation'])
    else:
        st.success(report['recommendation'])
    if report['mandatory_gaps']:
        st.write('**Mandatory evidence gaps:** ' + '; '.join(report['mandatory_gaps']))
    d1, d2 = st.columns(2)
    d1.download_button('Download PDF report', st.session_state['pdf_bytes'], file_name=report_filename(report, 'pdf'), mime='application/pdf', width='stretch', on_click='ignore')
    d2.download_button('Download HTML report', st.session_state['html_bytes'], file_name=report_filename(report, 'html'), mime='text/html', width='stretch', on_click='ignore')
    st.subheader('Skill-by-skill evidence')
    status = st.selectbox('Filter status', ['All statuses', *report['counts']])
    for row in report['requirements']:
        if status != 'All statuses' and status != row['status']:
            continue
        with st.expander(f'{row["name"]} · {row["status"]} · {row["category"]}'):
            st.text('JD: ' + row['description'])
            for unit in row['evidence']:
                st.text('“' + unit['quote'] + '”')
                st.caption(f'{unit["section"]} · Line {unit["line"]}')
            if not row['evidence']:
                st.caption('No supporting excerpt found.')
            st.write(row['reason'])
            st.text('Interview question: ' + row['question'])
    with st.expander('Scoring method & limitations'):
        st.write(report['method'])
        for note in report['limitations'] + report['document_warnings']:
            st.write('• ' + note)
        st.caption(f'Engine {report["engine_version"]} · Report {report["id"]} · Generated {report["generated_at"]}')
else:
    st.info('Add a resume, review the benchmark, and screen the candidate to see project-backed matches and evidence gaps.')
st.caption('This is a conservative local evidence-rules engine, not independent verification or an LLM. Custom JD drafts and resume claims require human review.')
