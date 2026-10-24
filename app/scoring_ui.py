"""Readable formulas, applicability rules and the actual result calculation."""
import streamlit as st
from .scoring import calculate_scoring, verdict_reason, MANDATORY_THRESHOLD, SUITABLE, CONDITIONAL, INSUFFICIENT


def render_scoring_guide(report=None):
    if report:
        scoring = report.get('scoring') or calculate_scoring(report['requirements'])
        st.markdown('**Calculation for this assessment**')
        st.dataframe([{
            'JD category': r['category'], 'Requirements': r['requirement_count'],
            'Earned / possible weight': f"{r['earned_weight']:g} / {r['total_weight']:g}" if r['applicable'] else 'Not applicable',
            'Coverage': f"{r['coverage']:g}%" if r['applicable'] else 'Not applicable',
            'Share of final score': f"{r['allocation']:g}%",
            'Points contributed': round(r['contribution'], 2),
        } for r in scoring['categories']], hide_index=True, width='stretch')
        terms = [f"({r['coverage']:g} × {r['allocation']:g}%)" for r in scoring['categories'] if r['applicable']]
        st.markdown('**Final score = ' + ' + '.join(terms) + f" = {scoring['overall_score']:.1f}/100**")
        if not any(r['category'] == 'Good to Have' and r['applicable'] for r in scoring['categories']):
            st.info('No good-to-have requirements in this JD. Good-to-have coverage is not applicable and contributes no penalty; mandatory coverage determines 100% of the final score.')
        st.markdown('**Why this verdict?**')
        st.write(verdict_reason(report))

    st.markdown('**1. Assign evidence credit to each JD requirement**')
    st.markdown('| Evidence status | Credit |\n|---|---:|\n| Matched | 1 (100%) |\n| Partial Match | 0.5 (50%) |\n| Claimed but Unevidenced | 0 |\n| Missing | 0 |')
    st.markdown('**2. Calculate coverage within each applicable category**')
    st.markdown('**Category coverage (%) = 100 × Σ(credit × requirement weight) ÷ Σ(requirement weights)**')
    st.caption('Each requirement has weight 1 unless you change it in the benchmark. Sum only the requirements belonging to that category.')
    st.markdown('**3. Use only the categories present in the JD**')
    st.markdown('| Requirements in the JD | Final score formula |\n|---|---|\n| Mandatory and good-to-have | (Mandatory coverage × 80%) + (Good-to-have coverage × 20%) |\n| Mandatory only | Mandatory coverage × 100%; good-to-have is excluded |\n| Good-to-have only | Good-to-have coverage × 100%; mandatory is excluded |')
    st.write('A category is applicable because its requirements appear in the reviewed JD benchmark. If good-to-have requirements are in the JD but absent from the resume, they remain in the calculation with zero credit. Extra resume skills that are not JD requirements do not affect the score.')
    st.caption('Category coverage and the final score are rounded to one decimal place. The final score uses the displayed category coverages.')
    st.markdown('**4. Determine the verdict from mandatory coverage and gaps**')
    st.markdown(f'| Verdict | Rule |\n|---|---|\n| {INSUFFICIENT} | Mandatory coverage below {MANDATORY_THRESHOLD}% |\n| {CONDITIONAL} | Mandatory coverage at least {MANDATORY_THRESHOLD}%, with one or more unresolved mandatory requirements |\n| {SUITABLE} | No unresolved mandatory requirements |')
    st.caption('Partial Match, Claimed but Unevidenced and Missing are unresolved mandatory requirements. Good-to-have requirements affect the score when present in the JD; they do not create mandatory gaps. A JD with no mandatory requirements has no mandatory gap gate. Verdicts describe resume evidence and require human verification.')
