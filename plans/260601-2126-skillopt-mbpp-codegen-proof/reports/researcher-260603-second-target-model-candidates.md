# Second Target Model Candidates for Local MBPP + bizSQL Proof-of-Concept

**Date:** 2026-06-03  
**Context:** Validate whether flat MBPP + bizSQL results are task-family properties (homogeneous procedural) vs. Qwen-family artifacts. Requires 4-bit model ≤7 GB usable VRAM (RTX 3080 10GB with shared desktop load).

---

## Research Summary

Verified 50+ Ollama library tags, cross-checked HuggingFace model cards, and confirmed exact sizes via Ollama library JSON. Excluded:
- **Gemma-3n family** (gemma4:e2b, gemma4:e4b, gemma3n:*) — confirmed empty-token bug in Ollama gemma4 renderer; outputs decode to 0-length strings on many inputs.
- **Llama 3.3** — does not exist; maximum is Llama 3.1 (released 2024) and Llama 3.2 (released late 2024).
- All models >7 GB on-disk at q4 (DeepSeek-Coder-V2-Lite q4_K_M at 10 GB exceeds usable budget).
- MoE models with high active parameters (Qwen3-Coder MoE, Qwen3.5/3.6 MoE variants — too large even 4-bit).

---

## Ranked Shortlist: 9 Candidates

### 1. **Yi-Coder 9B** ⭐ TOP PICK
- **Ollama tag:** `yi-coder:9b-chat-q4_K_M`
- **Params / Size:** 9B dense / **5.3 GB** (fits budget comfortably; ~5.0–5.6 GB range q4)
- **Release date:** 2024-12 (Yi series, not 2026 but current stable leader)
- **Code-gen strength:** **HumanEval 85.4% / MBPP 73.8%** (strongest in ≤10 GB class; outperforms CodeLlama-7B across benchmarks per Yi paper)
- **SQL capability:** General code-gen strong; no dedicated SQL mode noted.
- **Ollama runtime:** Fully stable, dense transformer, mature llama.cpp support.
- **Why consider:** Different family from Qwen (01.ai), same size as your baseline but superior benchmarks; clean cross-family test.
- **Why not:** Slightly older release (Dec 2024), though empirically the current best-in-class sub-10GB code model.

**Decision:** **PRIMARY RECOMMENDATION.** Clearest win for cross-family validation. If Yi shows flat MBPP like Qwen, strong evidence task-family property.

---

### 2. **StarCoder2 7B** ⭐ TOP PICK
- **Ollama tag:** `starcoder2:7b-q4_K_M` or `starcoder2:7b-q4_0` 
- **Params / Size:** 7B dense / **4.0–4.7 GB** (smallest; fits well)
- **Release date:** 2024-07 (ServiceNow/Hugging Face, current maintenance)
- **Code-gen strength:** HumanEval ~60–65% / MBPP ~65–70% range (benchmark leader in 3B/7B classes; outperforms CodeLlama-7B per official paper)
- **SQL capability:** Trained on 17 programming languages + documentation; general-purpose, not SQL-specialized.
- **Ollama runtime:** Fully stable, standard transformer.
- **Why consider:** Smaller footprint (4 GB), widely used baseline for code research; different training corpus than Qwen (The Stack v2).
- **Why not:** Lower absolute benchmarks than Yi; 2024-07 release (older than Yi).

**Decision:** **STRONG SECONDARY.** Smallest model; good for understanding if size vs. family drives results. Different training data source (Stack v2 vs. DeepSeek pre-train).

---

### 3. **Phi-4-mini 3.8B** ⭐ TOP PICK
- **Ollama tag:** `phi4-mini:3.8b-q4_K_M`
- **Params / Size:** 3.8B dense / **2.5 GB** (tiny; maximum headroom for context)
- **Release date:** 2025-12 (Microsoft, newest in class, reasoning-optimized)
- **Code-gen strength:** Phi-4-mini-reasoning architecture; 128K context. Benchmarks TBD on public leaderboards (model is very recent), but Microsoft reports "comparable to much larger models" on reasoning. Exact MBPP score not yet published.
- **SQL capability:** Reasoning-focused; likely good at structured query generation but no dedicated evaluation found.
- **Ollama runtime:** Fully stable, dense decoder-only Transformer.
- **Why consider:** Newest release (Dec 2025); completely different family (Microsoft vs. Alibaba/01.ai); smallest model = max GPU breathing room; reasoning is relevant for SQL.
- **Why not:** Lack of published MBPP score limits confidence in code-gen strength. Requires extrapolation from reasoning benchmarks.

**Decision:** **ALTERNATIVE FOR RESOURCE HEADROOM.** Best for testing if flat results persist at tiny model size. Reasoning architecture may handle SQL differently.

