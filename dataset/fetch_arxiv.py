import time
import json, os
import re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag

UA = "your-app-name/1.0 (mailto:you@example.com)"

REF_HEAD_RE = re.compile(r"^\s*(references|bibliography|reference|references and notes)\s*$", re.IGNORECASE)
DOI_RE = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"arxiv\.org/(abs|pdf)/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.IGNORECASE)

def _normalize_space(s: str) -> str:
    return " ".join(s.split())

def _heading_level(tag_name: str) -> int:
    if tag_name and tag_name.lower().startswith("h") and tag_name[1:].isdigit():
        return int(tag_name[1:])
    return 7

def _find_bibliography_container(soup: BeautifulSoup):
    node = soup.select_one(".ltx_bibliography")
    if node:
        return node
    node = soup.find(
        lambda t: isinstance(t, Tag)
        and (
            ("bibliography" in (t.get("id", "") + " " + " ".join(t.get("class", []))).lower())
            or ("references" in (t.get("id", "") + " " + " ".join(t.get("class", []))).lower())
        )
    )
    if node:
        return node
    for h in soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE)):
        title = _normalize_space(h.get_text(" ", strip=True))
        if REF_HEAD_RE.match(title):
            lvl = _heading_level(h.name or "")
            wrapper = soup.new_tag("div")
            for sib in h.next_siblings:
                if isinstance(sib, NavigableString):
                    if not sib.strip():
                        continue
                    p = soup.new_tag("p")
                    p.string = str(sib)
                    wrapper.append(p)
                    continue
                if isinstance(sib, Tag):
                    if _heading_level(sib.name or "") <= lvl:
                        break
                    wrapper.append(sib)
            return wrapper
    return None

def extract_refs(soup: BeautifulSoup):
    cont = _find_bibliography_container(soup)
    if not cont:
        return []
    items = cont.select(".ltx_bibitem")
    if not items:
        items = cont.find_all(["li", "p"])
    out = []
    for idx, it in enumerate(items, 1):
        text = _normalize_space(it.get_text(" ", strip=True))
        links, dois, arxivs = [], [], []
        for a in it.find_all("a", href=True):
            href = a["href"].strip()
            links.append(href)
            m = DOI_RE.search(href)
            if m:
                dois.append(m.group(1))
            m = ARXIV_RE.search(href)
            if m:
                arxivs.append(m.group(2))
        out.append({
            "index": idx,
            "id": it.get("id"),
            "text": text,
            "links": sorted(set(links)),
            "doi": dois[0] if dois else None,
            "arxiv_id": arxivs[0] if arxivs else None,
        })
    return out

def ar5iv_text_and_refs(arxiv_id):
    url = f"https://ar5iv.org/html/{arxiv_id}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "header", "nav", "footer"]):
        tag.decompose()
    refs = extract_refs(soup)
    bibl = _find_bibliography_container(soup)
    if bibl:
        bibl.decompose()
    body = (soup.find("body") or soup).get_text("\n", strip=True)
    return body, refs

ids = ["2101.00001", "2101.00002"]
for aid in ids:
    try:
        body, refs = ar5iv_text_and_refs(aid)
        os.makedirs(f"data/{aid}", exist_ok=True)
        with open(f"data/{aid}/body.txt", "w", encoding="utf-8") as f:
            f.write(body)
        with open(f"data/{aid}/ref.json", "w", encoding="utf-8") as f:
            json.dump(refs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("failed:", aid, e)
    time.sleep(2)


