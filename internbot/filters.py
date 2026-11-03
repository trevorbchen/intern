import re
from .models import Posting


def _has(text: str, terms) -> bool:
    return any(re.search(r"\b" + re.escape(t.lower()) + r"\b", text) for t in terms)


def matches(p: Posting, keywords, exclude, locations) -> bool:
    text = f"{p.title} {p.description}".lower()
    title = p.title.lower()
    if not _has(text, keywords):
        return False
    if "intern" not in text and "reu" not in text and "research assistant" not in text:
        return False
    if _has(title, exclude):
        return False
    if locations and p.location and not any(l.lower() in p.location.lower() for l in locations):
        return False
    return True