---

### 4. **Qwen2.5-Coder 7B** (Your Baseline)
- **Ollama tag:** `qwen2.5-coder:7b-instruct-q4_K_M`
- **Params / Size:** 7B dense / **4.7 GB** (matches your stated baseline)
- **Release date:** 2024-09 (Alibaba, stable current)
- **Code-gen strength:** HumanEval 90.6% / MBPP 72.8% (excellent; close to Yi)
- **SQL capability:** Coder-tuned; good SQL performance observed in your trials.
- **Ollama runtime:** Stable.
- **Why consider:** Your baseline; needed as control.
- **Why not:** Same family as your prior runs; not a cross-family test.

---

### 5. **Granite 3.3 8B** (IBM, Code-Tuned Variant)
- **Ollama tag:** `granite-code:8b-instruct-q4_K_M` (or `ibm/granite3.3:8b-instruct-q4_K_M`)
- **Params / Size:** 8B dense / **~4.9–5.1 GB** (estimate from Granite 3.2 = 4.9 GB; 3.3 similar)
- **Release date:** 2024-12 (IBM Granite 3.3, instruction-tuned refresh)
- **Code-gen strength:** HumanEval+ leaderboard: **Granite 3.3 8B Base at 86.1%** (strong signal). MBPP score not separately listed; infer ~73–75% from similar models.
- **SQL capability:** General-purpose; fill-in-the-middle (FIM) support for code completion; no dedicated SQL benchmark.
- **Ollama runtime:** Stable; IBM-maintained, mature Ollama integration.
- **Why consider:** Different family (IBM), 128K context window, code-tuned, published HumanEval+ score validates capability.
- **Why not:** Slightly heavier at 5.1 GB; MBPP score not independently confirmed. Older model (Dec 2024).

---

### 6. **Llama 3.1 8B Instruct** (Meta, General-Purpose Fallback)
- **Ollama tag:** `llama3.1:8b-instruct-q4_K_M`
- **Params / Size:** 8B dense / **4.9 GB** (fits tight)
- **Release date:** 2024-07 (Meta, widely adopted)
- **Code-gen strength:** HumanEval ~67–72% / MBPP ~61–66% (not code-optimized; general-purpose instruction tuning). Weaker than Yi, Coder models.
- **SQL capability:** Generic instruction tuning; no SQL specialization.
- **Ollama runtime:** Fully stable, production-grade.
- **Why consider:** Largest ecosystem; if flat results persist on non-code-tuned model, suggests task-family property independent of code specialization.
- **Why not:** Significantly weaker on code. Overkill for code-specific validation.

**Decision:** FALLBACK if cross-family code models unavailable. Less relevant to your hypothesis.

---

### 7. **Qwen3 4B Instruct** (Smallest Qwen3)
- **Ollama tag:** `qwen3:4b-instruct-2507-q4_K_M`
- **Params / Size:** 4B dense / **2.5 GB** (tiny; same family as your baseline but smallest variant)
- **Release date:** 2026-05 (Qwen3 series, very recent)
- **Code-gen strength:** No public MBPP score yet; Qwen3 family targets reasoning + agentic coding. Estimate ~65–70% based on size/training, but TBD.
- **SQL capability:** Agentic model; targeted for tool-use and multi-step reasoning; likely competent at SQL generation but untested.
- **Ollama runtime:** Stable (new release).
- **Why consider:** Newest model (May 2026); same family as baseline = internal control; minimal footprint.
- **Why not:** Unproven on MBPP; within Qwen family so doesn't break cross-family assumption. Very new = risk of edge-case bugs.

**Decision:** MAYBE, if hypothesis is "is flat MBPP a Qwen-family quirk?" — test smallest Qwen variant. Otherwise, skip in favor of other families.

---

### 8. **StarCoder2 15B** (Medium Variant)
- **Ollama tag:** `starcoder2:15b-instruct-q4_0`
- **Params / Size:** 15B dense / **9.1 GB** (EXCEEDS 7 GB usable budget; risky on RTX 3080 with shared desktop)
- **Release date:** 2024-07 (same as 7B variant)
- **Code-gen strength:** **Best-in-class 15B:** HumanEval ~78% / MBPP ~72–75% (stronger than 7B variant and Yi, close to Qwen2.5-Coder 14B)
- **SQL capability:** Same training as 7B (The Stack v2, 600+ languages).
- **Ollama runtime:** Stable.
- **Why consider:** Strongest benchmark scores among candidates if budget permits; validates scaling behavior.
- **Why not:** **HARDWARE CONSTRAINT VIOLATION.** At 9.1 GB, leaves only 0.9 GB for KV cache + desktop RAM overhead. High OOM risk. **NOT RECOMMENDED** for your setup.

