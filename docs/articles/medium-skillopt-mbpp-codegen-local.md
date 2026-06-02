# I Trained a Markdown File to Write SQL on a 7B Model — and Found the Exact Line Where Prompt-Optimization Starts Working

> In my last post, Microsoft's SkillOpt — a trainer that treats a prompt like a neural-network weight — ran flat on a local 7B across three commonsense datasets and two optimizers. The obvious next move was to try a *procedural* task, where a skill has something concrete to teach. So I ran two: a public code benchmark (MBPP) and a business Text-to-SQL benchmark I generated myself. One went flat. One produced a real, three-seed, held-out win. The gap between them is the whole point.

*Companion to ["I Spent 3 Cents Training a Markdown File on My Gaming GPU"](./medium-skillopt-local-oss-csqa.md) — read that first for the setup and the commonsense-MC baseline. This post reuses the exact same loop, optimizer, GPU, target model, and hyperparameters. The only thing that changes is the task.*

---

## TL;DR

Same loop. Same `qwen2.5:7b-instruct-q4_K_M` target on an RTX 3080. Same `deepseek-v4-pro` optimizer. Same hyperparameters that were flat on commonsense multiple-choice. I only changed the *task family*:

| Experiment | Family | Held-out test Δ (n=200) | Verdict |
|---|---|---|---|
| Commonsense MC (prior post) | knowledge-bound | **−0.6 pp** (DeepSeek) / −1.2 pp (Sonnet) | flat |
| **MBPP — Python code-gen** (public) | **heterogeneous** procedure | **−3.0 pp** (dev +9, overfit) | flat |
| **bizSQL — business Text-to-SQL** (self-made) | **homogeneous** procedure | **+8.2 pp** mean over 3 seeds (+10.5 / +7.5 / +6.5) | **win** |

The headline I went in expecting was "procedural tasks lift, knowledge tasks don't." **That's wrong.** MBPP is *pure procedure* — write a Python function, run it against unit tests — and it went flat, with the same dev-climbs/test-falls overfit signature as commonsense MC.

The real lever is narrower and more interesting: **SkillOpt wins when a task's failures collapse to a small set of *transferable* fixes — conventions that are the same for the held-out test items as for the training items.** Business SQL has that (qualify your columns, exclude refunded orders, `BETWEEN` not `MONTH()`). MBPP does not — every problem fails for its own reason, so the optimizer can only write generic "read the example carefully" advice that fits the 100 training items and evaporates on the 200 test items.

Total cost of the winning experiment: about **8 cents of optimizer spend per run** (the local rollouts are free), three runs, ~100 minutes of GPU time.

---

## The question this post answers

The prior post ended on a cliffhanger. SkillOpt's loop ran end-to-end on hobby hardware for pennies — the gate fired, the optimizer wrote real heuristics, val accuracy climbed. But the *held-out* test number never moved, across CommonsenseQA, SocialIQA, and LogiQA, two target models, and two optimizers (DeepSeek-V4-Pro and Claude-Sonnet-4-6). Mean delta: −0.6 to −1.2 points. Flat.

The diagnosis I landed on was **headroom**: commonsense MC is *knowledge-bound*. The 7B either knows that a lazy person watches TV because they're bored, or it doesn't. A markdown file can reframe the question, but it can't inject a fact that isn't in the weights. The paper's wins (+9 to +25 pp) all came from tasks with *procedural* scaffolding — how to call a search API, navigate an environment, parse a spreadsheet — exactly what a text skill *can* supply.

So the experiment that mattered next was obvious: **run SkillOpt on a procedure-bound task and see if the held-out win finally shows up.**

I ran two, for two different reasons:

- **MBPP** (Mostly Basic Python Problems) — a *public* benchmark, so the result is reproducible by anyone and immune to "you cooked the data" objections. Code-gen is procedural by definition: there's a right way to structure the output and common pitfalls a skill can warn against.
- **bizSQL** — a business Text-to-SQL task I built myself, because the question every practitioner actually has is *"does this work on MY data?"* Natural-language questions over a fixed company database is the single most common real-world LLM ask. If SkillOpt can train a skill that makes a local 7B reliably write correct SQL over your schema, that's a tool you'd actually use.

Building your own benchmark invites the obvious criticism — *of course it worked, you engineered it to.* Half of Experiment B is the guardrails that make a self-made win credible. We'll get there.

---

## The setup (identical to the flat runs — that's the experiment)

