# CMC Course Planner — Build Progress

## Status: Step 9 of 11 complete (Lock/Unlock)

---

## Completed

### Step 1 — Data Loading `5d682fc`
**Files:** `models.py`, `data_loader.py`, `config.py`, `data/courses.yaml`, `data/teaching_history.csv`, `data/config.yaml`

- `Faculty`, `Course`, `Assignment`, `Plan` dataclasses with JSON serialization
- `load_faculty()` parses `faculty.csv`: handles 3 sci10 flavor columns, maps CSV column `"sci11 organic"` → course code `sci111`, builds generic `can_teach["sci10"]` from flavor union
- `load_courses()` parses `courses.yaml` → `Course` objects
- `load_config()` reads `config.yaml` with hardcoded fallback defaults
- 21 faculty/course loading tests passing

### Step 2 — Load Calculator `5d682fc`
**Files:** `load_calc.py`, `tests/test_load_calc.py`

- `section_weight(course, faculty, times_taught_before, cfg)` — new-prep bonus (2.0 for first N times, then 1.67), upper-div fixed at 2.0/1.0
- `semester_load(faculty, assignments, courses, cumulative_counts, cfg)` — applies `extra_section_weight_multiplier` (0.5× default) for 2nd+ sections of same course in same semester
- `all_faculty_loads(faculty_list, assignments, courses, cfg)` — iterates semesters in chronological order, carrying cumulative counts forward so weight transitions happen correctly mid-plan
- `new_preps_in_semester()` — identifies new prep courses for a faculty in a given semester
- Load status colours: green (at target), yellow-under, yellow-over, red
- 24 load calculator tests passing — **45 total**

### Step 3 — Static Grid Rendering `fbac0da` + `685a451`
**Files:** `app.py`, `templates/base.html`, `templates/planner.html`, `templates/diagnostics.html`, `templates/faculty_detail.html`

- Flask app with routes: `GET /`, `GET /diagnostics`, `GET /faculty/<name>`
- `build_grid()` produces semester → course-group → slot structure for the template
- 6-column horizontally-scrollable grid, each column 26 sections
- Section cards use a thin left-border accent in the category colour; group headers (course name + category badge) always rendered so every course has a visible separator regardless of section count — this fixed a layout bug where single-section courses (e.g. sci30a in fall) had no visual break
- Filled/total counter in each column header
- Faculty sidebar with rank badge (J/S) and area
- Stub pages for diagnostics and faculty detail
- All routes return 200; plan stored in `data/plan.json` (auto-created)

### Step 4 — Manual Assignment UI
**Files:** `app.py`, `templates/planner.html`

- `POST /assign`: parses slot_id, validates faculty qualification, rejects locked assignments; sets `sci10` flavor from first matching faculty qualification
- `POST /unassign`: removes non-locked assignments; returns 403 for locked slots
- `index()` now passes `loads_by_sem` (string-keyed `"year__season" → {name → {total, status}}`) for dropdown load display
- Each slot card wrapped in `x-data="slotDropdown()"` Alpine component; dropdown uses `position:fixed` to escape `overflow-y:auto` clipping
- Dropdown groups: available qualified faculty (clickable with colour-coded load), junior-at-hard-cap (greyed/disabled), unqualified (greyed/disabled)
- Locked cards render as static display with 🔒 badge (no dropdown)
- `sci10` flavor auto-assigned to first qualified flavor on assignment
- **Bug fix:** placeholder courses (`udl_lab_*`, `udl_lec_*`) had no CSV qualification columns, so all faculty appeared unqualified; fixed by bypassing `can_teach` check for `is_placeholder` courses in both `/assign` and the dropdown template

### Step 5 — Live Load Display
**Files:** `app.py`, `templates/planner.html`

- `index()` computes `annual_loads`: `{faculty_name: {year: {total, status}}}` — annual totals per year with colour status (green near target 4.0, yellow-under/over, red over cap+1.0); junior/senior cap-aware
- Faculty sidebar rows expanded to 2 lines: name/rank/area on top, three annual load badges (Y1/Y2/Y3) below, colour-coded; tooltip shows exact value
- Assigned section cards (both locked and interactive) show the faculty's total semester load as a small coloured badge (`green`/`amber`/`red`) next to their name — updates on every page load after each assignment

### Step 6 — Constraint Validator
**Files:** `app.py`, `templates/planner.html`

- `compute_violations()` checks three rules per faculty: (1) junior semester load > `junior_faculty_hard_cap`, (2) senior semester load > `senior_faculty_soft_cap`, (3) junior faculty with > 1 brand-new lab-category course (`upper_div_lecture_lab` / `upper_div_lab`) in the same academic year
- Returns `{faculty_name: {items, has_error, has_warning, count}}`; used by `index()` and passed to template
- Sidebar faculty rows show a coloured count badge (red for hard-cap errors, amber for warnings) with a `title` tooltip listing all violation descriptions

### Step 7 — Diagnostics Panel v1
**Files:** `app.py`, `templates/diagnostics.html`

