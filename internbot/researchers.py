"""Find researchers at target companies whose recent papers overlap with YOUR interests (via OpenAlex).

Needs a free OpenAlex API key (openalex.org -> account -> API key) as OPENALEX_API_KEY in .env.
Put your interests in profile.yaml:  interests: ["reinforcement learning", "interpretability", ...]
"""
import json, os, re, time
import requests
from .filters import canon

API = "https://api.openalex.org"


class OpenAlexError(Exception):
    pass


def _get(path, **params):
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    params.setdefault("mailto", "internbot@example.com")
    r = requests.get(f"{API}/{path}", params=params, timeout=30)
    time.sleep(0.2)
    if r.status_code == 429:
        raise OpenAlexError("OpenAlex rate limit - set a free OPENALEX_API_KEY in .env (openalex.org)")
    r.raise_for_status()
    return r.json()


def find_institution(name):
    """Company -> OpenAlex institution id (only accepts company-type matches with the same canonical name)."""
    for inst in _get("institutions", search=name, **{"per-page": 5}).get("results", []):
        if inst.get("type") == "company" and canon(inst["display_name"]) == canon(name):
            return inst["id"].split("/")[-1]
    return None


def recent_works(inst_id, since="2025-01-01", pages=2):
    works = []
    for page in range(1, pages + 1):
        d = _get("works", filter=f"institutions.id:{inst_id},from_publication_date:{since}",
                 sort="publication_date:desc", **{"per-page": 100, "page": page})
        works += d.get("results", [])
        if len(d.get("results", [])) < 100:
            break
    return works


def user_terms(profile, resume=""):
    terms = [t.lower() for t in profile.get("interests", [])]
    if not terms:  # fall back: crude keywords from background text
        txt = f"{profile.get('background', '')} {resume}".lower()
        terms = [w for w in set(re.findall(r"[a-z][a-z\-]{5,}", txt)) if w not in _STOP][:40]
    return terms


_STOP = {"research", "student", "university", "project", "projects", "experience", "working", "worked",
         "intern", "internship", "developed", "building", "learning", "science", "computer", "engineering"}


def similarity(terms, work):
    topics = " ".join(t["display_name"] for t in work.get("topics", [])) + " " + \
             " ".join(k.get("display_name", "") for k in work.get("keywords", []))
    title = (work.get("title") or "").lower()
    return sum(2.0 for t in terms if t in title) + sum(1.0 for t in terms if t in topics.lower())


def rank_authors(works, inst_id, terms, top=8):
    """Aggregate authors affiliated with inst_id; score = summed overlap of their papers with `terms`."""
    by = {}
    for w in works:
        s = similarity(terms, w)
        if s <= 0:
            continue
        for a in w.get("authorships", []):
            if inst_id not in [i["id"].split("/")[-1] for i in a.get("institutions", [])]:
                continue
            au = a["author"]
            e = by.setdefault(au["id"].split("/")[-1], {"author_id": au["id"].split("/")[-1], "name": au["display_name"],
                                                        "url": au["id"], "score": 0.0, "papers": []})
            e["score"] += s
            e["papers"].append({"title": w.get("title"), "year": w.get("publication_year"),
                                "url": w.get("doi") or w.get("id"), "match": s})
    out = sorted(by.values(), key=lambda e: -e["score"])[:top]
    for e in out:
        e["papers"] = sorted(e["papers"], key=lambda p: -p["match"])[:3]
    return out


def find_researchers(targets, profile, resume="", top_per_company=6, db=None, since="2025-01-01", batch=None):
    """With a key: scans every company. Keyless: scans `batch` (default 6) least-recently-scanned companies per call,
    so the small free daily budget is enough - run daily and it covers everyone over a few days."""
    terms = user_terms(profile, resume)
    if batch is None:
        batch = None if os.environ.get("OPENALEX_API_KEY") else 6
    if db and batch:
        targets = sorted(targets, key=lambda t: db.get("scanned:" + t["name"], ""))[:batch]
    if not terms:
        print("[researchers] add `interests:` (and a `background:`) to profile.yaml so I know who is similar to you")
        return []
    print(f"[researchers] matching on: {', '.join(terms[:12])}")
    found = []
    for t in targets:
        try:
            inst = find_institution(t["name"].split("(")[0].strip())
            if not inst:
                continue
            ranked = rank_authors(recent_works(inst, since), inst, terms, top_per_company)
        except OpenAlexError:
            raise
        except Exception as e:
            print(f"[researchers] {t['name']}: {type(e).__name__}")
            continue
        for r in ranked:
            r["company"] = t["name"]
            found.append(r)
            if db:
                db.upsert_researcher(r)
        if db:
            from datetime import datetime
            db.put("scanned:" + t["name"], datetime.now().isoformat())
        if ranked:
            print(f"[researchers] {t['name']}: {len(ranked)} similar researchers")
    return found
