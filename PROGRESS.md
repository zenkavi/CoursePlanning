# CMC Course Planner — Build Progress

## Status: Step 3 of 11 complete (grid layout polished)

---

## Completed

### Step 1 — Data Loading `5d682fc`
**Files:** `models.py`, `data_loader.py`, `config.py`, `data/courses.yaml`, `data/teaching_history.csv`, `data/config.yaml`

- `Faculty`, `Course`, `Assignment`, `Plan` dataclasses with JSON serialization
- `load_faculty()` parses `faculty.csv`: handles 3 sci10 flavor columns, maps CSV column `"sci11 organic"` → course code `sci111`, builds generic `can_teach["sci10"]` from flavor union
- `load_courses()` parses `courses.yaml` → `Course` objects
- `load_config()` reads `config.yaml` with hardcoded fallback defaults
- 11 faculty/course loading tests passing

### Step 2 — Load Calculator `5d682fc`
**Files:** `load_calc.py`, `tests/test_load_calc.py`

- `section_weight(course, faculty, times_taught_before, cfg)` — new-prep bonus (2.0 for first N times, then 1.67), upper-div fixed at 2.0/1.0
- `semester_load(faculty, assignments, courses, cumulative_counts, cfg)` — applies `extra_section_weight_multiplier` (0.5× default) for 2nd+ sections of same course in same semester
- `all_faculty_loads(faculty_list, assignments, courses, cfg)` — iterates semesters in chronological order, carrying cumulative counts forward so weight transitions happen correctly mid-plan
- `new_preps_in_semester()` — identifies new prep courses for a faculty in a given semester
- Load status colours: green (at target), yellow-under, yellow-over, red
- 34 load calculator tests passing — **45 total**

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

---

## Up Next

### Step 4 — Manual Assignment UI
Click a section card → dropdown of qualified faculty → POST `/assign` → card updates.
- Placeholder (upper-div) cards should also be assignable
- Faculty in dropdown greyed if unqualified or over cap
- Requires Alpine.js dropdown component and `/assign` + `/unassign` Flask routes

### Step 5 — Live Load Display
Per-faculty, per-semester load badges update as assignments change.
- Colour-coded badges on faculty sidebar (green/yellow/red)
- Load shown on assigned section cards
- Annual load shown in faculty sidebar

### Step 6 — Constraint Validator
Real-time warnings surfaced in the UI without blocking assignment.
- Junior faculty over 2.0 hard cap → block or warn
- Junior faculty > 1 new lab prep per year → warn
- Senior faculty over soft cap → yellow warning

### Step 7 — Diagnostics Panel v1
- Coverage % per semester
- Unfilled sections table
- Faculty load table
- Bottleneck courses (worst supply/demand ratio)
- Junior new-prep counts per year

### Step 8 — OR-Tools Solver
"Suggest assignments" button runs CP-SAT on non-locked, non-manual slots.
- `solver.py` with CP-SAT model
- Objective: coverage (1000) > junior new-preps (100) > load balance (50) > ...
- Load weights scaled by ×100 for integer arithmetic

### Step 9 — Lock/Unlock
- Lock individual assignments (solver won't touch them on re-run)
- "Lock all" / "Unlock all" buttons
- Locked cards show 🔒 icon

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
─────────────────────────────────────
Total                        45 tests  all passing
```

Run with: `python -m pytest tests/ -v`
