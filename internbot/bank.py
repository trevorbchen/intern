"""Permanent question bank: answers.yaml (gitignored). One entry per distinct application question."""
import os, re, yaml

PATH = "answers.yaml"
SKIP = re.compile(r"^(first|last|preferred|full)?\s*name\b|^email|^phone|resume|cv\b|cover letter|^search$|"
                  r"linkedin|github|website|portfolio|twitter", re.I)


def norm(s: str) -> str:
    s = re.sub(r"\(optional\)|\*", "", (s or "").lower())
    return re.sub(r"\s+", " ", s).strip(" :?")


def load(path=PATH):
    return (yaml.safe_load(open(path)) or []) if os.path.exists(path) else []


def save(entries, path=PATH):
    entries = sorted(entries, key=lambda e: (-e.get("seen", 0), e["q"]))
    with open(path, "w") as f:
        f.write("# Your permanent answers. Fill in `answer:` (for dropdowns use one of `options` exactly).\n"
                "# {company} matches any company name. Blank answer = skipped / asked to Claude / flagged.\n")
        yaml.safe_dump(entries, f, sort_keys=False, allow_unicode=True, width=100)


def _rx(q: str) -> str:
    return ".+?".join(re.escape(p) for p in q.split("{company}"))


def lookup(entries, label: str):
    n = norm(label)
    for e in entries:
        a = e.get("answer")
        if a not in (None, "") and re.fullmatch(_rx(e["q"]), n):
            return str(a)
    return None


def merge(entries, found):
    """found: list of dict(q,type,options,required,company). Keeps existing answers."""
    by = {e["q"]: e for e in entries}
    for f in found:
        e = by.setdefault(f["q"], {"q": f["q"], "type": f["type"], "required": f["required"],
                                   "options": f.get("options") or [], "seen": 0, "companies": [], "answer": ""})
        e["seen"] += 1
        e["required"] = e.get("required") or f["required"]
        if f.get("options") and not e.get("options"):
            e["options"] = f["options"]
        if f["company"] not in e["companies"] and len(e["companies"]) < 6:
            e["companies"].append(f["company"])
    return list(by.values())
