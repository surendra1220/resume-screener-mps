"""Consolidate equivalent areas without dropping their source conditions."""
import re
import unicodedata


def normalized(value):
    return re.sub(r'[^\w+#]+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip()


def area_key(name):
    value = normalized(name)
    if re.match(r'^(?:ci cd|cicd|continuous integration)(?:\b|$)', value):
        return 'ci cd integration'
    aliases = {'test complete': 'testcomplete', 'python programming': 'python',
               'python skills': 'python', 'stakeholder collaboration': 'stakeholder management'}
    return aliases.get(value, value)


def kind(req):
    return 'experience' if req.id == 'experience' or req.id.startswith('custom-experience-') else 'qualification' if req.id.startswith('custom-qualification-') else 'skill'


def join_text(first, second, limit):
    parts = list(dict.fromkeys(p.strip() for p in (first + '\n' + second).splitlines() if p.strip()))
    text = '\n'.join(parts)
    if len(text) > limit:
        raise ValueError('Repeated JD requirements contain too much source detail for one area. Shorten the repeated paragraphs; no expectations were discarded.')
    return text


def facet_key(facet):
    return frozenset(normalized(p) for p in facet.split('|') if p.strip())


def consolidate_requirements(requirements):
    result, areas, signatures = [], {}, {}
    for original in requirements:
        req = original.model_copy(deep=True)
        area = (kind(req), area_key(req.name))
        groups = req.all_of or (['|'.join(req.alternatives)] if req.alternatives else [])
        signature = (kind(req), frozenset(facet_key(f) for f in groups))
        # Audited default IDs have their own semantic rules: never infer their
        # equivalence from a keyword list alone.
        semantic = signature if req.id.startswith('custom-skill-') and groups else None
        target = areas.get(area)
        if target is None and semantic is not None:
            target = signatures.get(semantic)
        if target is None:
            result.append(req)
            areas[area] = req
            if semantic is not None:
                signatures[semantic] = req
            continue
        target.name = {'ci cd integration': 'CI/CD integration', 'python': 'Python',
                       'testcomplete': 'TestComplete', 'stakeholder management': 'Stakeholder management'}.get(area_key(target.name), target.name)
        old_category = target.category
        if old_category != req.category:
            first = target.description if target.description.startswith(('Mandatory:', 'Good to Have:')) else f'{old_category}: {target.description}'
            target.description = join_text(first, f'{req.category}: {req.description}', 2000)
        else:
            target.description = join_text(target.description, req.description, 2000)
        target.source = join_text(target.source, req.source, 4000)
        target.category = 'Mandatory' if 'Mandatory' in (target.category, req.category) else 'Good to Have'
        existing_groups = target.all_of or (['|'.join(target.alternatives)] if target.alternatives else [])
        if old_category == 'Mandatory' and req.category == 'Good to Have':
            # Optional details stay visible without becoming mandatory conditions.
            combined = existing_groups
        elif old_category == 'Good to Have' and req.category == 'Mandatory':
            combined = groups
            target.alternatives = req.alternatives
            target.knowledge_ok = req.knowledge_ok
        else:
            target.knowledge_ok = target.knowledge_ok and req.knowledge_ok
            target.alternatives = list(dict.fromkeys(target.alternatives + req.alternatives))
            combined = existing_groups + groups
        unique = {facet_key(f): f for f in combined if facet_key(f)}
        # A narrower OR group implies a broader one, so keep the stronger AND
        # condition rather than requiring the same skill twice.
        target.all_of = [f for key, f in unique.items() if not any(other < key for other in unique)]
        if len(target.all_of) > 20 or len(target.alternatives) > 30:
            raise ValueError('Repeated skill requirements are too complex to combine safely. Shorten their conditions; no criteria were discarded.')
        areas[area] = target
        if semantic is not None:
            signatures[semantic] = target
    return result
