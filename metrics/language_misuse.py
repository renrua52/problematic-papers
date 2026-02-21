from api.api import chat, extract_score

prompt_template = """
Academic papers may suffer from language misuse, which mainly manifests in the following three forms: 

1. Suggestive Definitions
   Definition: Coining anthropomorphic/colloquial technical terms without justification and overstating performance via vague "human-level" claims.
   - Mild: Describing a model as "learning" or "recognizing patterns" when the mechanism is clearly explained elsewhere
   - Severe: Claiming an AI system has "intuition", "consciousness", or "creativity" without operational definitions, or asserting "superhuman performance" without specifying the benchmark or human baseline

2. Overloading Technical Terminology
   Definition: Misapplying precisely defined technical terms in inappropriate contexts, confusing their original meanings.
   - Mild: Using "optimize" loosely to mean "improve" rather than referring to a formal optimization procedure
   - Severe: Claiming a language model achieves "understanding" or "reasoning" (terms with precise cognitive science meanings) based solely on benchmark accuracy, or using "causal" to describe purely correlational findings

3. Suitcase Words
   Definition: Multi-meaning vocabulary without a unified definition, causing inconsistent references in academic dialogue.
   - Mild: Using "intelligence" with slightly varying scope across sections, but context makes the intended meaning recoverable
   - Severe: Using "understanding" to mean statistical correlation in one paragraph, causal inference in another, and phenomenal comprehension in the conclusion, without ever defining the term or acknowledging the shifts


You should identify to what degree this problem exists in the following paper. You should give your evaluation in an integer scale of 1-10 (1 for there being no such issue, 10 for the most serious case). 

Wrap the score in the pair <SCORE> and </SCORE>.

Example: 
<SCORE>9<\SCORE>

Paper content:
{}
"""

def eval_language_misuse(text):
    prompt = prompt_template.format(text)
    return extract_score(chat(prompt))

if __name__ == '__main__':
    with open("data/papers/2601.10679/body.txt", "r") as f:
        text = f.read()
        print(eval_language_misuse(text))