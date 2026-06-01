# Medium Technical Article Best Practices — SkillOpt Experiment Writeup

**For**: ML/AI engineers audience (TDS / Better Programming / The Gradient style)  
**Scope**: Hook, narrative structure, pacing, code embeds, null-result handling, SEO, anti-patterns  
**Date**: 2025-05-28

---

## 1. HOOK & OPENING

### What Works

**First two lines decide 80% of clicks.** Max two lines, ~200 characters. No hesitation.

**Proven hook patterns** (ranked by engagement):
1. **Personal story hook** (4x engagement): "3 years ago I almost quit..." → specific, emotional, grounded in failure or surprise.
2. **Bold claim** (2x engagement): "The [conventional practice] is killing your [outcome]." Inverse opinion.
3. **Specific number + claim**: "$0.01 optimized a 7B model faster than I expected" (your cost angle works here).
4. **Question hook** (1.8x engagement): "What if you could optimize a language model with $0.01?" Curiosity-driven.

### For Your SkillOpt Article

**Option A (Cost-surprising):**  
"I optimized a 7B-parameter local model for $0.01 using a cheap cloud API. Here's what surprised me."

**Option B (Methodology-contrarian):**  
"Prompt optimization doesn't require enterprise spend. I validated Microsoft's SkillOpt on Qwen2.5-7B with DeepSeek and CommonsenseQA—three runs, three learnings."

**Option C (Story-lead):**  
"After spending weeks on manual prompt engineering, I discovered a $0.01 optimizer outperformed my intuition. Here's how."

**Bad openings to avoid:**
- Slow academic intro ("In this paper, we explore...")
- Vague statement ("Prompt optimization is important...")
- Burying the hook in paragraph 3

---

## 2. TL;DR / SUMMARY PLACEMENT

### Placement Strategy

**Top position recommended** (after hook, before methodology).  
- Signals respect for reader time.
- Enables decision to dive deep or skim.
- ~2–4 sentences.

### Format

Use **key results table** (compact, scannable):

```
| Metric | Result |
|--------|--------|
| Cost (all 3 runs) | $0.01 |
| Best accuracy (CommonsenseQA) | X% (vs Y% baseline) |
| Model | Qwen2.5-7B local |
| Optimizer | DeepSeek cloud |
| Runs | 3 |
```

Or one-sentence summary:
"SkillOpt, powered by a $0.01 DeepSeek optimizer, achieved [X% accuracy] on CommonsenseQA—matching manual tuning at 1/100th the cost."

---

## 3. NARRATIVE ARC FOR TECHNICAL EXPERIMENTS

### Template Structure (background → reason → methodology → experiments → results → conclusion)

**A. Background (1 paragraph)**
- Prior state: "I'd been tweaking prompts manually for weeks."
- Pain point: "Took hours, inconsistent results."
- Industry context: "Prompt optimization is either manual labor or $$$."

**B. Reason / Motivation (1 paragraph)**
- What changed: "Microsoft published SkillOpt; I wondered if cheap cloud LLMs could power it."
- Hypothesis: "Text-as-weights optimization + low-cost API = practical alternative."

**C. Methodology (2–3 paragraphs)**
- Setup: "Qwen2.5-7B (local) + DeepSeek API (optimizer) + CommonsenseQA (benchmark)."
- Why these choices: "Qwen = reproducible local baseline; DeepSeek = cheap; CommonsenseQA = public benchmark, no cheating."
- Three runs described: parameters, seed variance, re-runs if needed.

**D. Experiments (2–4 sections, one per run or grouping)**
- Each section: run number, setup tweak, intermediate results, observation.
- Avoid dry tables; weave numbers into narrative: "Run 2 dropped accuracy 2% — I hypothesized [reason] and adjusted [parameter]."

**E. Results (1 detailed + 1 summary)**
- Detailed: "Accuracy plateaued at 71.2% on run 3; cost was $0.008 of the $0.01 budget."
- Summary table: final metrics vs baseline, cost breakdown.

**F. Conclusion (1–2 paragraphs)**
- What worked: "SkillOpt generalizes to local models + cheap cloud optimizers."
- What didn't: "We couldn't push beyond 71.2%; unclear if it's the model, optimizer, or prompt space."
- Takeaway: "For resource-constrained teams, this pattern is worth piloting."
- Next: "Open: does scaling to 13B or 70B improve further?"

### Transition Words (Minimize friction)

- "But here's the catch:" (before limitations)
- "Unexpectedly, run 2 showed..." (before surprises)
- "To verify, I re-ran with..." (before validation)

---

## 4. SECTION HEADERS — POWER PATTERNS

### What Gets Clicked Into

