"""Readable count-based formulas and separate category/verdict diagnostics."""
import streamlit as st
from .scoring import calculate_scoring, verdict_reason, CREDITS, MANDATORY_THRESHOLD, SUITABLE, CONDITIONAL, INSUFFICIENT


def render_evidence_summary(scoring):
    st.markdown('**Evidence status counts**')
    for column, (status, count) in zip(st.columns(4), scoring['counts'].items()):
        column.metric(status, count)
    st.caption(f"{scoring['total_requirements']} total requirements · {scoring['earned_credits']:g} evidence credits · Not matching: {scoring['not_matching_count']} (claimed + missing; not counted again). Partial matches are shown separately.")


def render_scoring_guide(report=None):
    if report:
        scoring = report.get('scoring') or calculate_scoring(report['requirements'])
        counts = scoring['counts']
        st.markdown('**Calculation for this assessment**')
        st.dataframe([{'Evidence status': status, 'Count': counts[status], 'Credit each': credit,
                       'Evidence credits': counts[status] * credit} for status, credit in CREDITS.items()],
                     hide_index=True, width='stretch')
        st.markdown(f"**Overall evidence coverage = 100 × ({counts['Matched']} + 0.5 × {counts['Partial Match']}) ÷ {scoring['total_requirements']} = {scoring['overall_score']:.1f}/100**")
        st.caption('Every JD requirement counts once. Claimed and missing requirements stay in the denominator and earn zero credit. Category labels and requirement weights do not affect overall evidence coverage.')
        st.markdown('**Separate category diagnostics — not components of the overall score**')
        st.dataframe([{'JD category': r['category'], 'Requirements': r['requirement_count'],
                       'Evidence credits': r['earned_credits'],
                       'Coverage': f"{r['coverage']:g}%" if r['applicable'] else 'Not applicable'}
                      for r in scoring['categories']], hide_index=True, width='stretch')
        st.markdown('**Why this verdict?**')
        st.write(verdict_reason(report))

    st.markdown('**1. Count each requirement by its evidence status**')
    st.markdown('| Evidence status | Credit per requirement |\n|---|---:|\n| Matched | 1 |\n| Partial Match | 0.5 |\n| Claimed but Unevidenced | 0 |\n| Missing | 0 |')
    st.markdown('**2. Calculate overall evidence coverage directly from the counts**')
    st.markdown('**Overall evidence coverage (%) = 100 × (Matched count + 0.5 × Partial Match count) ÷ Total requirement count**')
    st.write('Total requirement count = Matched + Partial Match + Claimed but Unevidenced + Missing. Each requirement counts equally, regardless of whether it is mandatory or good-to-have. Requirement weights and category percentages do not enter this formula.')
    st.caption('“Not matching” summarizes Claimed but Unevidenced + Missing. It is not a fifth evidence status and is not added again to the denominator. Partial Match remains a separate status.')
    st.markdown('**Example:** 6 Matched, 2 Partial Match, 1 Claimed and 1 Missing → 100 × (6 + 0.5 × 2) ÷ 10 = **70% overall evidence coverage**.')
    st.markdown('**3. Show mandatory and good-to-have coverage separately**')
    st.markdown('**Category coverage (%) = 100 × (Matched in category + 0.5 × Partial Match in category) ÷ Requirements in category**')
    st.write('These are separate diagnostics. A category absent from the reviewed JD is Not applicable. Good-to-have requirements included in the JD are assessed even when missing from the resume. Skills that are not JD requirements are not added to the counts.')
    st.caption('Coverage percentages are rounded to one decimal place. Overall coverage is calculated directly from the counts, not from rounded category percentages.')
    st.markdown('**4. Determine the verdict from mandatory coverage and gaps**')
    st.markdown(f'| Verdict | Rule |\n|---|---|\n| {INSUFFICIENT} | Mandatory coverage below {MANDATORY_THRESHOLD}% |\n| {CONDITIONAL} | Mandatory coverage at least {MANDATORY_THRESHOLD}%, with one or more unresolved mandatory requirements |\n| {SUITABLE} | No unresolved mandatory requirements |')
    st.caption('The verdict is a separate mandatory-gap check; it is not the overall evidence percentage. Partial Match, Claimed but Unevidenced and Missing are unresolved mandatory requirements. A JD with no mandatory requirements has no mandatory gap gate. Verdicts describe resume evidence and require human verification.')
