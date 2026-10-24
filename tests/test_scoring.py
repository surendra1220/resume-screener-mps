"""Category applicability is determined by the JD, independent of resume coverage."""
from app.engine import analyze, parse_custom_jd
from app.models import AnalyzeRequest, Requirement
from app.scoring import calculate_scoring, CREDITS, SUITABLE, CONDITIONAL, INSUFFICIENT

RESUME = 'PROFESSIONAL EXPERIENCE:\nDeveloped Python automation tests for a customer billing platform.'


def screen(jd, resume=RESUME):
    return analyze(AnalyzeRequest(jd_text=jd, resume_text=resume, requirements=parse_custom_jd(jd)))


def test_no_preferences_in_jd_counts_only_existing_requirements():
    r = screen('Must Have Skills:\nPython: Develop automated tests for the customer billing platform.')
    assert r['score'] == 100
    assert r['scores'] == {'Mandatory': 100, 'Good to Have': None}
    mandatory, preferred = r['scoring']['categories']
    assert mandatory['earned_credits'] == mandatory['requirement_count'] == 1
    assert not preferred['applicable'] and preferred['requirement_count'] == 0
    assert preferred['earned_credits'] == 0 and preferred['coverage'] is None
    assert r['recommendation'] == SUITABLE


def test_absent_preferences_do_not_reduce_partial_mandatory_coverage():
    r = screen('Must Have Skills:\nUse Python and SQL to develop automated tests for the platform.')
    assert r['scores']['Mandatory'] == r['score'] == 50
    assert r['scores']['Good to Have'] is None
    assert r['recommendation'] == CONDITIONAL


def test_jd_preferences_missing_from_resume_are_still_counted():
    r = screen('Must Have Skills:\nPython: Develop automated tests for the platform.\nNice to Haves:\nAWS: Experience running cloud environments.')
    assert r['scores'] == {'Mandatory': 100, 'Good to Have': 0}
    assert r['score'] == 50
    assert r['scoring']['categories'][1]['applicable']
    assert r['scoring']['categories'][1]['requirement_count'] == 1
    assert r['recommendation'] == SUITABLE


def test_extra_resume_skills_do_not_create_a_preferred_category():
    jd = 'Must Have Skills:\nPython: Develop automated tests for the customer billing platform.'
    r = screen(jd, RESUME + '\nUsed AWS to provision cloud environments.\nImplemented SQL tests.')
    assert r['score'] == 100 and r['scores']['Good to Have'] is None
    assert len(r['requirements']) == 1


def test_preference_only_jd_normalizes_to_one_hundred_percent():
    r = screen('Nice to Haves:\nPython: Develop automated tests for the customer billing platform.')
    assert r['score'] == 100
    assert r['scores'] == {'Mandatory': None, 'Good to Have': 100}
    assert r['scoring']['total_requirements'] == 1


def test_requirement_weights_do_not_affect_count_based_coverage():
    requirements = [
        Requirement(id='a', name='Python', description='Python required', alternatives=['Python'], weight=3),
        Requirement(id='b', name='SQL', description='SQL required', alternatives=['SQL'], weight=1),
        Requirement(id='c', name='AWS Lambda', description='AWS Lambda preferred', alternatives=['AWS'], all_of=['Lambda'], category='Good to Have', weight=2),
    ]
    r = analyze(AnalyzeRequest(jd_text='Require Python and SQL. AWS Lambda is preferred for cloud deployment.',
                               resume_text=RESUME + '\nUsed AWS to provision cloud environments.', requirements=requirements))
    assert r['scores'] == {'Mandatory': 50, 'Good to Have': 50}
    assert r['score'] == 50
    assert r['scoring']['earned_credits'] == 1.5
    assert r['scoring']['total_requirements'] == 3


def test_preferred_matches_cannot_override_low_mandatory_coverage():
    r = screen('Must Have Skills:\nSQL: Develop automated database tests for the platform.\nNice to Haves:\nPython: Develop automated tests for the platform.')
    assert r['score'] == 50
    assert r['recommendation'] == INSUFFICIENT


def test_all_four_statuses_are_counted_once():
    rows = [dict(status=status, category='Mandatory', weight=10, credit=credit) for status, credit in CREDITS.items()]
    scoring = calculate_scoring(rows)
    assert scoring['counts'] == {status: 1 for status in CREDITS}
    assert scoring['not_matching_count'] == 2
    assert scoring['earned_credits'] == 1.5
    assert scoring['total_requirements'] == 4
    assert scoring['overall_score'] == 37.5


def test_overall_uses_counts_not_a_category_average():
    rows = [dict(status='Matched', category='Mandatory', weight=10)]
    rows += [dict(status='Missing', category='Good to Have', weight=1) for _ in range(9)]
    scoring = calculate_scoring(rows)
    assert [r['coverage'] for r in scoring['categories']] == [100, 0]
    assert scoring['overall_score'] == 10
    for row in rows:
        row['category'] = 'Good to Have' if row['category'] == 'Mandatory' else 'Mandatory'
        row['weight'] = 1 if row['weight'] == 10 else 10
    changed = calculate_scoring(rows)
    assert changed['overall_score'] == scoring['overall_score']
    assert changed['counts'] == scoring['counts']


def test_documented_example_six_matches_two_partial_one_claim_one_missing():
    rows = [dict(status=status, category='Mandatory') for status, count in
            [('Matched', 6), ('Partial Match', 2), ('Claimed but Unevidenced', 1), ('Missing', 1)] for _ in range(count)]
    scoring = calculate_scoring(rows)
    assert scoring['overall_score'] == 70
    assert scoring['total_requirements'] == 10
