# Disagreement Map: Attack Effectiveness

*Generated: 2026-03-01 15:18*

# Disagreement Map: Effectiveness and Limitations of Jailbreak Attacks

---

## Points of Agreement

### **Claim 1: Current LLMs are broadly vulnerable to jailbreak attacks**
- **Supporting sources:**
  - [how_do_llms_fail, how_do_llms_fail_c12]: "Our results confirm...the diversity of jailbreaks that can work" across GPT-4, Claude v1.3, GPT-3.5 Turbo
  - [pair, pair_c13]: PAIR achieves 50% on GPT-3.5/4, 73% on Gemini, 88% on Vicuna
  - [artprompt, artprompt_c14]: ArtPrompt is effective against all victim LLMs including GPT-3.5, GPT-4, Claude, Gemini
  - [crescendo, crescendo_c27]: Crescendo achieves 98% binary ASR on GPT-4 and 100% on GeminiPro
  - [fitd, fitd_c16]: FITD achieves average 94%/91% ASR across all tested models
- **Strength: STRONG** (5+ sources converge)

---

### **Claim 2: Combination/multi-component attacks outperform simple single-strategy attacks**
- **Supporting sources:**
  - [how_do_llms_fail, how_do_llms_fail_c16]: "combinations of simple attacks...may be the most difficult to defend against"; combination_3 achieves 0.94 BAD BOT rate vs. lower rates for individual attacks
  - [how_do_llms_fail, how_do_llms_fail_c13]: combination attacks consistently rank among the top performers in Table 1
  - [fitd, fitd_c16]: Multi-turn FITD (avg 94%/91%) consistently outperforms all single-turn baselines (max ~75%)
  - [crescendo, crescendo_c27]: Multi-turn Crescendo outperforms single-shot MSJ by 29–61% on average ASR
- **Strength: STRONG** (4 sources converge)

---

### **Claim 3: Adaptive attacks that iteratively refine prompts achieve near-universal success**
- **Supporting sources:**
  - [how_do_llms_fail, how_do_llms_fail_c16]: Adaptive attack achieves 100% BAD BOT rate on both GPT-4 and Claude v1.3
  - [pair, pair_c09]: PAIR's iterative LLM-assisted refinement converges to successful jailbreaks within ~20 queries
  - [crescendo, crescendo_c26]: Crescendomation with iterative refinement achieves best-in-class ASR vs. PAIR, MSJ, CoA, CIA
- **Strength: STRONG** (3 sources)

---

### **Claim 4: Claude and Llama-2 are comparatively more resistant to jailbreaks than GPT and Gemini models**
- **Supporting sources:**
  - [pair, pair_c13]: PAIR achieves only 3% on Claude-1 and 0% on Claude-2, vs. 48–51% on GPT models and 73% on Gemini
  - [how_do_llms_fail, how_do_llms_fail_c16]: Claude v1.3 resists all roleplay attacks (0% success), attributed to targeted safety training
  - [artprompt, artprompt_c14]: Most baselines fail on Claude (ASR = 0%) except GCG (4%) and ArtPrompt (20–52%)
  - [fitd, fitd_c16]: GCG achieves only 2% on Llama-2 (Table in pair_c09 context)
- **Strength: STRONG** (3+ sources)

---

### **Claim 5: Fine-tuning alone (targeted safety training) is insufficient as a complete defense**
- **Supporting sources:**
  - [how_do_llms_fail, how_do_llms_fail_c16]: "targeted training is insufficient" — Claude resists roleplay attacks but remains 100% vulnerable to adaptive attacks
  - [safedecoding, safedecoding_c41]: "Fine-tuning alone is insufficient to defend against jailbreak attacks"; expert model significantly compromises utility while failing against some attacks
- **Strength: MODERATE** (2 sources, but finding is internally consistent)

---

### **Claim 6: Query efficiency varies substantially across attack methods, with gradient-based methods being the least efficient**
- **Supporting sources:**
  - [pair, pair_c13]: PAIR finds jailbreaks in ~10–56 queries; GCG requires ~256,000 queries
  - [artprompt, artprompt_c14]: ArtPrompt achieves highest ASR with only one iteration; other methods require more optimization steps
  - [safedecoding, safedecoding_c06]: Classifies gradient-based methods (GCG) as one distinct, computationally intensive category
- **Strength: STRONG** (3 sources)

---

## Points of Disagreement

