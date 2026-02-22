# In order to use import correctly, you should run this (in root) with something like:
# python -m pipeline.four_metric_pipeline 2026 --num_sample 10

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
import re
import requests
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

    ### Download these papers.
    ### you should need to call the function ar5iv_text_and_refs imported
    # 1. 定义论文保存根目录，自动创建缺失目录
    PAPER_SAVE_DIR = "data/papers"
    os.makedirs(PAPER_SAVE_DIR, exist_ok=True)
    
    # 2. 封装下载单篇论文的函数（内部调用ar5iv_text_and_refs）
    def download_single_paper(arxiv_id):
        """下载单篇论文并保存正文到本地，返回是否成功"""
        paper_dir = os.path.join(PAPER_SAVE_DIR, arxiv_id)
        os.makedirs(paper_dir, exist_ok=True)
        body_path = os.path.join(paper_dir, "body.txt")
        
        # 已下载则跳过，避免重复请求
        if os.path.exists(body_path):
            print(f"[SKIP] 论文 {arxiv_id} 已下载")
            return True
        
        try:
            print(f"[DOWNLOAD] 正在下载 {arxiv_id}...")
            body, _ = ar5iv_text_and_refs(arxiv_id)  # 调用导入的下载函数，仅保留正文
            # 保存论文正文
            with open(body_path, "w", encoding="utf-8") as f:
                f.write(body)
            time.sleep(1)  # 限流，避免请求过快被封禁
            print(f"[SUCCESS] 论文 {arxiv_id} 下载完成")
            return True
        except Exception as e:
            print(f"[FAIL] 论文 {arxiv_id} 下载失败: {str(e)}")
            return False
    
    # 3. 批量下载math和cs.ai领域的论文
    downloaded_papers = []  # 记录成功下载的论文（领域, arxiv_id）
    # 下载math领域
    for arxiv_id in math_list:
        if download_single_paper(arxiv_id):
            downloaded_papers.append(("math", arxiv_id))
    # 下载cs.ai领域
    for arxiv_id in csai_list:
        if download_single_paper(arxiv_id):
            downloaded_papers.append(("cs.ai", arxiv_id))
    
    # 无成功下载的论文则终止流程
    if not downloaded_papers:
        print("[ERROR] 无论文下载成功，终止评估流程")
        exit(1)


    ### Load and evaluate these papers.
    ### you should need to make up the directories to target papers, in order to load their contents
    ### you should need to use the 4 metric functions imported, in order to eval
    ### Maybe you should iteratively load a paper, eval it, save its result, the unload it
    ### instead of loading all papers all at once, in order to save memory.
    eval_results = []  # 存储所有论文的评估结果
    
    #增加函数对论文text截断，避免prompt过长大模型无法读取
    #目前用的是thinking，运行较慢
    def truncate_text_for_llm(text, max_tokens=2000, model="gemini-2.5-pro"):
        """
        截断文本到指定Token数，优先保留前半部分（适配大模型prompt限额）
        :param text: 原始论文文本
        :param max_tokens: 最大Token数（留1000 Token给prompt模板，避免超限）
        :param model: 目标大模型（决定Token编码方式）
        :return: 截断后的文本
        """
        # 初始化Token编码器
        try:
            encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            # 兼容其他模型，用cl100k_base编码（通用）
            encoder = tiktoken.get_encoding("cl100k_base")
        
        # 编码文本为Token列表
        tokens = encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text  # 无需截断
        
        # 截断到max_tokens，保留前半部分
        truncated_tokens = tokens[:max_tokens]
        # 解码回文本（避免截断在单词/句子中间，可选优化）
        truncated_text = encoder.decode(truncated_tokens)
        
        # 可选优化：截断到最后一个完整句子（提升文本完整性）
        # 找最后一个句末标点（. ! ?），截断到该位置
        end_punctuations = ['.', '!', '?']
        last_punc_idx = max([truncated_text.rfind(p) for p in end_punctuations])
        if last_punc_idx != -1 and last_punc_idx > max_tokens * 0.8:  # 确保保留大部分内容
            truncated_text = truncated_text[:last_punc_idx + 1]
        
        print(f"[WARN] 文本过长，已截断至 {len(truncated_tokens)} Token（原 {len(tokens)} Token）")
        return truncated_text
    # 迭代评估每篇论文（单篇加载→评估→释放内存）
    for domain, arxiv_id in downloaded_papers:
        # 1. 加载论文正文
        body_path = os.path.join(PAPER_SAVE_DIR, arxiv_id, "body.txt")
        if not os.path.exists(body_path):
            print(f"[SKIP] 论文 {arxiv_id} 正文文件缺失，跳过评估")
            continue
        
        try:
            print(f"[EVAL] 正在评估 {domain} 领域论文 {arxiv_id}...")
            # 单篇加载文本（读完即释放，不占用大量内存）
            with open(body_path, "r", encoding="utf-8") as f:
                paper_text = f.read()
            
            # 2. 调用4个评估函数打分
            paper_text_truncated = truncate_text_for_llm(paper_text)
            score_empirical = eval_empirical_clarity(paper_text)
            score_explanation = eval_explanation_vs_speculation(paper_text)
            score_language = eval_language_misuse(paper_text)
            score_math = eval_math_quality(paper_text)
            
            # 3. 收集单篇论文结果（自动释放paper_text内存）
            eval_results.append({
                "arxiv_id": arxiv_id,
                "domain": domain,
                "year": year,
                "empirical_clarity_score": score_empirical,
                "explanation_vs_speculation_score": score_explanation,
                "language_misuse_score": score_language,
                "math_quality_score": score_math
            })
            print(f"[SUCCESS] 论文 {arxiv_id} 评估完成")
        except Exception as e:
            print(f"[FAIL] 论文 {arxiv_id} 评估失败: {str(e)}")
            continue

    ### Store eval results somewhere nice (under 'results' folder, for example), in nice formats (like json).
    ### PS: I have made sure that 'results' folder would be ignored by git.
    # 1. 创建results目录（自动创建）
    RESULT_SAVE_DIR = "results"
    os.makedirs(RESULT_SAVE_DIR, exist_ok=True)
    
    # 2. 定义结果文件名（包含年份和样本数，便于区分）
    result_filename = f"eval_results_{year}_{num_sample}.json"
    result_path = os.path.join(RESULT_SAVE_DIR, result_filename)
    
    # 3. 保存结果为JSON（格式化，便于阅读）
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(eval_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n[FINISH] 评估流程完成！")
    print(f"- 成功评估 {len(eval_results)} 篇论文")
    print(f"- 结果已保存至: {result_path}")

    
