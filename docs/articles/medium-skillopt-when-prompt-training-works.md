# I Trained a Markdown File Like a Neural Network on My Gaming GPU — Here's the Exact Line Where It Starts Working

> Microsoft's *SkillOpt* takes a prompt and trains it the way you'd train a neural network — epochs, batch size, learning rate, a validation gate that accepts or rejects each change. No model weights ever move; only the text of the prompt does. I ran that loop on a 7-billion-parameter model on a home gaming GPU, for pennies, across five different kinds of task. Four went flat. One produced a real, repeatable, held-out win. This post is about the single line that separates them — and how to tell, *before* you spend a GPU-hour, which side of that line your own task is on.

---

## Who this is for, and what you'll walk away with

**If you're not deeply technical:** think of a prompt as the *instruction note* you hand a new employee before they start a task — "here's how we do things here." Most teams write that note once, by hand, and never touch it again. The idea I'm testing is whether you can *improve the note automatically* by watching where the worker keeps messing up and editing the note accordingly — like a manager refining a one-page cheat-sheet after every shift. The surprising result: this works brilliantly for some kinds of work and is a complete waste of time for others, and the difference is sharp and predictable.

**If you're technical:** SkillOpt is a prompt/skill optimizer that frames a markdown system-prompt as the trainable parameter and wraps a supervised-learning loop around it — rollout → reflect → patch → validation gate. The paper reports +9 to +25 point lifts, but on *frontier* targets and optimizers. I wanted to know whether the loop survives a 10–100× downscale to a local quantized 7B target and a cheap cloud optimizer, and — more importantly — *which task families* it actually helps. The answer turned out to have nothing to do with model size and everything to do with the **shape of the failures**.

**What you'll be able to do after reading this:**

1. **Decide** — in one question — whether prompt-training is worth running on your task, before spending any compute.
2. **Run it yourself**, locally, for cents, on a gaming GPU (full commands in the appendix).
3. **Avoid the two traps** that made my own measurements lie to me — a noisy validation gate, and a token-starved reasoning model.

**The one-sentence answer, up front:** prompt-training pays off when your model's mistakes collapse into a *small set of repeated fixes that are the same on the questions you'll be graded on as on the ones you trained on*. When every mistake is its own special snowflake, it doesn't — no matter how procedural the task looks, and no matter how big or small the model is.

---

## TL;DR — five experiments, one win

