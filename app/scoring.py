"""Count-based evidence coverage. Category diagnostics never feed the overall score."""
CATEGORIES = ('Mandatory', 'Good to Have')
CREDITS = {'Matched': 1, 'Partial Match': .5, 'Claimed but Unevidenced': 0, 'Missing': 0}
MANDATORY_THRESHOLD = 40
SUITABLE = 'Suitable on documented evidence — verify in interview'
CONDITIONAL = 'Conditional fit — mandatory evidence gaps require review'
INSUFFICIENT = 'Insufficient documented fit — substantial mandatory gaps'


def calculate_scoring(rows):
    if not rows:
        raise ValueError('At least one JD requirement is needed to calculate a score.')
    counts = {status: sum(r['status'] == status for r in rows) for status in CREDITS}
    if sum(counts.values()) != len(rows):
        raise ValueError('Every requirement must have one recognized evidence status.')
    earned = sum(counts[status] * credit for status, credit in CREDITS.items())
    raw_score = 100 * earned / len(rows)
    categories = []
    for category in CATEGORIES:
        subset = [r for r in rows if r['category'] == category]
        category_earned = sum(CREDITS[r['status']] for r in subset)
        categories.append(dict(category=category, requirement_count=len(subset), applicable=bool(subset),
                               earned_credits=category_earned,
                               coverage=round(100 * category_earned / len(subset), 1) if subset else None))
    return {'basis': 'requirement-counts', 'counts': counts, 'total_requirements': len(rows),
            'earned_credits': earned, 'raw_score': raw_score,
            'not_matching_count': counts['Claimed but Unevidenced'] + counts['Missing'],
            'categories': categories, 'overall_score': round(raw_score, 1)}


def verdict(scores, mandatory_gaps):
    if scores['Mandatory'] is not None and scores['Mandatory'] < MANDATORY_THRESHOLD:
        return INSUFFICIENT
    return CONDITIONAL if mandatory_gaps else SUITABLE


def verdict_reason(report):
    coverage = report['scores']['Mandatory']
    if coverage is None:
        return 'The screening scope has no mandatory requirements, so there are no mandatory gaps to assess. The score reflects only its included good-to-have requirements.'
    if coverage < MANDATORY_THRESHOLD:
        return f'Mandatory coverage is {coverage:g}%, below the {MANDATORY_THRESHOLD}% threshold. This produces the insufficient documented fit verdict.'
    if report['mandatory_gaps']:
        count = len(report['mandatory_gaps'])
        return f'Mandatory coverage is {coverage:g}% (at least {MANDATORY_THRESHOLD}%), but {count} mandatory requirement(s) remain unresolved. This produces the conditional fit verdict.'
    return 'Every mandatory requirement is Matched. This produces the suitable on documented evidence verdict; good-to-have gaps do not block it.'