The entire scientific value here rests on one discipline: **change only the task.** Every hyperparameter is byte-for-byte the same as the commonsense-MC v3 run that went flat.

```
┌───────────────────────────┐         ┌──────────────────────────────┐
│ Optimizer (cloud)         │ reflect │ Target (local)               │
│ deepseek-v4-pro           │◄────────│ qwen2.5:7b-instruct-q4_K_M    │
│ via /v1 OpenAI-compatible │         │ via Ollama, ~8.5 GB VRAM      │
│ writes the skill edits    │ patches │ RTX 3080, runs every rollout  │
└───────────────────────────┘────────►└──────────────────────────────┘
```

| Knob | Value (same across MC / MBPP / bizSQL) |
|---|---|
| Target | `qwen2.5:7b-instruct-q4_K_M` (Ollama, RTX 3080), eval temp 0 (greedy) |
| Optimizer | `deepseek-v4-pro` (direct DeepSeek API) |
| Splits | 100 train / 100 val / 200 test, per seed |
| Schedule | batch 20, 2 epochs → 10 candidate edits, edit_budget 4, cosine LR |
| Update | patch mode (add/replace/append), strict-improvement gate on val |
| Init | a deliberately weak one-line skill, so there's room to climb |
| Rigor | seed-42 pilot first; scale to seeds 43/44 only if held-out Δ beats ±1 SE (~±3.5 pp at n=200) with ≥1 accepted edit |

A quick refresher on the loop (full version in the [companion post](./medium-skillopt-local-oss-csqa.md)): each step is **rollout → reflect → aggregate → select → update → gate.** The target runs the current skill on a batch; the optimizer reads the failures, clusters them, and proposes textual edits; the candidate skill is re-scored on the held-out val set and accepted *only if it strictly beats the incumbent*. The weights never move. The artifact you ship is `best_skill.md`.

Both new tasks get the same pre-flight check the MC runs skipped at their peril: a **headroom probe**. Before spending a single GPU-hour training, I measure whether the weak-init 7B actually fails in *skill-fixable* ways, or whether it's just hitting a capability wall a markdown file can't move. If there's no procedural headroom, the experiment is dead on arrival and you've learned that for the price of one eval pass instead of a full training run.

---

## Experiment A — MBPP (public Python code-gen)

### The task

MBPP is 974 short Python problems: a one-sentence spec plus three `assert` tests. The target sees the spec and one example assert (which pins the exact function name and signature), and must emit a complete function. Scoring is **pass@1 against all three hidden asserts**, run in a subprocess sandbox — fully deterministic, no LLM judge.

Weak init:

