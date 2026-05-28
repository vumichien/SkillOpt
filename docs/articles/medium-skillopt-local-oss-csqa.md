# Can Microsoft's SkillOpt Optimize an OSS Model on Your Gaming GPU? I Spent $0.01 to Find Out.

> Training a markdown file like a neural network — without touching weights — on Qwen2.5-7B running locally in Ollama, driven by DeepSeek as the cheap cloud "optimizer." 12 minutes, one cent, three real findings.

---

## TL;DR

I ran **SkillOpt** (Microsoft's text-as-weights optimizer, [arXiv 2025](https://arxiv.org/abs/2509.02075)) on a non-paper task — 100 CommonsenseQA multiple-choice items — using a **local OSS target** (Qwen2.5-7B-Instruct Q4_K_M via Ollama on an RTX 3080) and a **cheap cloud optimizer** (DeepSeek-chat at $0.014 / $0.28 per 1M tokens).

Three runs, ~30 minutes total compute, **~1 cent of DeepSeek spend**:

| Run | Val acc lift | Test delta | Accepts | Wall time | Verdict |
|-----|---|---|---|---|---|
| v1 — strong init, noisy eval | 0 | −8.3 % | 0 / 6 | 15 min | gate too noisy |
| v2 — weak init, temp=0 eval | +4.2 % | −4.2 % | 1 / 6 | 4.7 min | gate fires, no transfer |
| **v3 — bigger splits** | **+4.0 %** (86 → 90 %) | −2.0 % (within CI) | **3 / 10** | 12 min | **loop works; generalization is the next problem** |

**The optimization loop is real:** SkillOpt accepted 3 of 10 candidate edits, the skill markdown grew from 154 B → 3.6 KB of substantive CSQA heuristics, val accuracy climbed monotonically across the accepted steps. **The bottleneck isn't the loop — it's that 100 val items is still small enough for the optimizer to fit to surface patterns.**

The skill it actually wrote is at the bottom of this post. It's a real prompt-engineering guide that a human would write.

---

## What is SkillOpt, briefly

SkillOpt trains a **single markdown file** — a "skill" — as if it were a neural network:

- **Forward pass**: run the target model on a minibatch with the skill in its system prompt
- **Loss**: per-item correctness (or any other scalar)
- **Backward pass**: an **optimizer model** reads the failures, proposes textual edits ("gradients") to the skill
- **Gate**: only accept the edit if it improves accuracy on a held-out val split

The whole thing is two LLMs talking through a markdown file. No weights move. No training data leaks into the model. The artifact you ship is the skill.md.

In the paper, SkillOpt uses GPT-5 + Claude as optimizer/target on benchmarks like SWE-Bench. The question I wanted to answer: **does this generalize to a small local OSS target + a cheap cloud optimizer, on a task the paper never tested?**

---

## The setup

```
┌───────────────────────────┐         ┌──────────────────────────────┐
│ Optimizer (cloud)         │         │ Target (local)               │
│ DeepSeek-chat             │ reflect │ Qwen2.5-7B-Instruct Q4_K_M   │
│ via /v1 OpenAI-compatible │◄────────│ via Ollama /v1               │
│ $0.014 / $0.28 per 1M tok │ patches │ ~8.5 GB VRAM, RTX 3080       │
└───────────────────────────┘────────►└──────────────────────────────┘
        Reflects on failures           Runs rollouts on each batch
```

**Task**: CommonsenseQA — 5-way multiple-choice, output a single letter in `<answer>...</answer>` tags. Source: `tau/commonsense_qa` on HF.

**Splits**: 100 train / 100 val / 200 test, sampled deterministically from the 10,962 labeled CSQA rows (the HF test split has hidden labels, so I pooled train+validation).

**Initial skill** (weak — leaves headroom for the optimizer to climb):

```markdown
# Multiple-Choice Task

Pick the single best option for the question. Output only that option's
letter inside `<answer>` tags, e.g. `<answer>B</answer>`.
```

**Reflect schedule**: bs=20, 5 minibatch steps × 2 epochs = 10 candidate edits proposed total. Gate evals every candidate on all 100 val items at temperature 0 (deterministic).

---

## Three runs, three lessons

### v1 — Strong initial skill + temp=0.7 eval → nothing moved

I started with a hand-written CSQA rubric: "eliminate wrong options, watch for negation traps, output the letter." It already hit **87.5% val acc** on Qwen2.5-7B before SkillOpt ran at all.

```
step 1: sel=0.792  reject
step 2: sel=0.833  reject
step 3: sel=0.708  reject
step 4: sel=0.833  reject
step 5: sel=0.875  reject  (tie, no strict improvement)
step 6: sel=0.750  reject
```

**0 of 6 candidates accepted.** Final test acc went DOWN 8 percentage points from baseline (75 % → 67 %). But the trained skill was byte-identical to the initial. Same skill, different result.

The "different result" was just **sampling noise**: Qwen's default temperature is 0.7. On 24-item val, one item = 4.2 % accuracy. The gate was making decisions on coin flips.

**Lesson 1: gate quality is bounded by eval temperature × eval set size.** If you can't separate signal from sampling jitter, no improvement is detectable.

### v2 — Weak init + temp=0 eval → gate fires, but doesn't transfer

Two changes:
- **Weakened initial skill** (the 3-line stub above) → no rubric, just the task framing
- **`QWEN_CHAT_TEMPERATURE=0`** → greedy decoding, deterministic eval

```
step 1: sel=0.750  reject
step 2: sel=0.833  reject
step 3: sel=0.792  reject
step 4: sel=0.875  reject  (tie)
step 5: sel=0.833  reject
step 6: sel=0.917  ACCEPT_NEW_BEST   ← gate fired!
```

**1 of 6 accepted** at step 6, val acc 0.875 → 0.917 (+4.2 %). The skill grew from 157 B → 547 B with this addition:

> *"Before selecting, check that the option matches the entire scenario or constraint—not just a single keyword from the question."*

That's a real CSQA failure mode (distractor options that share keywords with the question).

**But test went down 4.2 % anyway** (0.771 → 0.729). With only 24 val items, the +1-item val improvement (22/24 → 21/24 actually 21→22) didn't transfer to the broader test pool. Classic small-eval-set overfit.

Wall time also dropped from 15 min to 4.7 min — **temperature=0 made Ollama 3× faster** (no sampling overhead, no retries).

**Lesson 2: deterministic decoding doesn't only stabilize the gate — it speeds up the whole pipeline.**

### v3 — Bigger splits → SkillOpt's loop visibly works

Final config:
- 100 train / **100 val** / 200 test (4× val, 4× test)
- bs=20, 10 candidate edits total
- workers=8 (RTX 3080 was at <20 % mean util in v2)

The trajectory was the cleanest possible optimization curve:

```
step 1: sel=0.860  reject
step 2: sel=0.870  ACCEPT  skill 154 → 374 B
step 3: sel=0.890  ACCEPT  skill 374 → 1707 B
step 4: sel=0.900  ACCEPT  skill 1707 → 3628 B   ← peak
step 5: sel=0.880  reject  (regression)
step 6-10:         reject  (plateau)
```

**3 of 10 accepted**, all consecutive, val acc climbing monotonically 0.86 → 0.87 → 0.89 → 0.90. After step 4 the optimizer plateaued: every subsequent candidate failed to beat 0.90 strictly.

**This is what a working optimization loop looks like.** Monotonic improvement until the model finds a local plateau.

### Final numbers (v3)

| Metric | Baseline | Trained |
|---|---|---|
| Val acc (100 items) | 0.860 | **0.900** (+4.0 %) |
| Test acc (200 items) | 0.760 | 0.740 (−2.0 %, within 95 % CI) |
| Skill size | 154 B | **3 628 B** (24×) |
| Wall time | — | **708 s** |
| GPU duty cycle | — | 35 % (peak 100 %, mean 24.8 %) |
| DeepSeek tokens | — | 200 k in + 23 k out |
| **DeepSeek cost** | — | **~$0.01** |

Yes, one cent. The local Qwen rollouts (1.7k calls) are free; the only billable spend is the optimizer.

---

## The skill SkillOpt actually wrote

This is `best_skill.md` after 3 accepts — autogenerated by DeepSeek, no human edits:

```markdown
# Multiple-Choice Task

Pick the single best option for the question. Output only that option's
letter inside `<answer>` tags, e.g. `<answer>B</answer>`.

## Avoid Keyword Matching
Be especially careful with idioms or implied meanings. The question may
use figurative language that is not meant literally. Evaluate the
intended meaning, not the surface wording of the phrase.

Instead, identify the core concept or scenario described in the question,
then evaluate which option best fits that core concept. Distractors may
share incidental keywords but fail to address the question's central
meaning.

## Step-by-Step Reasoning
Before selecting an answer:
1. Restate the question in your own words to identify what it is truly asking.
2. For each option, ask: "Does this option fully capture the meaning of the
   question, or does it only share a word/phrase with it?"
3. Eliminate options that are clearly irrelevant, contradictory, or describe
   a different concept.
4. Among the remaining options, choose the one that best matches the core
   meaning of the question.

## Identify the Causal or Functional Core
When a question describes an effect ("let more light in", "dry storage",
"uninhabited without a queen"), ask: "What property or function directly
explains this effect?" Then look for the option that names that property
(e.g., "clear" explains why glass lets light in, "dry" is what storage
must be, "queen" is essential for a bee hive).

## Consider Social and Situational Context
When a question describes a social scenario or spatial constraint, identify
the core situational requirement. Pick the option that best fits the entire
scenario, not just one keyword.

## Example of Superficial Matching
If asked: "If you were lazy you'd probably choose to just watch television
simply because what?" with options A. entertained, B. see favorite show,
C. plug in, D. get comfortable, E. you're bored — the correct answer is E.
Laziness implies boredom, not just entertainment.
```

A human prompt engineer would write basically this. The "lazy watching TV" example does look like a near-duplicate of a val item, which probably explains why val climbed and test didn't.

---

## The honest verdict

**What's proven:**
1. ✅ SkillOpt's loop runs end-to-end on a local OSS target + cheap cloud optimizer
2. ✅ The gate fires on real signal when noise is removed (3 accepts, monotonic climb)
3. ✅ The optimizer writes substantive, human-readable heuristics — not random text
4. ✅ The cost is genuinely trivial (~$0.01 per run of this size)

**What isn't:**
1. ❌ Improved val didn't translate to improved test (−2.0 %, within noise CI)
2. ❌ A 100-item val set is still small enough for the optimizer to fit val-specific patterns

The trained skill is statistically indistinguishable from baseline on held-out test — it's not *better*, but it's also not *worse*. SkillOpt didn't fail; it ran into the well-known **small-eval-set overfitting** problem that every prompt-tuning paper has to navigate.

**The next experiment that would actually settle it**: run the trained skill against a *different* MCQA dataset (ARC-Challenge, OpenBookQA) where it can't have seen val-leakage during reflect. If the v3 skill still adds value there, the loop has produced a transferable artifact. If not, the val→test gap is genuinely an overfit story.

---

## Reproducing this on your machine

The full pipeline is in [the repo](https://github.com/microsoft/SkillOpt) (my fork; PR upstream pending). On Windows with an RTX 3080 + Ollama:

```powershell
# 1. install Ollama, pull Qwen2.5-7B (4 GB download)
ollama serve
ollama pull qwen2.5:7b-instruct-q4_K_M

# 2. clone + venv
git clone https://github.com/<your-fork>/SkillOpt
cd SkillOpt
uv venv && uv pip install -r requirements.txt

# 3. prepare CSQA data (100/100/200)
python scripts/prepare_mcqa_data.py --n-train 100 --n-val 100 --n-test 200 \
       --out-dir data/mcqa_csqa_split

# 4. fill in your DeepSeek key
cp .env.local-pilot.example .env.local-pilot
# edit OPTIMIZER_OPENAI_API_KEY

# 5. run (~12 min)
.\scripts\run_local_pilot.ps1
```

Artifacts land in `outputs/mcqa_local_pilot/`:
- `best_skill.md` — the trained skill (the actual deliverable)
- `history.json` — per-step trajectory data
- `gpu.csv` — RTX 3080 utilization timeline
- `summary.json` — final metrics + token spend

---

## What's next (an update is coming)

I'm running a follow-up experiment to settle the generalization question: feeding the v3-trained CSQA skill into ARC-Challenge and OpenBookQA, with no further training, to see if the heuristics SkillOpt wrote are CSQA-specific or genuinely transferable. **I'll update this post with those numbers within a week.**

If you've tried SkillOpt or similar text-only optimizers on local models, I'd love to hear how the val/test gap behaved in your setup.

---

*Code: github.com/<your-fork>/SkillOpt · Reach out: vumichien1692@gmail.com*
