"""Source-grounded JD drafts. Documents are data, never agent instructions.

Competencies are phrases, not capitalized words. Unknown domains retain their
source wording and explicit matching facets for human review.
"""
import re
from .models import Requirement
from .requirements import consolidate_requirements, join_text

VERSION = '2.0.0'
OPTIONAL = re.compile(r'good[ -]to[ -]haves?|nice[ -]to[ -]haves?|preferred|desirable|optional|added advantage|a plus|an advantage', re.I)
HEADINGS = re.compile(r'^(?:technical|ai & innovation|leadership & strategic|minimum qualifications?|qualifications?|required knowledge and experience|responsibilities.*|job description(?:\s*[-–]\s*\d+)?|key responsibilities|duties|skills|education)\s*:?$', re.I)
METADATA = re.compile(r'^(?:job title|role|location|salary|benefits|about us|job id|department|employment type|you will report|you will interacts?)\b', re.I)
INSTRUCTIONS = re.compile(r'ignore (?:all|previous|prior)|system prompt|assign .*score|override .*score|mark .*matched', re.I)

# Canonical labels and literal aliases; longer aliases take precedence over their
# contained words (e.g. JavaScript is never Java; Page Object is never Page).
ALIASES = {
 'Python': ['Python'], 'Java': ['Java'], 'C#': ['C#', 'C sharp'],
 'JavaScript': ['JavaScript'], 'TypeScript': ['TypeScript'], 'SQL': ['SQL'],
 'Selenium': ['Selenium'], 'Appium': ['Appium'], 'TestComplete': ['TestComplete', 'Test Complete'],
 'WinAppDriver': ['WinAppDriver'], 'Katalon Studio': ['Katalon Studio', 'Katalon'],
 'Pywinauto': ['Pywinauto'], 'White framework': ['White'], 'LabVIEW': ['LabVIEW'],
 'Playwright': ['Playwright'], 'Cypress': ['Cypress'], 'Postman': ['Postman'],
 'RestAssured': ['RestAssured', 'Rest Assured'], 'Jenkins': ['Jenkins'],
 'Azure DevOps': ['Azure DevOps'], 'GitLab CI': ['GitLab CI'], 'GitHub Actions': ['GitHub Actions'],
 'CI/CD integration': ['CI/CD', 'continuous integration', 'continuous delivery'],
 'Page Object Model': ['Page Object', 'POM'], 'Screenplay pattern': ['Screenplay'],
 'Web automation': ['web automation', 'web testing', 'browser testing', 'UI testing', 'web'],
 'Mobile automation': ['mobile automation', 'mobile testing', 'mobile applications', 'mobile'],
 'Desktop automation': ['desktop automation', 'desktop testing', 'desktop'],
 'API automation': ['API automation', 'API testing', 'REST testing', 'API'],
 'Cloud testing': ['cloud testing', 'cloud'],
 'Embedded automation': ['embedded test automation', 'embedded testing', 'embedded applications', 'embedded'],
 'Automation strategy': ['automation strategy', 'test strategy', 'test strategies', 'quality strategy'],
 'Automation frameworks': ['automation framework', 'automation frameworks', 'test framework', 'test frameworks', 'framework', 'frameworks'],
 'Automation architecture': ['automation architecture', 'automation architect', 'automation architecting'],
 'Reusable test code': ['reusable', 'reusability', 'maintainability', 'componentization'],
 'Parallel execution': ['parallel execution', 'parallel testing'],
 'Self-healing tests': ['self-healing', 'self healing'],
 'Visual verification': ['visual verification', 'visual testing'],
 'Intelligent object recognition': ['object recognition'],
 'AI testing tools': ['AI-powered testing', 'AI-assisted', 'AI-driven automation', 'Katalon AI'],
 'Generative AI': ['GenAI', 'Generative AI'], 'Prompt engineering': ['prompt engineering', 'prompt validation'],
 'Machine learning': ['machine learning'], 'Test selection': ['test selection'],
 'Test data generation': ['data generation', 'test data'], 'Failure analysis': ['failure pattern', 'failure analysis', 'root cause'],
 'Automation roadmap': ['automation roadmap', 'automation roadmaps', 'technology roadmap'],
 'Tool evaluation': ['tool evaluation', 'evaluate tools', 'evaluate and introduce'],
 'Automation metrics': ['KPIs', 'ROI', 'automation coverage', 'test coverage'],
 'Team leadership': ['lead teams', 'lead large', 'led', 'managed the team', 'QA Lead', 'QA COE Lead'],
 'Mentoring': ['mentor', 'mentoring', 'mentored', 'mentorship', 'coaching', 'capability building'],
 'Cross-functional collaboration': ['cross-functional', 'cross functional'],
 'Test planning': ['test plans', 'test planning'], 'Test case design': ['test cases', 'test case', 'test design'],
 'Problem solving': ['problem-solving', 'problem solving'], 'Attention to detail': ['attention to detail'],
 'Adaptability': ['dynamic environment', 'adaptability', 'willingness to learn'],
 'Agile': ['Agile', 'Scrum'], 'Logical reasoning': ['logical', 'reasoning'],
 'Communication': ['communication', 'communicated'],
 'Stakeholder management': ['stakeholder management', 'stakeholder collaboration', 'stakeholders'],
 'Presentation': ['presentation', 'present progress', 'presented'],
 'Medical devices': ['medical devices', 'medical device'],
 'Regulated environment': ['regulated environment', 'regulatory compliance'],
 'Version control': ['version control', 'Git', 'SVN'],
 'AWS': ['AWS', 'Amazon Web Services'], 'Azure': ['Azure'], 'GCP': ['GCP', 'Google Cloud'],
 'Docker': ['Docker'], 'Kubernetes': ['Kubernetes'], 'React': ['React'],
 'Excel': ['Excel'], 'Accounting': ['accounting'], 'Financial reporting': ['financial reporting'],
 'Patient care': ['patient care'], 'Registered nurse': ['registered nurse', 'RN'],
}

