# In order to use import correctly, you should run this (in root) with something like:
# python -m pipeline.four_metric_pipeline 2026 --num_sample 1000

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

    indices = json.load(f"data/indices/indices_{year}.json")
    math_list = random.sample(indices["math"], num_sample)
    csai_list = random.sample(indices["cs.ai"], num_sample)

    ### Download these papers.
    ### you should need to call the function ar5iv_text_and_refs imported


    ### Load and evaluate these papers.
    ### you should need to make up the directories to target papers, in order to load their contents
    ### you should need to use the 4 metric functions imported, in order to eval
    ### Maybe you should iteratively load a paper, eval it, save its result, the unload it
    ### instead of loading all papers all at once, in order to save memory.


    ### Store eval results somewhere nice (under 'results' folder, for example), in nice formats (like json).
    ### PS: I have made sure that 'results' folder would be ignored by git.


    
