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

    @property
    def uid(self) -> str:
        return hashlib.sha1(self.url.split("?")[0].encode()).hexdigest()
