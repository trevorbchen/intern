"""Watch fellowship / residency pages: detect open/closed, deadlines, and page changes."""
import hashlib, re, yaml
from datetime import datetime
from bs4 import BeautifulSoup
from .sources import get

OPEN = re.compile(r"applications?\s+(are\s+)?(now\s+)?open|now accepting|apply now|applications? (are )?live|rolling basis", re.I)
CLOSED = re.compile(r"applications?\s+(are\s+|have\s+)?(now\s+)?closed|no longer accepting|not currently accepting", re.I)
DATE = re.compile(r"(?:deadline|apply by|applications? (?:close|due)|due)[^.\n]{0,50}?"
                  r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+20\d\d)", re.I)


def parse_date(s: str):
    s = re.sub(r"(st|nd|rd|th),", ",", s.replace("Sept", "Sep")).replace(".", "")
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s)
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    return None


def analyze(text: str):
    """-> (status, deadline_iso|None). status: open | closed | unknown"""
    closed, opened = bool(CLOSED.search(text)), bool(OPEN.search(text))
    status = "closed" if closed and not opened else "open" if opened and not closed else \
             ("check" if opened and closed else "unknown")
    m = DATE.search(text)
    return status, (parse_date(m.group(1)) if m else None)


def load(path="programs.yaml"):
    return yaml.safe_load(open(path)) or []


def check_all(db, path="programs.yaml"):
    alerts = []
    for p in load(path):
        status, deadline, h = "manual", p.get("deadline"), ""
        if p.get("auto_check", True):
            try:
                html = get(p["url"], headers={"User-Agent": "Mozilla/5.0"}).text
                text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
                status, found = analyze(text)
                deadline = p.get("deadline") or found
                h = hashlib.sha1(re.sub(r"\s+", " ", text)[:20000].encode()).hexdigest()
            except Exception as e:
                status = f"error ({type(e).__name__})"
        changed = db.upsert_program(p["name"], p["url"], status, deadline, h)
        if changed:
            alerts.append(p["name"])
            print(f"[programs] page changed: {p['name']} ({status}) {p['url']}")
    return alerts
