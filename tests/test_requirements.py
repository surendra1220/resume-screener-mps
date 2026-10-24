import pytest
from app.engine import analyze, parse_custom_jd
from app.models import Requirement, AnalyzeRequest
from app.requirements import consolidate_requirements


def req(id, name, facets, **kwargs):
    return Requirement(id=id, name=name, description=kwargs.pop('description', 'Required competency for the role.'),
                       alternatives=list(dict.fromkeys(p for f in facets for p in f.split('|'))), all_of=facets, **kwargs)


def test_name_case_alias_and_spacing_duplicates_merge():
    items = [req('custom-skill-1', 'Python', ['Python']), req('custom-skill-2', ' PYTHON programming ', ['Python'])]
    result = consolidate_requirements(items)
    assert len(result) == 1 and result[0].name == 'Python'
    assert items[0].all_of == ['Python']


def test_repeated_area_keeps_different_required_expectations():
    items = [req('custom-skill-1', 'Python', ['Python', 'web'], description='Develop Python web tests.'),
             req('custom-skill-2', 'Python', ['Python', 'API'], description='Develop Python API tests.')]
    result = consolidate_requirements(items)
    assert len(result) == 1
    assert result[0].all_of == ['Python', 'web', 'API']
    assert all(r.description in result[0].description for r in items)
    report = analyze(AnalyzeRequest(jd_text='Develop Python web tests and Python API tests for this role.',
        resume_text='PROFESSIONAL EXPERIENCE:\nDeveloped Python web tests for the customer billing platform.', requirements=result))
    assert report['score'] == 50 and len(report['requirements']) == 1


@pytest.mark.parametrize('reverse', [False, True])
def test_optional_details_are_not_promoted_to_mandatory(reverse):
    mandatory = req('custom-skill-1', 'Python', ['Python'], knowledge_ok=True, description='Python knowledge required.')
    optional = req('custom-skill-2', 'Python', ['Python', 'performance'], category='Good to Have', description='Python performance optimization preferred.')
    result = consolidate_requirements([optional, mandatory] if reverse else [mandatory, optional])
    assert len(result) == 1 and result[0].category == 'Mandatory'
    assert result[0].all_of == ['Python'] and result[0].knowledge_ok
    assert 'Good to Have:' in result[0].description and 'performance' in result[0].description


def test_distinct_areas_and_distinct_qualifications_stay_separate():
    items = [req('custom-skill-1', 'Python', ['Python']), req('custom-skill-2', 'SQL', ['SQL']),
             req('custom-qualification-3', "Bachelor's degree", ['bachelor']),
             req('custom-qualification-4', "Master's degree", ['master'])]
    assert len(consolidate_requirements(items)) == 4


def test_ci_cd_area_merges_repeated_section_and_preserves_tool_condition():
    rows = parse_custom_jd('Integrate automation suites into CI/CD pipelines (Jenkins, Azure DevOps, GitLab CI).\nExperience integrating automation in CI/CD pipelines.')
    assert len(rows) == 1
    assert 'Jenkins' in rows[0].description and 'Experience integrating' in rows[0].description
    assert len(rows[0].all_of) == 2


def test_same_conditions_under_different_labels_are_one_requirement():
    items = [req('custom-skill-1', 'Python development', ['Python']), req('custom-skill-2', 'Python usage', ['Python'])]
    assert len(consolidate_requirements(items)) == 1


def test_duplicate_strength_does_not_depend_on_source_order():
    for text in ['Knowledge of Python is required.\nUse Python for automation testing.',
                 'Use Python for automation testing.\nKnowledge of Python is required.']:
        rows = parse_custom_jd(text)
        assert len(rows) == 1 and not rows[0].knowledge_ok


def test_empty_literal_facets_do_not_drop_one_of_two_conditions():
    first = req('custom-skill-1', 'Data engineering', ['Python']); first.all_of = []
    second = req('custom-skill-2', 'Data engineering', ['SQL']); second.all_of = []
    assert consolidate_requirements([first, second])[0].all_of == ['Python', 'SQL']