| Topic | Position A | Position B | Type | Sources |
|-------|-----------|-----------|------|---------|
| **Relative effectiveness of PAIR vs. other attacks** | PAIR achieves strong results (51% GPT-3.5, 48% GPT-4, 73% Gemini) and is significantly more query-efficient than GCG | ArtPrompt (Ensemble) outperforms PAIR on GPT-3.5 (78% vs. 38% ASR), GPT-4 (32% vs. 30%), Claude (52% vs. 0%), Gemini (76% vs. 50%), and average ASR (52% vs. 28%) | empirical | [pair, pair_c13] vs. [artprompt, artprompt_c14] |
| **GCG effectiveness on GPT-3.5** | GCG requires white-box access and cannot be evaluated on GPT-3.5/4; implying it is inapplicable in closed-source settings | GCG achieves 54% ASR on GPT-3.5 (Table 3 in artprompt_c14), suggesting it was somehow evaluated | methodological | [pair, pair_c13] vs. [artprompt, artprompt_c14] |
| **Whether model scale/capability increases or decreases vulnerability** | Larger models (GPT-4) are more vulnerable to complex attacks (combination*, auto_payload_splitting) that require strong instruction-following; GPT-3.5 lacks capability to execute these | Larger, more capable models (GPT-4 vs. GPT-3.5) show greater resistance to simple roleplay attacks, implying scale can improve robustness to certain attack types | empirical | [how_do_llms_fail, how_do_llms_fail_c16] (both positions implied within same source; scope of effect disputed) |
| **Effectiveness of Crescendo/multi-turn vs. PAIR** | PAIR achieves competitive ASR (76% binary on GPT-4) and is an established strong baseline | Crescendo outperforms PAIR by 40% on average ASR on GPT-4 (56.2% vs. 40.0%) and by 49% on GeminiPro (82.6% vs. 33%) | empirical | [pair, pair_c13] vs. [crescendo, crescendo_c26, crescendo_c27] |
| **ArtPrompt vs. PAIR on Llama-2/open-source models** | PAIR achieves 4% on Llama-2 (low but non-zero), while human JBC templates achieve 0% | AutoDAN and PAIR outperform ArtPrompt specifically on Llama-2; ArtPrompt's advantage does not generalize uniformly | scope | [pair, pair_c09] vs. [artprompt, artprompt_c14] |
| **Defense utility trade-off: SafeDecoding vs. fine-tuning (expert model)** | SafeDecoding achieves near-equivalent jailbreak defense as the expert model (fine-tuning) with minimal utility cost (MT-Bench: 6.63 vs. 3.46) | The expert fine-tuned model achieves comparable or slightly better defense on some attacks (e.g., GCG: 8% vs. 4%) but collapses general utility | empirical | [safedecoding, safedecoding_c41] (internal comparison) |
| **Whether targeted safety training on specific attack categories is a viable partial defense** | Targeted training against roleplay attacks is effective for Claude (0% roleplay ASR), suggesting category-specific training has value | Targeted training is ultimately insufficient because it leaves the model fully vulnerable to out-of-distribution attack strategies (100% adaptive ASR on Claude) | scope | [how_do_llms_fail, how_do_llms_fail_c16] (tension within same source) |
| **Paraphrase defense efficacy against ArtPrompt** | Paraphrase is the most effective defense against ArtPrompt, reducing but not eliminating ASR (average 39% remains) | PPL filtering and retokenization fail entirely against ArtPrompt; retokenization may inadvertently help the attack | empirical | [artprompt, artprompt_c16] (internal differentiation among defenses) |

---

## Unresolved Questions

1. **Long-term transferability of adversarial chat histories**: [fitd, fitd_c16] demonstrates cross-model transfer of FITD adversarial histories, but no other source examines this phenomenon. It is unclear whether this is a general property of multi-turn attacks or specific to FITD's foot-in-the-door escalation mechanism.

2. **Comparative defense effectiveness across SafeDecoding, ArtPrompt-specific mitigations, and fine-tuning at scale**: The evidence for each defense comes from different papers using different benchmarks (AdvBench, JailbreakBench, HEx-PHI), evaluation metrics (ASR, BAD BOT rate, HS), and target models. No source provides a unified comparison of all defense strategies against all attack types on the same models.

3. **Whether ASCII art / non-semantic input vulnerabilities (ArtPrompt) can be fully closed by fine-tuning on non-semantic corpora**: [artprompt, artprompt_c16] shows fine-tuning on VITC-S reduces but does not eliminate vulnerability, but the authors explicitly defer further investigation as future work.

4. **Effectiveness of PAIR and similar LLM-assisted attacks against Claude-2 (0% in PAIR data)**: [pair, pair_c09] reports 0% for PAIR on Claude-2 with no successful queries, but no other source systematically investigates why Claude-2 resists LLM-assisted iterative attacks while Claude-1 does not.

5. **The interaction between model capability and attack complexity at scales beyond GPT-4**: [how_do_llms_fail, how_do_llms_fail_c16] observes that capability affects the attack surface, but no source examines whether this trend continues at frontier scales beyond those tested.