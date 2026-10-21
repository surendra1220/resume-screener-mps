import html
import io
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.pagesizes import A4

FONT_DIR = Path(__file__).parent / 'static/fonts'
for name, filename in [('OpenSans', 'OpenSans-Regular.ttf'), ('OpenSans-Bold', 'OpenSans-Bold.ttf'), ('OpenSans-Italic', 'OpenSans-Italic.ttf')]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / filename)))
pdfmetrics.registerFontFamily('OpenSans', normal='OpenSans', bold='OpenSans-Bold', italic='OpenSans-Italic', boldItalic='OpenSans-Bold')


def esc(value):
    return html.escape(str(value), quote=True)


def html_report(report):
    rows = ''
    for r in report['requirements']:
        evidence = ''.join(f'<blockquote>{esc(u["quote"])}<cite>{esc(u["section"])} · line {u["line"]}</cite></blockquote>' for u in r['evidence']) or '<p>No supporting excerpt found.</p>'
        rows += f'<article><div class="row"><h3>{esc(r["name"])}</h3><b>{esc(r["status"])}</b></div><small>{esc(r["category"])} · Weight {r["weight"]}</small><p><strong>JD:</strong> {esc(r["description"])}</p>{evidence}<p>{esc(r["reason"])}</p><p><strong>Interview:</strong> {esc(r["question"])}</p></article>'
    gaps = ''.join(f'<li>{esc(x)}</li>' for x in report['mandatory_gaps']) or '<li>No mandatory evidence gaps found.</li>'
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Screening report — {esc(report['candidate'])}</title><style>
    body{{font:15px/1.6 system-ui;color:#162a29;background:#f4f7f5;margin:0}}main{{max-width:950px;margin:40px auto;padding:32px;background:white}}h1{{font-size:34px}}h2{{margin-top:35px}}small,cite{{color:#5d6e69}}cite{{display:block;font-size:12px}}article{{border-top:1px solid #dce5df;padding:20px 0;break-inside:avoid}}blockquote{{margin:12px 0;padding:12px 18px;background:#f0f6f2;border-left:3px solid #2c7864}}.row{{display:flex;justify-content:space-between;gap:20px;align-items:center}}.score{{font-size:48px;color:#17634c}}@media print{{body{{background:white}}main{{margin:0;padding:0}}}}</style><main><small>PROOFPOINT / CANDIDATE SCREENING · {esc(report['id'])}</small><h1>{esc(report['candidate'])}</h1><p>{esc(report['jd_label'])} · {esc(report['generated_at'])}</p><div class="score">{report['score']} / 100</div><h2>{esc(report['recommendation'])}</h2><p>Mandatory: {report['scores']['Mandatory']}% · Good to Have: {report['scores']['Good to Have']}%</p><h2>Mandatory evidence gaps</h2><ul>{gaps}</ul><h2>Evidence matrix</h2>{rows}<h2>Scoring method</h2><p>{esc(report['method'])}</p><h2>Review limitations</h2><ul>{''.join('<li>'+esc(s)+'</li>' for s in report['limitations']+report['document_warnings'])}</ul><small>Engine {esc(report['engine_version'])}<br>JD SHA256: {esc(report['jd_sha256'])}<br>Resume SHA256: {esc(report['resume_sha256'])}</small></main></html>'''


def pdf_report(report):
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = 'OpenSans-Bold' if 'Heading' in style.name or style.name == 'Title' else 'OpenSans'
    styles.add(ParagraphStyle(name='Evidence', parent=styles['BodyText'], fontSize=9, leading=13, textColor=colors.HexColor('#34564c'), leftIndent=10, spaceAfter=8))
    styles['BodyText'].spaceAfter = 8
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42, title='Candidate screening report', author='Proofpoint')
    p = lambda text, style='BodyText': Paragraph(esc(text), styles[style])
    story = [p('PROOFPOINT / CANDIDATE SCREENING', 'Heading3'), p(report['candidate'], 'Title'), p(report['jd_label']),
             p(f"Evidence score: {report['score']} / 100", 'Heading1'), p(report['recommendation'], 'Heading2'),
             p(f"Mandatory: {report['scores']['Mandatory']}% | Good to Have: {report['scores']['Good to Have']}%"),
             p('Mandatory evidence gaps', 'Heading2')]
    story.extend(p('- ' + x) for x in report['mandatory_gaps'])
    if not report['mandatory_gaps']:
        story.append(p('No mandatory evidence gaps found.'))
    for r in report['requirements']:
        story.append(KeepTogether([Spacer(1, 12), p(r['name'], 'Heading2'), p(f"{r['category']} | {r['status']} | Weight {r['weight']}"), p('JD: ' + r['description'])]))
        for u in r['evidence']:
            story.append(p(f'“{u["quote"]}” — {u["section"]}, line {u["line"]}', 'Evidence'))
        if not r['evidence']:
            story.append(p('No supporting excerpt found.', 'Evidence'))
        story += [p(r['reason']), p('Interview: ' + r['question'])]
    story += [p('Method and limitations', 'Heading2'), p(report['method'])]
    story.extend(p(s) for s in report['limitations'] + report['document_warnings'])
    story += [p(f"Generated {report['generated_at']} | Engine {report['engine_version']} | ID {report['id']}"), p('JD SHA256: ' + report['jd_sha256']), p('Resume SHA256: ' + report['resume_sha256'])]
    def footer(canvas, doc):
        canvas.setFont('OpenSans', 8)
        canvas.setFillColor(colors.HexColor('#667970'))
        canvas.drawString(42, 24, 'Confidential · Evidence review for human decision support')
        canvas.drawRightString(A4[0]-42, 24, str(doc.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
