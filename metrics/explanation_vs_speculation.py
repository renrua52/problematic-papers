from api.api import chat, extract_score

prompt_template = """
Academic papers may suffer from conflating explanation with speculation., which mainly manifests in the following three forms: 

1. Vaguely defined key concepts, with analyses based on them presented as technical facts
   Definition: Introducing loosely defined concepts and treating analyses based on them as established technical facts, without specifying measurable criteria or formal definitions.
   - Mild: Using a conceptual term (e.g., "model capacity") without a precise formula, but the intended meaning is inferable from context and does not affect core claims
   - Severe: Introducing "internal covariate shift" as the causal explanation for batch normalization's success without defining the divergence metric for "distribution changes", leading to widespread citation as fact despite later studies disproving the explanation

2. Authors use unvalidated subjective intuitions to explain conclusions
   Definition: Presenting subjective hunches or intuitions as explanatory conclusions without experimental validation or acknowledgment of their speculative nature.
   - Mild: Suggesting a plausible interpretation in the discussion section while implicitly leaving room for alternative explanations
   - Severe: Claiming "high dimensionality and irrelevant features make adversarial attacks easier" as a conclusion without any experiments testing dimensionality's effect, or using undefined terms like "coverage" to explain model behavior without marking it as speculation

3. Unlabeled speculations intermingled with factual claims
   Definition: Failing to distinguish speculative interpretations from verified conclusions, leaving readers unable to assess the reliability of each claim.
   - Mild: Occasionally mixing interpretation with results in the same paragraph, but using hedging language (e.g., "may", "possibly", "one explanation is")
   - Severe: Presenting speculations and evidence-backed conclusions in identical assertive tone throughout the paper, with no dedicated sections, no linguistic markers (e.g., "we hypothesize"), and no explicit acknowledgment of uncertainty levels


You should identify to what degree this problem exists in the following paper. You should give your evaluation in an integer scale of 1-10 (1 for there being no such issue, 10 for the most serious case). 

Wrap the score in the pair <SCORE> and </SCORE>.

Example: 
<SCORE>9<\SCORE>

Paper content:
{}
"""

def eval_explanation_vs_speculation(text):
    prompt = prompt_template.format(text)
    return extract_score(chat(prompt))

if __name__ == '__main__':
    with open("data/papers/2601.10679/body.txt", "r") as f:
        text = f.read()
        print(eval_explanation_vs_speculation(text))