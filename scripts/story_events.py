"""Conservative matching for explicit service-resumption event paraphrases.

Requires a shared named entity, the same action/object/cause, and no conflicting
numbers. Unsupported events deliberately remain separate for review.
"""
import re
import unicodedata


def _normalize(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold().replace('ł', 'l'))
                   if not unicodedata.combining(c))


def _signature(title):
    text = _normalize(title)
    if not re.search(r'\b(?:resum\w*|restart\w*|reprise|reprend\w*|wznaw\w*|wznow\w*)\b', text):
        return None
    if re.search(r'\b(?:suspend\w*|halt\w*|stop\w*|not|no|pas|nie|could|might|may|pourrait|moze)\b', text):
        return None
    objects = {
        'withdrawals': r'\b(?:withdrawals?|retraits?|wyplat\w*)\b',
        'trains': r'\b(?:trains?|rail|pociag\w*)\b',
        'flights': r'\b(?:flights?|vols|loty)\b',
    }
    causes = {
        'breach': r'\b(?:breach\w*|hack\w*|piratag\w*|cyberatak\w*|wlaman\w*)\b',
        'strike': r'\b(?:strikes?|walkouts?|greve\w*|strajk\w*)\b',
        'closure': r'\b(?:closures?|fermeture\w*|zamkn\w*)\b',
    }
    targets = {name for name, pattern in objects.items() if re.search(pattern, text)}
    reasons = {name for name, pattern in causes.items() if re.search(pattern, text)}
    if len(targets) != 1 or len(reasons) != 1:
        return None
    # Capitalization alone is not enough: compare only shared non-generic tokens.
    ignored = {'the', 'after', 'following', 'biggest', 'ever', 'crypto', 'hack', 'breach',
               'resumes', 'restarts', 'withdrawals', 'trains', 'train', 'services',
               'la', 'le', 'les', 'une', 'un', 'des', 'reprise', 'retraits', 'plateforme'}
    entities = {_normalize(word) for word in re.findall(r'\b[A-ZÀ-Ý][\w-]+', title)
                if len(word) >= 4 and _normalize(word) not in ignored}
    numbers = set(re.findall(r'\b\d+(?:[.,]\d+)?\b', text))
    return targets, reasons, entities, numbers


def same_event(left, right):
    a, b = _signature(left), _signature(right)
    return bool(a and b and a[:2] == b[:2] and a[2] & b[2]
                and not (a[3] and b[3] and a[3] != b[3]))
