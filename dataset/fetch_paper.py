import time
import json, os
import re
import requests
from bs4 import BeautifulSoup, NavigableString, Tag
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# More professional user agent
UA = "ArxivResearchBot/1.0 (mailto:research@example.com)"

REF_HEAD_RE = re.compile(r"^\s*(references|bibliography|reference|references and notes)\s*$", re.IGNORECASE)
DOI_RE = re.compile(r"doi\.org/(10\.\d{4,9}/\S+)", re.IGNORECASE)
ARXIV_RE = re.compile(r"arxiv\.org/(abs|pdf)/([a-z\-]+/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", re.IGNORECASE)

# Set to True if you want to keep section numbers like "1 Introduction"
KEEP_SEC_NUMBER = False

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

def _replace_math_with_tex(root: Tag):
    for m in root.find_all("math"):
        tex = None
        sem = m.find("semantics")
        if sem:
            for ann in sem.find_all(["annotation", "annotation-xml"]):
                enc = (ann.get("encoding") or "").lower()
                if "tex" in enc:
                    if ann.string and ann.string.strip():
                        tex = ann.string.strip()
                    else:
                        tex = re.sub(r"\s+", " ", ann.get_text(" ", strip=True))
                    break
        if tex is None:
            tex = re.sub(r"\s+", " ", m.get_text(" ", strip=True))
        disp = ((m.get("display") or "").lower() == "block")
        repl = ("$$%s$$" % tex) if disp else ("$%s$" % tex)
        m.replace_with(repl)

def _remove_reference_headings(soup: BeautifulSoup):
    for h in list(soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))):
        title = _normalize_space(h.get_text(" ", strip=True))
        if REF_HEAD_RE.match(title):
            h.decompose()

def _markdownize_headings(soup: BeautifulSoup, keep_number: bool = False):
    for h in list(soup.find_all(re.compile(r"^h[1-6]$", re.IGNORECASE))):
        lvl = max(1, min(6, _heading_level(h.name or "")))
        h_local = h
        if not keep_number:
            for t in h_local.select(".ltx_tag, .ltx_refnum"):
                t.decompose()
        title = _normalize_space(h_local.get_text(" ", strip=True))
        if not title:
            h.decompose()
            continue
        line = "#" * lvl + " " + title
        h.replace_with(NavigableString("\n" + line + "\n\n"))

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

def _validate_paper_content(text):
    """Validate that the content looks like an actual paper."""
    # Check if the content is too short
    if len(text) < 500:  # Reduced minimum length
        return False
    
    # Check for common paper sections
    paper_indicators = [
        r'\b(abstract|introduction|conclusion|discussion|method|results)\b',
        r'\bfigure\s+\d+\b',
        r'\btable\s+\d+\b',
        r'\bequation\s+\d+\b',
        r'\bsection\s+\d+\b',
        r'#\s+\w+',  # Markdown headings
        r'\*\*\w+\*\*'  # Bold text often used for section titles
    ]
    
    # Count how many indicators are found
    indicator_count = 0
    for pattern in paper_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            indicator_count += 1
    
    # Check for common meaningless content
    meaningless_indicators = [
        r'view\s+pdf',
        r'download\s+pdf',
        r'\blogin\b',
        r'\bregister\b',
        r'\baccess denied\b',
        r'submission history',
        r'cite as',
        r'arxiv:',
        r'bibliographic tools',
        r'focus to learn more'
    ]
    
    # Check for landing page patterns
    landing_page_patterns = [
        r'arxiv:\d{4}\.\d{5}',  # arxiv ID pattern
        r'\[v\d+\]',  # version pattern like [v1]
        r'submitted on \d+ [a-z]+ \d{4}',  # submission date
        r'https://doi\.org/10\.\d+/arxiv\.',  # DOI pattern
        r'full-text links',
        r'access paper',
        r'view license'
    ]
    
    # If we find landing page patterns, it's likely not the full paper
    for pattern in landing_page_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return False
    
    # If we find meaningless indicators that take up a significant portion of the text, reject it
    for pattern in meaningless_indicators:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # If these phrases appear multiple times or make up a significant portion of the text
            if len(matches) > 2 or len(''.join(matches)) > len(text) * 0.03:  # If meaningless content is >3% of text
                return False
    
    # For longer content, we need some structure
    if len(text) > 10000:
        # Need some indicators of paper structure
        if indicator_count == 0:
            # No paper indicators found, but let's check if it has enough paragraphs and sentences
            if text.count('.') < 20 or text.count('\n\n') < 5:
                return False
    else:
        # For shorter content, we need at least some paper indicators
        if indicator_count == 0:
            return False
    
    # For any content, check for minimal text structure
    if text.count('.') < 5:  # At least 5 sentences
        return False
    
    # Check for extremely repetitive content (often a sign of garbage)
    words = text.lower().split()
    if len(words) > 100:  # Only check for longer texts
        unique_words = set(words)
        unique_ratio = len(unique_words) / len(words)
        if unique_ratio < 0.1:  # Less than 10% unique words
            return False
    
    return True

