#!/usr/bin/env python3
# arxiv_sampler.py
# ASCII only

import sys
import time
import math as _pymath
import random
import argparse
import urllib.parse
import requests
import xml.etree.ElementTree as ET
import re
import json

ARXIV_API = "http://export.arxiv.org/api/query"
UA = "your-app-name/1.0 (mailto:you@example.com)"
RATE_DELAY = 2.0  # seconds between API calls (arXiv guidance)

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

ID_RE_VERSION = re.compile(r"v\d+$")

def _date_range_for_year(year: int):
    y = int(year)
    return f"{y}01010000", f"{y}12312359"

def _build_query(cat_expr: str, year: int) -> str:
    s, e = _date_range_for_year(year)
    # submittedDate range AND category expression
    q = f"submittedDate:[{s} TO {e}] AND ({cat_expr})"
    return q

def _http_get(url, params, timeout=60):
    headers = {"User-Agent": UA}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text

def _parse_total_results(xml_text: str) -> int:
    root = ET.fromstring(xml_text)
    tr = root.find("opensearch:totalResults", NS)
    return int(tr.text) if tr is not None and tr.text and tr.text.isdigit() else 0

def _extract_ids_from_feed(xml_text: str):
    root = ET.fromstring(xml_text)
    out = []
    for entry in root.findall("atom:entry", NS):
        ide = entry.find("atom:id", NS)
        if ide is None or not ide.text:
            continue
        aid = ide.text.split("/abs/", 1)[-1]
        aid = aid.split("?", 1)[0].split("#", 1)[0]
        aid = ID_RE_VERSION.sub("", aid)
        out.append(aid)
    return out

def _fetch_ids_for_category_year(cat_expr: str, year: int, page_size: int = 2000):
    ids = []
    q = _build_query(cat_expr, year)
    params = {
        "search_query": q,
        "start": 0,
        "max_results": 1,
        "sortBy": "submittedDate",
        "sortOrder": "ascending",
    }
    xml_text = _http_get(ARXIV_API, params)
    total = _parse_total_results(xml_text)
    if total == 0:
        return ids

    # FIXME: Too many papers result in error.
    # page through results
    n_pages = int(_pymath.ceil(total / float(page_size)))
    for p in range(n_pages):
        start = p * page_size
        params = {
            "search_query": q,
            "start": start,
            "max_results": page_size,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
        xml_text = _http_get(ARXIV_API, params)
        batch = _extract_ids_from_feed(xml_text)
        if not batch:
            break
        ids.extend(batch)
        time.sleep(RATE_DELAY)
    return ids

def sample_arxiv_ids(year: int, seed: int = None):
    """
    Return up to num_sample arXiv IDs (strings) for the given year,
    restricted to cs.AI and Mathematics.
    """
    if seed is not None:
        random.seed(seed)

    # Query cs.AI and Mathematics separately, then take union.
    # For Mathematics, 'cat:math' matches the math group.
    cs_ids = _fetch_ids_for_category_year("cat:cs.AI", year)
    math_ids = _fetch_ids_for_category_year("cat:math.*", year)

    cs_list = list(sorted(set(cs_ids)))
    math_list = list(sorted(set(math_ids)))

    return {
        "cs.ai": cs_list,
        "math": math_list,
    }

def main():
    ap = argparse.ArgumentParser(description="Sample arXiv IDs from cs.AI and Mathematics for a given year.")
    ap.add_argument("year", type=int, help="Year, e.g., 2023")
    ap.add_argument("--seed", type=int, default=None, help="Random seed")
    ap.add_argument("--no-delay", action="store_true", help="DO NOT sleep between requests (not recommended)")
    args = ap.parse_args()

    global RATE_DELAY
    if args.no_delay:
        RATE_DELAY = 0.0

    result = sample_arxiv_ids(args.year, seed=args.seed)
    with open(f"data/indices/indices_{args.year}.json", "w") as f:
        json.dump(result, f)

if __name__ == "__main__":
    main()

