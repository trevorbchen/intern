import requests

UA = "internbot/0.1 (research internship finder)"


def get(url, **kw):
    kw.setdefault("timeout", 20)
    kw.setdefault("headers", {}).setdefault("User-Agent", UA)
    r = requests.get(url, **kw)
    r.raise_for_status()
    return r