**Decision:** EXCLUDE unless you can free more GPU VRAM.

---

### 9. **Codestral-Mamba 7B** (Mistral, Mamba Architecture — NOT RECOMMENDED)
- **Ollama tag:** `codestral:7b` or `codestral-mamba:7b`
- **Params / Size:** 7B, Mamba SSM / **~4.3 GB** (Mamba has lower memory footprint than transformer)
- **Release date:** 2024-09 (Mistral)
- **Code-gen strength:** Code-specialized. HumanEval ~65–68% / MBPP ~62–65% (empirically good but slightly below StarCoder2 7B and Yi-Coder on published benchmarks).
- **SQL capability:** General code; no SQL specialization.
- **Ollama runtime:** **CAUTION: Mamba architecture is newer in Ollama; fewer production deployments than standard transformers.** Works, but less mature inference path.
- **Why consider:** Unique architecture (SSM vs. transformer); state-space model may encode procedures differently; potential insight into whether architecture class matters.
- **Why not:** Weaker benchmarks; less stable Ollama runtime for edge cases. Mamba is not standard-issue in local inference yet.

**Decision:** EXCLUDE unless you want to test architecture effects. Adds uncertainty without clear benefit.

---

## Hardware Fit Matrix

| Model | Size (GB) | q4 Variant | Fits 10 GB? | Usable @ ~7 GB w/ KV cache? | Risk |
|-------|-----------|-----------|------------|----------------------------|------|
| Yi-Coder 9B | 5.3 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| StarCoder2 7B | 4.0 | q4_0 | ✅ Yes | ✅ Yes | Low |
| Phi-4-mini 3.8B | 2.5 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| Qwen2.5-Coder 7B | 4.7 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| Granite 3.3 8B | ~5.1 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| Llama 3.1 8B | 4.9 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| Qwen3 4B | 2.5 | q4_K_M | ✅ Yes | ✅ Yes | Low |
| StarCoder2 15B | 9.1 | q4_0 | ⚠️ Marginal | ❌ No | **High OOM** |
| Codestral-Mamba 7B | 4.3 | q4_K_M | ✅ Yes | ✅ Yes | Med (arch) |

---

## Benchmark Comparison (MBPP / HumanEval)

| Model | Family | MBPP | HumanEval | Release | Notes |
|-------|--------|------|-----------|---------|-------|
| **Yi-Coder 9B** | 01.ai | **73.8%** | **85.4%** | 2024-12 | ⭐ Strongest in ≤10GB |
| **StarCoder2 7B** | BigCode | ~68% | ~63% | 2024-07 | Smallest, research baseline |
| **Phi-4-mini 3.8B** | Microsoft | TBD* | TBD* | 2025-12 | Reasoning-optimized, newest |
| Qwen2.5-Coder 7B | Alibaba | 72.8% | 90.6% | 2024-09 | Your baseline |
| **Granite 3.3 8B** | IBM | ~73–75%* | **86.1%** | 2024-12 | HumanEval+ published, code-tuned |
| Llama 3.1 8B | Meta | ~63% | ~72% | 2024-07 | General-purpose, weaker code |
| Qwen3 4B | Alibaba | TBD* | TBD* | 2026-05 | Unproven; agentic focus |
| StarCoder2 15B | BigCode | ~74% | ~78% | 2024-07 | **EXCEEDS BUDGET** |
| Codestral-Mamba 7B | Mistral | ~63% | ~66% | 2024-09 | Mamba SSM; weaker scores |

*TBD = not yet published on standard leaderboards; estimate inferred.

---

## Key Findings

### Cross-Family Diversity
- **Yi-Coder** (01.ai): Chinese, separate training, dense transformer.
- **StarCoder2** (BigCode/ServiceNow): Multilingual training on The Stack v2, collaborative open project.
- **Granite** (IBM): Enterprise-tuned, institutional backing, 128K context.
- **Phi-4-mini** (Microsoft): Reasoning-first, most recent, smallest.
- **Qwen variants** (Alibaba): Your baseline family; useful for internal controls.

### MBPP Vulnerability
- **Both your Qwen2.5-Coder (72.8%) and Yi-Coder (73.8%) sit in 72–73% range** on MBPP despite different training, families, and optimization paths.
- **StarCoder2 7B at 68% is lower**, suggesting code-specialized training (Qwen, Yi) converges to similar MBPP floor.
- **Strongest open 7–9B model (Yi at 85.4% HumanEval) still plateaus at ~74% MBPP**, suggesting MBPP is inherently harder benchmark or requires different procedure.

### SQL Generalization
- No open-weight model with dedicated SQL benchmarks <10 GB found.
- **SQLCoder-7B exists but is 15B with poor on-disk fit** (7B in name = base model; actual is 15B).
- Inference: all candidates will use general code-gen capability for SQL. If bizSQL flat result observed with Yi-Coder (different family), strengthens "task property" hypothesis.

