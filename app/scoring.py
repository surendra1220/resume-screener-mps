"""Shared score arithmetic. Applicability comes from JD requirements, not resume hits."""
CATEGORY_WEIGHTS = {'Mandatory': 80, 'Good to Have': 20}
CREDITS = {'Matched': 1, 'Partial Match': .5, 'Claimed but Unevidenced': 0, 'Missing': 0}
MANDATORY_THRESHOLD = 40
SUITABLE = 'Suitable on documented evidence — verify in interview'
CONDITIONAL = 'Conditional fit — mandatory evidence gaps require review'
INSUFFICIENT = 'Insufficient documented fit — substantial mandatory gaps'


def calculate_scoring(rows):
    categories = []
    for category, base_weight in CATEGORY_WEIGHTS.items():
        subset = [r for r in rows if r['category'] == category]
        total = sum(r['weight'] for r in subset)
        earned = sum(r['credit'] * r['weight'] for r in subset)
        categories.append(dict(category=category, requirement_count=len(subset), applicable=bool(subset),
                               base_weight=base_weight, total_weight=total, earned_weight=earned,
                               coverage=round(100 * earned / total, 1) if subset else None))
    active_weight = sum(r['base_weight'] for r in categories if r['applicable'])
    if not active_weight:
        raise ValueError('At least one JD requirement is needed to calculate a score.')
    for row in categories:
        row['allocation'] = 100 * row['base_weight'] / active_weight if row['applicable'] else 0
        row['contribution'] = row['coverage'] * row['allocation'] / 100 if row['applicable'] else 0
    return {'categories': categories, 'overall_score': round(sum(r['contribution'] for r in categories), 1)}


def verdict(scores, mandatory_gaps):
    if scores['Mandatory'] is not None and scores['Mandatory'] < MANDATORY_THRESHOLD:
        return INSUFFICIENT
    return CONDITIONAL if mandatory_gaps else SUITABLE


def verdict_reason(report):
    coverage = report['scores']['Mandatory']
    if coverage is None:
        return 'The JD has no mandatory requirements, so there are no mandatory gaps to assess. The score reflects only its good-to-have requirements.'
    if coverage < MANDATORY_THRESHOLD:
        return f'Mandatory coverage is {coverage:g}%, below the {MANDATORY_THRESHOLD}% threshold. This produces the insufficient documented fit verdict.'
    if report['mandatory_gaps']:
        count = len(report['mandatory_gaps'])
        return f'Mandatory coverage is {coverage:g}% (at least {MANDATORY_THRESHOLD}%), but {count} mandatory requirement(s) remain unresolved. This produces the conditional fit verdict.'
    return 'Every mandatory requirement is Matched. This produces the suitable on documented evidence verdict; good-to-have gaps do not block it.'
