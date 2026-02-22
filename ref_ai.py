import os
import json
import re
import requests
import Levenshtein
from habanero import Crossref
from typing import Dict, List, Optional
import time

# ====================== 配置常量 ======================
# 根路径（注意用原始字符串避免转义）
PAPERS_ROOT = r"D:/校务/Projects/problematic-papers/data/papers"
# 结果保存路径
RESULT_SAVE_PATH = r"D:/校务/Projects/problematic-papers/citation_ai_rate.json"
# API请求头（
HEADERS = {
    "User-Agent": "CitationChecker/1.0 (mailto:csy24@ruc.edu.cn)",
    "Accept": "application/json"
}
# 模糊匹配阈值（标题相似度≥0.8视为匹配）
TITLE_SIMILARITY_THRESHOLD = 0.8
# 年份容忍区间
YEAR_TOLERANCE = 1
# Crossref实例（用于学术数据库查询）
#cr = Crossref(headers=HEADERS)
#cr = Crossref(request_options={"headers": HEADERS})
# ====================== 工具函数 ======================
def get_all_ref_json_paths() -> List[Dict[str, str]]:
    """遍历papers目录，获取所有ref.json的路径及对应的arxiv_id"""
    ref_files = []
    for folder_name in os.listdir(PAPERS_ROOT):
        folder_path = os.path.join(PAPERS_ROOT, folder_name)
        if not os.path.isdir(folder_path):
            continue
        ref_json_path = os.path.join(folder_path, "ref.json")
        if os.path.exists(ref_json_path):
            ref_files.append({
                "arxiv_id": folder_name,
                "ref_path": ref_json_path
            })
    return ref_files

def parse_citation_text(citation_text: str) -> Dict:
    """
    解析引文文本，提取结构化数据（作者、标题、年份、DOI）
    结合正则+简单规则，兼顾鲁棒性和易用性
    """
    parsed = {
        "authors": [],
        "title": "",
        "year": None,
        "doi": None,
        "journal": "",
        "original_text": citation_text
    }

    # 1. 提取DOI（优先）
    doi_pattern = r"doi:\s*(10\.\d{4,9}/[-._;()/:A-Z0-9]+)"
    doi_match = re.search(doi_pattern, citation_text, re.IGNORECASE)
    if doi_match:
        parsed["doi"] = doi_match.group(1).strip().upper()

    # 2. 提取年份（括号内的4位数字）
    year_pattern = r"\((\d{4})\)"
    year_match = re.search(year_pattern, citation_text)
    if year_match:
        try:
            parsed["year"] = int(year_match.group(1))
        except ValueError:
            parsed["year"] = None

    # 3. 提取作者（逗号分隔的姓名，直到年份前的括号）
    author_part = re.split(r"\(\d{4}\)", citation_text)[0].strip()
    if author_part and " and " in author_part:
        # 拆分作者（处理 "A, B, and C" 格式）
        authors = re.split(r",\s*and\s*", author_part)
        if len(authors) == 2:
            first_authors = re.split(r",\s*", authors[0])
            authors = first_authors + [authors[1]]
        parsed["authors"] = [a.strip() for a in authors if a.strip()]
    elif author_part:
        parsed["authors"] = [author_part.strip()]

    # 4. 提取标题（年份后到期刊/会议前的部分）
    title_match = re.search(r"\(\d{4}\)\s*(.+?)\s*(In|in|//|—|–)", citation_text)
    if title_match:
        parsed["title"] = title_match.group(1).strip().rstrip(".,:;")
    else:
        # 兜底：取年份后到末尾前的部分
        title_part = re.split(r"\(\d{4}\)", citation_text)[-1].strip()
        # 移除期刊/会议标识
        title_part = re.sub(r"\s*(In|in)\s*.+", "", title_part).strip()
        parsed["title"] = title_part.rstrip(".,:;")

    # 5. 提取期刊/会议
    journal_match = re.search(r"(In|in)\s*(.+?)\s*(,|pp\.|–|—)", citation_text)
    if journal_match:
        parsed["journal"] = journal_match.group(2).strip()

    return parsed

def validate_doi(doi: str) -> Optional[Dict]:
    """验证DOI是否存在，返回权威元数据（None表示不存在）"""
    if not doi:
        return None
    # DOI标准化（移除前缀）
    doi = doi.replace("https://doi.org/", "").strip()
    # 调用doi.org API
    url = f"https://doi.org/api/handles/{doi}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 404:
            return None  # DOI不存在
        elif response.status_code == 200:
            cr_url = f"https://api.crossref.org/works/{doi}"
            cr_response = requests.get(cr_url, headers=HEADERS, timeout=10)
            if cr_response.status_code == 200:
                return cr_response.json().get("message", {})
        return None
    except Exception as e:
        print(f"DOI验证失败 {doi}: {str(e)}")
        return None

def search_by_title_author(title: str, authors: List[str]) -> Optional[Dict]:
    """通过标题+作者搜索CrossRef，返回最匹配的元数据"""
    if not title or not authors:
        return None
    # 构造搜索关键词（作者姓氏 + 标题核心词）
    author_surnames = [a.split()[-1] for a in authors if a.strip()]
    query = f"{', '.join(author_surnames)} {title[:100]}"  # 截断过长标题

    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": 1,
        "sort": "relevance"
    }

    try:
        # 直接使用 requests 调用 API
        response = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            items = response.json().get("message", {}).get("items", [])
        if items:
            return items[0]  # 返回最相关的结果
        return None
    except Exception as e:
        print(f"标题+作者搜索失败 {title[:50]}: {str(e)}")
        return None

