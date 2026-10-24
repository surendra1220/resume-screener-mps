"""Reference-style audit exports with one shared presentation model for HTML and PDF."""
import html
import io
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas
from .scoring import calculate_scoring, CREDITS
from .streamlit_support import scope_description

FONT_DIR = Path(__file__).parent / 'static/fonts'
for name, filename in [('OpenSans', 'OpenSans-Regular.ttf'), ('OpenSans-Bold', 'OpenSans-Bold.ttf'), ('OpenSans-Italic', 'OpenSans-Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily('OpenSans', normal='OpenSans', bold='OpenSans-Bold', italic='OpenSans-Italic', boldItalic='OpenSans-Bold')

BANNER = 'AI CANDIDATE SCREENER | EVIDENCE-DRIVEN ATS AUDIT REPORT'
SECTIONS = ('1) Candidate Ranking Leaderboard', '2) 4-Tier Evidence Gap Matrix', '3) Detailed Candidate Arithmetic & Verdicts')
STATUS_COLORS = {'Matched': '#15803d', 'Partial Match': '#a16207', 'Claimed but Unevidenced': '#475569', 'Missing': '#dc2626'}
IST = timezone(timedelta(hours=5, minutes=30))


def esc(value):
    return html.escape(str(value), quote=True)


def audit_view(report):
    """Map current results into the reference layout without changing scores or importing example data."""
    stamp = datetime.fromisoformat(report['generated_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(IST)
    scoring = calculate_scoring(report['requirements'])
    arithmetic = [dict(status=status, count=scoring['counts'][status], credit=credit,
                       earned=scoring['counts'][status] * credit) for status, credit in CREDITS.items()]
    raw = scoring['raw_score']
    terms = ' + '.join(f"{row['status']} {row['count']} × {row['credit']:g}" for row in arithmetic)
    breakdown = f"100 × ({terms}) ÷ {scoring['total_requirements']} requirements → Raw: {raw:.2f}/100 → Final: {report['score']:.1f}/100. Category coverage is separate."
    diagnostics = '; '.join(f"{category}: {coverage:g}%" if coverage is not None else f"{category}: Not applicable" for category, coverage in report['scores'].items())
    breakdown += ' Separate category diagnostics (not used in overall): ' + diagnostics + '.'
    experience = 'Not established'
    exp_row = next((r for r in report['requirements'] if r['id'] == 'experience' or r['id'].startswith('custom-experience-')), None)
    if exp_row:
        match = re.search(r'approximately (\d+(?:\.\d+)?) years', exp_row['reason'])
        if match:
            experience = match.group(1) + ' yrs (employment timeline)'
    unresolved = '; '.join(report['mandatory_gaps']) or 'None'
    decision = 'No override applied. Mandatory evidence gaps remain unresolved; the mandatory gate is enforced.' if report['mandatory_gaps'] else 'No override applied. All mandatory requirements match resume evidence; independent verification is still required.'
    counts = ' · '.join(f'{key}: {value}' for key, value in report['counts'].items())
    return {'date': stamp.date().isoformat(), 'generated': stamp.strftime('%Y-%m-%d %H:%M IST'),
            'files': ', '.join(report.get('screened_files') or ['Not recorded']), 'experience': experience,
            'unresolved': unresolved, 'decision': decision, 'counts': counts, 'breakdown': breakdown,
            'arithmetic': arithmetic, 'raw': raw,
            'scope': scope_description(report['screening_scope']) if report.get('screening_scope') else f"All {len(report['requirements'])} requirements supplied for screening."}


def report_filename(report, format):
    if format not in ('pdf', 'html'):
        raise ValueError('Choose PDF or HTML.')
    return f"candidate_screening_report_{audit_view(report)['date']}.{format}"


def html_report(report):
    view = audit_view(report)
    matrix, details = [], []
    for row in report['requirements']:
        evidence = ''.join(f'<p class="excerpt">{esc(unit["quote"])}<span class="source">{esc(unit["section"])} · Line {unit["line"]}{" · " + esc(unit["page"]) if unit.get("page") else ""}</span></p>' for unit in row['evidence']) or '<p>No positive supporting excerpt found.</p>'
        matrix.append(f'<tr><th scope="row">{esc(row["name"])}</th><td>{esc(row["description"])}</td><td>{esc(row["category"])}</td><td class="status" style="color:{STATUS_COLORS[row["status"]]}">{esc(row["status"])}</td><td>{evidence}</td></tr>')
        details.append(f'<article class="audit-detail"><h4>{esc(row["name"])} — {esc(row["status"])}</h4><p><strong>Assessment:</strong> {esc(row["reason"])}</p><p><strong>Interview question:</strong> {esc(row["question"])}</p><p class="source">Category: {esc(row["category"])} · Credit: {row["credit"] * 100:g}%</p></article>')
    limitations = ''.join(f'<li>{esc(note)}</li>' for note in report['limitations'] + report['document_warnings'])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Candidate Screening Audit Report — {esc(report['candidate'])}</title>
<style>
*{{box-sizing:border-box}}body{{margin:0;background:#edf1f7;color:#172033;font:13px/1.55 Arial,sans-serif}}.banner{{background:#0f172a;color:white;padding:19px 34px;font-size:11px;letter-spacing:2px;font-weight:bold}}main{{max-width:1180px;margin:0 auto;background:white;padding:26px 34px 40px}}h1{{font-size:25px;margin:0 0 15px}}h2{{font-size:19px;color:#1e40af;margin:26px 0 10px}}h3{{font-size:15px}}h4{{margin:0 0 7px}}p{{margin:5px 0}}.metadata{{padding:14px;background:#f1f5f9;border:1px solid #cbd5e1}}.table-scroll{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:11px;table-layout:fixed}}th,td{{border:1px solid #cbd5e1;padding:8px;vertical-align:top;text-align:left;overflow-wrap:anywhere}}thead th{{background:#1e293b;color:white;font-weight:bold}}.leaderboard th:nth-child(1){{width:4%}}.leaderboard th:nth-child(2){{width:19%}}.leaderboard th:nth-child(3){{width:10%}}.leaderboard th:nth-child(4){{width:23%}}.leaderboard th:nth-child(5){{width:14%}}.leaderboard th:nth-child(6){{width:30%}}.takeaway{{margin:16px 0;padding:13px;background:#fef3c7;border:1px solid #f59e0b;color:#854d0e}}.candidate-bar{{background:#e0e7ff;border:1px solid #f59e0b;padding:10px;font-weight:bold;font-size:12px}}.matrix th,.matrix td{{border-color:#f59e0b}}.matrix thead th{{background:#f1f5f9;color:#334155}}.matrix thead th:nth-child(1){{width:17%}}.matrix thead th:nth-child(2){{width:24%}}.matrix thead th:nth-child(3){{width:10%}}.matrix thead th:nth-child(4){{width:13%}}.matrix thead th:nth-child(5){{width:36%}}.status{{font-weight:bold}}.excerpt{{margin:0 0 10px}}.excerpt:last-child{{margin-bottom:0}}.source{{display:block;color:#64748b;font-size:10px;margin-top:4px}}.note{{font-size:11px;color:#64748b}}.audit-detail{{border-top:1px solid #e2e8f0;padding:14px 0}}footer{{border-top:1px solid #cbd5e1;margin-top:25px;padding-top:15px;font-size:10px;color:#64748b;overflow-wrap:anywhere}}@media(max-width:650px){{main{{padding:20px 14px}}.banner{{padding:15px 14px}}h1{{font-size:22px}}table{{min-width:860px}}}}@media print{{@page{{size:A4;margin:12mm}}body{{background:white}}main{{padding:0;max-width:none}}.banner{{padding:12px}}table{{font-size:8px;min-width:0}}th,td{{padding:5px}}thead{{display:table-header-group}}.table-scroll{{overflow:visible}}h2,h3,h4{{break-after:avoid}}.audit-detail{{break-inside:avoid}}}}
</style></head><body><header class="banner">{BANNER}</header><main><h1>Candidate Screening Audit Report - {view['date']}</h1>
<div class="metadata"><p><strong>Screened Files:</strong> {esc(view['files'])}</p><p><strong>Active JD:</strong> {esc(report['jd_label'])}</p><p><strong>Screening scope:</strong> {esc(view['scope'])}</p><p><strong>Candidates Ranked:</strong> 1</p><p class="note">Generated: {view['generated']} · Report: {esc(report['id'])} · Resume evidence is self-reported.</p></div>
<h2>{SECTIONS[0]}</h2><div class="table-scroll"><table class="leaderboard"><thead><tr><th>#</th><th>Candidate</th><th>Score</th><th>Verdict</th><th>Exp</th><th>Missing Mandatory</th></tr></thead><tbody><tr><td>1</td><td>{esc(report['candidate'])}</td><td><strong>{report['score']:.1f}/100</strong></td><td>{esc(report['recommendation'])}</td><td>{esc(view['experience'])}</td><td>{esc(view['unresolved'])}</td></tr></tbody></table></div>
<div class="takeaway"><strong>Key Takeaway &amp; Override Decisions:</strong><p>{esc(report['candidate'])}: {esc(report['recommendation'])}.</p><p>{esc(view['decision'])}</p><p>{esc(view['counts'])}</p></div><p class="note">“Missing Mandatory” lists all unresolved mandatory requirements, including Partial Match and Claimed but Unevidenced. Ranking applies to the one candidate in this screening.</p>
<h2>{SECTIONS[1]}</h2><div class="candidate-bar">Candidate: {esc(report['candidate'])} | Score: {report['score']:.1f}/100 | {esc(report['recommendation'])}</div><div class="table-scroll"><table class="matrix"><thead><tr><th>Skill / Area</th><th>Expectation</th><th>Type</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{''.join(matrix)}</tbody></table></div>
<h2>{SECTIONS[2]}</h2><h3>1. {esc(report['candidate'])} — {esc(report['recommendation'])}</h3><p><strong>Total Experience:</strong> {esc(view['experience'])} | <strong>Final Score:</strong> {report['score']:.1f} / 100</p><p><strong>Score Breakdown:</strong> {esc(view['breakdown'])}</p><p><strong>Override Decision:</strong> {esc(view['decision'])}</p><p class="note">Experience is assessed within the JD requirement matrix, not added as a separate bonus.</p><h3>Requirement reasoning &amp; interview checks</h3>{''.join(details)}<h3>Scoring method &amp; review limitations</h3><p>{esc(report['method'])}</p><ul>{limitations}</ul><footer>Confidential · Evidence review for human decision support<br>Generated: {view['generated']} · Engine: {esc(report['engine_version'])} · Report ID: {esc(report['id'])}<br>JD SHA256: {esc(report['jd_sha256'])}<br>Resume SHA256: {esc(report['resume_sha256'])}</footer></main></body></html>'''


class NumberedCanvas(Canvas):
    """Replay pages with a Page n/N footer, including tables that continue across pages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved_pages = []

    def showPage(self):
        self.saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        count = len(self.saved_pages)
        for state in self.saved_pages:
            self.__dict__.update(state)
            self.setFont('OpenSans', 7)
            self.setFillColor(colors.HexColor('#94a3b8'))
            self.drawString(30, 17, 'Confidential · Evidence review for human decision support')
            self.drawRightString(A4[0] - 30, 17, f'Page {self._pageNumber}/{count}')
            super().showPage()
        super().save()


def pdf_report(report):
    view = audit_view(report)
    buffer = io.BytesIO()
    width = A4[0] - 60
    base = ParagraphStyle('Body', fontName='OpenSans', fontSize=8, leading=11.2, textColor=colors.HexColor('#172033'), spaceAfter=5, splitLongWords=True)
    styles = {'body': base,
              'title': ParagraphStyle('Title', parent=base, fontName='OpenSans-Bold', fontSize=15, leading=20, spaceAfter=10),
              'heading': ParagraphStyle('Section', parent=base, fontName='OpenSans-Bold', fontSize=11, leading=15, textColor=colors.HexColor('#1e40af'), spaceBefore=14, spaceAfter=6, keepWithNext=True),
              'sub': ParagraphStyle('Sub', parent=base, fontName='OpenSans-Bold', fontSize=9, leading=13, spaceBefore=9, keepWithNext=True),
              'cell': ParagraphStyle('Cell', parent=base, fontSize=6.8, leading=9.5, spaceAfter=0),
              'small': ParagraphStyle('Small', parent=base, fontSize=7, leading=10, textColor=colors.HexColor('#64748b'))}
    p = lambda text, style='body': Paragraph(esc(text), styles[style])
    def cell(text, header=False, color=None):
        style = ParagraphStyle('TableCell', parent=styles['cell'], fontName='OpenSans-Bold' if header else 'OpenSans', textColor=colors.HexColor(color or ('#ffffff' if header else '#172033')))
        return Paragraph(esc(text), style)
    def box(lines, background, border):
        table = Table([[p(line)] for line in lines], colWidths=[width])
        table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(background)), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor(border)), ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        return table
    story = [p(f"Candidate Screening Audit Report - {view['date']}", 'title'),
             box([f"Screened Files: {view['files']}", f"Active JD: {report['jd_label']}", f"Screening scope: {view['scope']}", 'Candidates Ranked: 1', f"Generated: {view['generated']} | Report: {report['id']} | Resume evidence is self-reported."], '#f1f5f9', '#cbd5e1'),
             p(SECTIONS[0], 'heading')]
    leaderboard = LongTable([[cell(x, True) for x in ['#', 'Candidate', 'Score', 'Verdict', 'Exp', 'Missing Mandatory']],
        [cell('1'), cell(report['candidate']), cell(f"{report['score']:.1f}/100"), cell(report['recommendation']), cell(view['experience']), cell(view['unresolved'])]],
        colWidths=[width*x for x in [.035, .18, .095, .235, .13, .325]], repeatRows=1, splitInRow=1, hAlign='LEFT')
    leaderboard.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')), ('GRID', (0, 0), (-1, -1), .4, colors.HexColor('#cbd5e1')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6)]))
    story += [leaderboard, Spacer(1, 10), box(['Key Takeaway & Override Decisions:', f"{report['candidate']}: {report['recommendation']}.", view['decision'], view['counts']], '#fef3c7', '#f59e0b'),
              p('Missing Mandatory lists all unresolved mandatory requirements, including Partial Match and Claimed but Unevidenced. Ranking applies to this single-candidate screening.', 'small')]
    matrix_data = [[p(SECTIONS[1], 'heading'), '', '', '', ''], [cell(f"Candidate: {report['candidate']} | Score: {report['score']:.1f}/100 | {report['recommendation']}", color='#1e3a8a'), '', '', '', ''],
                   [cell(x, color='#334155') for x in ['Skill / Area', 'Expectation', 'Type', 'Status', 'Evidence']]]
    for row in report['requirements']:
        excerpts = []
        for unit in row['evidence']:
            excerpts += [p(unit['quote'], 'cell'), p(f"{unit['section']} · Line {unit['line']}" + (f" · {unit['page']}" if unit.get('page') else ''), 'small'), Spacer(1, 5)]
        matrix_data.append([cell(row['name']), cell(row['description']), cell(row['category']), cell(row['status'], color=STATUS_COLORS[row['status']]), excerpts or cell('No positive supporting excerpt found.')])
    matrix = LongTable(matrix_data, colWidths=[width*x for x in [.17, .24, .10, .13, .36]], repeatRows=3, splitInRow=1, hAlign='LEFT')
    matrix.setStyle(TableStyle([('SPAN', (0, 0), (-1, 0)), ('SPAN', (0, 1), (-1, 1)), ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e0e7ff')), ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f1f5f9')), ('GRID', (0, 1), (-1, -1), .4, colors.HexColor('#f59e0b')), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story += [matrix, p(SECTIONS[2], 'heading'), p(f"1. {report['candidate']} — {report['recommendation']}", 'sub'),
              p(f"Total Experience: {view['experience']} | Final Score: {report['score']:.1f} / 100"), p('Score Breakdown: ' + view['breakdown']), p('Override Decision: ' + view['decision']),
              p('Experience is assessed within the JD requirement matrix, not added as a separate bonus.', 'small'), p('Requirement reasoning & interview checks', 'sub')]
    for row in report['requirements']:
        story += [p(f"{row['name']} — {row['status']}", 'sub'), p('Assessment: ' + row['reason']), p('Interview question: ' + row['question']), p(f"Category: {row['category']} | Credit: {row['credit'] * 100:g}%", 'small')]
    story += [p('Scoring method & review limitations', 'sub'), p(report['method'])]
    story.extend(p('• ' + note) for note in report['limitations'] + report['document_warnings'])
    story.extend(p(line, 'small') for line in [f"Generated: {view['generated']} | Engine: {report['engine_version']} | Report: {report['id']}", 'JD SHA256: ' + report['jd_sha256'], 'Resume SHA256: ' + report['resume_sha256']])
    def header(canvas, doc):
        canvas.setFillColor(colors.HexColor('#0f172a'))
        canvas.rect(0, A4[1]-38, A4[0], 38, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont('OpenSans-Bold', 7)
        canvas.drawString(30, A4[1]-23, BANNER)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=51, bottomMargin=32,
                            title='Candidate Screening Audit Report', author='Proofpoint')
    doc.build(story, onFirstPage=header, onLaterPages=header, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