- `build_diagnostics()` in `app.py` computes all panel data and passes it to the template; no separate `diagnostics.py` (diagnostics logic is small enough to live in `app.py`)
- **Coverage** — 6 cards (one per semester), showing filled/26 with a colour-coded progress bar
- **Unfilled sections** — table of every empty slot with semester, course, and section number; placeholder slots marked
- **Course supply/demand** — non-placeholder courses sorted by sections-over-3-years ÷ qualified-faculty-count; ratio ≥ 2.0 red, ≥ 1.5 amber, lower green
- **Faculty loads** — all 20 faculty (juniors first), fall/spring/annual columns per year, same status colours as sidebar
- **Junior new-prep counts** — per-year count of brand-new courses (zero prior history, matching `compute_violations` logic); red with `!` badge if > 1 in a year
- Suggestions feature deferred to post-MVP

### Step 8 — OR-Tools Solver
**Files:** `solver.py`, `app.py`, `templates/planner.html`, `tests/test_solver.py`

- `solver.py` with CP-SAT model: `solve(faculty_list, courses, plan, cfg, year_range)` returns list of `Assignment` objects
- Hard constraints: at-most-one faculty per slot; junior semester load hard cap (full weights, no `extra_section_weight_multiplier` — conservative but safe)
- Objective (descending weight): coverage (+1000/slot) > junior new-preps (−100) > load balance (−50/unit over per-sem target) > senior over soft cap (−75/unit) > sci10 flavor diversity (+10/flavor/sem) > senior takes new lab preps (+25)
- Load weights scaled ×100 for CP-SAT integer arithmetic; 25-second time limit
- `POST /solve` route: runs solver, replaces prior solver assignments, preserves locked + manual
- `POST /clear_solver` route: drops all non-locked, non-manual assignments
- "Suggest assignments" and "Clear solver" buttons wired up (show "Solving…" during run)
- 8 solver tests passing — **53 total**

### Step 9 — Lock/Unlock
**Files:** `app.py`, `templates/planner.html`

- `POST /lock` and `POST /unlock` routes: accept `slot_id`, set `locked=True/False` on matching assignment, return `{ok: true}`
- `POST /lock_all`: sets `locked=True` on all assignments; redirects to index
- `POST /unlock_all`: sets `locked=False` on all assignments; solver protection for manual assignments comes from `manual=True`, not `locked`
- `doLock`, `doUnlock`, `doLockAll`, `doUnlockAll` JS functions wired up
- Locked cards: 🔒 badge is a clickable button that calls `doUnlock`; card remains static (no dropdown)
- Assigned non-locked cards: dropdown gains "🔒 Lock assignment" option above "Unassign"
- "Lock all" / "Unlock all" buttons added to top bar

### sci10 Flavor-Specific Teaching History
**Files:** `data/teaching_history.csv`, `data_loader.py`, `load_calc.py`, `solver.py`, `app.py`, `templates/planner.html`

- `teaching_history.csv` now tracks sci10 by flavor: `sci10h`, `sci10n`, `sci10e` columns (instead of a single `sci10` column)
- `data_loader.py`: `_HISTORY_COL_MAP` maps `sci10h/n/e` → `sci10_health/neuro/earth`; `prior_teaching_counts` now stores flavor-specific keys aligned with `can_teach` naming; other course codes pass through unchanged
- `load_calc.py`: `count_key(assignment)` exported helper returns `sci10_{flavor}` for sci10 (when flavor is set) or `assignment.course_code` otherwise; used in `semester_load`, `all_faculty_loads`, `new_preps_in_semester`, and `build_diagnostics` so new-prep bonuses are flavor-accurate
- `solver.py`: `_build_pre_counts` aggregates `sci10_health + sci10_neuro + sci10_earth` into a single total for solver pre-counts (solver assigns flavor post-hoc); locked/manual plan assignments update the flavor-specific key via `count_key`
- `app.py`: `POST /set_flavor` route validates faculty qualification for the requested flavor, then updates `assignment.flavor`; `build_diagnostics` junior new-prep counts updated to use `count_key`
- `templates/planner.html`: H/N/E flavor badge on all assigned sci10 cards; flavor selection dropdown (filtered to flavors the assigned faculty qualifies for, with checkmark on current); `doSetFlavor()` JS helper

---

## Up Next

### Step 10 — Config Panel
Sidebar with tunable parameters from `config.yaml`; "Re-solve" triggers a new solver run with updated weights.

### Step 11 — CSV Export
Export current plan + gap report to CSV/Excel via `openpyxl`.

---

## Deferred (Post-MVP)

- **Step 12:** Sabbatical / faculty unavailability UI (mark semesters as unavailable)
- **Step 13:** Edit faculty qualifications in-app (currently CSV-only)

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| State persistence | `data/plan.json` | Simple, no DB dependency for MVP |
| Load weight fractions | Scaled ×100 for CP-SAT | OR-Tools CP-SAT requires integers |
| Extra-section multiplier | 0.5 (configurable) | 2nd section of same course shares prep |
| sci10 in solver | 8 generic slots | Flavor tracked on assignment, not as separate course codes |
| `sci11` → `sci111` | Mapped in `data_loader.py` | CSV has typo vs. spec course code |
| `faculty.csv` gitignored | Yes | Treat as potentially sensitive faculty data |
| `plan.json` gitignored | Yes | Runtime state, not source |

---

## Test Coverage

```
tests/test_data_loader.py   21 tests  ✅
tests/test_load_calc.py     24 tests  ✅
tests/test_solver.py         8 tests  ✅
─────────────────────────────────────
Total                        53 tests  all passing
```

Run with: `python -m pytest tests/ -v`