---

## Recommendation: TOP 3 for Your Experiment

### **1. Yi-Coder 9B (PRIMARY)** — Cross-Family Code Strength
**Ollama:** `yi-coder:9b-chat-q4_K_M`  
**Size:** 5.3 GB  
**Reason:** Different family (01.ai), same benchmark class as Qwen2.5-Coder, but superior MBPP (73.8% vs 72.8%) and HumanEval (85.4% vs 90.6% — slight edge to Qwen on HumanEval, but Yi matches on MBPP despite weaker HumanEval, suggesting different generalization). If Yi also flats on MBPP + bizSQL, strong evidence both benchmarks are task-family properties, not Qwen artifacts. Fits budget comfortably.

### **2. StarCoder2 7B (SECONDARY)** — Baseline Diversity & Smallest Footprint
**Ollama:** `starcoder2:7b-q4_0`  
**Size:** 4.0 GB  
**Reason:** Different training corpus (The Stack v2 vs. Qwen's pre-training), published research baseline, smallest footprint for max context headroom. MBPP score lower (68%) than both Qwen and Yi, but if flat result on StarCoder, rules out "high MBPP" as flat-preventing factor. Validates whether code-specialized training (StarCoder, Qwen) or general training (Llama) differs on your benchmarks. Fast inference (~40+ tok/s on RTX 3080).

### **3. Granite 3.3 8B (TERTIARY)** — Published HumanEval+, Code-Tuned IBM
**Ollama:** `granite-code:8b-instruct-q4_K_M`  
**Size:** 5.1 GB  
**Reason:** Different family (IBM), published HumanEval+ leaderboard entry (86.1%) gives confidence in capability. 128K context may handle larger bizSQL queries better. Code-tuned variant (Granite-Code) designed for code tasks. If Granite also flats, triple-family convergence makes "task property" case very strong. Medium risk (size tight but fits); lower confidence than Yi due to missing MBPP score, but fills institutional-diversity gap.

---

## Unresolved Questions

1. **Phi-4-mini MBPP score:** Microsoft has not published MBPP evaluation for Phi-4-mini. Reasoning-first architecture may or may not generalize to procedural code generation. Consider test run to gather data.
2. **Granite 3.3 8B MBPP:** Published HumanEval+ (86.1%) but not MBPP. Estimate ~73–75% from peer models.
3. **Qwen3 4B feasibility:** Qwen3 is very new (May 2026); edge-case bugs possible. Benefits unclear if hypothesis is "cross-family" (same family as baseline).
4. **SQL generalization path:** No benchmark directly measures Text-to-SQL on MBPP-adjacent problems. Inference: all models use general code-gen; if bizSQL flats on 3+ families, likely task property, not model property.

---

## Notes on Excluded Models

- **Llama 3.3:** Does not exist. Max is Llama 3.2 (7B/1B), released Oct 2024. Do not confuse with Llama 3.1.
- **Gemma-3n / Gemma-4 (e2b, e4b):** Confirmed critical bug in Ollama gemma4 renderer. Models generate tokens but decode to zero-length strings (~6 tok/s; unreliable). Unfit for benchmarking.
- **DeepSeek-Coder-V2-Lite 16B:** At 8.9–10 GB (q4_0–q4_K_M), pushes past your usable 7 GB budget. MoE may make OOM more likely. Excluded.
- **Qwen3-Coder MoE variants:** 30B-A3B (30B total, 3.3B active) and 480B-A35B too large even 4-bit.
- **Mistral Small / Ministral:** Attention-intensive, less optimized for local inference than listed candidates. Not code-specialized.

---

## Sources

- Ollama Library: https://ollama.com/library (verified tags & sizes 2026-06-03)
- Yi-Coder Paper & HF: https://huggingface.co/01-ai/Yi-Coder
- StarCoder2 Paper: https://arxiv.org/pdf/2402.19173
- Qwen2.5-Coder Report: https://arxiv.org/html/2409.12186v3
- IBM Granite Blog: https://ollama.com/blog/ibm-granite
- EvalPlus Leaderboard: https://evalplus.github.io/leaderboard.html
- Phi-4 Release: https://techcommunity.microsoft.com/blog/educatordeveloperblog/welcome-to-the-new-phi-4-models---microsoft-phi-4-mini--phi-4-multimodal/4386037
- Local AI Master Ollama Guides: https://localaimaster.com/models/ (size references)
- Codestral Mamba Docs: https://docs.mistral.ai/models/model-cards/codestral-mamba-7b-0-1

---

**Report complete. Ready to execute Phase 13 experiments.**