✅ **Question headers**: "Does SkillOpt work on local models?" "Can $0.01 beat manual tuning?" (2x click rate)  
✅ **Numbered insights**: "Lesson 1: Optimizer cost ≠ quality" (scannable, promise structure)  
✅ **Specific, not generic**: "Run 2: The accuracy plateau" beats "Results"  
✅ **Action headers**: "How I validated SkillOpt" beats "Methodology"

### Anti-Patterns (Skipped)

❌ "Introduction" / "Methodology" / "Results" (lab-report tone, reader skips)  
❌ "SkillOpt" (title is already there, redundant)  
❌ Vague: "Implementation" / "Analysis" / "Findings" (no promise)

### Example Header Sequence

```
- Hook (opening narrative)
- The Setup (why I cared + baseline)
- Run 1: Baseline Prompt [+result]
- Run 2: Optimizer Tweak [+surprise]
- Run 3: Fine-Tuned Parameters [+plateau]
- What I Got vs. What I Spent
- The Three Lessons
- Open Questions
```

---

## 5. PACING & LENGTH

### Ideal Range

**5–8 minutes** (1600–1900 words) for **technical deep dives** with experiments.  
- ~150 words/minute; Medium's 7-minute sweet spot tested on 64 top posts.
- Your case: 3 runs + cost breakdown + local-vs-cloud comparison justifies 7–8 min.

### Section Pacing (For 1800-word article)

| Section | Words | Notes |
|---------|-------|-------|
| Hook + TL;DR | 100 | Brief; snappy. |
| Background + Motivation | 250 | Set up the problem, not the solution. |
| Methodology | 300 | Model choice, API choice, benchmark. Cite once. |
| Run 1 narrative | 250 | Baseline; keep short. |
| Run 2 narrative | 250 | Surprise; the meat. |
| Run 3 narrative | 250 | Validation or plateau. |
| Results summary + table | 150 | Cost, accuracy, trade-offs. |
| Lessons + Conclusion | 200 | 3 takeaways; "what's next." |
| **Total** | **1700** | Target range. |

### Sub-Section Discipline

- Paragraphs: 2–4 sentences max (blogs, not academic papers).
- Bullet lists: 3–5 items (more = wall of text).
- Code blocks: see section 6.

---

## 6. CODE BLOCKS, TABLES, DIAGRAMS

### Code Block Best Practices

**Ideal length**: 15–25 lines.  
- Longer? Link to GitHub Gist or repo; show excerpt + comment.
- Syntax highlight: always specify language (```python, ```bash, etc.).

**Placement**:
- Immediately after explanation, not before.
- Caption: "Code 1: DeepSeek API call for optimizer."

**What to show**:
- Initialization / key call (not full boilerplate).
- One tricky line with inline comment? Yes.
- Full 60-line training loop? No—extract the optimizer call.

### Tables vs. Prose

**Use tables for**:
- Cost breakdown (API calls, tokens, time).
- Accuracy comparison across runs.
- Hyperparameter sweep summary.

**Use prose for**:
- Single-value insights ("The optimizer used 8,240 tokens per run").
- Narrative of why a parameter was chosen.

Example table:
```
| Run | Prompt Version | DeepSeek Cost | Accuracy | Time |
|-----|---|---|---|---|
| 1 | Baseline | $0.002 | 68.4% | 2m |
| 2 | Tweaked | $0.003 | 70.1% | 2.5m |
| 3 | Fine-tuned | $0.003 | 71.2% | 2.5m |
```

### Diagrams (ASCII, Mermaid, or image?)

