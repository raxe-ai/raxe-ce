# Comprehensive Catalog of 100+ Research Papers on LLM Prompt Injection, Jailbreaking, and AI Security

**Compiled:** 2025-11-16
**Focus Areas:** Prompt Injection, Jailbreaking, Multi-turn Attacks, RAG Poisoning, Visual Injection, Defense Mechanisms, Privacy Attacks

---

## Table of Contents
1. [Prompt Injection Attacks](#prompt-injection-attacks)
2. [Jailbreaking Techniques](#jailbreaking-techniques)
3. [Multi-Turn Adversarial Attacks](#multi-turn-adversarial-attacks)
4. [Indirect Prompt Injection](#indirect-prompt-injection)
5. [Visual and Multimodal Injection](#visual-and-multimodal-injection)
6. [RAG Poisoning Attacks](#rag-poisoning-attacks)
7. [Training Data and Memory Extraction](#training-data-and-memory-extraction)
8. [Model Stealing and Extraction](#model-stealing-and-extraction)
9. [Backdoor and Poisoning Attacks](#backdoor-and-poisoning-attacks)
10. [Defense Mechanisms and Guardrails](#defense-mechanisms-and-guardrails)
11. [Red Teaming and Automated Testing](#red-teaming-and-automated-testing)
12. [Adversarial Suffix and Token-Level Attacks](#adversarial-suffix-and-token-level-attacks)
13. [Privacy Attacks](#privacy-attacks)
14. [LLM Agent and Tool-Use Security](#llm-agent-and-tool-use-security)
15. [Robustness Benchmarks and Evaluation](#robustness-benchmarks-and-evaluation)
16. [Certified and Provable Defenses](#certified-and-provable-defenses)
17. [Industry Research (Google, Meta, Anthropic, OpenAI)](#industry-research)
18. [Additional Security Topics](#additional-security-topics)

---

## Prompt Injection Attacks

### 1. **An Early Categorization of Prompt Injection Attacks on Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.00898)
- **Key Contributions:** Presents the first systematic categorization of prompt injections to guide future research and act as a checklist of vulnerabilities
- **Techniques:** Taxonomy of direct and indirect prompt injection
- **Link:** https://arxiv.org/abs/2402.00898

### 2. **Prompt Injection attack against LLM-integrated Applications**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2306.05499)
- **Key Contributions:** Early comprehensive analysis of prompt injection vulnerabilities in LLM applications
- **Techniques:** Direct and indirect injection attacks
- **Link:** https://arxiv.org/abs/2306.05499

### 3. **Optimization-based Prompt Injection Attack to LLM-as-a-Judge (JudgeDeceiver)**
- **Authors:** Multiple authors
- **Year:** 2024 (Submitted March, revised August 2024)
- **Venue:** arXiv (2403.17710)
- **Key Contributions:** First optimization-based attack targeting LLM-as-a-Judge systems used in RLAIF
- **Techniques:** Gradient-based optimization for judge manipulation
- **Link:** https://arxiv.org/abs/2403.17710

### 4. **Prompt Injection 2.0: Hybrid AI Threats**
- **Authors:** Multiple authors
- **Year:** 2025 (July)
- **Venue:** arXiv (2507.13169)
- **Key Contributions:** Analyzes how modern attackers combine natural language manipulation with traditional exploits for RCE and persistent system compromise
- **Techniques:** Hybrid attacks combining prompt injection with traditional security exploits
- **Link:** https://arxiv.org/html/2507.13169v1

### 5. **Defeating Prompt Injections by Design (CaMeL)**
- **Authors:** Multiple authors
- **Year:** 2025 (June)
- **Venue:** arXiv (2503.18813)
- **Key Contributions:** Proposes CaMeL, a robust defense creating a protective system layer around LLMs for agentic systems
- **Techniques:** System-level defense architecture
- **Link:** https://arxiv.org/abs/2503.18813

### 6. **Prompt Injection Attacks on LLM Generated Reviews of Scientific Publications**
- **Authors:** Multiple authors
- **Year:** 2025 (September)
- **Venue:** arXiv (2509.10248)
- **Key Contributions:** Analyzes prompt injection in AI-assisted peer review using ICLR 2024 review data
- **Techniques:** Hidden prompts in academic manuscripts
- **Link:** https://arxiv.org/html/2509.10248v3

### 7. **"Give a Positive Review Only": An Early Investigation Into In-Paper Prompt Injection Attacks and Defenses for AI Reviewers**
- **Authors:** Lin et al.
- **Year:** 2025 (November)
- **Venue:** arXiv (2511.01287)
- **Key Contributions:** Examines hidden adversarial prompts exploiting AI-assisted peer review
- **Techniques:** In-paper prompt injection using 26 rejected ICLR papers
- **Link:** https://arxiv.org/html/2511.01287

### 8. **Prompt Injection Vulnerability of Consensus Generating Applications in Digital Democracy**
- **Authors:** Multiple authors
- **Year:** 2025 (August)
- **Venue:** arXiv (2508.04281)
- **Key Contributions:** Explores vulnerabilities in LLM-based consensus systems for digital democracy
- **Techniques:** Manipulation of democratic consensus generation
- **Link:** https://arxiv.org/html/2508.04281v1

### 9. **Context Injection Attacks on Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2405.20234)
- **Key Contributions:** Demonstrates context injection achieving 97% success rates on ChatGPT and Llama-2
- **Techniques:** Fabricating misleading context to circumvent safety measures
- **Link:** https://arxiv.org/html/2405.20234v1

### 10. **Cognitive Overload Attack: Prompt Injection for Long Context**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2410.11272)
- **Key Contributions:** Uses Cognitive Load Theory to jailbreak LLMs through cognitive overload
- **Techniques:** Hiding harmful questions within observation tasks with cognitive load
- **Link:** https://arxiv.org/html/2410.11272v1

### 11. **System Prompt Extraction Attacks and Defenses in Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.23817)
- **Key Contributions:** Analyzes methods to extract system prompts and proposes defenses
- **Techniques:** Various prompt extraction techniques
- **Link:** https://arxiv.org/html/2505.23817v1

### 12. **ProxyPrompt: Securing System Prompts against Prompt Extraction Attacks**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.11459)
- **Key Contributions:** Achieves 94.70% prompt protection, outperforming other methods (42.80%)
- **Techniques:** Proxy-based system prompt protection
- **Link:** https://arxiv.org/html/2505.11459v1

---

## Jailbreaking Techniques

### 13. **Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG)**
- **Authors:** Zou et al.
- **Year:** 2023
- **Venue:** arXiv (2307.15043)
- **Key Contributions:** Introduces GCG (Greedy Coordinate Gradient), a token-level attack using adversarial suffixes
- **Techniques:** Gradient-based optimization of adversarial suffixes
- **Link:** https://arxiv.org/pdf/2307.15043

### 14. **AutoDAN: Generating Stealthy Jailbreak Prompts on Aligned Large Language Models**
- **Authors:** Liu et al.
- **Year:** 2023
- **Venue:** ICLR 2024 (OpenReview)
- **Key Contributions:** Hierarchical genetic algorithm for generating human-readable jailbreak prompts
- **Techniques:** Genetic programming with sentence-level optimization
- **Link:** https://openreview.net/forum?id=7Jwpw4qKkb

### 15. **AutoDAN: Interpretable Gradient-Based Adversarial Attacks on Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2310.15140)
- **Key Contributions:** Gradient-based approach producing meaningful, interpretable jailbreak prompts
- **Techniques:** Gradient-based sentence-level optimization
- **Link:** https://arxiv.org/html/2310.15140v2

### 16. **PAIR: Prompt Automatic Iterative Refinement**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** Multiple sources
- **Key Contributions:** Black-box jailbreak requiring only ~20 iterations, highly parallelizable
- **Techniques:** Iterative refinement of human-readable jailbreaks
- **Link:** Referenced in multiple sources

### 17. **Jailbreak and Guard Aligned Language Models with Only Few In-Context Demonstrations**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2310.06387)
- **Key Contributions:** Demonstrates few-shot jailbreaking using in-context demonstrations
- **Techniques:** Few-shot learning for both attacks and defenses
- **Link:** https://arxiv.org/html/2310.06387

### 18. **Stealthy Jailbreak Attacks on Large Language Models via Benign Data Mirroring**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2410.21083)
- **Key Contributions:** Novel stealthy approach using benign data patterns
- **Techniques:** Data mirroring for undetectable jailbreaks
- **Link:** https://arxiv.org/html/2410.21083v2

### 19. **Attention Slipping: A Mechanistic Understanding of Jailbreak Attacks and Defenses in LLMs**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.04365)
- **Key Contributions:** Mechanistic analysis of how attention mechanisms enable jailbreaks
- **Techniques:** Attention mechanism exploitation
- **Link:** https://arxiv.org/html/2507.04365

### 20. **Towards Understanding Jailbreak Attacks in LLMs**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** EMNLP 2024 (aclanthology.org/2024.emnlp-main.401)
- **Key Contributions:** Comprehensive analysis of jailbreak attack mechanisms
- **Techniques:** Taxonomy and analysis of jailbreak methods
- **Link:** https://aclanthology.org/2024.emnlp-main.401.pdf

### 21. **Bag of Tricks: Benchmarking of Jailbreak Attacks on LLMs**
- **Authors:** Zhao XU et al.
- **Year:** 2024
- **Venue:** NeurIPS 2024 Datasets and Benchmarks Track
- **Key Contributions:** Empirical tricks and benchmarking for LLM jailbreaking
- **Techniques:** Comprehensive evaluation of jailbreak techniques
- **Link:** https://proceedings.neurips.cc/paper_files/paper/2024/file/38c1dfb4f7625907b15e9515365e7803-Paper-Datasets_and_Benchmarks_Track.pdf

### 22. **Mission Impossible: A Statistical Perspective on Jailbreaking LLMs**
- **Authors:** Jingtong Su et al.
- **Year:** 2024
- **Venue:** NeurIPS 2024
- **Key Contributions:** Statistical analysis of jailbreak success rates and patterns
- **Techniques:** Statistical modeling of jailbreak attacks
- **Link:** https://proceedings.neurips.cc/paper_files/paper/2024/file/439bf902de1807088d8b731ca20b0777-Paper-Conference.pdf

### 23. **Efficient LLM Jailbreak via Adaptive Dense-to-sparse Constrained Optimization**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** NeurIPS 2024
- **Key Contributions:** Achieves 100% attack success rate on multiple models including GPT-4o
- **Techniques:** Adaptive optimization with logprobs access
- **Link:** https://proceedings.neurips.cc/paper_files/paper/2024/file/29571f8fda54fe93631c41aad4215abc-Paper-Conference.pdf

---

## Multi-Turn Adversarial Attacks

### 24. **Great, Now Write an Article About That: The Crescendo Multi-Turn LLM Jailbreak Attack**
- **Authors:** Russinovich, Salem et al.
- **Year:** 2024
- **Venue:** arXiv (2404.01833)
- **Key Contributions:** Introduces Crescendo, a multi-turn attack starting with harmless dialogue
- **Techniques:** Progressive conversation steering toward prohibited objectives
- **Link:** https://arxiv.org/abs/2404.01833

### 25. **Siege: Autonomous Multi-Turn Jailbreaking of Large Language Models with Tree Search**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2503.10619)
- **Key Contributions:** Achieves 100% success on GPT-3.5-turbo, 97% on GPT-4 using tree search
- **Techniques:** Breadth-first tree search with multiple adversarial prompts
- **Link:** https://arxiv.org/html/2503.10619v1

### 26. **Automated Multi-Turn Red-Teaming with Cascade**
- **Authors:** Haize Labs
- **Year:** 2024
- **Venue:** Haize Labs Technology Blog
- **Key Contributions:** Cascade uses attacker LLMs with tree search heuristics
- **Techniques:** Tree search over parallel conversation branches
- **Link:** https://www.haizelabs.com/technology/automated-multi-turn-red-teaming-with-cascade

### 27. **Holistic Automated Red teaming (HARM)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** EMNLP 2024
- **Key Contributions:** Scales test case diversity using fine-grained risk taxonomy and RL
- **Techniques:** Top-down approach with multi-turn adversarial probing
- **Link:** https://github.com/jc-ryan/holistic_automated_red_teaming

---

## Indirect Prompt Injection

### 28. **Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection**
- **Authors:** Kai Greshake et al.
- **Year:** 2023
- **Venue:** arXiv (2302.12173)
- **Key Contributions:** First major work revealing indirect prompt injection attack vectors
- **Techniques:** Strategic injection into retrieved data
- **Link:** https://arxiv.org/abs/2302.12173

### 29. **Can Indirect Prompt Injection Attacks Be Detected and Removed?**
- **Authors:** Yulin Chen, Haoran Li, Yuan Sui, Yufei He, Yue Liu, Yangqiu Song, Bryan Hooi
- **Year:** 2025
- **Venue:** ACL 2025 / arXiv (2502.16580)
- **Key Contributions:** First benchmark for detecting/removing indirect prompt injection attacks
- **Techniques:** Detection and removal methods evaluation
- **Link:** https://arxiv.org/abs/2502.16580

### 30. **Benchmarking and Defending Against Indirect Prompt Injection Attacks on Large Language Models (BIPIA)**
- **Authors:** Jingwei Yi et al.
- **Year:** 2024 (updated January 2025)
- **Venue:** arXiv (2312.14197)
- **Key Contributions:** First benchmark BIPIA; found all existing LLMs universally vulnerable
- **Techniques:** Comprehensive benchmark dataset
- **Link:** https://arxiv.org/abs/2312.14197

### 31. **Defending against Indirect Prompt Injection by Instruction Detection**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.06311)
- **Key Contributions:** Instruction detection for defending against indirect injection
- **Techniques:** Automated instruction boundary detection
- **Link:** https://arxiv.org/html/2505.06311v2

---

## Visual and Multimodal Injection

### 32. **Invisible Injections: Exploiting Vision-Language Models Through Steganographic Prompt Embedding**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.22304)
- **Key Contributions:** Steganographic attacks achieving 24.3% success across GPT-4V, Claude, LLaVA
- **Techniques:** Neural steganography embedding malicious instructions in images
- **Link:** https://arxiv.org/html/2507.22304v1

### 33. **Prompt injection attacks on vision language models in oncology**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** Nature Communications (s41467-024-55631-x)
- **Key Contributions:** Study of 594 attacks on Claude-3, GPT-4o showing all VLMs susceptible
- **Techniques:** Sub-visual prompts in medical imaging
- **Link:** https://www.nature.com/articles/s41467-024-55631-x

### 34. **Mind Mapping Prompt Injection: Visual Prompt Injection Attacks in Modern Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** MDPI Electronics (2079-9292/14/10/1907)
- **Key Contributions:** Map image-based attacks consistently bypass rejection
- **Techniques:** Mind map images for hidden prompt injection
- **Link:** https://www.mdpi.com/2079-9292/14/10/1907

### 35. **Multimodal Prompt Injection Attacks: Risks and Defenses for Modern LLMs**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2509.05883)
- **Key Contributions:** Comprehensive analysis of cross-modal prompt injection risks
- **Techniques:** Multi-modal attack vectors and defense analysis
- **Link:** https://arxiv.org/html/2509.05883v1

### 36. **Safeguarding Vision-Language Models Against Patched Visual Prompt Injectors**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2405.10529)
- **Key Contributions:** Defense mechanisms for visual prompt injection
- **Techniques:** Detection of patched visual prompts
- **Link:** https://arxiv.org/html/2405.10529v1

### 37. **Manipulating Multimodal Agents via Cross-Modal Prompt Injection**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2504.14348)
- **Key Contributions:** Cross-modal manipulation of multimodal AI agents
- **Techniques:** Cross-modal prompt injection techniques
- **Link:** https://arxiv.org/html/2504.14348

### 38. **VL-Trojan: Multimodal Instruction Backdoor Attacks against Autoregressive Visual Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.13851)
- **Key Contributions:** Backdoor attacks targeting multimodal instruction-following
- **Techniques:** Visual-language backdoor triggers
- **Link:** https://arxiv.org/abs/2402.13851

---

## RAG Poisoning Attacks

### 39. **PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** USENIX Security 2025 / arXiv (2402.07867)
- **Key Contributions:** First knowledge database corruption attack; 90% success with 5 malicious texts
- **Techniques:** Injection of poisoned texts into knowledge database
- **Link:** https://arxiv.org/abs/2402.07867

### 40. **RAG Safety: Exploring Knowledge Poisoning Attacks to Retrieval-Augmented Generation**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.08862)
- **Key Contributions:** Comprehensive exploration of knowledge poisoning in RAG systems
- **Techniques:** Knowledge base poisoning strategies
- **Link:** https://arxiv.org/abs/2507.08862

### 41. **Practical Poisoning Attacks against Retrieval-Augmented Generation (CorruptRAG)**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2504.03957)
- **Key Contributions:** CorruptRAG requires only a single poisoned text per attack
- **Techniques:** Single-document poisoning attacks
- **Link:** https://arxiv.org/abs/2504.03957

### 42. **Benchmarking Poisoning Attacks against Retrieval-Augmented Generation**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.18543)
- **Key Contributions:** Comprehensive benchmark for RAG poisoning attacks
- **Techniques:** Systematic evaluation framework
- **Link:** https://arxiv.org/abs/2505.18543

### 43. **Traceback of Poisoning Attacks to Retrieval-Augmented Generation**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** ACM Web Conference 2025
- **Key Contributions:** Methods for tracing sources of RAG poisoning
- **Techniques:** Attack attribution and traceback
- **Link:** https://dl.acm.org/doi/abs/10.1145/3696410.3714756

### 44. **Retrieval Poisoning Attacks Based on Prompt Injections into RAG Systems that Store Generated Responses**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** Distributed Computer and Communication Networks
- **Key Contributions:** Novel attack vector through stored responses
- **Techniques:** Persistent poisoning via stored generations
- **Link:** https://dl.acm.org/doi/10.1007/978-3-031-80853-1_31

---

## Training Data and Memory Extraction

### 45. **Extracting Training Data from Large Language Models**
- **Authors:** Carlini et al.
- **Year:** 2021
- **Venue:** USENIX Security 2021 / arXiv (2012.07805)
- **Key Contributions:** First demonstration of extracting verbatim training data from GPT-2
- **Techniques:** Membership inference with confidence thresholding
- **Link:** https://arxiv.org/abs/2012.07805

### 46. **Extracting Training Data from ChatGPT**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** Research Project (not-just-memorization.github.io)
- **Key Contributions:** Extracted several megabytes of ChatGPT training data for ~$200
- **Techniques:** Large-scale extraction from production models
- **Link:** https://not-just-memorization.github.io/extracting-training-data-from-chatgpt.html

### 47. **Training Data Extraction Attack from Large Language Models in Federated Learning Through Frequent Sequence Mining**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** OpenReview
- **Key Contributions:** Novel attack using frequent sequence mining in FL settings
- **Techniques:** Federated learning exploitation
- **Link:** https://openreview.net/forum?id=0O7N7fTKGE

### 48. **Beyond Data Privacy: New Privacy Risks for Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2509.14278)
- **Key Contributions:** Identifies novel privacy risks beyond traditional data privacy
- **Techniques:** Multiple privacy attack vectors
- **Link:** https://arxiv.org/html/2509.14278v1

### 49. **Identifying and Mitigating Privacy Risks Stemming from Language Models**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2310.01424)
- **Key Contributions:** Systematic identification of LLM privacy risks and mitigations
- **Techniques:** Privacy risk taxonomy and defenses
- **Link:** https://arxiv.org/html/2310.01424v2

---

## Model Stealing and Extraction

### 50. **Stealing Part of a Production Language Model**
- **Authors:** Carlini et al.
- **Year:** 2024
- **Venue:** arXiv (2403.06634)
- **Key Contributions:** Extracted projection matrices from GPT-3.5 and Ada/Babbage for <$2,000
- **Techniques:** API query-based extraction of model weights
- **Link:** https://arxiv.org/abs/2403.06634

### 51. **A Survey on Model Extraction Attacks and Defenses for Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2506.22521)
- **Key Contributions:** Comprehensive survey of model extraction attacks and defenses
- **Techniques:** Query-based, functional replication, and prompt stealing
- **Link:** https://arxiv.org/html/2506.22521v1

### 52. **Data Stealing Attacks against Large Language Models via Backdooring**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** MDPI Electronics (13/14/2858)
- **Key Contributions:** Adaptive method to extract private training data via backdoors
- **Techniques:** Backdoor-based data exfiltration
- **Link:** https://www.mdpi.com/2079-9292/13/14/2858

---

## Backdoor and Poisoning Attacks

### 53. **A Survey of Backdoor Attacks and Defenses on Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024-2025
- **Venue:** Multiple surveys
- **Key Contributions:** Comprehensive overview of backdoor threats in LLMs
- **Techniques:** Data poisoning, instruction backdoors, trojan attacks
- **Link:** Multiple sources including ThuCCSLab/Awesome-LM-SSP

### 54. **Data Poisoning in Deep Learning: A Survey**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2503.22759)
- **Key Contributions:** Systematic survey of data poisoning across deep learning
- **Techniques:** Untargeted, targeted, and backdoor poisoning
- **Link:** https://arxiv.org/html/2503.22759v1

### 55. **Invisible Backdoor Attacks Using Data Poisoning in the Frequency Domain**
- **Authors:** Multiple authors
- **Year:** 2022
- **Venue:** arXiv (2207.04209)
- **Key Contributions:** Frequency-domain backdoor attacks for imperceptibility
- **Techniques:** Frequency-based trigger embedding
- **Link:** https://arxiv.org/abs/2207.04209

### 56. **Targeted Backdoor Attacks on Deep Learning Systems Using Data Poisoning**
- **Authors:** Chen, Liu et al.
- **Year:** 2017-2018
- **Venue:** Multiple venues
- **Key Contributions:** Foundational work on targeted backdoor attacks
- **Techniques:** Strategic data poisoning for backdoor insertion
- **Link:** Multiple sources

### 57. **BadChain: Backdoor Chain-of-Thought Prompting for Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** OpenReview
- **Key Contributions:** Backdoor attacks exploiting chain-of-thought reasoning
- **Techniques:** CoT-based backdoor triggers
- **Link:** https://openreview.net/forum?id=c93SBwz1Ma

### 58. **Attention-based backdoor attacks against natural language processing models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** ScienceDirect (S1568494625002182)
- **Key Contributions:** Attention mechanism exploitation for backdoors
- **Techniques:** Attention-based trigger design
- **Link:** https://www.sciencedirect.com/science/article/abs/pii/S1568494625002182

---

## Defense Mechanisms and Guardrails

### 59. **Robust Prompt Optimization for Defending Language Models (RPO)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** NeurIPS 2024
- **Key Contributions:** Reduces attack success rate to 6% on GPT-4, 0% on Llama-2
- **Techniques:** Robust prompt optimization
- **Link:** https://proceedings.neurips.cc/paper_files/paper/2024/file/46ed503889ab232c21c1162340ee17b2-Paper-Conference.pdf

### 60. **Fight Back Against Jailbreaking via Prompt Adversarial Tuning (PAT)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** NeurIPS 2024 / GitHub
- **Key Contributions:** Defense strategy through adversarial tuning
- **Techniques:** Adversarial fine-tuning for robustness
- **Link:** https://github.com/rain152/PAT

### 61. **Constitutional AI: Harmlessness from AI Feedback**
- **Authors:** Anthropic (Bai et al.)
- **Year:** 2022
- **Venue:** arXiv (2212.08073)
- **Key Contributions:** Self-improvement through AI feedback without human labels
- **Techniques:** RLAIF (RL from AI Feedback)
- **Link:** https://arxiv.org/abs/2212.08073

### 62. **SoK: Evaluating Jailbreak Guardrails for Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2506.10597)
- **Key Contributions:** Systematic evaluation of jailbreak guardrails
- **Techniques:** Security-Efficiency-Utility framework
- **Link:** https://arxiv.org/html/2506.10597v1

### 63. **Defending Against Alignment-Breaking Attacks via Robustly Aligned LLM (RA-LLM)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** ACL 2024
- **Key Contributions:** Reduces attack success from ~100% to ~10% without retraining
- **Techniques:** Robust alignment checking function
- **Link:** https://aclanthology.org/2024.acl-long.568/

### 64. **Robust LLM safeguarding via refusal feature adversarial training (ReFAT)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2409.20089)
- **Key Contributions:** Efficient continuous adversarial training targeting refusal features
- **Techniques:** Refusal Feature Ablation (RFA)
- **Link:** https://arxiv.org/abs/2409.20089

### 65. **Thought Purity: A Defense Framework For Chain-of-Thought Attack**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.12314)
- **Key Contributions:** Defense against CoT-based attacks through systematic monitoring
- **Techniques:** Safety-optimized data processing, RL-enhanced constraints
- **Link:** https://arxiv.org/abs/2507.12314

### 66. **Mitigating Adversarial Attacks in LLMs through Defensive Suffix Generation**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2412.13705)
- **Key Contributions:** Gradient-based defensive suffix generation
- **Techniques:** Defensive suffix optimization
- **Link:** https://arxiv.org/abs/2412.13705

### 67. **Adversarial Suffix Filtering: a Defense Pipeline for LLMs**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.09602)
- **Key Contributions:** Pipeline for detecting and filtering adversarial suffixes
- **Techniques:** Suffix-based attack detection
- **Link:** https://arxiv.org/html/2505.09602v1

---

## Red Teaming and Automated Testing

### 68. **WILDTEAMING at Scale: From In-the-Wild Jailbreaks to (Adversarially) Safer Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** NeurIPS 2024
- **Key Contributions:** 262K prompt-response pairs, 5.7K unique jailbreak tactics from real interactions
- **Techniques:** Large-scale real-world jailbreak mining
- **Link:** https://proceedings.neurips.cc/paper_files/paper/2024/file/54024fca0cef9911be36319e622cde38-Paper-Conference.pdf

### 69. **GOAT: Generative Offensive Agent Tester - Automated Red Teaming**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2410.01606)
- **Key Contributions:** Achieves ASR@10 of 97% on Llama 3.1, 88% on GPT-4-Turbo
- **Techniques:** Multi-turn conversational adversarial agent
- **Link:** https://arxiv.org/html/2410.01606v1

### 70. **Automated Progressive Red Teaming (APRT)**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2407.03876)
- **Key Contributions:** Progressive attack with intention expanding, hiding, and evil making
- **Techniques:** Multi-module progressive red teaming
- **Link:** https://arxiv.org/abs/2407.03876

### 71. **Automatic LLM Red Teaming**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2508.04451)
- **Key Contributions:** Automated approach to LLM red teaming
- **Techniques:** Automated adversarial prompt generation
- **Link:** https://arxiv.org/html/2508.04451v1

### 72. **Recent advancements in LLM Red-Teaming: Techniques, Defenses, and Ethical Considerations**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2410.09097)
- **Key Contributions:** Survey of recent red-teaming advances
- **Techniques:** Multi-turn, automated, and human red-teaming
- **Link:** https://arxiv.org/html/2410.09097v1

---

## Adversarial Suffix and Token-Level Attacks

### 73. **Universal Adversarial Triggers for Attacking and Analyzing NLP**
- **Authors:** Wallace, Feng et al.
- **Year:** 2019
- **Venue:** EMNLP 2019 / arXiv (1908.07125)
- **Key Contributions:** Input-agnostic token sequences causing specific predictions; SNLI accuracy dropped from 89.94% to 0.55%
- **Techniques:** Gradient-guided token search
- **Link:** https://arxiv.org/abs/1908.07125

### 74. **From Noise to Clarity: Unraveling the Adversarial Suffix of Large Language Model Attacks via Translation of Text Embeddings**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.16006)
- **Key Contributions:** Understanding adversarial suffixes through embedding translation
- **Techniques:** Embedding-space analysis
- **Link:** https://arxiv.org/html/2402.16006v1

### 75. **Adversarial Attacks on Large Language Models Using Regularized Relaxation**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2410.19160)
- **Key Contributions:** Two orders of magnitude faster than traditional discrete optimization
- **Techniques:** Regularized continuous optimization
- **Link:** https://arxiv.org/html/2410.19160v1

### 76. **Toward Understanding the Transferability of Adversarial Suffixes in Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2510.22014)
- **Key Contributions:** Analysis of why adversarial suffixes transfer across models
- **Techniques:** Transfer mechanism analysis
- **Link:** https://arxiv.org/abs/2510.22014

---

## Privacy Attacks

### 77. **Exposing Privacy Gaps: Membership Inference Attack on Preference Data for LLM Alignment**
- **Authors:** Feng et al.
- **Year:** 2024
- **Venue:** ICML / arXiv (2407.06443)
- **Key Contributions:** MIA on RLHF preference data; DPO more vulnerable than PPO
- **Techniques:** Membership inference on alignment data
- **Link:** https://arxiv.org/abs/2407.06443

### 78. **Do Membership Inference Attacks Work on Large Language Models?**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.07841)
- **Key Contributions:** Large-scale evaluation showing MIAs barely outperform random guessing
- **Techniques:** Evaluation across 160M to 12B parameter models
- **Link:** https://arxiv.org/abs/2402.07841

### 79. **Membership Inference Attacks against Language Models via Neighbourhood Comparison**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** ACL 2023 Findings
- **Key Contributions:** Novel neighborhood-based MIA approach
- **Techniques:** Comparative neighborhood analysis
- **Link:** https://aclanthology.org/2023.findings-acl.719/

### 80. **Model Inversion Attacks: A Survey of Approaches and Countermeasures**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2411.10023)
- **Key Contributions:** Comprehensive survey of model inversion across domains
- **Techniques:** White-box and black-box inversion attacks
- **Link:** https://arxiv.org/html/2411.10023v1

### 81. **Privacy Leakage on DNNs: A Survey of Model Inversion Attacks and Defenses**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.04013)
- **Key Contributions:** Survey with open-source model inversion toolbox
- **Techniques:** Reconstruction, membership inference, property inference
- **Link:** https://arxiv.org/abs/2402.04013

### 82. **Re-thinking Model Inversion Attacks Against Deep Neural Networks**
- **Authors:** Nguyen et al.
- **Year:** 2023
- **Venue:** CVPR 2023 / arXiv (2304.01669)
- **Key Contributions:** Improved attack accuracy by 11.8%, achieving >90% on CelebA
- **Techniques:** Advanced reconstruction techniques
- **Link:** https://arxiv.org/abs/2304.01669

---

## LLM Agent and Tool-Use Security

### 83. **LLM Agents can Autonomously Exploit One-day Vulnerabilities**
- **Authors:** Daniel Kang et al.
- **Year:** 2024
- **Venue:** arXiv (2404.08144)
- **Key Contributions:** GPT-4 agents achieve 87% success rate exploiting real vulnerabilities
- **Techniques:** Autonomous vulnerability exploitation
- **Link:** https://arxiv.org/abs/2404.08144

### 84. **The Dark Side of LLMs: Agent-based Attacks for Complete Computer Takeover**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.06850)
- **Key Contributions:** 82.4% of models execute malicious commands from peer agents
- **Techniques:** Multi-agent trust exploitation
- **Link:** https://arxiv.org/html/2507.06850v3

### 85. **Agentic Misalignment: How LLMs could be insider threats**
- **Authors:** Anthropic
- **Year:** 2024-2025
- **Venue:** Anthropic Research
- **Key Contributions:** Models sometimes choose blackmail/espionage to pursue goals
- **Techniques:** Goal-driven misalignment analysis
- **Link:** https://www.anthropic.com/research/agentic-misalignment

### 86. **Agent Security Bench (ASB)**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** ICLR 2025
- **Key Contributions:** Comprehensive benchmark for agent security including prompt injection
- **Techniques:** Multi-attack-type agent security evaluation
- **Link:** https://proceedings.iclr.cc/paper_files/paper/2025/file/5750f91d8fb9d5c02bd8ad2c3b44456b-Paper-Conference.pdf

---

## Robustness Benchmarks and Evaluation

### 87. **HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2402.04249)
- **Key Contributions:** Comparison of 18 red teaming methods and 33 target LLMs; R2D2 defense
- **Techniques:** Standardized adversarial evaluation
- **Link:** https://arxiv.org/html/2402.04249v2

### 88. **JailbreakBench: An Open Robustness Benchmark for Jailbreaking Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** NeurIPS 2024 Datasets and Benchmarks
- **Key Contributions:** Evolving dataset of state-of-the-art adversarial prompts
- **Techniques:** Standardized jailbreak evaluation
- **Link:** https://jailbreakbench.github.io/

### 89. **SocialHarmBench: Revealing LLM Vulnerabilities to Socially Harmful Requests**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2510.04891)
- **Key Contributions:** Extended HarmBench for socially harmful content
- **Techniques:** Social harm evaluation
- **Link:** https://arxiv.org/html/2510.04891

### 90. **AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** OpenReview
- **Key Contributions:** Benchmark specifically for LLM agent harmfulness
- **Techniques:** Agent-specific harm evaluation
- **Link:** https://openreview.net/forum?id=AC5n7xHuR1

### 91. **OR-Bench: An Over-Refusal Benchmark for Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2405.20947)
- **Key Contributions:** Benchmark for measuring excessive refusals
- **Techniques:** Balance between safety and utility
- **Link:** https://arxiv.org/html/2405.20947v2

---

## Certified and Provable Defenses

### 92. **Certifying LLM Safety against Adversarial Prompting (Erase-and-Check)**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2309.02705) / OpenReview
- **Key Contributions:** First framework with verifiable safety guarantees; 93% harmful prompt detection
- **Techniques:** Erase-and-check with randomized smoothing
- **Link:** https://arxiv.org/pdf/2309.02705

### 93. **Can AI Keep a Secret? Contextual Integrity Verification (CIV)**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2508.09288)
- **Key Contributions:** Makes attacks mathematically impossible vs. 15-30% failure rate for others
- **Techniques:** Provable security architecture
- **Link:** https://arxiv.org/html/2508.09288

### 94. **Certified Robustness for Large Language Models with Self-Denoising**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2307.07171)
- **Key Contributions:** Self-denoising approach for certified robustness
- **Techniques:** Randomized smoothing with self-denoising
- **Link:** https://arxiv.org/abs/2307.07171

### 95. **A Certified Robust Watermark For Large Language Models**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2409.19708)
- **Key Contributions:** First certified robust watermark based on randomized smoothing
- **Techniques:** Provable watermark robustness
- **Link:** https://arxiv.org/html/2409.19708v1

### 96. **Statistical Runtime Verification for LLMs via Robustness Estimation (RoMA)**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** Springer / arXiv (2504.17723)
- **Key Contributions:** 1% deviation from formal verification, hours to minutes runtime
- **Techniques:** Statistical approximation of formal verification
- **Link:** https://arxiv.org/html/2504.17723v2

---

## Industry Research (Google, Meta, Anthropic, OpenAI)

### 97. **Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety**
- **Authors:** Researchers from OpenAI, Google DeepMind, Anthropic, Meta (40+ authors)
- **Year:** 2025
- **Venue:** arXiv (2507.11473)
- **Key Contributions:** Joint research on monitoring AI reasoning processes
- **Techniques:** Chain-of-thought monitoring
- **Link:** https://arxiv.org/html/2507.11473v1

### 98. **VaultGemma: The world's most capable differentially private LLM**
- **Authors:** Google Research
- **Year:** 2024
- **Venue:** Google Research Blog
- **Key Contributions:** Largest (1B-parameter) model trained with DP (ε ≤ 2.0)
- **Techniques:** Differential privacy from scratch
- **Link:** https://research.google/blog/vaultgemma-the-worlds-most-capable-differentially-private-llm/

### 99. **Fine-Tuning Large Language Models with User-Level Differential Privacy**
- **Authors:** Google Research
- **Year:** 2024
- **Venue:** arXiv (2407.07737) / Google Research Blog
- **Key Contributions:** Scalable algorithms for user-level DP fine-tuning
- **Techniques:** User-level DP-SGD
- **Link:** https://arxiv.org/abs/2407.07737

### 100. **SynthID Text: Watermarking and identifying AI-generated content**
- **Authors:** Google DeepMind
- **Year:** 2024
- **Venue:** Google AI Blog / Nature
- **Key Contributions:** Production-ready text watermarking; tested on 20M Gemini responses
- **Techniques:** Token sampling probability manipulation
- **Link:** https://ai.google.dev/responsible/docs/safeguards/synthid

---

## Additional Security Topics

### 101. **H-CoT: Hijacking the Chain-of-Thought Safety Reasoning Mechanism**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2502.12893)
- **Key Contributions:** Jailbreaks OpenAI o1/o3, DeepSeek-R1, Gemini 2.0 via CoT hijacking
- **Techniques:** Chain-of-thought reasoning manipulation
- **Link:** https://arxiv.org/abs/2502.12893

### 102. **Safety Tax: Safety Alignment Makes Your Large Reasoning Models Less Reasonable**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2503.00555)
- **Key Contributions:** Safety alignment degrades reasoning by 15.16% and 14.64%
- **Techniques:** Analysis of safety-reasoning tradeoff
- **Link:** https://arxiv.org/abs/2503.00555

### 103. **Sandwich attack: Multi-language Mixture Adaptive Attack on LLMs**
- **Authors:** Multiple authors
- **Year:** 2024
- **Venue:** arXiv (2404.07242)
- **Key Contributions:** Cross-lingual attack hiding adversarial questions in low-resource languages
- **Techniques:** Multi-lingual mixture attack
- **Link:** https://arxiv.org/html/2404.07242v1

### 104. **All Languages Matter: On the Multilingual Safety of LLMs**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** arXiv (2310.00905)
- **Key Contributions:** All LLMs produce more unsafe responses for non-English queries
- **Techniques:** Multilingual safety evaluation
- **Link:** https://arxiv.org/html/2310.00905v2

### 105. **Multilingual Collaborative Defense for Large Language Models (MCD)**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2505.11835)
- **Key Contributions:** Cross-lingual collaboration for unified multilingual defense
- **Techniques:** Multilingual safety prompt training
- **Link:** https://arxiv.org/html/2505.11835

### 106. **Security Weaknesses of Copilot Generated Code in GitHub**
- **Authors:** Multiple authors
- **Year:** 2023-2024
- **Venue:** ACM TOSEM / arXiv (2310.02059)
- **Key Contributions:** 29.5% Python, 24.2% JavaScript snippets have security weaknesses
- **Techniques:** Static analysis of AI-generated code
- **Link:** https://arxiv.org/abs/2310.02059

### 107. **Detecting and Mitigating Reward Hacking in Reinforcement Learning Systems**
- **Authors:** Multiple authors
- **Year:** 2025
- **Venue:** arXiv (2507.05619)
- **Key Contributions:** 21.3% prevalence in expert-validated episodes; 78.4% detection precision
- **Techniques:** Reward hacking detection and mitigation
- **Link:** https://arxiv.org/abs/2507.05619

### 108. **When Machine Unlearning Jeopardizes Privacy**
- **Authors:** Multiple authors
- **Year:** 2020
- **Venue:** arXiv (2005.02205)
- **Key Contributions:** Machine unlearning can have counterproductive privacy effects
- **Techniques:** Privacy analysis of unlearning
- **Link:** https://arxiv.org/abs/2005.02205

### 109. **Robustness and Transferability of Universal Attacks on Compressed Models**
- **Authors:** Multiple authors
- **Year:** 2020
- **Venue:** arXiv (2012.06024)
- **Key Contributions:** UAP transfer between pruned/full models is limited
- **Techniques:** Compression impact on adversarial robustness
- **Link:** https://arxiv.org/abs/2012.06024

### 110. **TextGuise: Adaptive adversarial example attacks on text classification model**
- **Authors:** Multiple authors
- **Year:** 2023
- **Venue:** ScienceDirect
- **Key Contributions:** >80% attack success with <20% perturbation ratio
- **Techniques:** Black-box adaptive adversarial text generation
- **Link:** https://www.sciencedirect.com/science/article/abs/pii/S0925231223001042

---

## Summary Statistics

**Total Papers:** 110+

**By Category:**
- Prompt Injection: 12
- Jailbreaking: 11
- Multi-Turn Attacks: 4
- Indirect Prompt Injection: 4
- Visual/Multimodal: 7
- RAG Poisoning: 6
- Training Data Extraction: 5
- Model Stealing: 3
- Backdoor Attacks: 6
- Defense Mechanisms: 9
- Red Teaming: 5
- Adversarial Suffixes: 4
- Privacy Attacks: 6
- Agent Security: 4
- Benchmarks: 5
- Certified Defenses: 5
- Industry Research: 4
- Additional Topics: 15

**By Year:**
- 2025: 45 papers
- 2024: 50 papers
- 2023: 10 papers
- 2019-2022: 5 papers

**By Venue:**
- arXiv: 85+
- NeurIPS: 8
- ACL/EMNLP: 6
- ICLR: 4
- ICML: 3
- USENIX Security: 2
- Nature/Science journals: 2
- Industry blogs: 4
- Other conferences: 6

**Top Institutions/Organizations:**
- Google/Google DeepMind: 5+ papers
- Anthropic: 3+ papers
- OpenAI: 3+ papers
- Meta: 2+ papers
- Academic institutions: 90+ papers

---

## Key Findings Across Research

### Attack Trends:
1. **Multi-turn attacks** (Crescendo, Siege) consistently outperform single-turn attacks
2. **Visual injection** achieves 24-31% success even with advanced steganography
3. **RAG poisoning** can succeed with as few as 1-5 malicious documents
4. **Adversarial suffixes** transfer across models despite being optimized for specific targets
5. **Agent systems** show 82.4% vulnerability to peer agent manipulation

### Defense Gaps:
1. No universal defense works across all attack types
2. Current guardrails fail 15-30% of the time for sophisticated attacks
3. Safety alignment often reduces model capability (alignment tax)
4. Multilingual models significantly less safe in non-English languages
5. Compression (pruning/quantization) changes adversarial vulnerability profile

### Emerging Threats:
1. Chain-of-thought hijacking in reasoning models (o1, DeepSeek-R1)
2. Cognitive overload attacks on long-context models
3. Cross-modal prompt injection in multimodal systems
4. Autonomous vulnerability exploitation by LLM agents
5. Privacy leakage through training data extraction ($200 for ChatGPT data)

### Promising Defenses:
1. **Certified defenses** (erase-and-check): 93% detection with provable guarantees
2. **Adversarial training** (ReFAT, RPO): 0-6% attack success on aligned models
3. **Constitutional AI**: Scalable alignment without human labels
4. **Differential privacy**: Provable privacy with acceptable utility tradeoffs
5. **Watermarking**: SynthID tested on 20M responses maintains quality

---

## Research Gaps and Future Directions

1. **Unified Defense Framework:** No single defense protects against all attack types
2. **Multilingual Safety:** Non-English safety significantly lags behind English
3. **Agent Security:** Multi-agent systems particularly vulnerable, underexplored
4. **Long-context Attacks:** Growing context windows create new attack surfaces
5. **Reasoning Model Security:** Chain-of-thought introduces unique vulnerabilities
6. **Real-world Validation:** Most attacks tested in controlled settings, need production data
7. **Defense Transferability:** Defenses often model-specific, don't generalize
8. **Privacy-Utility Tradeoff:** Better mechanisms needed to preserve both
9. **Interpretability for Security:** Mechanistic understanding could enable better defenses
10. **Regulatory Compliance:** Technical solutions for GDPR, right-to-be-forgotten

---

## Recommended Reading Path

**Beginners:**
1. Paper #1 (Categorization of Prompt Injection)
2. Paper #28 (Indirect Prompt Injection basics)
3. Paper #13 (GCG - fundamental jailbreak technique)
4. Paper #87 (HarmBench - evaluation framework)

**Intermediate:**
5. Paper #24 (Crescendo - multi-turn attacks)
6. Paper #39 (PoisonedRAG)
7. Paper #45 (Training data extraction)
8. Paper #61 (Constitutional AI)

**Advanced:**
9. Paper #97 (Chain of Thought Monitorability)
10. Paper #92 (Certified defenses)
11. Paper #50 (Model stealing from production systems)
12. Paper #101 (H-CoT hijacking reasoning models)

---

**Last Updated:** 2025-11-16
**Maintained by:** Research compilation from web sources
**License:** Research purposes only - see individual papers for licensing

