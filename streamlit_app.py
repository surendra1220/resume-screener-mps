"""Community Cloud entry point. Reports belong to st.session_state, never a shared API cache."""
import json
import hashlib
import time
from pathlib import Path

import streamlit as st
from pydantic import ValidationError
from app.documents import extract, DocumentError, MAX_BYTES
from app.engine import analyze, parse_custom_jd, VERSION
from app.models import AnalyzeRequest, Requirement
from app.requirements import consolidate_requirements
from app.ui import stylesheet, section_heading, session_status, evidence_quote, empty_state
from app.scoring_ui import render_scoring_guide, render_evidence_summary
from app.reports import html_report, pdf_report, report_filename
from app.streamlit_support import DEMO_RESUME, editor_rows, reviewed_requirements, fingerprint, screening_scope, scope_description

ROOT = Path(__file__).resolve().parent
FORMATS = ['pdf', 'docx', 'doc', 'txt', 'md', 'rtf', 'odt', 'html', 'htm']
st.set_page_config(page_title='Proofpoint · Screening workspace', page_icon='◈', layout='wide')
st.markdown(stylesheet(), unsafe_allow_html=True)


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
    st.markdown('<div class="brand"><span class="brand-mark">p</span><div><div class="brand-name">proofpoint</div><div class="brand-subtitle">Hiring workspace</div></div></div>', unsafe_allow_html=True)
    st.markdown('**Appearance**')
    st.caption('Switch Light / Dark from the ⋮ menu at the top right. Your browser remembers your choice.')
    st.markdown('<div class="rail-label">WORKSPACE</div><nav class="rail-nav" aria-label="Workspace sections"><a href="#documents" target="_self"><span class="nav-symbol" aria-hidden="true">&#9639;</span>Documents</a><a href="#benchmark" target="_self"><span class="nav-symbol" aria-hidden="true">&#8801;</span>Requirements</a><a href="#results" target="_self"><span class="nav-symbol" aria-hidden="true">&#9678;</span>Screening results</a></nav>', unsafe_allow_html=True)
    status_slot = st.empty()
    st.markdown('<div class="rail-note"><strong>Evidence before assumptions.</strong>Every match connects a job requirement to supporting resume evidence.</div>', unsafe_allow_html=True)
    with st.expander('About your session'):
        st.caption('Documents are processed on the hosting server within your session. No candidate data is written to the repository or a shared report cache. Use documents you are authorized to process.')
        st.caption('PDF, Word and text documents · Up to 10 MB per file')
    if st.button('Clear session', width='stretch'):
        st.session_state.clear()
        st.rerun()

st.markdown('<div class="page-topline"><span>Workspace<span class="slash">/</span>Candidate screening</span><span class="page-badge">Human-reviewed decisions</span></div>', unsafe_allow_html=True)
st.title('Candidate screening')
st.markdown('<p class="page-description">A structured review, from job requirements to resume evidence.<br>Upload your documents, review the benchmark, and make an informed assessment.</p>', unsafe_allow_html=True)
st.markdown('<div class="workflow" aria-label="Screening workflow"><div class="workflow-item"><span class="workflow-index">01</span><div><strong>Add documents</strong><small>Job description & candidate resume</small></div></div><div class="workflow-item"><span class="workflow-index">02</span><div><strong>Review requirements</strong><small>Confirm the screening benchmark</small></div></div><div class="workflow-item"><span class="workflow-index">03</span><div><strong>Explore the evidence</strong><small>Assess gaps & export your report</small></div></div></div>', unsafe_allow_html=True)

with st.expander('How scoring and verdicts work'):
    render_scoring_guide()

if time.time() - st.session_state.get('report_time', time.time()) > 3600:
    clear_screening()

