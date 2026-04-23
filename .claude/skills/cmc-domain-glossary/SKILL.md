---
name: cmc-domain-glossary
description: Domain vocabulary and invariants for the CMC Integrated Science Course Planner. Load this when working on anything involving faculty assignments, course loads, sci10 flavors, upper-div placeholders, new-prep logic, the solver, or when a term in the codebase (junior/senior, foundational, UDL, sci111 vs sci11) is ambiguous. Especially important before editing load_calc.py, solver.py, data_loader.py, models.py, or the planner templates.
---

# CMC Course Planner — Domain Glossary & Invariants

This codebase plans faculty teaching assignments at Claremont McKenna College's Integrated Science program across a 3-year, 6-semester horizon. The vocabulary below is load-bearing: most bugs in this project come from misunderstanding one of these terms, not from coding errors.

## Core entities

**Faculty** — A professor. Has a `rank` of `"junior"` or `"senior"` (this controls load caps), an `area` (e.g. chemistry, biology), and a `can_teach: {course_code: bool}` qualification map. Junior faculty have a **hard** load cap of 2.0 per semester; senior faculty have a **soft** cap of 2.0 (violations penalized but allowed).

**Course** — A class with a `code` (e.g. `sci10`, `sci111`), a `category`, and a per-semester section count. Categories:
- `foundational` — intro courses (sci10, sci30a/b, sci31a/b, sci40, sci50). Weight depends on prior teaching count.
- `upper_div_lecture_lab` — sci111, sci112, and the `udl_lab_*` placeholders. Weight always 2.0.
- `upper_div_lecture` — the `udl_lec_*` placeholders. Weight 1.0.
- `upper_div_lab` — Weight 1.0. (Currently no non-placeholder courses in this category.)

**Assignment** — A (faculty, course, year, semester, section_number) tuple. Flags: `locked` (solver won't touch), `manual` (user-placed, distinguishing from solver output), and `flavor` (sci10 only).

**Plan** — The full list of assignments. Persisted to `data/plan.json` at runtime. Gitignored.

## Terms that trip people up

**"New prep"** — A course a faculty member has taught fewer than `new_prep_bonus_count` times (default 2). New preps get a weight bonus (2.0 instead of 1.67 for foundational). This is about *prep burden*, not novelty — a faculty teaching sci10 for the third time is no longer "new prep" even if it's been years.

**"Times taught before"** — A running count. It starts from `teaching_history.csv` (prior counts before the plan begins) and **accumulates across semesters within the plan**. A faculty who taught sci10 once in Fall Y1 has `times_taught_before = prior_count + 1` in Spring Y1. This is why `all_faculty_loads()` must iterate semesters chronologically.

**"Extra section"** — The 2nd, 3rd, ... section of the *same course* in the *same semester* taught by the *same faculty*. These get multiplied by `extra_section_weight_multiplier` (default 0.5) to reflect shared prep. Does NOT apply across semesters or across different courses.

**"Placeholder course"** — `udl_lab_1`, `udl_lab_2`, `udl_lec_1`, `udl_lec_2`. These represent upper-div slots we know exist but haven't named yet. The solver **skips** them (they must be manually assigned). They have no entries in `faculty.csv`, so faculty qualification checks must be **bypassed** for placeholders — everyone is eligible. If you see "no faculty qualified" for a `udl_*` slot, this check is the bug.

**"sci10 flavor"** — sci10 is taught in three flavors: health, neuro, earth. The CSV has separate columns for each (`sci10 health`, `sci10 neuro`, `sci10 earth`). The faculty's generic `can_teach["sci10"]` is the **union** — true if they can teach any flavor. The solver treats sci10 as 8 generic sections per semester; flavor is resolved at assignment time based on the faculty's qualified flavors.

**"Junior new lab prep"** — Junior faculty are limited to 1 *new* lab prep per academic year (soft constraint, warned not blocked). "Lab" here means foundational courses with labs + `upper_div_lecture_lab` + `upper_div_lab`. It does NOT include pure lectures.

**"Target annual load"** — 4.0 weighted units per year (default). This is what "at target" (green) means in the load display. Yellow-under / yellow-over is near target; red is significantly over cap.

## Course code gotchas

- **`sci11` ≠ `sci111`.** The CSV column is `sci11 organic`, but the internal code is `sci111`. Mapping happens in `data_loader.py`. If you see `sci11` anywhere in Python code, it's a bug.
- **`sci30a` is chem, `sci30b` is phys, `sci31a` is chem2, `sci31b` is bio.** The CSV column names encode the subject (`sci30a chem1`, etc.) but the internal codes drop it. See `SPEC.md` → CSV Column Mapping.
- **26 sections per semester** = 22 solver-assigned + 4 manual placeholders. If section counts don't sum to 26, something's wrong.

## Load calculation invariants

1. **Chronological iteration.** `all_faculty_loads()` must iterate (year, semester) in order so `times_taught_before` accumulates correctly.
2. **Integer scaling for solver.** OR-Tools CP-SAT requires integer weights. All float weights (2.0, 1.67, 0.5 multiplier) are scaled ×100 in solver code. Keep this convention; don't mix scaled and unscaled weights.
3. **Extra-section multiplier is per (course, semester, faculty).** Not per course, not per semester. The full triple.
4. **Weight is a property of (course, faculty, times_taught_before).** Not of the course alone. Two faculty teaching the same section in the same semester can have different weights.

## Constraint vocabulary

- **Hard** — inviolable. Qualification match, junior ≤ 2.0 cap, locked assignments.
- **Hard-with-flag** — solver avoids but allows with penalty. Senior > 2.0, junior > 1 new lab prep/year.
- **Soft** — objective-function terms. Coverage, junior new-prep minimization, load balance, flavor diversity, senior-takes-new-preps preference.

When adding a new constraint, decide which tier it belongs in before writing code — the enforcement mechanism differs.

## When in doubt

- The authoritative source for course structure and constraints is `SPEC.md`.
- The authoritative source for what's implemented is `PROGRESS.md`.
- If the two disagree, `SPEC.md` is intent and `PROGRESS.md` is reality — flag the drift, don't silently pick one.