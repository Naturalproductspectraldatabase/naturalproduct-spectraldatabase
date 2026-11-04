"""Presentation-only helpers; never mutate scientific records or infer taxonomy."""
import re
from urllib.parse import urlsplit


def display_class_term(value, approved_aliases=None):
    text = ' '.join(str(value or '').split())
    if isinstance(approved_aliases, dict):
        targets = {v.strip() for k, v in approved_aliases.items()
                   if isinstance(k, str) and isinstance(v, str) and v.strip()
                   and k.strip().casefold() == text.casefold()}
        if len(targets) == 1:
            return targets.pop()
    return text


def category_counts(values):
    groups = {}
    for value in values:
        text = ' '.join(str(value or '').split()) or 'Uncategorized'
        key = text.casefold()
        labels, count = groups.get(key, (set(), 0))
        labels.add(text)
        groups[key] = labels, count + 1
    return [{'Category': sorted(labels)[0], 'Count': count}
            for key, (labels, count) in sorted(groups.items())]


def compound_open_label(compound_id, name):
    text = ' '.join(str(name or '').split()) or 'Unnamed compound'
    return f'Open {text} (#{int(compound_id)})'


def approved_recovery_route(value):
    text = str(value or '').strip()
    if not text or any(ord(c) < 33 for c in text) or '\\' in text:
        return ''
    try:
        parsed = urlsplit(text)
        if parsed.scheme == 'https' and parsed.hostname and parsed.username is None and parsed.password is None:
            return text
        if parsed.scheme == 'mailto' and not parsed.query and not parsed.fragment and re.fullmatch(r'[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+', parsed.path):
            return text
    except ValueError:
        pass
    return ''