st.markdown('<div id="documents"></div>', unsafe_allow_html=True)
left, right = st.columns(2, gap='medium')
jd_text, originals, resume_text, approved = '', [], '', False
resume_file = None
try:
    with left, st.container(border=True, key='jd_card'):
        st.markdown(section_heading('JD', 'Job description', 'Define the role and the skills that matter.'), unsafe_allow_html=True)
        jd_mode = st.radio('Job description source', ['Default SDET JD', 'Upload a custom JD'], horizontal=True)
        if jd_mode == 'Default SDET JD':
            jd_text = (ROOT / 'data/default-jd.md').read_text()
            originals = json.loads((ROOT / 'data/default-requirements.json').read_text())
            originals = [r.model_dump() for r in consolidate_requirements([Requirement(**r) for r in originals])]
            jd_label = 'Default · SDET'
            st.success('SDET · 3–12 years · 13 mandatory requirements · 6 preferences')
            st.session_state.pop('jd_document', None)
        else:
            jd_file = st.file_uploader('Upload job description', type=FORMATS, key='jd_upload')
            if jd_file is not None:
                jd_text = read_upload(jd_file, 'jd_document')
                jd_label = jd_file.name
                originals = [r.model_dump() for r in parse_custom_jd(jd_text)]
                if not originals:
                    st.error('No draft requirements found. Upload a clearer job description.')
            else:
                st.caption('Choose a file to extract the role requirements.')
        if jd_text:
            with st.expander('Read job description'):
                st.text(jd_text)

    with right, st.container(border=True, key='resume_card'):
        st.markdown(section_heading('CV', 'Candidate resume', 'Add the experience you want to evaluate.'), unsafe_allow_html=True)
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

    if not originals:
        clear_screening()
        status_slot.markdown(session_status(False, bool(resume_text)), unsafe_allow_html=True)
        st.markdown('<div id="benchmark"></div>', unsafe_allow_html=True)
        st.markdown(empty_state('Your benchmark starts here', 'Add a job description to extract the skills, expectations and preferences for this role.'), unsafe_allow_html=True)
        st.markdown('<div id="results"></div>', unsafe_allow_html=True)
        st.stop()

    st.markdown('<div id="benchmark"></div>', unsafe_allow_html=True)
    with st.container(border=True, key='benchmark_card'):
        st.markdown(section_heading('02', 'Review the benchmark', 'Confirm what the candidate will be evaluated against.'), unsafe_allow_html=True)
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
        with st.expander('How to review the requirements'):
            st.caption('Equivalent skills/areas are consolidated into one row, retaining their source expectations and required conditions. Mandatory takes precedence when the same area is also listed as preferred. Check each expectation against the job description. Alternatives are comma-separated (OR). Required facets are semicolon-separated (AND); | means OR inside a facet. Editing default facets switches to literal matching.')
        st.caption('Use the Screen column to choose the skills/areas to assess. Select none to screen all requirements by default. Only assessed requirements affect the score, category coverage, evidence gaps and verdict.')
        edited = st.data_editor(editor_rows(originals), key='requirements_editor', num_rows='dynamic', hide_index=True, width='stretch', height=330,
            column_order=['selected', 'name', 'category', 'description', 'alternatives', 'all_of', 'knowledge_ok'],
            column_config={
                'selected': st.column_config.CheckboxColumn('Screen', default=False, help='Include this skill in screening. If no skills are checked, all requirements are screened.'),
                'id': None,
                'name': st.column_config.TextColumn('Skill / Area', required=True),
                'category': st.column_config.SelectboxColumn('Category', options=['Mandatory', 'Good to Have'], required=True),
                'weight': None,
                'description': st.column_config.TextColumn('Expectation from JD', required=True, width='large'),
                'alternatives': st.column_config.TextColumn('Accepted alternatives', width='large'),
                'all_of': st.column_config.TextColumn('Required facets', width='large'),
                'knowledge_ok': st.column_config.CheckboxColumn('JD accepts knowledge'),
            })
        assessed_rows, scope = screening_scope(edited)
        requirements = reviewed_requirements(assessed_rows, originals)
        merged_count = len(assessed_rows) - len(requirements)
        scope['total_count'] -= merged_count
        scope['assessed_count'] = len(requirements)
        if scope['mode'] == 'selected':
            st.info(f"{scope['assessed_count']} of {scope['total_count']} skills/areas selected for screening. {scope['excluded_count']} unselected requirements will be excluded.")
        else:
            st.caption(f"No skills selected: all {scope['total_count']} skills/areas will be screened by default.")
        benchmark = fingerprint(edited, scope, [r.model_dump() for r in requirements])
        if st.session_state.get('benchmark') != benchmark:
            st.session_state['benchmark'] = benchmark
            st.session_state['approval_revision'] = st.session_state.get('approval_revision', 0) + 1
            for key in list(st.session_state):
                if key.startswith('approve_requirements'):
                    del st.session_state[key]
        approved = st.checkbox('I have reviewed the requirements, alternatives, categories, and source JD.',
                               key=f"approve_requirements_{st.session_state['approval_revision']}")
        signature = fingerprint(jd_text, resume_text, benchmark, candidate_label, VERSION)
        if st.session_state.get('report_signature') != signature:
            clear_screening()

        status_slot.markdown(session_status(bool(jd_text), bool(resume_text), approved), unsafe_allow_html=True)
        if not resume_text or not approved:
            st.caption('Add a resume and confirm the benchmark to enable screening.')
        if st.button('Screen candidate →', type='primary', disabled=not resume_text or not approved, width='stretch'):
            with st.spinner('Reviewing project evidence and mandatory gaps…'):
                request = AnalyzeRequest(resume_text=resume_text, jd_text=jd_text, requirements=requirements,
                                         jd_label=jd_label, candidate_label=candidate_label,
                                         resume_filename=resume_file.name if resume_mode == 'Upload resume' else None)
                report = analyze(request)
                report['screening_scope'] = scope
                pdf = pdf_report(report)
                html = html_report(report)
                st.session_state.update(report=report, pdf_bytes=pdf, html_bytes=html,
                                        report_signature=signature, report_time=time.time())

