import json
from pathlib import Path
from dataclasses import dataclass
from .text import normalize

@dataclass(frozen=True)
class Service:
    id: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    seeds: tuple[str, ...]

class Registry:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.services = [Service(x["id"], tuple(x["aliases"]), tuple(x["domains"]), tuple(x["seeds"])) for x in raw["services"]]
        self.policy_domains = tuple(raw["policy_domains"])

    def match(self, question):
        import re
        q = normalize(question)
        return [s for s in self.services if any(
            re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", q) if a.isascii()
            else normalize(a) in q for a in s.aliases)]
