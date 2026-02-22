# In order to use import correctly, you should run this (in root) with something like:
# python -m pipeline.get_metrics 2026 --num_sample 5 --seed 1

# Preferably, use argparse and arguments in commands, rather than writing things like number of samples in code.

from metrics.empirical_clarity import eval_empirical_clarity
from metrics.explanation_vs_speculation import eval_explanation_vs_speculation
from metrics.language_misuse import eval_language_misuse
from metrics.math_quality import eval_math_quality

from dataset.fetch_paper import ar5iv_text_and_refs

import argparse
import json
import os
import random
import time
import tiktoken



if __name__ == '__main__':
    ap = argparse.ArgumentParser(description="Start evaluation pipeline.")
    ap.add_argument("year", type=int, help="Year, e.g., 2023")
    ap.add_argument("--num_sample", type=int, default=10, help="Number of samples")
    ap.add_argument("--seed", type=int, default=None, help="Random seed")
    args = ap.parse_args()
    num_sample = args.num_sample
    year = args.year

    if args.seed is not None:
        random.seed(args.seed)

    indices = json.load(open(f"data/indices/indices_{year}.json", "r", encoding="utf-8"))#是否需要修改？
    math_list = random.sample(indices["math"], num_sample)
    csai_list = random.sample(indices["cs.ai"], num_sample)

    
    # 3. 批量下载math和cs.ai领域的论文
    downloaded_papers = []  # 记录成功下载的论文（领域, arxiv_id）
    # 下载math领域
    for arxiv_id in math_list:
        if os.path.exists(f"data/papers/{arxiv_id}"):
            print(f"[SKIP] 论文 {arxiv_id} 已下载")
            downloaded_papers.append(("cs.ai", arxiv_id))
            continue
        try:            
            body, refs = ar5iv_text_and_refs(arxiv_id)
            os.makedirs(f"data/papers/{arxiv_id}", exist_ok=True)
            with open(f"data/papers/{arxiv_id}/body.txt", "w", encoding="utf-8") as f:
                f.write(body)
            with open(f"data/papers/{arxiv_id}/ref.json", "w", encoding="utf-8") as f:
                json.dump(refs, f, ensure_ascii=False, indent=2)
            downloaded_papers.append(("math", arxiv_id))
        except Exception as e:
            print("failed:", arxiv_id, e)
        time.sleep(2)
        
    for arxiv_id in csai_list:
        if os.path.exists(f"data/papers/{arxiv_id}"):
            print(f"[SKIP] 论文 {arxiv_id} 已下载")
            downloaded_papers.append(("cs.ai", arxiv_id))
            continue
        try:
            body, refs = ar5iv_text_and_refs(arxiv_id)
            os.makedirs(f"data/papers/{arxiv_id}", exist_ok=True)
            with open(f"data/papers/{arxiv_id}/body.txt", "w", encoding="utf-8") as f:
                f.write(body)
            with open(f"data/papers/{arxiv_id}/ref.json", "w", encoding="utf-8") as f:
                json.dump(refs, f, ensure_ascii=False, indent=2)
            downloaded_papers.append(("cs.ai", arxiv_id))
        except Exception as e:
            print("failed:", arxiv_id, e)
        time.sleep(2)
    
    # 无成功下载的论文则终止流程
    if not downloaded_papers:
        print("[ERROR] 无论文下载成功，终止评估流程")
        exit(1)
        
    for domain, arxiv_id in downloaded_papers:
        body_path = os.path.join("data/papers", arxiv_id, "body.txt")
        if not os.path.exists(body_path):
            print(f"[SKIP] 论文 {arxiv_id} 正文文件缺失，跳过评估")
            continue
        
        try:
            print(f"[EVAL] 正在评估 {domain} 领域论文 {arxiv_id}...")
            with open(body_path, "r", encoding="utf-8") as f:
                paper_text = f.read()
            
            # paper_text_truncated = truncate_text_for_llm(paper_text)
            score_empirical = eval_empirical_clarity(paper_text)
            score_explanation = eval_explanation_vs_speculation(paper_text)
            score_language = eval_language_misuse(paper_text)
            score_math = eval_math_quality(paper_text)
            
            # 3. 收集单篇论文结果（自动释放paper_text内存）
            eval_results = {
                "arxiv_id": arxiv_id,
                "domain": domain,
                "year": year,
                "empirical_clarity_score": score_empirical,
                "explanation_vs_speculation_score": score_explanation,
                "language_misuse_score": score_language,
                "math_quality_score": score_math
            }

            RESULT_SAVE_DIR = "results"
            os.makedirs(RESULT_SAVE_DIR, exist_ok=True)
            result_filename = f"eval_results_{domain}_{arxiv_id}.json"
            result_path = os.path.join(RESULT_SAVE_DIR, result_filename)
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(eval_results, f, ensure_ascii=False, indent=2)

            print(f"[SUCCESS] 论文 {arxiv_id} 评估完成")

        except Exception as e:
            print(f"[FAIL] 论文 {arxiv_id} 评估失败: {str(e)}")
            continue
    
    print(f"\n[FINISH] 评估流程完成！")
    print(f"- 结果已保存至: {RESULT_SAVE_DIR}")