except (DocumentError, ValidationError, ValueError) as exc:
    clear_screening()
    st.error(str(exc))
    st.stop()

st.markdown('<div id="results"></div>', unsafe_allow_html=True)
report = st.session_state.get('report')
if report:
    st.header('Screening results')
    st.caption(f"{report['candidate']} \u00b7 {report['jd_label']}")
    st.caption('Screening scope — ' + scope_description(report['screening_scope']))
    c1, c2, c3 = st.columns(3)
    c1.metric('Overall evidence coverage', f'{report["score"]:.1f} / 100',
              help='100 × (Matched count + 0.5 × Partial Match count) ÷ Total JD requirements. Every requirement counts equally.')
    c2.metric('Mandatory coverage', f'{report["scores"]["Mandatory"]}%' if report['scores']['Mandatory'] is not None else 'Not applicable',
              help='Coverage of mandatory requirements included in this screening scope. Unselected requirements are excluded.')
    c3.metric('Good-to-have coverage', f'{report["scores"]["Good to Have"]}%' if report['scores']['Good to Have'] is not None else 'Not applicable',
              help='Coverage of good-to-have requirements included in this screening scope. Missing evidence for an included requirement receives zero credit.')
    if report['scores']['Good to Have'] is None:
        st.caption('No good-to-have requirements in this screening scope. Good-to-have coverage is Not applicable.')
    elif report['scores']['Mandatory'] is None:
        st.caption('No mandatory requirements in this screening scope. Mandatory coverage is Not applicable.')
    st.caption('Overall coverage comes directly from evidence status counts. Mandatory and good-to-have coverage are shown separately and are not combined into the overall score.')
    render_evidence_summary(report['scoring'])
    if report['mandatory_gaps']:
        st.warning(report['recommendation'])
    else:
        st.success(report['recommendation'])
    with st.container(border=True, key='results_card'):
        title_col, pdf_col, html_col = st.columns([2, 1, 1], gap='small')
        title_col.markdown('**Candidate assessment**')
        title_col.caption(f"{len(report['requirements'])} requirements reviewed \u00b7 {len(report['mandatory_gaps'])} mandatory gaps")
        pdf_col.download_button('Download PDF report', st.session_state['pdf_bytes'], file_name=report_filename(report, 'pdf'), mime='application/pdf', width='stretch', on_click='ignore')
        html_col.download_button('Download HTML report', st.session_state['html_bytes'], file_name=report_filename(report, 'html'), mime='text/html', width='stretch', on_click='ignore')
        matrix_tab, interview_tab, method_tab = st.tabs(['Evidence matrix', 'Interview guide', 'Scoring & methodology'])
        with matrix_tab:
            f1, f2, f3 = st.columns([1, 1, 1.5])
            status = f1.selectbox('Evidence status', ['All statuses', *report['counts']])
            category = f2.selectbox('Requirement type', ['All requirements', *[c for c, coverage in report['scores'].items() if coverage is not None]])
            search = f3.text_input('Search requirements', placeholder='Search a skill or expectation...')
            rows = [r for r in report['requirements'] if (status == 'All statuses' or r['status'] == status)
                    and (category == 'All requirements' or r['category'] == category)
                    and (not search or search.casefold() in (r['name'] + ' ' + r['description']).casefold())]
            st.caption(f"Showing {len(rows)} of {len(report['requirements'])} requirements")
            if rows:
                st.dataframe([{'Skill / Area': r['name'], 'Expectation': r['description'], 'Type': r['category'], 'Status': r['status']} for r in rows], hide_index=True, width='stretch',
                    column_config={'Expectation': st.column_config.TextColumn(width='large')})
                selected = st.selectbox('Inspect a requirement', range(len(rows)), format_func=lambda i: rows[i]['name'])
                row = rows[selected]
                st.markdown('**' + row['status'] + '** \u00b7 ' + row['category'])
                st.text(row['description'])
                if row['evidence']:
                    for unit in row['evidence']:
                        source = f'{unit["section"]} \u00b7 Line {unit["line"]}' + (f' \u00b7 {unit["page"]}' if unit.get('page') else '')
                        st.markdown(evidence_quote(unit['quote'], source), unsafe_allow_html=True)
                else:
                    st.caption('No supporting excerpt found in the resume.')
                st.text(row['reason'])
            else:
                st.markdown(empty_state('No matching requirements', 'Try another status, requirement type or search term.'), unsafe_allow_html=True)
        with interview_tab:
            st.caption('Use these questions to verify experience and close evidence gaps.')
            for row in sorted(report['requirements'], key=lambda r: (r['status'] == 'Matched', r['category'] != 'Mandatory')):
                with st.expander(f'{row["name"]} \u00b7 {row["status"]}'):
                    st.text(row['question'])
                    st.text('JD expectation: ' + row['description'])
        with method_tab:
            render_scoring_guide(report)
            st.markdown('**How resume evidence is assessed**')
            st.write(report['method'])
            st.markdown('**Review limitations**')
            for note in report['limitations'] + report['document_warnings']:
                st.write('- ' + note)
            st.caption(f'Engine {report["engine_version"]} \u00b7 Report {report["id"]} \u00b7 Generated {report["generated_at"]}')
else:
    st.markdown(empty_state('Your next assessment, ready to begin', 'Add a resume and approve the benchmark above. Your score, supporting evidence and interview questions will appear here.'), unsafe_allow_html=True)
st.markdown('<footer class="workspace-footer"><span>Proofpoint \u00b7 Evidence-led resume screening</span><span>Resume claims require human verification.</span></footer>', unsafe_allow_html=True)