def _download_from_ar5iv(arxiv_id):
    """Download paper from ar5iv.org."""
    url = f"https://ar5iv.org/html/{arxiv_id}"
    logging.info(f"Attempting to download from ar5iv: {url}")
    
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        
        # Check if we got a redirect to a login page or error page
        if "login" in r.url.lower() or "error" in r.url.lower():
            logging.warning(f"Redirected to a login or error page: {r.url}")
            return None, None
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Quick check for common error patterns in the page
        title_text = soup.title.string.lower() if soup.title else ""
        if any(x in title_text for x in ["error", "not found", "404", "403", "login", "access denied"]):
            logging.warning(f"Error page detected: {title_text}")
            return None, None
        
        # Check for arxiv landing page indicators
        if soup.find("div", class_="submission-history") or soup.find("div", class_="submission-details"):
            logging.warning("Found arxiv landing page indicators")
            return None, None
            
        # Check for "View PDF" links that might indicate we're on a landing page, not the actual paper
        view_pdf_links = soup.find_all("a", string=re.compile(r"view\s+pdf", re.IGNORECASE))
        if view_pdf_links and len(view_pdf_links) > 0:
            logging.warning("Found 'View PDF' links, likely a landing page")
            return None, None
        
        # Remove non-content elements
        for tag in soup(["script", "style", "header", "nav", "footer"]):
            tag.decompose()
        
        # Check if we have actual content
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="ltx_page_main")
        
        if not main_content:
            # Try to find the largest content div as a fallback
            content_divs = soup.find_all("div")
            if content_divs:
                # Sort divs by content length
                content_divs.sort(key=lambda x: len(x.get_text()), reverse=True)
                main_content = content_divs[0]  # Use the div with the most content
            else:
                logging.warning("No main content found in ar5iv page")
                return None, None
        
        # Check if the main content has enough text
        main_text = main_content.get_text(" ", strip=True)
        if len(main_text) < 500:  # Reduced minimum length
            logging.warning(f"Main content too short: {len(main_text)} characters")
            return None, None
        
        # 1) normalize math to TeX
        _replace_math_with_tex(soup)
        
        # 2) extract references
        refs = extract_refs(soup)
        
        # 3) remove bibliography content and its heading
        bibl = _find_bibliography_container(soup)
        if bibl:
            bibl.decompose()
        _remove_reference_headings(soup)
        
        # 4) markdownize headings
        _markdownize_headings(soup, keep_number=KEEP_SEC_NUMBER)
        
        # 5) extract text
        body = (main_content or soup.find("body") or soup).get_text("\n", strip=True)
        body = re.sub(r"\n{3,}", "\n\n", body)
        
        # Validate content
        if not _validate_paper_content(body):
            logging.warning("Content validation failed for ar5iv source")
            return None, None
            
        return body, refs
    except Exception as e:
        logging.error(f"Error downloading from ar5iv: {e}")
        return None, None

def _download_from_arxiv_abstract(arxiv_id):
    """Download paper abstract from arxiv.org."""
    url = f"https://arxiv.org/abs/{arxiv_id}"
    logging.info(f"Attempting to download abstract from arxiv: {url}")
    
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Extract abstract
        abstract = soup.find("blockquote", class_="abstract")
        if not abstract:
            logging.warning("No abstract found on arxiv page")
            return None, None
            
        # Get title
        title_element = soup.find("h1", class_="title")
        title = title_element.get_text(" ", strip=True).replace("Title:", "").strip() if title_element else "Unknown Title"
        
        # Get authors
        authors_element = soup.find("div", class_="authors")
        authors = authors_element.get_text(" ", strip=True).replace("Authors:", "").strip() if authors_element else "Unknown Authors"
        
        # Construct a basic paper structure with the abstract
        body = f"# {title}\n\n**Authors:** {authors}\n\n## Abstract\n\n{abstract.get_text(' ', strip=True)}\n\n"
        body += "\n\n*Note: This is only the abstract. Full paper content could not be retrieved.*"
        
        # No references from abstract page
        refs = []
        
        return body, refs
    except Exception as e:
        logging.error(f"Error downloading from arxiv abstract: {e}")
        return None, None

def _download_from_arxiv_pdf(arxiv_id):
    """
    This is a placeholder for PDF extraction functionality.
    In a real implementation, you would use a PDF extraction library like PyPDF2 or pdfminer.
    """
    logging.info(f"PDF extraction not implemented in this version")
    return None, None

def ar5iv_text_and_refs(arxiv_id):
    """
    Download and extract text and references from an arxiv paper.
    Raises an exception if the full paper content cannot be downloaded.
    """
    # Try ar5iv first (HTML version)
    body, refs = _download_from_ar5iv(arxiv_id)
    if body and _validate_paper_content(body):
        logging.info(f"Successfully downloaded paper {arxiv_id} from ar5iv")
        return body, refs
    
    # If ar5iv fails, raise an exception
    raise Exception(f"Failed to download full paper content for {arxiv_id}")

def main():
    # Test with multiple paper IDs to ensure robustness
    ids = ["2601.10679", "2310.06825", "2402.01703", "2312.11805", "2401.08406", "2305.14314", "1706.03762"]
    for aid in ids:
        try:
            logging.info(f"Processing paper: {aid}")
            body, refs = ar5iv_text_and_refs(aid)
            
            # Save the results only if we have valid content
            os.makedirs(f"data/papers/{aid}", exist_ok=True)
            with open(f"data/papers/{aid}/body.txt", "w", encoding="utf-8") as f:
                f.write(body)
            with open(f"data/papers/{aid}/ref.json", "w", encoding="utf-8") as f:
                json.dump(refs, f, ensure_ascii=False, indent=2)
            
            logging.info(f"Successfully saved paper {aid}")
        except Exception as e:
            logging.error(f"Failed to process paper {aid}: {e}")
            # Do not save anything for failed papers
        time.sleep(2)

if __name__ == "__main__":
    main()
    