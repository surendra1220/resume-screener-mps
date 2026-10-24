"""Conservative local evidence rubric; scores document support, not actual competence."""
import calendar
import re
from datetime import date, datetime, timezone
from hashlib import sha256
from .models import Requirement
from .scoring import calculate_scoring, verdict, CREDITS

VERSION = '3.1.0'
POINTS = CREDITS
ACTION = re.compile(r'\b(built|build|designed|developed|implemented|automated|tested|integrated|maintained|worked|utilized|used|enabled|applied|supported|collaborated|participated|mentored|executed|validated|wired|converted|performed|created|led|managed|deployed|analyzed|analysed)\b', re.I)
INSTRUCTION = re.compile(r'ignore (?:all|previous|prior)|system prompt|you (?:must|should|are)|assign (?:a |the )?score|mark (?:me|all|the candidate)|rank (?:me|this)|instruction to|override .*score', re.I)
PROJECT = re.compile(r'professional experience|work experience\s*$|employment|roles\s*&?\s*responsibilities|project(?:s|\s*\d+| experience)?\s*:?$|employment history', re.I)
NONPROJECT = re.compile(r'^(?:technical skills|core competencies|professional summary|skills|summary|profile|education|certifications?|accomplishments|personal details|declaration|awards|languages known)\s*:?$', re.I)


