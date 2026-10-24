"""Session-independent helpers for the Streamlit surface. Never cache candidate data globally."""
import hashlib
import json
from .models import Requirement


def editor_rows(requirements):
    return [dict(selected=False, id=r['id'], name=r['name'], category=r['category'], weight=r['weight'],
                 description=r['description'], alternatives=', '.join(r['alternatives']),
                 all_of='; '.join(r['all_of']), knowledge_ok=r['knowledge_ok']) for r in requirements]


def screening_scope(rows):
    """Explicit Screen checkboxes control assessment; no checks means all rows."""
    selected = [row for row in rows if row.get('selected') is True]
    assessed = selected or rows
    return assessed, {'mode': 'selected' if selected else 'all', 'total_count': len(rows),
                      'assessed_count': len(assessed), 'excluded_count': len(rows) - len(assessed)}


def scope_description(scope):
    if scope['mode'] == 'selected':
        return f"Selected skills only: {scope['assessed_count']} of {scope['total_count']} requirements assessed; {scope['excluded_count']} excluded."
    return f"No skills selected: all {scope['total_count']} requirements assessed by default."


def reviewed_requirements(rows, originals):
    known = {r['id']: r for r in originals}
    result = []
    for index, row in enumerate(rows):
        original = known.get(row.get('id'), {})
        facets = [x.strip() for x in str(row.get('all_of') or '').split(';') if x.strip()]
        rid = original.get('id', f'custom-added-{index}')
        if original and facets != original.get('all_of', []):
            rid = f'custom-edited-{index}'
        alternatives = [x.strip() for x in str(row.get('alternatives') or '').split(',') if x.strip()]
        if not alternatives and rid != 'experience':
            raise ValueError(f"Row {index+1}: provide at least one accepted skill term.")
        result.append(Requirement(id=rid, name=row.get('name') or '', category=row.get('category'),
                                  description=row.get('description') or '', source=original.get('source', ''),
                                  alternatives=alternatives, all_of=facets, weight=row.get('weight') or 1,
                                  knowledge_ok=bool(row.get('knowledge_ok'))))
    if not result or len(result) > 60:
        raise ValueError('Provide between 1 and 60 requirements.')
    if len({r.id for r in result}) != len(result):
        raise ValueError('Each requirement needs a unique ID. Remove duplicated rows.')
    return result


def fingerprint(*values):
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


DEMO_RESUME = '''ALEX MORGAN — SYNTHETIC DEMO
SUMMARY:
Automation engineer with an interest in AI-assisted testing.
PROFESSIONAL EXPERIENCE:
Jan 2020 - Present
Developed Python automation frameworks using Pytest for clinical trial data validation.
Automated browser UI tests using Cucumber BDD scenarios for the clinical portal.
Worked on API testing using Postman for the clinical platform.
Implemented STLC test strategy covering functional and non-functional performance testing.
Managed test cases and defects using Jira for the clinical delivery project.
Worked in Agile Scrum delivery with the clinical product team.
Developed AI agents to reduce manual effort in Playwright test creation.
Tested AI-powered solutions using evaluation tests for the clinical assistant.
Integrated automated test suites into CI/CD pipelines using GitHub Actions.
Used Azure services to provision test environments for the clinical portal.
Developed failure analysis using Splunk logs to identify root causes across services.
TECHNICAL SKILLS:
TestComplete, MABL, RAG, MCP.
'''
