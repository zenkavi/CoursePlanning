---
name: next-step
description: Reads PROGRESS.md and SPEC.md to tell you what step is next, which files it will touch, what acceptance criteria look like, and what to watch out for. Invoke with /next-step at the start of a work session or when you're deciding what to tackle.
---

# Next Step Planner

Tell the user what's next on the build list, concretely enough to start work. This is the orientation skill — it turns "I have an hour, what should I do" into "I'm going to open these three files and implement X."

## How to do it

### 1. Read PROGRESS.md

Identify the first step marked ⬜ (not ✅, not deferred). That's the next step. Note which step number it is and its stated scope.

### 2. Cross-reference with SPEC.md

Find the corresponding entry in the SPEC's "MVP Build Order" section and any related detail elsewhere in the SPEC (constraints, data model, etc.) that informs what "done" means for this step.

### 3. Produce a concrete plan

Format the output with these sections. Keep it tight — this is meant to be scannable, not a novel.

```
# Next: Step N — <Step Name>

## Scope
<1-3 sentences from PROGRESS.md and SPEC.md describing what this step delivers.>

## Files likely to change
- path/to/file.py — <what changes>
- path/to/template.html — <what changes>
(Only files that almost certainly need touching. If unsure, say "possibly" and explain.)

## Acceptance criteria
- <Concrete, checkable outcome 1>
- <Concrete, checkable outcome 2>
(These are what you'd check before marking the step ✅ in PROGRESS.md.)

## Watch out for
- <Gotcha drawn from SPEC, e.g. constraint tier, edge case, invariant>
- <Anything in the "Project-specific pitfalls" territory that this step could trip>

## First concrete action
<One sentence: what to do in the next 5 minutes to start.>
```

## Guidelines

- **Don't plan the whole step.** Sketch enough to start. The main thread does the real planning with full context.
- **Use code file paths from the actual project**, not the SPEC's idealized structure. The SPEC lists `solver.py`, `diagnostics.py`, etc. — but some of those may not exist yet. If the file doesn't exist, say "new file: path/to/thing.py".
- **Acceptance criteria should be falsifiable.** "The solver works" is not acceptance. "CP-SAT run on the current plan completes in <30s and fills non-locked solver-assigned slots respecting junior faculty 2.0 cap" is acceptance.
- **"Watch out for" should be specific to this step**, not general programming advice. Pull from the SPEC's constraint descriptions and the PROGRESS.md bug-fix notes.
- **If every step is done**, say so and point to the deferred items or note that the MVP is complete.
- **If PROGRESS.md and SPEC.md disagree** on what's next or what the step entails, flag it and stop. Don't guess which is right.

## Example output (for the current state, Step 6)

```
# Next: Step 6 — Constraint Validator

## Scope
Real-time warnings in the planner UI when an assignment would violate a soft or hard-with-flag constraint. No blocking of assignment — surface warnings, let the user decide. Junior > 2.0 hard cap is already blocked in the /assign route; Step 6 adds the visible warnings.

## Files likely to change
- app.py — extend /assign (or build_grid) to compute per-slot warnings
- load_calc.py — possibly add helper for "would this assignment create a violation"
- templates/planner.html — render warning badges/tooltips on cards
- new file: tests/test_constraints.py

## Acceptance criteria
- A slot where the assigned faculty is over the senior soft cap shows a visible yellow warning
- A junior faculty with > 1 new lab prep in the year shows a warning (but is not blocked)
- Warnings update on assign/unassign without a full reload being required (or are clearly visible on reload, per spec's "real time" flexibility)
- At least 3 unit tests: senior soft cap violation, junior new-prep count violation, clean assignment produces no warnings

## Watch out for
- Constraint tiers: hard (block) vs hard-with-flag (allow+warn) vs soft (objective, solver-only). Step 6 is about hard-with-flag warnings. Don't accidentally block.
- Junior "new lab prep" counts labs only — foundational courses with labs, upper_div_lecture_lab, upper_div_lab. Pure lectures don't count. See SPEC "Constraints" section.
- Cumulative teaching counts need to be right for "new prep" detection. Reuse load_calc's logic, don't re-implement.
- Placeholder courses: warnings should still apply to udl_lab_* assignments, but qualification warnings don't (anyone is "qualified" for placeholders).

## First concrete action
Add a `compute_warnings(faculty, semester, plan, courses, cfg) -> list[str]` helper in load_calc.py (or a new validators.py) and unit-test it before touching the template.
```

## Project-specific notes

- Build order is in SPEC's "MVP Build Order" section; status is in PROGRESS.md's "Up Next" and "Completed" sections. These should agree; if they don't, say so.
- Steps 12 and 13 are deferred — don't suggest them as "next" even if everything else is ⬜.
- Step 8 (OR-Tools solver) is the biggest single step and worth flagging as such when it comes up — it's not a one-afternoon task.