def contains(text, alias):
    # Escaped aliases, not user-provided regex. Word boundaries prevent AI in 'maintained'.
    return bool(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', text, re.I))


def evidence_units(text):
    units, section, project, page = [], 'Unsectioned', False, None
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip(' \t•-*#')
        if not line:
            continue
        if re.fullmatch(r'\[Page \d+\]', line):
            page = line
            continue
        if NONPROJECT.match(line):
            section, project = line.rstrip(':'), False
        elif PROJECT.search(line) or (len(line) < 140 and re.search(r'\b(?:19|20)\d{2}\s*[-–].*(?:present|20\d{2})', line, re.I)):
            section, project = line, True
        elif len(line) < 100 and re.search(r'\(\d{1,2}/\d{1,2}/\d{4}\s*[-–]', line):
            section, project = line, True
        # PDF line wrapping: retain exact source substrings, including whitespace.
        # Merge only continuation lines inside a work section, never new bullets,
        # role headings, page boundaries, or instructions.
        if (units and project and units[-1]['project'] and units[-1]['section'] == section
                and units[-1]['page'] == page and not re.match(r'^\s*[•·●▪*-]', raw)
                and units[-1]['quote'].rstrip(':') != section.rstrip(':')
                and not re.search(r'[.!?]$', units[-1]['quote'])
                and not INSTRUCTION.search(raw) and not INSTRUCTION.search(units[-1]['quote'])
                and not re.search(r'\b(?:19|20)\d{2}\b', raw)
                and not re.search(r'\b(?:19|20)\d{2}\b', units[-1]['quote'])):
            previous = units[-1]
            previous['quote'] = '\n'.join(text.splitlines()[previous['line']-1:n]).strip(' \t•·-*#')
        else:
            units.append({'line': n, 'quote': line, 'section': section, 'project': project, 'page': page})
    return units


def negated(text, terms):
    for term in terms:
        if re.search(r'\b(?:no|not|never|without|lack(?:s|ing)?|limited)\b[^.;\n]{0,35}(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I):
            return True
    return False


def experience_result(req, text, units, today):
    # Month-level employment ranges, unioned to avoid double-counting overlaps.
    months = {m.lower(): n for n, m in enumerate(calendar.month_name) if m}
    months.update({m.lower(): n for n, m in enumerate(calendar.month_abbr) if m})
    pattern = r'\b([A-Za-z]{3,9})\s+(\d{4})\s*[-–]\s*(?:([A-Za-z]{3,9})\s+(\d{4})|(present|current|now))\b'
    covered, quotes = set(), []
    for unit in units:
        if not unit['project']:
            continue
        for a, y, b, z, present in re.findall(pattern, unit['quote'], re.I):
            if a.lower() not in months or (not present and b.lower() not in months):
                continue
            start = int(y) * 12 + months[a.lower()] - 1
            end = today.year * 12 + today.month - 1 if present else int(z) * 12 + months[b.lower()] - 1
            end = min(end, today.year * 12 + today.month - 1)
            if 0 <= end - start <= 600:
                covered.update(range(start, end + 1))
                quotes.append(unit)
    bounds = re.search(r'(\d+)\s*[-–]\s*(\d+)\s*(?:years?|yrs?)', req.description, re.I)
    minimum = re.search(r'(\d+)\s*\+?\s*(?:years?|yrs?)', req.description, re.I)
    if covered and (bounds or minimum):
        years = len(covered) / 12
        low, high = map(int, bounds.groups()) if bounds else (int(minimum.group(1)), float('inf'))
        status = 'Matched' if low <= years <= high else 'Partial Match'
        if req.id.startswith('custom-experience-'):
            # A total timeline cannot establish the same duration in every JD skill.
            status = 'Partial Match'
        return status, quotes[:4], f'Employment timeline covers approximately {years:.1f} years (overlaps counted once; through {today:%B %Y}). Role relevance and skill-specific tenure need verification.'
    claims = [u for u in units if re.search(r'\d+\+?\s*(?:years?|yrs?)', u['quote'], re.I)]
    return ('Claimed but Unevidenced' if claims else 'Missing'), claims[:2], 'A claimed total is not a verified, non-overlapping employment timeline. Confirm the dates and relevant tenure.'


def assess(req, text, units, today):
    if req.id == 'experience' or req.id.startswith('custom-experience-'):
        status, quotes, reason = experience_result(req, text, units, today)
    else:
        terms = req.alternatives or [req.name]
        hits = [u for u in units if any(contains(u['quote'], x) for x in terms) and not INSTRUCTION.search(u['quote'])]
        positive = [u for u in hits if not negated(u['quote'], terms)]
        project_hits = [u for u in positive if u['project'] and (ACTION.search(u['quote']) or (req.id.startswith('custom-') and re.search(r'\b(architected|governed|established|acted|drove|engaged|prepared|customized|generated|mentoring|defining|collaborating)\b', u['quote'], re.I)))]
        qualification = req.id.startswith('custom-qualification-')
        if qualification:
            project_hits = positive
        # All required facets must be in the same evidence unit; never borrow a keyword from another project.
        # all_of is reviewer-editable plain alternatives, escaped to avoid regex injection/ReDoS.
        def facets(u):
            patterns = FACETS.get(req.id) if req.id in FACETS else None
            if patterns is None:
                return all(any(contains(u['quote'], part.strip()) for part in facet.split('|')) for facet in req.all_of)
            return all(re.search(p, u['quote'], re.I) for p in patterns)
        full = [u for u in project_hits if facets(u)]
        # Custom competencies may be evidenced by several statements in ONE role.
        # Keep every excerpt separate and never borrow facets across employers.
        if req.id.startswith('custom-') and not full and project_hits and req.all_of:
            for section in dict.fromkeys(u['section'] for u in project_hits):
                role_units = [u for u in project_hits if u['section'] == section and u['project']]
                if all(any(any(contains(u['quote'], part.strip()) for part in facet.split('|')) for u in role_units) for facet in req.all_of):
                    full = role_units
                    break
        knowledge = [u for u in positive if (req.id.startswith('custom-') or re.search(r'\b(knowledge|familiar|understanding|experience|worked|implemented|developed|utilized|exposure)\b', u['quote'], re.I)) and facets(u)]
        if full:
            status, quotes = 'Matched', full
            reason = 'Resume evidence covers the required facets within one work/education context. This is self-reported evidence, not independent verification.'
        elif req.knowledge_ok and knowledge:
            status, quotes = 'Matched', knowledge[:3]
            reason = 'The JD explicitly accepts knowledge or minimal experience; the resume makes an explicit knowledge/usage claim. Verify depth in interview.'
        elif project_hits:
            status, quotes = 'Partial Match', project_hits[:3]
            reason = 'Related project usage is documented, but not all required facets are evidenced in the same work statement.'
            patterns = FACETS.get(req.id)
            if patterns:
                best = max(project_hits, key=lambda u: sum(bool(re.search(p, u['quote'], re.I)) for p in patterns))
                missing = [label for pattern, label in zip(patterns, FACET_LABELS[req.id]) if not re.search(pattern, best['quote'], re.I)]
                if missing:
                    reason += ' Not shown in the strongest excerpt: ' + '; '.join(missing) + '.'
            elif req.all_of:
                best_section = max(dict.fromkeys(u['section'] for u in project_hits), key=lambda section: sum(any(any(contains(u['quote'], p.strip()) for p in f.split('|')) for u in positive if u['section'] == section) for f in req.all_of))
                missing = [f for f in req.all_of if not any(any(contains(u['quote'], p.strip()) for p in f.split('|')) for u in positive if u['section'] == best_section)]
                if missing:
                    reason += ' Not evidenced in the strongest role: ' + '; '.join(missing) + '.'
        elif positive:
            status, quotes = 'Claimed but Unevidenced', positive[:3]
            reason = 'Mentioned in a summary, skills list or general claim, without a concrete action in project/work context.'
        else:
            status, quotes = 'Missing', hits[:2]
            reason = 'No positive evidence found in the resume.' if not hits else 'Only a negated or explicitly limited claim was found; no positive project evidence.'
    return {**req.model_dump(), 'status': status, 'credit': POINTS[status], 'evidence': quotes,
            'reason': reason, 'question': f'For {req.name}, describe a specific project, your contribution, tools, dates, and a measurable outcome. ' + ('Clarify the missing facets in this requirement.' if status != 'Matched' else 'Walk through an implementation or sanitized artifact.')}


# Fixed, audited semantic facets for the default JD; custom requirements use literal facets.
FACETS = {
 'design': [r'build|built|design|develop|implement|maintain', r'framework'],
 'ui': [r'UI|web|browser', r'cucumber|specflow|\bBDD\b|gherkin|behavio[u]?r.driven'],
 'strategy': [r'\bSTLC\b|test strateg|test lifecycle', r'(?<!non-)(?<!non )\bfunctional\b', r'non.functional|performance|security|load testing'],
 'ai-solutions': [r'\bAI\b|artificial intelligence', r'built|creat|design|develop|implement|enabl', r'manual|effort|accelerat|reduc|rapid'],
 'ai-testing': [r'test(?:ed|ing|s)? (?:of |the )?AI|validat.*\bAI\b|evaluat.*\bAI\b|\bMCP\b', r'test|automat'],
 'cicd': [r'integrat|wired|pipeline', r'test|suite|automat'],
}

FACET_LABELS = {
 'design': ['framework design/build/maintenance action', 'automation framework'],
 'ui': ['UI/web testing', 'BDD using Cucumber, SpecFlow, Gherkin or equivalent'],
 'strategy': ['STLC or test-strategy ownership', 'functional testing', 'non-functional testing'],
 'ai-solutions': ['AI usage', 'solution creation', 'reduced manual effort'],
 'ai-testing': ['testing an AI-powered solution or using MCP automation', 'testing/automation activity'],
 'cicd': ['pipeline integration', 'automated test suite'],
}


def analyze(request, today=None):
    today = today or date.today()
    units = evidence_units(request.resume_text)
    # Bundled IDs select audited default facets; custom draft IDs use literal facets.
    rows = [assess(req, request.resume_text, units, today) for req in request.requirements]
    scoring = calculate_scoring(rows)
    scores = {r['category']: r['coverage'] for r in scoring['categories']}
    score = scoring['overall_score']
    gaps = [r['name'] for r in rows if r['category'] == 'Mandatory' and r['status'] != 'Matched']
    recommendation = verdict(scores, gaps)
    return {'id': sha256((request.jd_text + request.resume_text + str(rows)).encode()).hexdigest()[:12],
            'candidate': request.candidate_label, 'jd_label': request.jd_label,
            'screened_files': [request.resume_filename] if request.resume_filename else [],
            'generated_at': datetime.now(timezone.utc).isoformat(), 'engine_version': VERSION,
            'score': score, 'scores': scores, 'scoring': scoring, 'recommendation': recommendation, 'mandatory_gaps': gaps,
            'requirements': rows, 'counts': scoring['counts'],
            'method': 'Count-based evidence coverage: 100 x (Matched count + 0.5 x Partial Match count) / Total JD requirements. Claimed but Unevidenced and Missing earn zero credit and stay in the total. Every requirement counts equally; category labels and requirement weights do not influence overall coverage. Mandatory and Good to Have coverage are separate count-based diagnostics, with absent categories marked not applicable. Work evidence and required facets determine each status. Custom facets may span statements in one role, never across employers. Education does not need an action verb. The verdict remains a separate mandatory-gap check: mandatory coverage below 40% gives insufficient documented fit; otherwise unresolved mandatory gaps give conditional fit, and no mandatory gaps gives suitable on documented evidence. Scores require human review.',
            'limitations': ['Resume evidence is self-reported and not independently verified.', 'Local rules may miss paraphrases or ambiguous layouts; review extracted text and the requirement matrix.', 'Skill-specific duration and project domain cannot be inferred from total tenure.', 'Scanned files require OCR; no candidate identity or sensitive personal attributes are used in scoring.'],
            'document_warnings': ['Instruction-like text was excluded from evidence.'] if any(INSTRUCTION.search(u['quote']) for u in units) else [],
            'jd_sha256': sha256(request.jd_text.encode()).hexdigest(), 'resume_sha256': sha256(request.resume_text.encode()).hexdigest()}


# Shared parser for FastAPI and Streamlit.
from .jd import parse_custom_jd