**ASCII** (if it's a workflow):
```
Local Model (Qwen2.5-7B) 
         ↓ (prompt)
    DeepSeek Optimizer
         ↓ (refined prompt)
   Test on CommonsenseQA
         ↓
    Accuracy & Cost logged
```

**Mermaid** (if complex flow or decision tree):
- Good for "optimizer loop" with feedback.
- Medium supports Mermaid; renders well.

**Image** (screenshot of results):
- Only if it's output that prose can't capture (e.g., actual API response).
- Caption required; cite tool/model version.

**Don't use diagrams for**:
- Simple lists (use bullets).
- Single metric (use prose).

---

## 7. HONEST REPORTING — NULL RESULTS & PARTIAL FAILURES

### Building Trust When Results Are "Meh"

**Core principle**: Transparency builds credibility, not perfection.

**Frameworks**:

1. **Lead with the limitation**: "The experiment worked—but only to 71.2% accuracy, hitting a plateau I couldn't break."
2. **Explain the boundary**: "After 3 runs, diminishing returns suggested the prompt space, not the optimizer, was the constraint."
3. **Hypothesize openly**: "Three theories: (a) Qwen2.5-7B's base knowledge is weak on commonsense; (b) DeepSeek's optimization is conservative; (c) CommonsenseQA requires domain-specific knowledge I didn't encode."
4. **Don't claim victory if it's partial**: "SkillOpt works here—for cost, not accuracy. That's still useful."

### Null Result Patterns That Work

❌ **Avoid**: Burying failure in conclusion / reframing as success.  
✅ **Do**: State it clearly early and trace why.

Example rewrite (bad → good):
- Bad: "We achieved 71.2% accuracy on CommonsenseQA—a promising step forward."
- Good: "We achieved 71.2% accuracy—matching the manual baseline but not exceeding it. The optimizer excelled at cost, not score."

### Publication Bias Antidote

Readers trust writers who:
- Report null results (don't exist in most blogs).
- Admit what they don't know.
- List failure modes explicitly.
- Propose follow-up experiments to resolve ambiguity.

**Example closing**: "Next: test on larger models (13B, 70B) to isolate whether the plateau is model-size or optimizer-specific."

---

## 8. CLOSING & CTA

### Strong Closing Patterns

**Pattern 1: Open question** (drives comments)
"One surprise: DeepSeek's cost is so low, could you run 100 optimization attempts instead of one? Would that break the plateau?"

**Pattern 2: Actionable takeaway** (reader applies it)
"If you're optimizing a local model, try this: start with DeepSeek (it's cheap), run 3 variants, and measure cost-per-accuracy-point. If it's < $0.001/1%, scale up."

**Pattern 3: Honest boundary** (credibility signal)
"I'm uncertain whether the 71.2% plateau is Qwen's limitation, DeepSeek's conservatism, or CommonsenseQA's domain gap. If you run this and find something different, I'd love to hear it."

**Pattern 4: Next-step link** (engagement path)
"[GitHub repo](example.com) has the three runs logged. [Try it yourself](example.com) with your own model—takes 10 minutes."

### Sign-Off Phrasing

✅ "What's your experience with cheap optimizers? I'm curious if you've hit similar plateaus."  
✅ "Drop a comment if you reproduce this or find a way past the 71.2% wall."  
✅ "Questions, reproductions, or contrary results — [reach out here](contact)."

❌ "I hope this was helpful."  
❌ "Thanks for reading."  
❌ "Let me know in the comments." (too generic; no prompt)

### CTA Placement

- End of conclusion (last 1–2 sentences).
- Use **bold** or button-like styling (if Medium allows).
- Link to: GitHub, your Twitter, a follow-up question form.

---

## 9. SEO & DISCOVERABILITY

### Title Formula (clickable + searchable)

**Pattern**: `[Number/Adjective] + [Action/Topic] + [Specific outcome]`

✅ "$0.01 Optimized a 7B Model—Here's What Happened"  
✅ "Testing SkillOpt on Local Models: 3 Runs, 3 Lessons"  
✅ "Can Cheap LLM APIs Beat Manual Prompt Engineering?"  
✅ "I Validated Microsoft's SkillOpt for $0.01 — Here's the Data"

❌ "SkillOpt Experiment Report"  
❌ "Prompt Optimization Study"  
❌ "Testing Text-as-Weights Optimization"

### Subtitle (140 char limit; Medium often truncates ~80 char)

**Rule**: Reinforce title promise, hint at surprise or cost angle.

Example: "Using DeepSeek + Qwen2.5-7B + CommonsenseQA. Full results and cost breakdown."

### Keywords to Target

**Long-tail (lower competition, higher intent)**:
- "prompt optimization local model"
- "SkillOpt DeepSeek"
- "cheap LLM API experiments"
- "CommonsenseQA optimization"

**Broader (high volume)**:
- "prompt engineering"
- "LLM optimization"
- "local model fine-tuning"

**Use 2–3 long-tail in title + subtitle, 5–7 total in opening 200 words.**

### Meta Description (200 char for Medium)

"I ran 3 experiments optimizing Qwen2.5-7B using Microsoft's SkillOpt + DeepSeek API for $0.01 total. Cost breakdown, accuracy plateaus, and lessons learned."

### Tags

Pick 3–5:
- "Machine Learning"
- "LLM"
- "Prompt Engineering"
- "Experiment"
- "Cost Optimization" or "Budget-Friendly AI"

---

## 10. ANTI-PATTERNS — WHAT TO AVOID

| Anti-Pattern | Why It Fails | Fix |
|---|---|---|
| **Jargon dump without context** | Readers bounce if they don't understand "text-as-weights." | Define once: "SkillOpt treats prompts as weights, optimized via API calls." |
| **Walls of unbroken text** | TL;DR readers skip; perceived as dense/academic. | Break into 2–4 sentence paragraphs; use bullet lists for >3 items. |
| **Faux humility** ("I'm not an expert, but...") | Undermines authority; reader questions why they should trust you. | Lead with your credible setup (3 runs, cost, reproducibility), not apologies. |
| **Unfounded hype** ("This changes everything!") | When results are partial, hype erodes trust at close. | Claim modest wins: "Useful for cost-sensitive teams." |
| **Code-heavy sections** | >30-line blocks = readers skip; no value. | Extract snippet + comment; link full code to GitHub. |
| **Conclusion that doesn't conclude** | Readers feel unfinished; no clear takeaway. | End with 1 sentence summary + 1 open question. |
| **No source links** | Claims seem unverified. | Cite: SkillOpt paper, DeepSeek pricing, CommonsenseQA dataset. |
| **Burying caveats deep** | Readers believe headline; lose trust at reveal. | State limitations in results summary (section 3E). |
| **Generic headers** ("Results", "Methodology") | Scanners skip; no curiosity trigger. | Use specific, story-driven headers. |
| **Forgetting reader context** | Assume readers know why CommonsenseQA matters, what DeepSeek is. | One sentence context per new tool: "CommonsenseQA tests reasoning—not knowledge retrieval." |

---

## EXECUTIVE SUMMARY — STITCHED NARRATIVE

For your SkillOpt article, the flow should feel like:

1. **Hook** (10 sec): "$0.01 optimized a 7B local model. Here's what surprised me."
2. **TL;DR table** (20 sec): Cost, accuracy, model, runs.
3. **Background** (1 min): "I was tweaking prompts manually until I saw SkillOpt."
4. **Methodology** (1 min): "Qwen2.5-7B + DeepSeek API + CommonsenseQA, 3 runs."
5. **Three run narratives** (3 min): Run 1 baseline, Run 2 tweak, Run 3 plateau. Weave numbers into story.
6. **Honest results** (1 min): "71.2% accuracy—matches manual, costs $0.01. The plateau came fast."
7. **Three lessons** (1 min): Cost wins, diminishing returns, next questions.
8. **CTA** (10 sec): "Drop a comment if you've hit similar plateaus—curious what model size does."

**Total**: ~7 minutes, 1700 words. Scannable. Specific. Honest. Reproducible.

---

## UNRESOLVED QUESTIONS

1. **Image asset usage**: Should you include screenshots of API response / accuracy curve, or is prose sufficient? (Rule of thumb: if visual is output, include; if it's workflow, ASCII/Mermaid suffices.)
2. **Code depth**: Will readers want the full DeepSeek API wrapper code, or just the optimizer call? (Test by linking to GitHub and noting "full code here"; gauge comments for demand.)
3. **Audience specificity**: Are readers ML engineers (want reproducible code) or ML managers (want cost comparison)? Tailor intro. (Your TDS audience likely leans both—offer both angles.)

---

## SOURCES

- [Towards Data Science: Write for TDS](https://towardsdatascience.com/questions-96667b06af5/)
- [Towards Data Science: Submission Guidelines](https://towardsdatascience.com/submission-guidelines/)
- [How to Write Insightful Technical Articles | TDS](https://towardsdatascience.com/how-to-write-insightful-technical-articles/)
- [The Optimal Structure and Length for Medium Articles in 2025 | Florian Schroeder](https://medium.com/@florian-schroeder/the-optimal-structure-and-length-for-medium-articles-in-2025-0bd49fdddd7c)
- [Medium SEO Explained: Proven Ways to Rank Better in 2025 | Wordable](https://wordable.io/medium-seo/)
- [How to Change Your Title, Subtitle, and Description for SEO | The Writing Cooperative](https://writingcooperative.com/title-subtitle-and-description-bf6bf6b7b890/)
- [Simon Willison on Technical Blogging | Cynthia Dunlop](https://writethatblog.substack.com/p/simon-willison-on-technical-blogging)
- [Creating an Experiment Doc | Adam Fishman](https://www.fishmanafnewsletter.com/p/experiment-document-template)
- [How To Write A Technical Blog Post (Template) | Tech with Maddy](https://techwithmaddy.com/how-to-write-a-technical-blog-post-template)
- [Technical Writing Anti-Patterns | Digital.gov](https://digital.gov/guides/plain-language/principles/avoid-jargon/)
- [Publishing Negative Results | Enago Academy](https://www.enago.com/academy/top-10-journals-publish-negative-results/)
- [Is Your Blog Post Just a Dead-End? Why Calls To Action Are Necessary | Fuze32](https://blog.fuze32.com/blog/fuze32/blog/is-your-blog-post-just-a-dead-end-why-calls-to-action-are-necessary)
- [Markdown Code Block Best Practices | dasroot](https://dasroot.net/posts/2025/12/markdown-code-block-examples-and-best-practices/)
- [Guidelines for Writing Code Examples | MDN Web Docs](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Code_style_guide)