Same loop. Same `qwen2.5:7b-instruct-q4_K_M` target on an RTX 3080. Same `deepseek-v4-pro` optimizer. Same hyperparameters throughout. The **only** thing I changed between experiments was the *task* (and, in the last experiment, the *model* — to prove the point isn't about the model).

| Experiment | Task family | Held-out test Δ (n=200) | Verdict |
|---|---|---|---|
| 1. Commonsense MC (CSQA / SocialIQA / LogiQA) | knowledge-bound | **−0.6 pp** (DeepSeek) / −1.2 pp (Sonnet) | flat |
| 2. MBPP — Python code-gen (public) | **heterogeneous** procedure | **−3.0 pp** (dev +9, overfit) | flat |
| 3. bizSQL — business Text-to-SQL (self-made) | **homogeneous** procedure | **+8.2 pp** mean over 3 seeds | **win** |
| 4a. MBPP on a *second model* (granite-code 8B) | heterogeneous procedure | **+0.0 pp** | flat (replicates) |
| 4b. bizSQL on a *second model* (granite-code 8B) | homogeneous procedure | **+42.5 pp** (single seed) | **win** (replicates) |

The headline I *expected* going in was "procedural tasks lift, knowledge tasks don't." **That's wrong.** MBPP is pure procedure — write a Python function, run it against unit tests — and it went flat with the same overfit signature as commonsense trivia. The real dividing line is narrower and more useful, and the rest of this post is the story of finding it.

Total cost of the winning experiment: **low-tens-of-cents of cloud spend per run** (the local rollouts are free), ~33 minutes of GPU time per seed.

---

## Part 1 — The technical idea: training a prompt like a weight

### What "SkillOpt" actually is

Modern LLM apps have two big levers: the **model weights** (expensive, frozen for most of us) and the **prompt** (cheap, editable, and treated like furniture). A senior engineer writes a few hundred words of system prompt, eyeballs a couple of examples, ships it, and rewrites it by hand when it breaks. There's no gradient, no validation set, no checkpoint.

Microsoft's SkillOpt ([arXiv 2605.23904](https://arxiv.org/abs/2605.23904)) asks: what if we treat that prompt — they call it a **skill** — as the thing being *trained*, and wrap a real deep-learning loop around it? The mapping isn't a metaphor; it's literally how the code is organized:

| Deep learning | SkillOpt |
|---|---|
| Model weights | A markdown skill document (the prompt) |
| Forward pass | **Rollout**: the target model runs the task with the skill in its system prompt |
| Loss | **Reflect**: the optimizer reads the *failed* rollouts and proposes text edits |
| Gradient step | Apply patches (add / delete / replace) to the skill |
| Learning rate | Max number of edits accepted per step |
| Validation gate | Re-score the candidate skill on a held-out split; keep it only if it *strictly* beats the current best |
| Epoch | One pass over the training set |

**In plain English:** there are two AIs. One — the **target** — is the small, local worker that actually does the task. The other — the **optimizer** — is a smarter cloud model that never does the task itself; it just reads where the worker failed and rewrites the worker's cheat-sheet. The worker's brain (its weights) never changes. The only thing that gets "smarter" is the one-page note it reads before each answer. The artifact you ship at the end is a single file, `best_skill.md`.

### The loop, one stage at a time

Each training step runs six stages. Here is the whole thing in plain terms, then in precise terms:

1. **Rollout** — *Plain:* the worker answers a batch of ~20 practice questions using the current cheat-sheet. *Precise:* the target generates completions for a minibatch at eval temperature 0 (greedy, so it's deterministic and repeatable).
2. **Reflect** — *Plain:* a smart reviewer looks at only the wrong answers and asks "what's the pattern here?" *Precise:* the optimizer is handed the failed rollouts, grouped by error signature, plus the current skill.
3. **Aggregate** — *Plain:* similar suggested edits get merged so the note doesn't bloat. *Precise:* candidate patches with similar intent are clustered.
4. **Select** — *Plain:* keep only the top few edits this round (this is the "learning rate"). *Precise:* top-k patches by support count, capped by the edit budget.
5. **Update** — *Plain:* actually edit the cheat-sheet. *Precise:* apply add/replace/append patches to produce a *candidate* skill.
6. **Gate** — *Plain:* the edited note only "ships" if it beats the old note on a fresh practice test. Otherwise it's thrown away. *Precise:* re-score the candidate on the full validation split; accept *only* on strict improvement over the incumbent.

That gate is the heart of the whole method. It's what stops the optimizer from "improving" the prompt into something that sounds better but scores worse. When it works, you get a clean optimization curve. When the task has no real headroom, the gate honestly refuses every edit and you ship the prompt you started with — which, as we'll see, is exactly what *should* happen.

### The setup (held constant — that's the experiment)

The entire scientific value rests on one discipline: **change only the task.** Every knob below is byte-for-byte identical across experiments 1–4.

```
┌───────────────────────────┐         ┌──────────────────────────────┐
│ Optimizer (cloud)         │ reflect │ Target (local)               │
│ deepseek-v4-pro           │◄────────│ qwen2.5:7b-instruct-q4_K_M    │
│ via /v1 OpenAI-compatible │         │ via Ollama, ~8.5 GB VRAM      │
│ writes the skill edits    │ patches │ RTX 3080, runs every rollout  │
└───────────────────────────┘────────►└──────────────────────────────┘
```

| Knob | Value |
|---|---|
| Target | `qwen2.5:7b-instruct-q4_K_M` (Ollama, RTX 3080), eval temp 0 (greedy) |
| Optimizer | `deepseek-v4-pro` (direct DeepSeek API) |
| Splits | 100 train / 100 val / 200 test, per seed |
| Schedule | batch 20, 2 epochs → 10 candidate edits, edit budget 4, cosine LR |
| Update | patch mode (add/replace/append), strict-improvement gate on val |
| Init | a deliberately *weak* one-line skill, so there's room to climb |
| Rigor | seed-42 pilot first; scale to seeds 43/44 only if the held-out Δ beats ±1 SE (~±3.5 pp at n=200) with ≥1 accepted edit |

### The pre-flight check that saves you a wasted run: the headroom probe

Before spending a single GPU-hour training, I run a cheap **headroom probe**: I measure whether the weak-init model fails in ways a *prompt* could plausibly fix, versus failing because it simply lacks the capability.

**In plain English:** there's no point coaching someone on better note-taking if the real problem is they never learned the subject. The probe answers "is this a coaching problem or a knowledge problem?" for the price of one evaluation pass instead of a full training run. The rule I committed to *before* running: if at least ~10–15 points of the baseline failures are "coaching-fixable" (procedural), proceed; otherwise, stop — the task is capability-floored and a markdown file can't move it.

---

## Part 2 — The experiments on local OSS

### Experiment 1 — Commonsense multiple-choice (the flat baseline)

**The task:** CommonsenseQA, SocialIQA, and LogiQA — multiple-choice questions about everyday and logical reasoning. Output one letter. Scoring is exact-match, fully deterministic.

This is where I started, and it ran flat across the board: three datasets, two target models, and two different optimizers. To make *why* concrete, here is one real training step in full detail — the single most useful thing to understand about how SkillOpt works and where it can break.

#### Deep dive: one real step (LogiQA on a small model)

**Stage A — the optimizer gets a report card.** After the worker answers a batch of 20 questions (13 wrong), the harness clusters the mistakes and hands the optimizer the current skill plus this diagnosis:

```json
{
  "n_total": 20, "n_fail": 13,
  "failure_patterns": [{
    "count": 13,
    "pattern": "insufficient_reasoning_about_options: the agent selects
                option A prematurely without fully comparing all options,
                leading to a wrong answer when the correct answer is not A."
  }]
}
```

**In plain English:** the feedback isn't the answer key. It's a *behavioral* diagnosis — "the worker keeps grabbing option A without reading the rest." That's a coachable-sounding flaw, so the optimizer tries to coach it.

**Stage B — the optimizer rewrites the cheat-sheet.** It turns that diagnosis into concrete instructions:

| BEFORE — weak init (157 B) | AFTER — the optimizer's rewrite |
|---|---|
| *"Pick the single best option. Output the letter in `<answer>` tags."* | adds: *"Read ALL options completely; don't stop at A. Beware first-option bias — check B, C, D. Re-read the question for negations ('not'), qualifiers ('best summarizes')."* |

This is a *good* rewrite. The flaw ("picks A too early") maps almost one-to-one onto the new instructions. The optimizer did its job.

**Stage C — the gate weighs it, and this is where it dies.** Every rewrite is re-scored on a fixed selection set and compared to the incumbent (which scored 0.4167). Across the run, **all 10 rewrites were rejected** — here are 6 of them:

| Step | Rewritten-skill score | vs. init (0.4167) | Gate |
|---|---|---|---|
| 1 | 0.3967 | −2.0 pp | ❌ reject |
| 2 | 0.3167 | −10.0 pp | ❌ reject |
| 4 | 0.4000 | −1.7 pp | ❌ reject |
| 6 | 0.2267 | −19.0 pp | ❌ reject |
| 9 | 0.2200 | −19.7 pp | ❌ reject |
| 10 | 0.2767 | −14.0 pp | ❌ reject |

**Not one rewrite beat the one-liner — every single one scored *lower*.** The more the skill grew, the harder it crashed. On a small model, each added paragraph of "good advice" didn't sharpen reasoning — it crowded the context and degraded it. The strict-improvement gate worked exactly as designed: it protected the original prompt from 10 consecutive regressions. Because nothing was accepted, the "trained" skill *is* the original skill, and the test numbers are identical (0.385 either way).

#### The optimizer model is not the lever

The obvious objection: maybe a *smarter* optimizer would have found the lift. So I filled in the entire **2 targets × 3 datasets** grid with `deepseek-v4-pro`, then re-ran the whole grid with a frontier optimizer, **Claude-Sonnet-4-6** — changing *only* the model that writes the prompt.

| Optimizer | Mean test Δ (2 targets × 3 datasets) | Verdict |
|---|---|---|
| DeepSeek-V4-Pro | **−0.6 pp** | flat |
| Claude-Sonnet-4-6 | **−1.2 pp** | flat (marginally worse, within noise) |

Every single one of the twelve deltas lands inside ±1 binomial SE (≈ ±3.5 pp on n=200). One detail nails the noise floor: the *baselines* — same weak prompt, same model, optimizer not even involved yet — drift by up to **3.5 pp** between runs. When the noise of doing *nothing* exceeds the effect of doing *something*, the effect is zero.

**Finding 1:** Commonsense MC is **knowledge-bound**. The model either knows that a lazy person watches TV because they're bored, or it doesn't — a prompt can reframe the question but can't inject a missing fact. No procedure to teach → nothing to train → flat, regardless of optimizer.

### Experiment 2 — MBPP Python code-gen (procedural… and still flat)

If "procedure vs. knowledge" were the right axis, code generation should win — there's obviously a *right way* to write a function. So I ran MBPP (Mostly Basic Python Problems): a one-sentence spec plus an example `assert`, scored by **pass@1 against hidden unit tests** in a sandbox. Fully deterministic, no LLM judge.

#### The probe said go

Baseline pass@1 on 100 training problems: **0.66**. Of the 34 failures, 33 were `AssertionError` (code ran, wrong output) — the model writes valid Python, it just gets the logic wrong. I hand-labeled all 34: roughly **16–20 points were procedural / coaching-fixable** (off-by-one edges, misreading a spec the example disambiguates, index-convention slips). **Probe verdict: PASS.** There was real headroom. And it *still* went flat. Here's why.

#### Deep dive: why the clusters never cohere

Watch the failure report the optimizer received at **step 2** — 20 problems, 6 failed:

```json
{
  "step": 2, "n_fail": 6,
  "failure_patterns": [{
    "count": 6,
    "pattern": "pass@1 fail (0/3 asserts)",
    "task_ids": ["mbpp-686","mbpp-936","mbpp-415","mbpp-561","mbpp-202","mbpp-323"]
  }]
}
```

**Six failures, six *completely different* problems**, and the only "pattern" the clusterer can find is "they failed." There's no shared root cause because there *isn't* one — `mbpp-686` and `mbpp-936` fail for unrelated reasons. So the best edit the optimizer can write is generic — *"study the example assert first; prefer idiomatic built-ins."* Re-scored on val: **0.60 → 0.59. Rejected.** Generic advice didn't help.

Step 3 *did* get accepted, and it's just as telling — 4 failures split into *two* patterns of two ("not verified against the example", "misinterpreted the statement"). The optimizer wrote "disambiguate with the example — the example is ground truth," val ticked **0.60 → 0.63**, accepted. A real edit — but it's *meta-advice* ("check your work"), because there's no convention shared across the problems to encode.

#### Results: the gate fires, the transfer doesn't

| MBPP seed 42 | Baseline | Trained | Δ |
|---|---|---|---|
| Selection / dev (val) | 0.58 | **0.67** | **+9 pp** |
| **Held-out test (n=200)** | 0.65 | 0.62 | **−3.0 pp** |
| Accepts | — | 3 of 10 | — |

There it is — the *exact same signature* as commonsense trivia. Dev climbs nine points; held-out test *falls* three. **Scale gate: FAIL** — a −3 pp pilot doesn't justify burning GPU on more seeds, so I stopped. One honest flat seed is the result.

**Finding 2:** MBPP is **heterogeneous procedure**. Every problem has a procedure, but a *different* one. The optimizer can only write generic advice that fits the 100 training items and evaporates on the 200 unseen ones. **"Procedure vs. knowledge" was the wrong axis.**

### Experiment 3 — Business Text-to-SQL (the win)

The question I actually care about isn't "can a 7B do trivia." It's: *I have a company database. Can I train a small, local, private model to answer plain-English questions about it correctly — without shipping my schema to a frontier API?* That's Text-to-SQL over a fixed schema, and it's the most common real-world business LLM task there is.

There's no public benchmark for *my* schema, so I built one — a fixed 6-table e-commerce/SaaS database (`customers`, `products`, `orders`, `order_items`, `subscriptions`, `support_tickets`), deterministically seeded so anyone re-running gets byte-identical rows. But building your own benchmark invites the obvious objection: *of course it worked, you made the answer key.*

#### The three guardrails that make a self-made win credible

1. **An objective execution verifier — no LLM judge.** A prediction is correct iff, when run against the real database, its result set *equals the gold query's result set* (read-only, order-insensitive, compared at cent precision). No model decides "close enough."
2. **Blind gold.** The answer-key SQL is written from the question and schema *alone* — never from seeing what the 7B outputs.
3. **A pre-registered headroom gate.** Before training, a strong model must solve the task at **≥90%** (proving the questions are answerable, not engineered-impossible), *and* the 7B's failures must be **≥10–15 pp procedural**. I committed to these thresholds before running.

#### The probe that lied to me twice (read this if you use a reasoning model anywhere)

My first probe said FAIL — the strong-model ceiling came back at 0.66, then 0.74, *below* the gate. I wrote the FAIL report. **It was wrong.** Two measurement bugs were masking the real signal:

1. **Float precision.** I compared result cells at 6 decimal places, but the gold SQL wraps aggregates in `ROUND(x, 2)`. Correct answers were scored *wrong* over trailing decimals the question never asked about — and that same bug was corrupting the training reward. Fix: compare at 2 dp.
2. **Token starvation.** I capped the strong model at 512 completion tokens. But `deepseek-v4-pro` is a *reasoning* model — it spends tokens thinking before it answers. At 512, the reasoning ate the whole budget and the SQL came back empty. I wasn't measuring "can it solve this"; I was measuring "how much fits in 512 tokens after reasoning." Fix: 4096 tokens.

With both fixed, the strong-model ceiling **jumped from 0.63 to 1.00.** The data was never ambiguous; my ruler was broken.

> **The lesson, once, for anyone using a reasoning model as a judge or optimizer:** a tight token cap doesn't make it terser — it makes it *empty*. Give a reasoning model ≥4096 completion tokens or your measurements will lie to you.

Final probe, all guardrails satisfied: local 7B weak-init **0.82**, strong-model ceiling **1.00**, procedural share **~18 pp**. And the 18 failures were *almost entirely one thing repeated*: 10× an unqualified column in a join, 3× MySQL's `MONTH()` (which SQLite lacks), 1× an invented column, 4× top-N/grouping discipline. **Zero genuine capability misses.**

#### Deep dive: one root cause, five failures

Here is **step 1** of the seed-42 run — 20 rollouts, 5 failed — and this is the whole story in one JSON block:

```json
{
  "step": 1, "action": "accept_new_best", "n_fail": 5,
  "failure_patterns": [{
    "count": 5,
    "pattern": "execution error: no such function MONTH: used MONTH() which
                does not exist in SQLite; should use STRFTIME or a date-range.",
    "task_ids": ["bizsql-train-0010","bizsql-train-0004","bizsql-train-0025",
                 "bizsql-train-0091","bizsql-train-0065"]
  }]
}
```

**Five failures. One root cause.** Five *different* questions — different regions, periods, categories — all failing for the *identical* reason: the model reached for MySQL's `MONTH()`. This is the polar opposite of MBPP's "6 unrelated failures." Here the fix is a single transferable convention, and the optimizer writes exactly that ("There is no `MONTH()` in SQLite; use `STRFTIME` or a date range"). Re-scored on val: **0.88 → 0.91. Accepted.**

And here's the crux: **a fix for "five training questions used `MONTH()`" is also a fix for every *test* question that would have used `MONTH()`.** The convention is identical for items the optimizer never saw. *That* is why this transfers and "check the example" doesn't.

#### Results: a real, three-seed, held-out win

Seed-42 cleared the scale gate decisively, so I ran seeds 43 and 44:

| Seed | Baseline test | Trained test | **Δ (n=200)** | dev climb |
|---|---|---|---|---|
| 42 | 0.880 | 0.985 | **+10.5 pp** | 0.88 → 0.98 |
| 43 | 0.890 | 0.965 | **+7.5 pp** | 0.86 → 1.00 |
| 44 | 0.870 | 0.935 | **+6.5 pp** | 0.88 → 0.95 |
| **mean** | **0.880** | **0.962** | **+8.2 pp (± 2.1)** | |

Every seed positive. The worst seed (+6.5) is still ~3× the per-seed binomial SE above zero. And the tell that separates a *real* win from MBPP's overfit: **each seed's dev climb tracks its test climb.** When dev and test move *together*, the skill generalized. When dev climbs and test falls (MBPP, commonsense MC), it overfit. I also verified all three learned skills contain **zero leaked gold answers** — just conventions.

**Finding 3:** bizSQL is **homogeneous procedure**. A handful of schema-and-dialect house rules (`BETWEEN` not `MONTH()`, qualify columns, exclude refunded orders) are the *same* for the test set as for the training set, so encoding them generalizes. A local model that now writes correct business SQL **96% of the time, up from 88%**, for under a dollar.

### Experiment 4 — Swap the model itself (is it just qwen?)

A fair objection to everything above: every number is on one weak 7B. Maybe "MBPP is flat" just means *qwen* can't be coached on Python, and a stronger model would lift. So I changed the one thing the whole thesis hangs on — **the target model** — and re-ran both tasks identically.

*(A detour worth one sentence: the model I planned to use, Gemma-3n `e4b`, turned out to be unusable — Ollama's renderer emits empty completions for it on most prompts. "Looks fine in the model card" and "works in your harness" are different claims; always smoke-test the exact path. The landing spot was IBM's dense `granite-code:8b-instruct-q4_K_M`: 6/6 clean on the smoke test, ~40 tokens/sec, zero empties.)*

granite starts from a *very* different place than qwen — MBPP baseline 0.44 vs 0.65, bizSQL 0.215 vs 0.88. If raw capability were the hidden variable, the verdicts should flip. They didn't:

| Task | qwen2.5 7B (base → Δ) | granite-code 8B (base → Δ) | Verdict |
|---|---|---|---|
| MBPP | 0.65 → **−3 pp** | 0.44 → **+0.0 pp** | flat on both |
| bizSQL | 0.88 → **+8.2 pp** (3-seed) | 0.215 → **+42.5 pp** (z≈9.5) | wins on both |

Same story, **21 points of base-capability apart** on MBPP. MBPP's optimizer *again* found a real convention (function-name/arity discipline) that moved the *dev* gate +5 pp — and *again* it died on held-out, because there's no shared procedure to carry. bizSQL *again* learned a handful of house rules every test query reuses, so it transferred — and the lift was **bigger at the lower base**: the conventions a strong model already knows are exactly the headroom a weaker one gains.

*(Honesty note: the granite run is a single seed, so I trust its **direction** far more than the precise +42.5; a 3-seed confirmation is the next step before quoting that magnitude as a point estimate.)*

**Finding 4:** The lever is the **task family, not the model** — now demonstrated on two very different models. A markdown file can't manufacture a shared fix-set where none exists, and finds it effortlessly where it does.

---

## Part 3 — The finding, and what to do with it

Put all the families side by side. Same loop, same optimizer, same GPU — only the task changed:

| Family | Example | The failures are… | Held-out Δ | Why |
|---|---|---|---|---|
| Knowledge-bound | CommonsenseQA, SocialIQA, LogiQA | each its own missing fact | −0.6 pp | no procedure to teach |
| **Heterogeneous** procedure | MBPP code-gen | each its own wrong algorithm | **−3.0 pp** | real procedure per problem, but **no shared fix** → generic advice that overfits |
| **Homogeneous** procedure | bizSQL Text-to-SQL | a handful of repeated convention slips | **+8.2 pp** | one small fix-set is **identical** for train and test → it transfers |

### The exact line — the one question to ask before you train

> **Do your model's failures across the dataset share a small set of fixes that are the *same* for the items you'll be tested on?**

- **Yes → SkillOpt wins.** The optimizer encodes the shared fixes; because they're shared, they generalize. (bizSQL: +8.2 pp, replicated +42.5 pp on a second model.)
- **No → SkillOpt overfits.** Whether the per-item failures are knowledge gaps (trivia) or distinct algorithms (MBPP), the best the optimizer can do is fit the training set's quirks. Dev climbs, test doesn't. (MBPP −3 pp, MC −0.6 pp.)

### The proposal: a practical checklist for your own task

**Run SkillOpt when your task has *house rules*** — domain conventions, a SQL dialect, a schema's quirks, a required output format, an internal API's call shape — that the base model keeps getting wrong in the *same* ways. Concretely, before you train:

1. **Run the headroom probe first.** One eval pass. If the model is capability-floored (it can't do the task even with hints), stop — a prompt won't save you.
2. **Eyeball ~20 failures by hand.** Do they cluster into 3–6 repeated root causes, or are they all different? If they cluster, you're in the winning regime.
3. **Use an objective verifier if you possibly can** (execution, exact-match, unit tests). An LLM judge adds noise exactly where you need signal.
4. **Give any reasoning model in the loop ≥4096 completion tokens.** This single bug cost me two false FAILs.
5. **Watch dev *and* test together.** If dev climbs while test stays flat, you're overfitting — stop and don't scale to more seeds.

**Skip it** when your failures are all different from each other (general code-gen, open-ended reasoning, trivia). Save the GPU time.

Good real-world fits for the winning regime: **business Text-to-SQL, internal API call formatting, report/template generation, structured log parsing, domain-specific document extraction** — anywhere a fixed set of conventions trips the model repeatedly.

---

## Conclusion — the honest verdict

**What's proven:**

1. ✅ SkillOpt produces a **real, three-seed, held-out win** (+8.2 pp, every seed positive) on a procedure-bound task with a cheap optimizer and a local 7B — and it **replicates on a second, very different model** (+42.5 pp on granite-code 8B).
2. ✅ The win is **credible**: objective execution verifier, blind gold, a pre-registered ≥90% headroom gate, and learned skills verified to contain zero leaked answers.
3. ✅ The mechanism is **legible**: failures cluster to a shared root cause → the optimizer encodes the convention → it transfers because it's the *same* convention on the test set.
4. ✅ It's **cheap**: low-tens-of-cents of API per run, free local rollouts, ~33 min on a gaming GPU.

**What isn't — and what surprised me:**

1. ❌ "Procedural ⇒ SkillOpt wins" is **false.** MBPP is procedural, had confirmed headroom, and went flat. Procedure is *necessary, not sufficient* — it has to be *homogeneous*.
2. ❌ The model — target *or* optimizer — is **not the lever.** Flat held across two targets, three datasets, two optimizers; the win held across two targets. Task structure decides the outcome.
3. ⚠️ My headroom probe **lied to me twice** before I caught two measurement bugs. The most useful operational habit here is to *distrust a surprising probe result and audit the ruler before the conclusion.*

**The one takeaway:** stop asking "is my task hard enough / is my model good enough." Ask "**do my failures repeat?**" If your model botches the same handful of conventions over and over, a trained markdown file will fix it for pennies. If every mistake is unique, no amount of prompt-training — or model-swapping — will help.

---

## References

- **SkillOpt paper** — Microsoft, *Optimizing Agent Skills Like Neural-Network Weights*, [arXiv 2605.23904](https://arxiv.org/abs/2605.23904).
- **SkillOpt code** — [github.com/microsoft/SkillOpt](https://github.com/microsoft/SkillOpt) (this experiment runs on a fork).
- **Target model** — `qwen2.5:7b-instruct-q4_K_M` via [Ollama](https://ollama.com); second target `granite-code:8b-instruct-q4_K_M` (IBM Granite).
- **Optimizers** — DeepSeek (`deepseek-v4-pro`, and the cheap `deepseek-chat` tier at $0.14/$0.28 per 1M tokens); Claude-Sonnet-4-6 for the optimizer head-to-head.
- **Public datasets** — CommonsenseQA (`tau/commonsense_qa`), SocialIQA (`allenai/social_i_qa`, CC-BY-4.0), LogiQA, MBPP (`google-research-datasets/mbpp`).
- **Hardware** — single NVIDIA RTX 3080 (10 GB), Windows 11.
- Contact: vumichien1692@gmail.com

---

## Appendix

### A. Reproduce it

On Windows + RTX 3080 + Ollama:

```powershell
ollama serve
ollama pull qwen2.5:7b-instruct-q4_K_M
# fill OPTIMIZER_OPENAI_API_KEY (DeepSeek) in .env.local-pilot

# --- Experiment 2: MBPP (public) ---
python scripts/prepare_mbpp_data.py --n-train 100 --n-val 100 --n-test 200 `
       --seed 42 --out-dir data/mbpp_split_s42
$env:SKILLOPT_CONFIG="configs/mbpp/local-pilot.yaml"
$env:SKILLOPT_OUT_ROOT="outputs/mbpp-train/deepseek-v4-pro/qwen7b-s42"
.\scripts\run_mbpp_pilot.ps1            # ~32 min

# --- Experiment 3: bizSQL (self-made) ---
python scripts/seed_bizsql_db.py                       # deterministic DB (random seed 7)
python scripts/author_bizsql_pairs.py                  # 420 blind, execution-validated pairs
python scripts/prepare_bizsql_data.py --seed 42 --out-dir data/bizsql_split_s42
$env:SKILLOPT_CONFIG="configs/bizsql/local-pilot.yaml"
$env:SKILLOPT_OUT_ROOT="outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42"
$env:SKILLOPT_SPLIT_DIR="data/bizsql_split_s42"; $env:SKILLOPT_SEED="42"
.\scripts\run_bizsql_pilot.ps1          # ~33 min; repeat with seeds 43, 44

# --- Experiment 4: swap the target model ---
ollama pull granite-code:8b-instruct-q4_K_M
# configs/{mbpp,bizsql}/local-pilot-granite-8b.yaml override ONLY model.target (+ workers:4)
```

Each run writes `best_skill.md` (the deliverable), `history.json`, `gpu.csv`, `summary.json`, and per-step `steps/step_XXXX/` traces (the reflection JSON and skill diffs quoted above).

### B. What the optimizer wrote

**bizSQL (the win)** — seed-42 `best_skill.md`, abridged. Every line is a transferable convention; nothing is a memorized answer:

```markdown
## Key Conventions (must be applied)
* Revenue filtering: exclude refunded and cancelled orders with
  status NOT IN ('refunded','cancelled').
* Active subscriptions: canceled_at IS NULL; sum mrr only for those.
* Active products: active = 1.
* Money columns: REAL; round monetary aggregates to 2 decimal places.

## Grouping by entity
Group by the primary key (c.id, p.id), not the name — avoids merging
distinct entities that share a name. The name can still be SELECTed.

## SQLite Date & Time Functions
There is no MONTH() or YEAR(). Use STRFTIME('%m', col) / STRFTIME('%Y', col),
or ISO date ranges with BETWEEN ('2025-10-01' AND '2025-12-31' for Q4).

## Column Disambiguation
When joining tables that share a column name (unit_price in products and
order_items), qualify with the table alias. Unqualified refs error.
```

**MBPP (the flat one)** — seed-42 `best_skill.md`, abridged. Reasonable, general, and — the whole problem — *not specific to any shared failure mode*:

```markdown
## Before You Submit
- Check the example. Mentally compute the expected output for the example
  input; if your function wouldn't produce it exactly, revise until it does.
- Disambiguate with the example. If the wording is ambiguous, the example
  is the ground truth.

## Index Management in Loops
When using a while loop with a manual index, increment exactly once per
iteration. Prefer for/enumerate.
```

**Commonsense MC (also flat)** — what `deepseek` wrote for CSQA reads like a perfectly sensible prompt-engineering guide ("identify the causal core", "beware keyword matching") — it just encodes patterns specific to the items it trained on, so it doesn't transfer.

### C. Full commonsense-MC grid (the flat baseline, in detail)

**DeepSeek-V4-Pro optimizer, seed 42:**

| Dataset | Target | Baseline | Trained | Δ |
|---|---|---|---|---|
| CSQA | Qwen2.5-7B | 0.760 | 0.775 | +1.5 pp |
| CSQA | gemma3:4b | 0.610 | 0.615 | +0.5 pp |
| SocialIQA | Qwen2.5-7B | 0.785 | 0.795 | +1.0 pp |
| SocialIQA | gemma3:4b | 0.725 | 0.705 | −2.0 pp |
| LogiQA | Qwen2.5-7B | 0.585 | 0.590 | +0.5 pp |
| LogiQA | gemma3:4b | 0.375 | 0.325 | −5.0 pp |

**Optimizer head-to-head (mean Δ over the 6 cells):** DeepSeek-V4-Pro **−0.6 pp** vs Claude-Sonnet-4-6 **−1.2 pp** — both flat, indistinguishable from each other and from zero. SocialIQA 3-seed fresh-train: mean test Δ **+0.33 pp (± 0.29)**, also flat (one seed's gate never fired because the weak-init baseline was already 0.84). Cross-dataset transfer (a skill trained on one dataset run on another): **no positive transfer** — each thin skill helps at most on its own dataset.

### D. Open questions

- **Lower-baseline replication for bizSQL.** qwen started at 0.88; granite at 0.215 gave +42.5 pp single-seed. A 3-seed confirmation on the low base is the honest next step before quoting that magnitude as a point estimate. (Direction is solid: z≈9.5.)
- **Does an MBPP *sub-family* lift?** MBPP-as-a-whole is heterogeneous, but a narrow slice (only string-manipulation, or only off-by-one loops) might be homogeneous enough to transfer. Untested.
- **Skill portability.** Does the bizSQL skill trained on this schema help on a *different* schema with the same dialect, or is it schema-specific?
- **A code-aware reflection prompt for MBPP.** The runs use generic analyst prompts; a code-specific one might rescue MBPP — or just confirm the heterogeneity ceiling.

---

*Code: github.com/&lt;your-fork&gt;/SkillOpt · Reach out: vumichien1692@gmail.com*
