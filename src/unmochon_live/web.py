import asyncio
import hashlib
import ipaddress
import re
import socket
from urllib.parse import urlsplit, urljoin, parse_qs, unquote
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup
from .schemas import Evidence, now
from .text import tokens

class SourceError(ValueError): pass

def host_allowed(host, domains):
    return any(host == d or host.endswith("." + d) for d in domains)

def verify_url(url, domains=()):
    p = urlsplit(url)
    host = (p.hostname or "").lower().rstrip(".")
    if p.scheme != "https" or not host or p.username or p.password or p.port not in (None,443):
        raise SourceError("Expected public HTTPS government URL")
    if not host.endswith(".gov.bd"):
        raise SourceError("Non-government domain rejected")
    if domains and not host_allowed(host, domains):
        raise SourceError("Outside relevant authority domains")
    return host

async def public_dns(host):
    loop = asyncio.get_running_loop()
    addresses = await loop.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise SourceError("Non-public address rejected")

@dataclass
class Page:
    url: str
    title: str
    passages: list[str]
    links: list[str]
    checked_at: str
    sha256: str

class OfficialFetcher:
    def __init__(self, settings, transport=None, resolver=public_dns):
        self.settings=settings; self.transport=transport; self.resolver=resolver

    async def fetch(self,url,domains=()):
        async with httpx.AsyncClient(timeout=self.settings.web_timeout, follow_redirects=False,
                transport=self.transport, trust_env=False,
                headers={"User-Agent":"UnmochonResearch/0.1 (read-only official information retrieval)"}) as client:
            for _ in range(5):
                host=verify_url(url,domains)
                await self.resolver(host)
                async with client.stream("GET",url) as response:
                    if response.status_code in (301,302,303,307,308):
                        location=response.headers.get("location")
                        if not location: raise SourceError("Missing redirect location")
                        url=urljoin(url,location); continue
                    response.raise_for_status()
                    ct=response.headers.get("content-type","").lower()
                    if "html" not in ct and "text/plain" not in ct:
                        raise SourceError("Unsupported content: PDF/OCR processing belongs to acquisition phase")
                    chunks=[];size=0
                    async for chunk in response.aiter_bytes():
                        size+=len(chunk)
                        if size>self.settings.web_max_bytes: raise SourceError("Page exceeds byte limit")
                        chunks.append(chunk)
                    raw=b"".join(chunks)
                    encoding=response.encoding or "utf-8"
                return parse_page(url,raw,encoding)
        raise SourceError("Too many redirects")