# Preserve coverage of technologies outside the automation-specific vocabulary.
for _term in ['C++', 'Go', 'Rust', 'Pytest', 'Cucumber', 'SpecFlow', 'BDD', 'Jira', 'TestRail', 'ALM',
              'Kanban', 'Git', 'Angular', 'Vue', 'Node.js', 'Django', 'Flask', 'FastAPI', 'Spring',
              'REST', 'GraphQL', 'MongoDB', 'PostgreSQL', 'MySQL', 'Redis', 'Splunk', 'Grafana',
              'Power BI', 'MABL', 'MCP', 'RAG', 'TensorFlow', 'PyTorch', 'Healthcare', 'Life Sciences',
              'Pharma', 'Clinical', 'Regulatory', 'Foundry', 'Salesforce', 'SAP']:
    ALIASES.setdefault(_term, [_term])

STOP = set('a an the and or of in on for to with by from as at our your their this that is are be will have has must should required strong solid deep excellent good ability proficiency proficient experience knowledge understanding familiarity exposure expertise skills skill minimum years year using use work working develop build implement define architect lead manage support including software application applications tools tool concepts relevant'.split())


def has(text, term):
    return bool(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text, re.I))


def concepts(text):
    hits = [(name, aliases, [a for a in aliases if has(text, a)]) for name, aliases in ALIASES.items() if any(has(text, a) for a in aliases)]
    return [(name, aliases) for name, aliases, matched in hits
            if not all(any(a.lower() != b.lower() and a.lower() in b.lower() for _, _, other in hits for b in other) for a in matched)]


def fallback(text):
    """Never mine capitalization. Keep meaningful content words as AND facets."""
    words = [w.lower() for w in re.findall(r'[A-Za-z][A-Za-z0-9+#-]*', text) if w.lower() not in STOP]
    words = list(dict.fromkeys(words))[:12]
    return (' '.join(words[:7]).capitalize(), [[w] for w in words]) if words else ('', [])


