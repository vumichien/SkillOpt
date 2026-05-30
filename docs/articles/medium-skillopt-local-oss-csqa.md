# I Spent 3 Cents Training a Markdown File on My Gaming GPU

> Microsoft's SkillOpt treats prompts like neural-network weights — epochs, batch size, learning rate, validation gate. I tested whether the loop still works when the target shrinks to a 7B local model and the optimizer is a cloud LLM that costs pennies. 12 minutes, three cents, three honest findings.

*Last updated: 2026-05-30. Now includes a second dataset (SocialIQA, 3 seeds), a cross-dataset transfer matrix, and an analysis of why the loop stays flat on commonsense MC while the paper's heavyweight benchmarks lift +9–25 pp — see "A second dataset: SocialIQA" and "Why it didn't work here" below.*

---

## TL;DR

I ran **SkillOpt** ([Microsoft, arXiv 2605.23904](https://arxiv.org/abs/2605.23904)) on a task its authors never touched — 100 CommonsenseQA multiple-choice items — with a **local OSS target** (Qwen2.5-7B-Instruct Q4_K_M via Ollama on an RTX 3080) and a **cheap cloud optimizer** (DeepSeek-chat at $0.14 / $0.28 per 1M input/output tokens).

Three runs, ~30 minutes of GPU time, **~3¢ of DeepSeek spend** (200k prompt + 23k completion tokens; math at the bottom):

| Run | Val acc lift | Test delta | Accepts | Wall time | Verdict |
|-----|---|---|---|---|---|
| v1 — strong init, noisy eval | 0 | −8.3 % | 0 / 6 | 15 min | gate too noisy |
| v2 — weak init, temp=0 eval | +4.2 % | −4.2 % | 1 / 6 | 4.7 min | gate fires, no transfer |
| **v3 — bigger splits** | **+4.0 %** (86 → 90 %) | −2.0 % (within 95 % CI) | **3 / 10** | 12 min | **loop works; generalization is the next problem** |

**The optimization loop is real:** SkillOpt accepted 3 of 10 candidate edits, the skill markdown grew from 157 B → 3.7 KB of substantive CSQA heuristics, val accuracy climbed monotonically across the accepted steps. **The bottleneck isn't the loop — it's that 100 val items is still small enough for the optimizer to fit surface patterns.**

A (lightly trimmed) excerpt of the skill SkillOpt wrote is at the bottom of this post; the verbatim version lives in `outputs/mcqa_local_pilot_v3/best_skill.md`. Either way, it reads like a prompt-engineering guide a human would write.

**Update — a second dataset confirms the ceiling.** I re-ran the whole loop on **SocialIQA** (a different commonsense benchmark the paper never tested), with the overfit fix (3× larger val) and **3 seeds**. Mean held-out test delta: **+0.33 pp (± 0.29)** — flat again. One seed's gate never fired at all, because the weak-init baseline was already 0.84. The loop is real; the *task* has no headroom for it. And neither trained skill transfers to the other dataset (full matrix below). Full numbers and the "why" in **A second dataset: SocialIQA** and **Why it didn't work here** below.

---

## Background: why a markdown file deserves to be trained

Prompts are the second-largest lever in modern LLM pipelines after the weights themselves — and they're handled like *furniture*. A senior engineer writes a few hundred words of system prompt, eyeballs a couple of examples, and ships it. When it breaks in production, someone *rewrites* it. There is no gradient, no validation gate, no checkpoint.

This is what Microsoft's SkillOpt paper calls out (paraphrasing their introduction):

> *Agent skills today are hand-crafted, generated one-shot, or evolved through loosely controlled self-revision — none of which behaves like a deep-learning optimizer for the skill itself.* — adapted from [SkillOpt, arXiv 2605.23904](https://arxiv.org/abs/2605.23904)

Their fix is structurally simple: treat a **single markdown file** — what they call a *skill* — as the artifact being optimized, and wrap a real training loop around it. Forward pass, loss, backward pass, validation gate, epochs, learning rate. The model weights never move. Only the markdown moves.

In the paper, that loop wins **52 / 52** of the (model, benchmark, harness) configurations they evaluate, with +9 to +25 point lifts on heavyweight benchmarks (SearchQA, ALFWorld, DocVQA, LiveMathematicianBench, SpreadsheetBench, OfficeQA). The targets are frontier closed-source models. The optimizer is also a frontier model. The bill is presumably significant.

**Which leaves an obvious question for anyone who isn't a hyperscaler.**

---

## Why this experiment

The paper proves SkillOpt works *when both sides of the loop are top-shelf*. The interesting test for the rest of us is whether the loop survives two simultaneous downgrades:

1. **Target ↓ 10–100×**: from a frontier closed-source model to a Q4-quantized **Qwen2.5-7B** running locally on an RTX 3080.
2. **Optimizer ↓ ~10–100×**: from frontier model to **DeepSeek-chat** at $0.14 input / $0.28 output per 1M tokens.

And whether it generalizes to a **task the paper never tested**: CommonsenseQA, a 5-way multiple-choice benchmark for everyday reasoning.

If the loop only works at frontier scale, that's important to know — it would mean SkillOpt is a tool for labs, not for the rest of us. If it survives the downgrades, the article you're reading is basically a recipe.

---

## What SkillOpt actually does

The mental model is a straight port of supervised learning. The mapping isn't a metaphor — it's literally how the codebase is structured ([docs/guide/dl-analogy.md](https://github.com/microsoft/SkillOpt)):

| Deep learning | SkillOpt |
|---|---|
| Model weights | A markdown skill document |
| Forward pass | Rollout: target model runs the task with the skill in its system prompt |
| Loss | Reflect: optimizer reads failed rollouts and proposes textual edits |
| Gradient step | Apply patches (add/delete/replace) to the skill |
| Learning rate | Max edits accepted per step |
| Validation gate | Run candidate skill on held-out split; accept only if it strictly beats current best |
| Epoch | Pass over the train set; with a *slow update* boundary that prevents catastrophic forgetting |
| Meta-learning | A *meta-skill* file that accumulates cross-epoch strategy notes for the optimizer (off in this run; see [config](https://github.com/microsoft/SkillOpt)) |

The whole thing is two LLMs talking through a markdown file. No weights move. The artifact you ship is `best_skill.md`. That's the deliverable.

The training loop per step is six stages: **rollout → reflect → aggregate similar patches → select top-k → update skill → gate on val**. Epoch boundaries add the slow-update pass to detect regressions on previously-passing items.

---

## The setup

```
┌───────────────────────────┐         ┌──────────────────────────────┐
│ Optimizer (cloud)         │         │ Target (local)               │
│ DeepSeek-chat             │ reflect │ Qwen2.5-7B-Instruct Q4_K_M   │
│ via /v1 OpenAI-compatible │◄────────│ via Ollama /v1               │
│ $0.14 / $0.28 per 1M tok  │ patches │ ~8.5 GB VRAM, RTX 3080       │
└───────────────────────────┘────────►└──────────────────────────────┘
        Reflects on failures           Runs rollouts on each batch
```

**Task**: CommonsenseQA — 5-way multiple-choice, output a single letter in `<answer>...</answer>` tags. Source: `tau/commonsense_qa` on Hugging Face.

**Splits**: 100 train / 100 val / 200 test, sampled deterministically from the 10,962 labeled CSQA rows. (The HF test split has hidden labels, so I pooled train + validation.)

**Initial skill** (weak by design — leaves headroom for the optimizer to climb):

```markdown
# Multiple-Choice Task

Pick the single best option for the question. Output only that option's
letter inside `<answer>` tags, e.g. `<answer>B</answer>`.
```

**Reflect schedule**: batch size 20, 5 minibatch steps × 2 epochs = 10 candidate edits proposed total. Gate evals every candidate on all 100 val items at temperature 0 (deterministic).

---

## Three runs, three lessons

### v1 — Strong initial skill + temp=0.7 eval → nothing moved

I started with a hand-written CSQA rubric: "eliminate wrong options, watch for negation traps, output the letter." It already hit **87.5 % val acc** on Qwen2.5-7B before SkillOpt ran at all.

```
step 1: sel=0.792  reject
step 2: sel=0.833  reject
step 3: sel=0.708  reject
step 4: sel=0.833  reject
step 5: sel=0.875  reject  (tie, no strict improvement)
step 6: sel=0.750  reject
```

**0 of 6 candidates accepted.** Final test acc dropped 8 percentage points from baseline (75 % → 67 %). But the trained skill was byte-identical to the initial. Same skill, different result.

The "different result" was just **sampling noise**: Qwen's default temperature is 0.7. On a 24-item val split, one item = 4.2 % accuracy. The gate was making decisions on coin flips.

**Lesson 1: gate quality is bounded by `eval_temperature × eval_set_size`.** If you can't separate signal from sampling jitter, no improvement is detectable.

### v2 — Weak init + temp=0 eval → gate fires, but doesn't transfer

Two changes:
- **Weakened the initial skill** (the 3-line stub above) → no rubric, just the task framing
- **`QWEN_CHAT_TEMPERATURE=0`** → greedy decoding, deterministic eval

```
step 1: sel=0.750  reject
step 2: sel=0.833  reject
step 3: sel=0.792  reject
step 4: sel=0.875  reject  (tie)
step 5: sel=0.833  reject
step 6: sel=0.917  ACCEPT_NEW_BEST   ← gate fired!
```

**1 of 6 accepted** at step 6, val acc 0.875 → 0.917 (+4.2 pp). The skill grew from 157 B → 547 B with this addition:

> *"Before selecting, check that the option matches the entire scenario or constraint — not just a single keyword from the question."*

That's a real CSQA failure mode (distractor options that share keywords with the question). It's also exactly the kind of heuristic a human prompt engineer would write.

**But test went down 4.2 % anyway** (0.771 → 0.729). With only 24 val items, the +1-item val improvement (21 → 22 correct) didn't transfer to the broader test pool. Classic small-eval-set overfit.

Wall time also dropped from 15 min to 4.7 min — **temperature=0 was the largest factor in a ~3× speedup**. (The weaker init also produced shorter completions, so it's not 100 % attributable to decoding.)

**Lesson 2: deterministic decoding doesn't only stabilize the gate — it speeds up the whole pipeline.**

### v3 — Bigger splits → SkillOpt's loop visibly works

Final config:
- 100 train / **100 val** / 200 test (4× val, 4× test vs v2)
- bs=20, 10 candidate edits total
- workers=8 (RTX 3080 was at <20 % mean util in v2)

The trajectory was the cleanest possible optimization curve:

```
step 1: sel=0.860  reject
step 2: sel=0.870  ACCEPT  skill 157 → 380 B
step 3: sel=0.890  ACCEPT  skill 380 → 1728 B
step 4: sel=0.900  ACCEPT  skill 1728 → 3666 B   ← peak
step 5: sel=0.880  reject  (regression)
step 6-10:         reject  (plateau)
```

**3 of 10 accepted**, all consecutive, val acc climbing monotonically 0.86 → 0.87 → 0.89 → 0.90. After step 4 the optimizer plateaued: every subsequent candidate failed to beat 0.90 strictly.

**This is what a working optimization loop looks like.** Monotonic improvement until the model finds a local plateau, then strictly-better gate refuses to move.

### Final numbers (v3)

| Metric | Baseline | Trained |
|---|---|---|
| Val acc (100 items) | 0.860 | **0.900** (+4.0 pp) |
| Test acc (200 items) | 0.760 | 0.740 (−2.0 pp, within 95 % CI) |
| Skill size | 157 B | **3 666 B** (23×) |
| Wall time | — | **708 s** |
| GPU duty cycle | — | 35 % (peak 100 %, mean 24.8 %, sampled 147× over the run) |
| DeepSeek prompt tokens | — | 200 k |
| DeepSeek completion tokens | — | 23 k |
| **DeepSeek cost** | — | **~$0.034** |

Three cents. The math: `0.200 M × $0.14 (input) + 0.023 M × $0.28 (output) ≈ $0.028 + $0.006 ≈ $0.034`. The 1,700 local Qwen rollouts are free; only the optimizer's reflect / aggregate / rank traffic is billed.

---

## The skill SkillOpt actually wrote

This is `best_skill.md` after 3 accepts, lightly abridged for readability (full verbatim version at `outputs/mcqa_local_pilot_v3/best_skill.md`). Every word here was generated by DeepSeek:

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

A human prompt engineer would write basically this. The "lazy watching TV" example does look like a near-duplicate of a val item, which probably explains why val climbed and test didn't — more on that below.

---

## The honest verdict

**What's proven by this run:**
1. ✅ SkillOpt's loop runs end-to-end on a local OSS target + a cheap cloud optimizer
2. ✅ The gate fires on real signal once noise is removed (3 accepts, monotonic climb)
3. ✅ The optimizer writes substantive, human-readable heuristics — not random text
4. ✅ The cost is genuinely trivial (~3 cents per run of this size — about a fifth the price of a coffee creamer)

**What isn't:**
1. ❌ Improved val didn't translate to improved test (−2.0 %, within noise CI)
2. ❌ A 100-item val set is still small enough for the optimizer to fit val-specific patterns — see the "lazy watching TV" example baked into the skill

The trained skill is statistically indistinguishable from the baseline on held-out test — not *better*, but not *worse* either. SkillOpt didn't fail; it ran into the well-known **small-eval-set overfitting** problem that every prompt-tuning paper has to navigate.

That makes the next experiments the interesting ones.

---

## A second dataset: SocialIQA — the overfit fix and three seeds

The v3 CSQA result left one nagging question: was the flat test number a CSQA quirk, or something structural? So I ran the entire loop again on a commonsense benchmark **the paper never touched** — SocialIQA — from the same weak init, and this time with the overfit mitigations the v3 post-mortem called for.

### What changed vs CSQA v3

- **Dataset**: SocialIQA (`allenai/social_i_qa`, CC-BY-4.0) — 3-option social-reasoning MC (*"Cameron gathered her friends for a barbecue. How would others feel?"*). Different task, different option count, different source.
- **3× larger val** (the v3 overfit fix): 100 train / **300 val** / 200 test.
- **3 seeds (42 / 43 / 44)** — report mean ± std of the test delta, not a single lucky shuffle.
- Everything else identical to v3 (weak init, bs=20, 2 epochs → 10 candidate edits, lr=4 cosine, temp=0, workers=8).

*(Operational note: `allenai/social_i_qa` ships an old loader script that modern `datasets` refuses to run, so I load the auto-converted parquet branch. HF exposes 33,410 train + 1,954 validation labeled rows and no labeled test — so, as with CSQA, I pool train+validation and carve my own splits.)*

### The config

`configs/mcqa/local-pilot-siqa.yaml` is a two-line override on the v3 config — the whole point is that *nothing about the optimizer changed*, only the data:

```yaml
_base_: local-pilot.yaml
env:
  split_dir: data/mcqa_siqa_split   # 100 train / 300 val / 200 test; --split_dir overrides per seed
```

Effective settings inherited from `local-pilot.yaml` (the v3 setup):

```
optimizer       deepseek-chat (cloud, $0.14 / $0.28 per 1M tok)
target          qwen2.5:7b-instruct-q4_K_M (Ollama, RTX 3080)
train/val/test  100 / 300 / 200       epochs 2 → 10 candidate edits
batch_size 20   lr 4 cosine (min 2)   edit_budget 4
gate            strict-improvement on 300 val,  eval temp 0 (greedy)
workers 8
```

### Results — three seeds

| Seed | Baseline val | Best val | Baseline test | Trained test | Test Δ | Accepts |
|---|---|---|---|---|---|---|
| 42 | 0.817 | 0.830 (+1.3) | 0.785 | 0.790 | **+0.5 pp** | 2 / 10 |
| 43 | 0.837 | 0.837 (—) | 0.780 | 0.780 | **0.0 pp** | **0 / 10** (gate never fired) |
| 44 | 0.763 | 0.787 (+2.3) | 0.805 | 0.810 | **+0.5 pp** | 2 / 10 |
| **mean** | | | **0.790** | **0.793** | **+0.33 pp (± 0.29)** | |

~67 minutes of RTX 3080 time across the three runs (22 / 25 / 21 min), **~8.5¢ of DeepSeek spend** (per-seed $0.027 / $0.020 / $0.037). Each non-zero delta is exactly **one** test item out of 200 (0.5 pp). The mean +0.33 pp is statistically indistinguishable from zero — **flat, on a second dataset, with the overfit fix in place.**

Seed 43 is the most telling. The weak-init skill already scored **0.837** on the 300-item val set, and across all 10 candidate edits the optimizer **never produced one that strictly beat it**. The gate did its job perfectly — it refused to ship a non-improvement — and there was simply nothing to ship.

### What the optimizer wrote (seed 44)

This isn't the optimizer failing to do its job. On seed 44 — the run with the most headroom (baseline val 0.76) — it wrote a genuinely good, SocialIQA-specific rubric:

```markdown
### Temporal Anchoring for Future Actions
When the question asks about a future action or desire ('what will X want
to do next?'), eliminate options describing events that already happened…
Select the option that identifies a natural next logical step.

### Social Causality Heuristic
When a question describes a positive social interaction and asks about the
character's resulting feeling, prefer the option that reflects positive
self-regard (feeling valued, grateful) over negative or unrelated traits.
```

*(abridged; full skill at `outputs/mcqa_siqa_s44/best_skill.md`.)* These are real, correct heuristics for SocialIQA's question types. The loop worked. **The test number still didn't move.**

---

## Why it didn't work here — and why it worked in the paper

Two flat datasets in a row is a pattern, not an accident. The cause isn't the optimizer; it's the **headroom**.

**1. The paper's benchmarks have room; commonsense MC on a 7B does not.** SkillOpt's +9 to +25 pp lifts come from SearchQA, ALFWorld, DocVQA, LiveMathBench, SpreadsheetBench, OfficeQA — tasks where even frontier models start *far* from ceiling, with 20–40 points of recoverable performance on the table for a good skill to capture. On CSQA/SocialIQA, Qwen2.5-7B already scores **0.76–0.84 at baseline**. The gap left to 1.0 is mostly *irreducible*: ambiguous items, label noise, and questions that need world knowledge the 7B simply lacks. A markdown file can't inject knowledge that isn't in the weights.

**2. Skill optimization helps where the bottleneck is *procedure*, not *knowledge*.** The paper's wins cluster in tasks with format / tool / procedure scaffolding — how to call a search API, navigate an environment, parse a spreadsheet. That's exactly what a text skill *can* supply and what the base model genuinely lacks. Commonsense QA has no procedure to teach: the model either knows that "a lazy person watches TV because they're bored" or it doesn't. The skill can reframe the question, but the answer was already latent in pretraining.

**3. A high baseline turns the validation gate into a noise amplifier.** SkillOpt accepts an edit only if it strictly beats the current best on val. When baseline val is 0.84, the handful of items a skill can flip are as likely to be val-specific quirks as real signal — which is precisely the overfit we saw on CSQA v3, and why seed 43 couldn't move at all. Bigger val (300 vs 100) made the gate *honest* — it stopped manufacturing fake lifts — but an honest gate on a near-ceiling task correctly reports **nothing to gain**.

**4. Scale compounds it.** The paper pairs a frontier optimizer with a frontier target and large eval sets. Here the target is a 4-bit 7B and val is 300 items. A smaller model has less capacity to exploit subtle heuristics; a smaller eval set carries more sampling jitter. Both shrink the very signal SkillOpt is trying to climb.

**The honest takeaway:** SkillOpt's loop is real, and it runs end-to-end on hobby hardware for pennies — that part reproduced cleanly, twice. But its *gains* are a function of task headroom, and commonsense multiple-choice on a small local model has almost none. To actually see the loop produce a held-out win at this scale, you'd need a task where Qwen2.5-7B starts well below ceiling — a harder, lower-baseline benchmark (LogiQA, ReClor) or an agentic / tool-use task closer to what the paper tested. That's the experiment worth running next.

---

## Reproducing this on your machine

The full pipeline is in [the repo](https://github.com/microsoft/SkillOpt). On Windows with an RTX 3080 + Ollama:

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

## What's coming next

The v3 result teed up an experimental matrix I've been filling in. **Experiments 1 and 3 are now done** (the SocialIQA fresh-train and the cross-dataset transfer matrix above); **Experiments 2 and 4 remain open**. **I update this post in-place** as each row lands.

### Experiment 1 — Cross-dataset transfer (the central question) — ✅ done

Take each trained skill and run it zero-shot on the *other* dataset's held-out test set. If the heuristics SkillOpt wrote are transferable knowledge, they should hold up off-domain. If they're dataset-specific patterns, they won't. (Mode A — pure zero-shot eval, no further training; ~$0 optimizer spend.)

| Skill ↓ / test → | CSQA test (200) | SocialIQA test (200) |
|---|---|---|
| Weak init | 0.760 | 0.775 |
| v3 (CSQA-trained) | 0.740 | **0.775** |
| SocialIQA-trained (seed 44) | **0.730** | 0.790 |

**The off-diagonal cells are the answer: there is no positive transfer.**

- **CSQA-trained skill on SocialIQA = 0.775 — identical to the weak init (0.775).** Three accepts' worth of CSQA heuristics ("identify the causal core", the lazy-watching-TV example) made *exactly zero* difference on SocialIQA. Not portable knowledge; CSQA-shaped patterns.
- **SocialIQA-trained skill on CSQA = 0.730 — slightly *below* the weak init (0.760).** The SocialIQA rubric ("temporal anchoring for future actions", "social causality") is mildly *counterproductive* on CSQA: it imposes a social-reasoning frame on questions that aren't social.

Each trained skill helps (a little) at most on its own dataset and never on the other. That's the cleanest possible confirmation of the headroom story: SkillOpt isn't writing general reasoning knowledge a 7B lacks — it's writing thin, dataset-specific scaffolding whose ceiling is the few items the base model was already on the fence about.

*(Splits are canonical: CSQA = the v3 `csqa_split_v2` test; SocialIQA = the seed-42 test. The CSQA-column weak/v3 numbers are from the v3 run; the rest from `scripts/eval_skill_on_dataset.py`, all temp=0, errors=0.)*

### Experiment 2 — Multi-seed gate (rigor check)

Re-run v3 with 3-seed val evaluation (vote across 3 deterministic shuffles). If the +4 pp val lift survives a different val ordering, the gate signal is real. If it doesn't, v3 was a lucky shuffle.

| Variant | Val acc | Notes |
|---|---|---|
| v3 (seed=42 only) | 0.900 | reported above |
| **v3 multi-seed mean** | _coming_ | sanity check |

### Experiment 3 — Fresh SkillOpt loop from weak init (Mode B) — ✅ done

This one landed: I trained a *new* skill from weak init on **SocialIQA** (chosen over ARC for a cleaner 3-option commonsense task), across 3 seeds with the larger-val overfit fix. Result is the **"A second dataset: SocialIQA"** section above — mean test Δ **+0.33 pp (± 0.29)**, flat. The "Why it didn't work here" section explains the headroom ceiling that caps both CSQA and SocialIQA on a 7B target.

### Experiment 4 — Bigger target (stretch)

Run the same v3-trained skill against Qwen2.5-14B (with offload) or Qwen2.5-32B (cloud). Does a smarter target benefit *more* from the skill, or has it already internalized these heuristics from pretraining?

| Target | Baseline | v3-skill |
|---|---|---|
| Qwen2.5-7B (this post) | 0.760 | 0.740 |
| **Qwen2.5-14B** | _coming_ | _coming_ |
| **Qwen2.5-32B** | _coming_ | _coming_ |

---

## The hypothesis I'll be checking against

If Experiment 1 transfers cleanly, then the v3 val/test gap on CSQA was binomial noise on n=200 test, and SkillOpt produced a genuinely portable artifact even at the smallest scale anyone is likely to try it at. That's the result that matters.

If Experiment 1 is null, then the loop works per-dataset but the skills don't yet generalize, and the next move is enlarging the val split or holding part of it out of the optimizer's reach. That's also publishable — and more honest than the usual prompt-tuning paper, which would never run the cross-dataset experiment in the first place.

Either way, watch this post for the update.

If you've tried SkillOpt or similar text-only optimizers on local models, I'd love to hear how the val/test gap behaved in your setup — particularly whether smaller val splits ate your transfer numbers the way they ate mine.

---

*Code: github.com/&lt;your-fork&gt;/SkillOpt · Reach out: vumichien1692@gmail.com*
