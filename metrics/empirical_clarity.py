from api.api import chat, extract_score

prompt_template = """
Academic papers may suffer from a lack of empirical clarity, which mainly manifests in the following three forms: 

1. Unclear Gain Sources Without Ablation
   Definition: No ablation studies are conducted, and multiple model modifications are piled up to obscure the core source of empirical gains.
   - Mild: Ablation studies are provided but incomplete, testing only some components while leaving 1-2 modifications unexamined, though the main contribution is still identifiable
   - Severe: Introducing 5+ simultaneous modifications (new architecture, novel loss function, data augmentation, training schedule changes) with no ablation study, making it impossible to determine which component drives the reported improvements

2. Architectural Innovation Gains from Tuning
   Definition: Purported "architectural innovation" gains stem from hyperparameter tuning rather than the proposed structural changes.
   - Mild: New architecture shows genuine gains, but baseline uses default hyperparameters while the proposed method uses tuned ones, introducing moderate unfairness
   - Severe: Claimed architectural improvement disappears entirely when baselines receive equivalent hyperparameter tuning effort, or reported gains are later shown to stem from learning rate schedules, batch sizes, or training duration rather than the architectural novelty itself

3. Widespread in Multiple Subfields
   Definition: Empirical clarity issues persist across experiments in multiple subfields or application domains without consistent evaluation standards.
   - Mild: Experiments span 2-3 subfields with minor inconsistencies in evaluation metrics or protocols, but overall comparison remains meaningful
   - Severe: Paper claims generalization across NLP, vision, and reinforcement learning, but uses different baselines, incompatible metrics, and varying computational budgets per domain, making cross-domain conclusions unverifiable and potentially misleading


You should identify to what degree this problem exists in the following paper. You should give your evaluation in an integer scale of 1-10 (1 for there being no such issue, 10 for the most serious case). 

Wrap the score in the pair <SCORE> and </SCORE>.

Example: 
<SCORE>9<\SCORE>

Paper content:
{}
"""

def eval_empirical_clarity(text):
    prompt = prompt_template.format(text)
    return extract_score(chat(prompt))

if __name__ == '__main__':
    with open("data/papers/2601.10679/body.txt", "r") as f:
        text = f.read()
        print(eval_empirical_clarity(text))