def parse_custom_jd(text):
    category, result, seen = 'Mandatory', [], {}
    skip_section = False
    lines = []
    # Rejoin PDF continuations before classifying headings and extracting clauses.
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if (lines and (stripped[:1].islower() or re.search(r'(?:,|\band|\bor|\busing|\bwith)\s*$', lines[-1], re.I)) and not re.match(r'^\s*[•·●▪\-*#]', raw)
                and not re.search(r'[.:;]$', lines[-1]) and not HEADINGS.fullmatch(lines[-1].strip())):
            lines[-1] += '\n' + raw
        else:
            lines.append(raw)
    for raw in lines:
        line = re.sub(r'^\s*(?:[•·●▪\-*#]+|\d+[.)])\s*', '', raw).strip()
        if not line or re.fullmatch(r'\[Page \d+\]', line):
            continue
        if re.match(r'principal working relationship|benefits|about us', line, re.I):
            skip_section = True
            continue
        if OPTIONAL.fullmatch(line.rstrip(':').strip()) or re.fullmatch(r'(?:good[ -]to[ -]haves?|nice[ -]to[ -]haves?|preferred|optional|desirable)(?: skills| requirements| qualifications)?\s*:?', line, re.I):
            category, skip_section = 'Good to Have', False
            continue
        if re.fullmatch(r'(?:must.have|mandatory|required|job requirements|requirements)(?: skills| requirements| qualifications)?\s*:?', line, re.I) or HEADINGS.fullmatch(line):
            if re.match(r'must.have|mandatory|required|job requirements|requirements|minimum qualifications?', line, re.I):
                category = 'Mandatory'
            skip_section = False
            continue
        if skip_section or METADATA.match(line) or INSTRUCTIONS.search(line):
            continue
        current = line
        for sentence in re.split(r'(?<=[.;])\s+(?=[A-Z])', current):
            optional = bool(OPTIONAL.search(sentence))
            row_category = 'Good to Have' if optional else category
            # Optional parentheticals must not make the entire sentence optional.
            optional_parts = re.findall(r'\([^)]*optional[^)]*\)', sentence, re.I)
            core = sentence
            for part in optional_parts:
                core = core.replace(part, '')
            if optional_parts:
                row_category = category
            found = concepts(core)
            duration = re.search(r'(\d+(?:\.\d+)?)\s*(?:\+|[-–]\s*\d+)?\s*(?:years?|yrs?)', core, re.I)
            degree = re.search(r'bachelor|master|\bB\.?Tech\b|\bB\.E\.|degree|diploma', core, re.I)
            if duration:
                name = 'Relevant experience'
                groups = [[a for _, aliases in found for a in aliases]] if found else [['experience']]
                kind = 'experience'
            elif degree:
                degree_terms = ['bachelor', 'B.Tech', 'BTech', 'B.E.', 'Bachelor of Technology', 'Bachelor of Engineering'] if re.search(r'bachelor|\bB\.?Tech|\bB\.E\.', core, re.I) else ['master', 'M.Tech', 'MTech', 'M.E.']
                name = "Bachelor's degree" if degree_terms[0] == 'bachelor' else "Master's degree"
                groups, kind = [degree_terms], 'qualification'
                # Field restrictions remain explicit; a degree alone is partial.
                fields = re.findall(r'computer sciences?|biotechnology|bio-technology|bio-medical|electronics|electrical engineering', core, re.I)
                if fields:
                    groups.append(list(dict.fromkeys(fields)))
            else:
                kind = 'skill'
                # OR scope applies within each clause, never to the whole sentence.
                groups, labels = [], []
                clause_parts = re.split(r'\bwith support for\b|\bincluding\b|(?=\bsuch as\b)|(?=\blike\b)|[()]', core, flags=re.I)
                for clause_index, clause in enumerate(clause_parts):
                    # AND has wider scope than a local OR list. Do not turn
                    # "Python or Java and SQL" into three interchangeable tools.
                    if re.search(r'\bor\b', clause, re.I) and re.search(r'\band\b', clause, re.I):
                        segments = re.split(r'\band\b', clause, flags=re.I)
                        for segment in segments:
                            choices = concepts(segment)
                            if re.search(r'\bor\b', segment, re.I):
                                groups.append(list(dict.fromkeys(a for _, aliases in choices for a in aliases)))
                            else:
                                groups.extend(aliases for _, aliases in choices)
                            labels.extend(n for n, _ in choices)
                        continue
                    items = concepts(clause)
                    if not items:
                        continue
                    # A named area before a colon describes scope, not an extra tool.
                    if ':' in clause:
                        before, after = clause.split(':', 1)
                        if concepts(after):
                            items = concepts(after)
                            # An automation area remains a scope condition even
                            # when a tool can also be used in other domains.
                            area = next((n for n, _ in concepts(before) if n.endswith('automation')), None)
                            if area:
                                groups.append(ALIASES[area])
                    is_or = bool(re.search(r'\bor\b|such as|\blike\b|e\.g\.|\bEx\s*:|equivalent', clause, re.I))
                    # Parenthesized tools illustrate an implementation choice.
                    if clause_index and re.search(r'CI/CD pipelines\s*\(', core, re.I) and any(n in {'Jenkins', 'Azure DevOps', 'GitLab CI'} for n, _ in items):
                        is_or = True
                    if is_or:
                        groups.append(list(dict.fromkeys(a for _, aliases in items for a in aliases)))
                        labels.append(' / '.join(n for n, _ in items))
                    else:
                        groups.extend(aliases for _, aliases in items)
                        labels.extend(n for n, _ in items)
                if not groups:
                    name, groups = fallback(core)
                else:
                    name = ' / '.join(dict.fromkeys(labels))
                for phrase, aliases in [
                    ('distributed', ['distributed', 'global teams']),
                    ('multiple product lines', ['multiple product lines']),
                    ('AI for test selection', ['AI', 'GenAI', 'artificial intelligence']),
                    ('regulated medical devices', ['regulated', 'regulatory']),
                ]:
                    if has(core, phrase):
                        groups.append(aliases)
                groups = list(dict.fromkeys(tuple(g) for g in groups))
                groups = [list(g) for g in groups]
                if re.match(r'^[^:()]{2,60}:', core) and not core.lower().startswith(('required:', 'preferred:')):
                    name = core.split(':', 1)[0].strip()
                elif len(name) > 75:
                    # Describe the competency, keeping its detailed conditions in
                    # the expectation and facets rather than a truncated tool list.
                    for pattern, label in [
                        (r'strategy', 'Automation strategy and platform coverage'),
                        (r'architectures', 'Application architectures and testing methodologies'),
                        (r'AI-driven', 'AI-driven automation practices'),
                        (r'mentor|teams', 'Automation team leadership and mentoring'),
                        (r'framework', 'Automation framework engineering'),
                        (r'GenAI|prompt', 'Generative AI and test optimization'),
                        (r'KPIs|ROI', 'Automation metrics and ROI'),
                    ]:
                        if re.search(pattern, core, re.I):
                            name = label
                            break
            if not groups:
                continue
            # Preserve individual language conjunctions as separately reviewable rows.
            drafts = [(name, groups)]
            if kind == 'skill' and len(found) > 1 and all(n in {'Python', 'SQL', 'Java', 'C#', 'TypeScript', 'JavaScript'} for n, _ in found) and not re.search(r'\bor\b', core, re.I):
                drafts = [(n, [aliases]) for n, aliases in found]
            for label, facets in drafts:
                key = (row_category, kind, tuple(sorted('|'.join(sorted(a.lower() for a in g)) for g in facets)))
                if kind == 'experience':
                    key += (duration.group(),)
                if key in seen:
                    existing = seen[key]
                    existing.knowledge_ok = existing.knowledge_ok and bool(re.search(r'knowledge|understanding|familiarity|familiar|exposure', core, re.I))
                    if sentence not in existing.source:
                        existing.source = join_text(existing.source, sentence, 4000)
                        existing.description = join_text(existing.description, sentence, 2000)
                    continue
                terms = list(dict.fromkeys(a for g in facets for a in g))
                if len(sentence) > 2000 or len(terms) > 30 or len(facets) > 20:
                    raise ValueError('A JD requirement is too complex for one row. Split the paragraph into smaller requirements; no conditions were discarded.')
                req = Requirement(id=f'custom-{kind}-{len(result)+1}', name=label[:200], category=row_category,
                    description=sentence, source=sentence, alternatives=terms,
                    all_of=['|'.join(g) for g in facets],
                    knowledge_ok=bool(re.search(r'knowledge|understanding|familiarity|familiar|exposure', core, re.I)))
                result.append(req)
                seen[key] = req
            for part in optional_parts:
                for label, aliases in concepts(part):
                    result.append(Requirement(id=f'custom-skill-{len(result)+1}', name=label, category='Good to Have', description=sentence, source=sentence, alternatives=aliases))
    result = consolidate_requirements(result)
    if len(result) > 60:
        raise ValueError('The JD contains more than 60 requirements. Split it by role; no requirements were silently discarded.')
    return result