```markdown
# Python Coding Task
Write a Python function that solves the problem. Put it in a ```python code block.
```

### The headroom probe said go

Baseline pass@1 on 100 training problems: **0.66** (66/100, zero rollout errors). Of the 34 failures, 33 were `AssertionError` (the code ran but produced wrong output) and one was a `NameError`. No crashes, no timeouts — the model writes syntactically valid Python; it just gets the logic wrong.

I hand-labeled all 34 failures (the auto-bucketer can't read intent, so it floored at a useless 10%). The real split:

- **Procedural / skill-fixable (~16–20 pp):** off-by-one edge cases (passes 2 of 3 asserts), misread the spec where the example disambiguates it (`mbpp-415` returns `(8,7)` instead of `(7,8)`; `mbpp-470` treats "pairwise" as even/odd zip instead of consecutive), a 0-vs-1 index convention slip, an over-complicated solution to a one-line `map`.
- **Capability / genuine algorithm gaps:** a fence-painting DP recurrence, an unknown Carol-number formula, a missed odd-factors⇒perfect-square insight. A markdown file can't teach these to a 7B.
- **Bad tests (~2%):** MBPP gold that hardcodes `pi = 3.1415`, so a mathematically correct `2*math.pi*r` "fails."

**Verdict: PASS.** Roughly 16–20 points of procedural headroom, above the 10–15 pp gate. Caveat noted up front: baseline 0.66 caps total headroom at 34 points, and only about half is procedural — so movement should be *visible but bounded*. If the lift came back marginal, the baseline ceiling, not a capability floor, would be the reason. Hold that thought.

### Behind the scenes: one real step

This is where MBPP's character shows. Here's the failure report the optimizer received at **step 2** — 20 training problems, 6 failed:

```json
{
  "step": 2, "n_total": 20, "n_fail": 6,
  "failure_patterns": [{
    "count": 6,
    "pattern": "pass@1 fail (0/3 asserts)",
    "task_ids": ["mbpp-686","mbpp-936","mbpp-415","mbpp-561","mbpp-202","mbpp-323"]
  }]
}
```

Look at that cluster. Six failures, six *different problems*, and the only "pattern" the clusterer can find is "they failed." There's no shared root cause because there *isn't* one — `mbpp-686` and `mbpp-936` fail for completely unrelated reasons. So the best edit the optimizer can write is generic:

> *"## Coding Heuristics — Study the example assert first. It gives you the exact function name, the argument types, and the expected return type. Prefer idiomatic built-ins."*

Re-scored on val: **0.60 → 0.59. Rejected.** Generic advice didn't help.

Step 3 *did* get accepted, and it's just as telling. Four failures, this time split into *two* patterns of two:

```json
"failure_patterns": [
  {"count": 2, "pattern": "Not verified against provided example assert...",
   "task_ids": ["mbpp-470","mbpp-320"]},
  {"count": 2, "pattern": "Misinterpretation of problem statement (sum of powers
   vs single power, overlapping vs non-overlapping pairs)...",
   "task_ids": ["mbpp-617","mbpp-138"]}
]
```

Still heterogeneous. The optimizer wrote "Disambiguate with the example — the example is the ground truth," val ticked **0.60 → 0.63**, accepted. Real edit, real dev gain. But every edit it can write is *meta*-advice — "check your work," "read the example" — because there is no convention shared across the problems for it to encode.

### Results: the gate fires, the transfer doesn't

| MBPP seed 42 | Baseline | Trained | Δ |
|---|---|---|---|
| Selection / dev (val) | 0.58 | **0.67** | **+9 pp** |
| **Held-out test (n=200)** | 0.65 | **0.62** | **−3.0 pp** |
| Accepts | — | 3 of 10 | — |
| Wall time | — | 32 min | — |

There it is — the *exact same signature* as every commonsense-MC run. Dev climbs nine points; held-out test falls three. The skill the optimizer wrote (output contract, "mentally compute the example before submitting," while-loop index hygiene — [verbatim below](#what-the-mbpp-optimizer-wrote)) is *reasonable general advice*. It just doesn't move the needle on 200 unseen problems, because the 200 unseen problems don't share the failure modes of the 100 it trained on.

**Scale gate: FAIL.** A −3.0 pp pilot doesn't clear ±1 SE with a positive sign, so per my own pre-registered rule I did **not** spend GPU on seeds 43/44. One honest flat seed is the result.

This is the finding that broke my hypothesis. MBPP is procedural. The probe confirmed real procedural headroom. And it *still* went flat. "Procedure vs knowledge" was the wrong axis.

---

## Experiment B — Business Text-to-SQL (the one I built)

### Why build my own benchmark

The question I actually care about isn't "can a 7B do CommonsenseQA." It's: *I have a company database. Can I train a small local model to answer natural-language questions about it correctly, cheaply, privately, without sending my schema to a frontier API?* That's Text-to-SQL over a fixed schema — and it's the most common real LLM task in business that there is.

There's no public benchmark for *my* schema, so I generated one. Which immediately raises the objection that has to be answered before any number is believable:

> *You made the data AND the answer key. Of course your model "learned" it. You engineered the win.*

### The three guardrails that make a self-made win credible

I designed the whole pipeline around defeating that objection, not around getting a good number:

1. **An objective execution verifier — no LLM judge anywhere.** A prediction is correct iff, when executed against the seeded SQLite database, its result set *equals the gold query's result set*. Read-only, `SELECT`-only, order-insensitive (rows sorted before compare), numeric cells compared at cent precision. There is no model deciding "close enough." Either the rows match or they don't.

2. **Blind gold.** The gold SQL is written from the question and the schema *alone* — never from seeing what the 7B outputs. The answer key cannot be reverse-engineered to flatter the model.

3. **A pre-registered headroom gate.** Before training, a *strong* model (the same `deepseek-v4-pro`) must solve the task from the weak prompt at **≥90%** (proving the questions are actually answerable — not engineered-impossible), *and* the local 7B's failures must be **≥10–15 pp procedural** (skill-fixable, not capability). I committed to these thresholds before running. If the strong-model ceiling came in low, the verdict was "ambiguous data, FAIL" — fix the data, don't fudge the gate.

That third guardrail nearly killed the experiment, and the story of how is the most honest part of this post.

### How Claude Code generated the data

The schema is a fixed 6-table e-commerce/SaaS database — `customers`, `products`, `orders`, `order_items`, `subscriptions`, `support_tickets` — deterministically seeded (`random.Random(7)`) so anyone re-running gets byte-identical rows. The conventions a correct query must respect are documented *in the schema comments*, because they're the procedural headroom:

```sql
-- Dates are ISO TEXT 'YYYY-MM-DD' (lexicographic compare works for ranges).
-- orders.status is lowercase in {placed, shipped, delivered, refunded, cancelled}.
-- REVENUE excludes refunded AND cancelled orders
--     => WHERE status NOT IN ('refunded','cancelled').
-- products.active is 0/1; "active products" => active = 1.
-- An ACTIVE subscription has canceled_at IS NULL; MRR sums only those.
-- Money columns are REAL; round to 2 dp when the question asks for an amount.
-- Join keys: order_items.order_id->orders.id, order_items.product_id->products.id, ...
```

The pair generator (`scripts/author_bizsql_pairs.py`) follows a strict authoring discipline designed to keep the task *unambiguous but not trivial*:

- **Every question states its output shape** ("Return a single number", "Return rows of (name, revenue)").
- **Named formulas are spelled out** — when a question wants line-item revenue, it says *"measured as the sum of line-item value (quantity × unit price)"*, so there's exactly one correct reading.
- **Tie-breaks are stated** for top-N questions.
- **But the domain conventions stay implicit** — the question never says "exclude refunded orders" or "active = 1" or "use BETWEEN not MONTH()". Those are the things a skill has to *learn*. That's the headroom, by construction.

Two real (question, gold) pairs:

```text
Q: What is the average monthly recurring revenue of active enterprise subscriptions?
   Return a single number.
