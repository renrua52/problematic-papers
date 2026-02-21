# Usage: in the root directory, run:
# python -m metrics.math_quality

from api.api import chat, extract_score

prompt_template = """
Academic papers may suffer from mathiness, which mainly manifests in the following eight forms: 

1. Complex symbols replacing simple statements
   Definition: Using unnecessarily complicated mathematical notation to express ideas that could be stated plainly.
   - Mild: Using Σᵢxᵢ instead of "sum of all x values" in a non-technical context
   - Severe: Defining a 3-page tensor notation system to express "average price goes up when demand exceeds supply"
2. Disconnection between derivations and conclusions
   Definition: Logical gaps between mathematical derivations and the paper's claimed conclusions.
   - Mild: Minor logical leap that readers can fill in
   - Severe: Pages of differential equations followed by policy recommendations with no connecting argument
3. Forced quantification of non-quantifiable concepts
   Definition: Artificially modeling inherently qualitative or non-measurable concepts to create false precision.
   - Mild: Using Likert scales for subjective preferences
   - Severe: Defining "happiness utility function H(x) = integral e^(-rho t)u(c_t)dt" and treating it as measurable
4. Irrelevant advanced mathematics for decoration
   Definition: Introducing sophisticated mathematical theories unrelated to the research problem solely for academic appearance.
   - Mild: Mentioning a theorem in footnote without using it
   - Severe: Introducing stochastic calculus and measure theory for a problem solvable with basic algebra
5. Hidden unreasonable assumptions
   Definition: Building models on unstated or unrealistic assumptions while masking defects with the apparent "rigor" of formulas.
   - Mild: Standard simplifying assumptions (e.g., "assume normal distribution")
   - Severe: "Let f be infinitely differentiable" when real-world data is discrete and noisy
6. Overly complex models sacrificing interpretability
   Definition: Pursuing fitting accuracy with unnecessarily complicated models at the cost of explanatory clarity.
   - Mild: Using regularized regression when OLS would suffice
   - Severe: 47-parameter neural network to model a near-linear relationship
7. Misuse of cross-disciplinary mathematical terminology
   Definition: Applying mathematical terms from other fields incorrectly or against their original definitions.
   - Mild: Loose use of "entropy" as metaphor for disorder
   - Severe: Claiming "quantum superposition" applies to consumer choice without any quantum mechanics
8. Unreproducible derivations / reliance on unfounded intuition
   Definition: Presenting derivations that cannot be verified or reproduced, or depend on unjustified intuitive leaps.
   - Mild: Skipping tedious but standard algebraic steps
   - Severe: "It can be shown that..." for a non-obvious 10-step derivation with no reference

You should identify to what degree this problem exists in the following paper. You should give your evaluation in an integer scale of 1-10 (1 for there being no such issue(milder), 10 for the most serious case(severer)). 

Wrap the score in the pair <SCORE> and </SCORE>.

Example: 
<SCORE>9<\SCORE>

Paper content:
{}
"""

def eval_math_quality(text):
    prompt = prompt_template.format(text)
    return extract_score(chat(prompt))

if __name__ == '__main__':
    with open("data/papers/2601.10679/body.txt", "r") as f:
        text = f.read()
        print(eval_math_quality(text))