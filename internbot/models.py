from dataclasses import dataclass, field
import hashlib


@dataclass
class Posting:
    source: str          # greenhouse / lever / rss / linkedin / twitter
    title: str
    company: str
    url: str
    location: str = ""
    description: str = ""
    posted: str = ""
    handle: str = ""       # twitter author, e.g. @prof_smith
    apply_url: str = ""    # external application link found in the post

    @property
    def uid(self) -> str:
        return hashlib.sha1(self.url.split("?")[0].encode()).hexdigest()
