import re

_NOISE = {"inc", "ai", "labs", "lab", "technologies", "technology", "corp", "co", "the", "systems"}


def canon(name: str) -> str:
    words = [w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in _NOISE]
    return "".join(words)


def target_names(targets):
    """Canonical names (incl. parenthesised aliases like 'Cursor (Anysphere)')."""
    out = set()
    for t in targets:
        for part in re.split(r"[()]", t["name"]):
            if canon(part):
                out.add(canon(part))
    return out


def is_target(company: str, names) -> bool:
    c = canon(company)
    return bool(c) and any(c == n or (len(n) >= 4 and (c.startswith(n) or n.startswith(c)) and len(c) >= 4) for n in names)
from .models import Posting


def _has(text: str, terms) -> bool:
    return any(re.search(r"\b" + re.escape(t.lower()) + r"\b", text) for t in terms)


def matches(p: Posting, keywords, exclude, locations, topics=(), exclude_companies=(), targets=None) -> bool:
    text = f"{p.title} {p.description}".lower()
    title = p.title.lower()
    if topics and not _has(text, topics):  # must be AI-related
        return False
    if targets is not None and not is_target(p.company, targets):  # only top-tier target companies
        return False
    if any(c.lower() in p.company.lower() for c in exclude_companies if p.company):  # big corps
        return False
    if not _has(text, keywords):
        return False
    if "intern" not in text and "reu" not in text and "research assistant" not in text:
        return False
    if _has(title, exclude):
        return False
    if locations and p.location and not any(l.lower() in p.location.lower() for l in locations):
        return False
    return True