def calculate_text_similarity(text1: str, text2: str) -> float:
    """计算文本相似度（Levenshtein距离）"""
    if not text1 or not text2:
        return 0.0
    # 统一小写，移除标点
    clean1 = re.sub(r"[^\w\s]", "", text1.lower()).strip()
    clean2 = re.sub(r"[^\w\s]", "", text2.lower()).strip()
    if not clean1 or not clean2:
        return 0.0
    # 计算相似度（0-1）
    distance = Levenshtein.distance(clean1, clean2)
    max_len = max(len(clean1), len(clean2))
    return 1 - (distance / max_len) if max_len > 0 else 0.0

def compare_metadata(parsed: Dict, official_meta: Dict) -> int:
    """
    比对解析数据和权威元数据，返回级别：
    0 = L0（格式错误）, 1 = L1（部分失实）, 2 = L2（完全捏造）
    """
    # 1. 标题相似度检查
    official_title = official_meta.get("title", [""])[0]
    title_similarity = calculate_text_similarity(parsed["title"], official_title)
    if title_similarity < TITLE_SIMILARITY_THRESHOLD:
        return 2  # 标题不匹配，判定L2

    # 2. 作者比对（L1核心检查）
    parsed_authors = [a.split()[-1].lower() for a in parsed["authors"] if a.strip()]
    official_authors = []
    for auth in official_meta.get("author", []):
        if "family" in auth:
            official_authors.append(auth["family"].lower())
    # 检查作者交集（至少匹配1个核心作者）
    author_intersection = set(parsed_authors) & set(official_authors)
    if not author_intersection and len(parsed_authors) > 0 and len(official_authors) > 0:
        return 1  # 作者完全不匹配，判定L1

    # 3. 期刊比对（L1补充检查）
    if parsed["journal"]:
        journal_similarity = calculate_text_similarity(parsed["journal"], official_meta.get("container-title", [""])[0])
        if journal_similarity < 0.5:  # 期刊相似度极低
            return 1

    # 4. 年份比对（L0次要检查）
    official_year = None
    if "published-print" in official_meta and official_meta["published-print"].get("date-parts"):
        official_year = official_meta["published-print"]["date-parts"][0][0]
    elif "published-online" in official_meta and official_meta["published-online"].get("date-parts"):
        official_year = official_meta["published-online"]["date-parts"][0][0]
    
    if parsed["year"] and official_year:
        year_diff = abs(parsed["year"] - official_year)
        if year_diff > YEAR_TOLERANCE:
            return 0  # 年份误差超范围，判定L0

    # 5. 其他小错误（拼写、页码等）默认L0
    return 0

def process_paper_citations(arxiv_id: str, ref_path: str) -> float:
    """处理单篇论文的所有引用，返回引用AI率"""
    try:
        # 读取ref.json
        with open(ref_path, "r", encoding="utf-8") as f:
            citations = json.load(f)
        if not citations:
            print(f"[SKIP] {arxiv_id} 无引用数据")
            return 0.0

        citation_levels = []
        for idx, cite in enumerate(citations):
            cite_text = cite.get("text", "").strip()
            if not cite_text:
                citation_levels.append(2)  # 空引用判定L2
                continue
            
            # 步骤1：解析引文
            parsed = parse_citation_text(cite_text)
            # 步骤2：验证存在性（L2）
            official_meta = None
            # 2.1 优先验证DOI
            if parsed["doi"]:
                official_meta = validate_doi(parsed["doi"])
            # 2.2 其次验证标题+作者
            if not official_meta:
                official_meta = search_by_title_author(parsed["title"], parsed["authors"])
            
            if not official_meta:
                # 无匹配结果，判定L2
                citation_levels.append(2)
                print(f"[L2] {arxiv_id} 引用{idx+1}: 完全捏造")
                continue
            
            # 步骤3：元数据比对（L1/L0）
            level = compare_metadata(parsed, official_meta)
            citation_levels.append(level)
            level_name = {0: "L0", 1: "L1", 2: "L2"}[level]
            print(f"[{level_name}] {arxiv_id} 引用{idx+1}: {level_name}")
            
            # 限流：避免API请求过快
            time.sleep(0.5)

        # 计算AI率（L0=0, L1=1, L2=2，求平均）
        if not citation_levels:
            ai_rate = 0.0
        else:
            ai_rate = sum(citation_levels) / len(citation_levels)
        print(f"[DONE] {arxiv_id} 引用AI率: {ai_rate:.2f}")
        return ai_rate

    except Exception as e:
        print(f"[ERROR] 处理 {arxiv_id} 失败: {str(e)}")
        return 0.0

# ====================== 主函数 ======================
def main():
    print("开始处理所有论文的引用验证...")
    # 1. 获取所有ref.json路径
    ref_files = get_all_ref_json_paths()
    if not ref_files:
        print("未找到任何ref.json文件")
        return

    # 2. 处理每篇论文
    final_results = {}
    for file_info in ref_files:
        arxiv_id = file_info["arxiv_id"]
        ref_path = file_info["ref_path"]
        ai_rate = process_paper_citations(arxiv_id, ref_path)
        final_results[arxiv_id] = round(ai_rate, 4)  # 保留4位小数

    # 3. 保存结果到JSON
    with open(RESULT_SAVE_PATH, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n处理完成！结果已保存至: {RESULT_SAVE_PATH}")
    print(f"共处理 {len(final_results)} 篇论文")

if __name__ == "__main__":
    main()