def parse_page(url,raw,encoding="utf-8"):
    soup=BeautifulSoup(raw.decode(encoding,errors="replace"),"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else urlsplit(url).hostname or ""
    links=[urljoin(url,a["href"]) for a in soup.select("a[href]")]
    for node in soup.select("script,style,nav,footer,header,aside,form,noscript"):
        node.decompose()
    content=soup.select_one("main,article,#content,.content") or soup.body or soup
    passages=[]
    for node in content.select("h1,h2,h3,p,li,td"):
        # Avoid repeated blocks nested inside a list item or table cell.
        if node.find_parent(["p","li","td"]): continue
        t=re.sub(r"\s+"," ",node.get_text(" ",strip=True))
        if len(t)>=30 and t not in passages: passages.append(t[:4000])
    if not passages:
        text=re.sub(r"\s+"," ",content.get_text(" ",strip=True))
        if len(text)>=60: passages=[text[:4000]]
    return Page(url,title,passages,links,now(),hashlib.sha256(raw).hexdigest())

class DuckDuckGoSearch:
    """Best-effort, key-free discovery. Search snippets are NEVER answer evidence."""
    def __init__(self, settings): self.settings=settings
    async def search(self, question, domains):
        filters=" OR ".join("site:"+d for d in domains) if domains else "site:gov.bd"
        async with httpx.AsyncClient(timeout=self.settings.web_timeout,trust_env=False) as client:
            async with client.stream("GET","https://html.duckduckgo.com/html/",params={"q":question+" "+filters}) as r:
                r.raise_for_status();chunks=[];size=0
                async for chunk in r.aiter_bytes():
                    size+=len(chunk)
                    if size>self.settings.web_max_bytes: raise SourceError("Search response too large")
                    chunks.append(chunk)
        soup=BeautifulSoup(b"".join(chunks),"html.parser");urls=[]
        for a in soup.select("a.result__a"):
            link=a.get("href","");p=urlsplit(link)
            if "duckduckgo.com" in (p.hostname or ""):
                link=parse_qs(p.query).get("uddg",[""])[0]
            try: verify_url(link,domains)
            except (SourceError,ValueError): continue
            if link not in urls:urls.append(link)
        return urls[:6]

class LiveRetriever:
    def __init__(self,settings,registry,fetcher=None,searcher=None):
        self.settings=settings;self.registry=registry
        self.fetcher=fetcher or OfficialFetcher(settings)
        self.searcher=searcher or DuckDuckGoSearch(settings)

    async def retrieve(self,question,service=None,extra_seeds=()):
        domains=service.domains if service else self.registry.policy_domains if extra_seeds else ()
        seeds=list(service.seeds if service else extra_seeds)
        warnings=[];trace=["OFFICIAL_DISCOVERY"]
        evidence=[];fetched=0
        async def work():
            nonlocal fetched
            queue=list(seeds)
            if self.settings.enable_web_search:
                try: queue.extend(await self.searcher.search(question,domains))
                except (httpx.HTTPError,SourceError):warnings.append("Search unavailable; using curated official entry points.")
            seen=set();qt=set(tokens(question))
            qlower=question.lower()
            intent_groups=[
                (("document","কাগজ","নথি"),("document","কাগজ","নথি","nid","brc","birth","জন্ম","পরিচয়","পরিচয়")),
                (("fee","ফি","খরচ"),("fee","ফি","টাকা","bdt","cost")),
                (("age","বয়স","বয়স"),("age","বয়স","বয়স","বছর")),
            ]
            requested=[evidence_terms for query_terms,evidence_terms in intent_groups
                if any(w in qlower for w in query_terms)]
            while queue and len(seen)<self.settings.web_max_pages:
                url=queue.pop(0)
                if url in seen:continue
                try:verify_url(url,domains)
                except (SourceError,ValueError):continue
                seen.add(url)
                try:page=await self.fetcher.fetch(url,domains)
                except (httpx.HTTPError,SourceError,OSError,UnicodeError):
                    warnings.append("An official page could not be read; no facts inferred from it.");continue
                fetched+=1
                ranked=[]
                for text in page.passages:
                    matched=qt & set(tokens(text))
                    # Service name alone or a maintenance banner is not an answer.
                    requirement_words=("document","application","registration","eligib","require","কাগজ","আবেদন","নিবন্ধ","প্রয়োজন","যোগ্য","ফরম","বয়স","fee","cost","ফি","টাকা")
                    has_detail=any(w in text.lower() for w in requirement_words)
                    intent_match=all(any(w in text.lower() for w in terms) for terms in requested)
                    if (matched or requested) and has_detail and intent_match:
                        ranked.append((len(matched),text))
                for _,text in sorted(ranked,key=lambda item:item[0],reverse=True)[:2]:
                    evidence.append(Evidence(id=hashlib.sha256((page.url+text).encode()).hexdigest()[:16],
                        text=text,source_kind="official_web",title=page.title,source_url=page.url,
                        checked_at=page.checked_at,content_sha256=page.sha256,
                        verification="official_fetched",freshness="checked_now_version_unknown"))
                for link in page.links:
                    try:verify_url(link,domains)
                    except (SourceError,ValueError):continue
                    if link not in seen and link not in queue and any(s in unquote(link).lower() for s in
                        ("instruction","document","faq","enroll","registration","নিবন্ধ","কাগজ","প্রয়োজন")):
                        queue.append(link)
        try:
            async with asyncio.timeout(self.settings.web_total):await work()
        except TimeoutError:warnings.append("Official retrieval reached the time budget.")
        trace.append(f"OFFICIAL_PAGES_FETCHED:{fetched}")
        warnings.append("Live passages are source excerpts; fetching today does not establish latest-version validity or a complete personalised checklist.")
        # Separate source availability from answer adequacy.
        status="EVIDENCE_FOUND" if evidence else "NEEDS_VERIFICATION" if fetched else "UNAVAILABLE"
        return evidence[:6],list(dict.fromkeys(warnings)),trace,status