SQL: SELECT ROUND(AVG(mrr),2) FROM subscriptions
     WHERE plan='enterprise' AND canceled_at IS NULL;

Q: What was the total revenue from Hardware products sold to NA customers in Q4 2025,
   measured as the sum of line-item value (quantity x unit price) and excluding
   refunded and cancelled orders? Return a single number.
SQL: SELECT ROUND(SUM(oi.qty*oi.unit_price),2)
     FROM order_items oi
     JOIN orders o     ON oi.order_id=o.id
     JOIN products p   ON oi.product_id=p.id
     JOIN customers c  ON o.customer_id=c.id
     WHERE p.category='Hardware' AND c.region='NA'
       AND o.ordered_at BETWEEN '2025-10-01' AND '2025-12-31'
       AND o.status NOT IN ('refunded','cancelled');
```

The generator then **executes every gold query**, drops any that error, return empty, or scan a whole table (a degenerate-question filter), and dedups by normalized SQL *and* result signature. That produced **420 distinct, execution-validated pairs** (241 hard / 133 medium / 46 easy), carved into 100/100/200 splits weighted toward multi-table hard.

### The probe that almost failed — and the two bugs hiding under it

First probe: strong-model ceiling (Arm B) came back **0.66**, then **0.74** after a tweak — *below* the gate, and barely above the local 7B's own 0.82. By my pre-registered rule that's a FAIL: "the data is too ambiguous, even a strong model can't solve it." I wrote the FAIL report.

It was wrong. Two defects were masking the real signal:

1. **Evaluator float precision.** I compared result cells at 6 decimal places, but the gold SQL pervasively wraps aggregates in `ROUND(x, 2)`. A correct *unrounded* `SUM` was being scored wrong for trailing decimals the question never asked about — cosmetic false negatives that *also corrupt the training reward*. Fix: compare at **2 dp** (cent precision).

2. **Token starvation on the strong model.** The probe capped the strong model's output at `max_completion_tokens=512`. But `deepseek-v4-pro` is a *reasoning* model — it burns completion budget on hidden reasoning before emitting content. At 512 tokens, the reasoning ate the whole budget and the SQL came back truncated or empty. I wasn't measuring "can a strong model solve this"; I was measuring "how much SQL fits in 512 tokens after reasoning." Fix: **4096 tokens**.

With both fixed, **Arm B jumped from 0.63 to 1.00.** The data was never ambiguous; my measurement was broken. (Independently, I also discarded 701 genuinely free-form LLM-generated pairs from an earlier pool that *were* ambiguous, and rebuilt the 420 authored-only set above. Belt and suspenders.)

> **The lesson, stated once for anyone using a reasoning model as a judge or optimizer:** a tight `max_completion_tokens` doesn't make it terser, it makes it *empty*. Give a reasoning model ≥4096 completion tokens or your measurements lie to you. This same 512→4096 bug had already bitten me once on the data generator. Twice now.

Final probe, all guardrails satisfied:

| Arm | Score | Gate |
|---|---|---|
| **A** — local 7B, weak init | 0.82 (82/100) | baseline |
| **B** — strong-model ceiling | **1.00** (100/100) | ≥90% → clears |
| Procedural share of the 18-pt gap (hand-labeled, all 18) | **~18 pp** | ≥10–15 → clears |

And the 18 failures are *almost entirely one thing repeated*: 10× unqualified `unit_price` in a join (which often drops the `orders` join entirely, losing the date/status filter), 3× MySQL `MONTH()` in SQLite, 1× an invented `active` column on subscriptions, 4× top-N/group-by/date-window discipline. **Zero genuine capability misses.** A strong model applies these conventions unprompted; the q4 7B doesn't — yet.

### Behind the scenes: one real step (and why it's different from MBPP)

Here is **step 1** of the seed-42 run. Twenty training rollouts, 5 failed — and watch the cluster:

```json
{
  "step": 1, "action": "accept_new_best", "n_total": 20, "n_fail": 5,
  "failure_patterns": [{
    "count": 5,
    "pattern": "execution error: no such function MONTH: Agent used MONTH()
                which does not exist in SQLite; should use STRFTIME or date-range.",
    "task_ids": ["bizsql-train-0010","bizsql-train-0004","bizsql-train-0025",
                 "bizsql-train-0091","bizsql-train-0065"]
  }]
}
```

**Five failures. One root cause.** Five *different questions* — about different regions, periods, categories — all failing for the identical reason: the model reached for MySQL's `MONTH()`, which SQLite doesn't have. This is the polar opposite of MBPP's "6 unrelated failures." Here the fix is a single transferable convention, and the optimizer writes exactly that. Its three edits for this step:

```json
{ "op": "append", "source_type": "failure", "support_count": 5,
  "content": "## SQLite Date & Time Functions\n- There is no MONTH() or YEAR().
    Use STRFTIME('%m', column) ... or date-range comparisons.\n- For quarters use
    a range: ordered_at >= '2025-01-01' AND ordered_at < '2025-04-01'." }

{ "op": "append", "source_type": "failure", "support_count": 5,
  "content": "## Column Disambiguation\n- When joining tables that share a column
    name (e.g. unit_price in products and order_items), qualify with the alias." }

{ "op": "replace", "source_type": "success", "support_count": 8,
  "content": "...## Key Conventions (must be applied)\n* Revenue filtering: exclude
    refunded and cancelled orders with status NOT IN ('refunded','cancelled').\n
    * Active subscriptions: canceled_at IS NULL...\n* Active products: active = 1..." }

```

Re-scored on val: **0.88 → 0.91. Accepted.** And critically — a fix for "five training questions used `MONTH()`" is *also* a fix for every test question that would have used `MONTH()`. The convention is the same for items the optimizer never saw. **That is why this one transfers and MBPP's "check the example" doesn't.**

By the end of the run the skill is a tidy SQL style guide — output contract, the revenue/active/ROUND conventions, GROUP BY the primary key not the name, line-item-vs-`total_amount`, ISO date ranges, column qualification. **I verified all three seeds' learned skills contain zero leaked gold values** — no hardcoded answers, no specific question's result baked in. Just conventions. ([Verbatim excerpt below](#what-the-bizsql-optimizer-wrote).)

### Results: a real, three-seed, held-out win

Seed-42 cleared the scale gate decisively (+10.5 ≫ +3.5 pp), so I ran seeds 43 and 44:

| Seed | Baseline test | Trained test | **Δ (n=200)** | dev climb | Accepts |
|---|---|---|---|---|---|
| 42 | 0.880 | 0.985 | **+10.5 pp** | 0.88 → 0.98 (+10) | 4 / 10 |
| 43 | 0.890 | 0.965 | **+7.5 pp** | 0.86 → 1.00 (+14) | 2 / 10 |
| 44 | 0.870 | 0.935 | **+6.5 pp** | 0.88 → 0.95 (+7) | 2 / 10 |
| **mean** | **0.880** | **0.962** | **+8.2 pp (± 2.1)** | | |

Every seed positive. Worst seed (+6.5) is still ~3× the per-seed binomial SE (~2.1 pp at n=200) above zero. And the tell that separates a *real* win from MBPP's overfit: **each seed's dev climb tracks its test climb** (+10/+10.5, +14/+7.5, +7/+6.5). When dev and test move together, the skill generalized. When dev climbs and test falls — MBPP, commonsense MC — it overfit. Three independent runs from three different training shuffles converged on the *same small convention set*. That's the signature of a homogeneous-procedural task.

Cost, per run: ~345k–384k optimizer prompt tokens + ~87k–125k completion tokens. The 1,500 local Qwen rollouts per run are **free**. At DeepSeek's cheapest published rate ($0.14/$0.28 per 1M) that's **~8 cents**; the v4-pro tier I actually used is pricier, so call it low-tens-of-cents per run. Three seeds, ~100 minutes of RTX 3080 time, well under a dollar of API spend, and a local model that now writes correct business SQL **96% of the time, up from 88%.**

---

## The cross-family conclusion — where the line actually is

Put all three families side by side. Same loop, same optimizer, same GPU, same 7B, same hyperparameters — only the task changed:

| Family | Example | Failures are… | Held-out Δ | Why |
|---|---|---|---|---|
| Knowledge-bound | CommonsenseQA, SocialIQA, LogiQA | each its own missing fact | −0.6 pp | no procedure to teach; the answer is latent or it isn't |
| **Heterogeneous** procedure | MBPP code-gen | each its own wrong algorithm | **−3.0 pp** | a real procedure per problem, but **no shared fix** → optimizer writes generic meta-advice that fits the 100 train items and dies on the 200 test items |
| **Homogeneous** procedure | bizSQL Text-to-SQL | a handful of repeated convention slips | **+8.2 pp** | one small fix set (`BETWEEN` not `MONTH()`, qualify columns, exclude refunds) is **identical** for train and test → it transfers |

I started this thinking the axis was **procedure vs. knowledge.** MBPP — procedural, headroom-confirmed, and flat — proved that wrong. The axis is:

> **Do the failures across the dataset share a small set of fixes that are the same for the items you'll be tested on?**

- **Yes → SkillOpt wins.** The optimizer encodes the shared fixes into the skill, and because they're shared, they generalize. (bizSQL: +8.2 pp.)
- **No → SkillOpt overfits.** Whether the per-item failures are knowledge gaps (commonsense MC) or distinct algorithms (MBPP), the best the optimizer can do is fit the training set's idiosyncrasies. Dev climbs, test doesn't. (MBPP: −3 pp. MC: −0.6 pp.)

This also re-confirms, from the other direction, the prior post's finding that **the optimizer model is not the lever.** A frontier optimizer can't manufacture a shared fix set where none exists (MBPP, MC). A cheap one finds it effortlessly where it does exist (bizSQL). The task's structure decides the outcome; the optimizer just reads it.

The practical upshot for anyone with a local model and their own data: **SkillOpt is worth running exactly when your task has house rules** — domain conventions, a dialect, a schema's quirks, an output format — that the base model keeps getting wrong in the *same* ways. Business SQL, internal API call formats, report templating, log parsing: these are homogeneous-procedure tasks, and this is the regime where a trained markdown file earns its keep. If your failures are all different from each other, save the GPU time.

---

## Reproduce it

Full pipeline in [the repo](https://github.com/microsoft/SkillOpt). On Windows + RTX 3080 + Ollama:

```powershell
ollama serve
ollama pull qwen2.5:7b-instruct-q4_K_M
# fill OPTIMIZER_OPENAI_API_KEY (DeepSeek) in .env.local-pilot

# --- Experiment A: MBPP ---
python scripts/prepare_mbpp_data.py --n-train 100 --n-val 100 --n-test 200 `
       --seed 42 --out-dir data/mbpp_split_s42
$env:SKILLOPT_CONFIG="configs/mbpp/local-pilot.yaml"
$env:SKILLOPT_OUT_ROOT="outputs/mbpp-train/deepseek-v4-pro/qwen7b-s42"
.\scripts\run_mbpp_pilot.ps1            # ~32 min

# --- Experiment B: bizSQL ---
python scripts/seed_bizsql_db.py                       # deterministic DB (random seed 7)
python scripts/author_bizsql_pairs.py                  # 420 blind, execution-validated pairs
python scripts/prepare_bizsql_data.py --seed 42 --out-dir data/bizsql_split_s42
$env:SKILLOPT_CONFIG="configs/bizsql/local-pilot.yaml"
$env:SKILLOPT_OUT_ROOT="outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42"
$env:SKILLOPT_SPLIT_DIR="data/bizsql_split_s42"; $env:SKILLOPT_SEED="42"
.\scripts\run_bizsql_pilot.ps1          # ~33 min; repeat with seeds 43, 44
```

Each run writes `best_skill.md` (the deliverable), `history.json`, `gpu.csv`, `summary.json`, and per-step `steps/step_XXXX/` traces (the reflection JSON and skill diffs quoted above).

---

## The honest verdict

**What's proven:**
1. ✅ SkillOpt produces a **real, three-seed, held-out win** (+8.2 pp, every seed positive) on a procedure-bound task, with a cheap optimizer and a local 7B — the first non-flat result in this whole series.
2. ✅ The win is **credible**: objective execution verifier, blind gold, pre-registered ≥90% headroom gate, and learned skills verified to contain zero leaked answers.
3. ✅ The mechanism is **legible**: failures cluster to a shared root cause → the optimizer encodes the convention → it transfers because it's the same convention on the test set.
4. ✅ It's **cheap**: low-tens-of-cents of API per run, free local rollouts, ~33 min on a gaming GPU.

**What isn't, and what surprised me:**
1. ❌ "Procedural ⇒ SkillOpt wins" is **false.** MBPP is procedural, had confirmed headroom, and went flat (−3 pp, classic overfit). Procedure is necessary, not sufficient.
2. ⚠️ The bizSQL baseline was **already high (0.88)** — the clarifying-question authoring that made the data unambiguous also helped the 7B, capping absolute lift at ~18 points. The +8.2 pp is real and it generalizes, but it's a *bounded* win, not a +25 pp paper headline. I'd love to see this regime with a lower starting baseline.
3. ⚠️ My headroom probe **lied to me twice** before I caught two measurement bugs (6-dp rounding; 512-token reasoning starvation). The single most useful operational lesson here is to *distrust a surprising probe result* and audit the measurement before the conclusion.

## Open questions

- **Lower-baseline replication.** bizSQL started at 0.88. Does the win grow on a harder schema / harder question mix where the 7B starts at 0.50–0.60 — more like the paper's regime? (Expectation: bigger absolute lift, same mechanism.)
- **Does an MBPP *sub-family* lift?** MBPP-as-a-whole is heterogeneous, but a narrow slice (e.g., only string-manipulation problems, or only off-by-one-prone loops) might be homogeneous enough to transfer. Untested.
- **Skill portability.** Does the bizSQL skill trained on this schema help on a *different* schema with the same dialect (SQLite conventions), or is it schema-specific the way the commonsense skills were dataset-specific?
- **A code-specific reflection prompt for MBPP.** The current run uses generic analyst prompts. A code-aware reflection prompt is the documented fallback I deliberately did *not* run, to keep MBPP a clean control. Would it rescue MBPP, or just confirm the heterogeneity ceiling?

---

## Appendices

### What the bizSQL optimizer wrote

Seed-42 `best_skill.md`, abridged (full verbatim at `outputs/bizsql-train/deepseek-v4-pro/qwen7b-s42/best_skill.md`). Every line is a transferable convention; nothing is a memorized answer:

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

### What the MBPP optimizer wrote

Seed-42 `best_skill.md`, abridged. Reasonable, general, and — the whole problem — *not specific to any shared failure mode*:

```markdown
## Before You Submit
- Check the example. Mentally compute the expected output for the example
  input; if your function wouldn't produce it exactly, revise until it does.
- Disambiguate with the example. If the wording is ambiguous ("pairwise
  addition", "sum of powers"), the example is the ground truth.

## Index Management in Loops
When using a while loop with a manual index, increment exactly once per
iteration. Prefer for/enumerate; for consuming multiple items use iter()/next().
```

---

*Code: github.com/&lt;your-fork&gt;/SkillOpt · Companion post: ["I Spent 3 Cents Training a Markdown File on My Gaming GPU"](./medium-skillopt-local-oss-csqa.md) · Reach out: vumichien1692@gmail.com*
