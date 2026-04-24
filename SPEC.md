# CMC Integrated Science Course Planner — Specification

## Goal

A what-if planning tool for faculty course assignments across a 3-year (6-semester) horizon. The tool helps the department:
- Produce the best-achievable assignment given known constraints
- **Surface gaps** (unfilled sections, overloaded faculty, bottleneck courses) to inform hiring and curricular decisions
- Explore tradeoffs by adjusting constraints and weighting rules

This is a diagnostic/exploratory tool as much as an optimization tool. Unfilled sections are expected and informative, not errors.

---

## Stack

- **Backend:** Python 3.12, Flask, pandas, Google OR-Tools (CP-SAT)
- **Frontend:** Jinja2 templates, Alpine.js, Tailwind via CDN
- **Data:** CSV + YAML config files (no database for MVP)
- **Environment:** pyenv virtualenv `cmc-planner` (Python 3.12.5)

---

## Project Structure

```
CoursePlanning/
├── app.py                   # Flask entry point, routes, diagnostics logic
├── solver.py                # OR-Tools CP-SAT model
├── models.py                # Faculty, Course, Assignment, Plan dataclasses
├── load_calc.py             # Weighted load calculation with new-prep logic
├── config.py                # Load tunable parameters from config.yaml
├── data_loader.py           # CSV/YAML → dataclasses
├── data/
│   ├── faculty.csv          # Qualification matrix (gitignored — contains PII)
│   ├── courses.yaml         # Course definitions
│   ├── teaching_history.csv # Prior teaching counts per faculty/course
│   ├── config.yaml          # Tunable parameters (weights, caps, etc.)
│   └── plan.json            # Current plan state (gitignored, created at runtime)
├── templates/
│   ├── base.html
│   ├── planner.html         # Main 6-semester grid
│   ├── diagnostics.html     # Gap report
│   └── faculty_detail.html
├── static/
│   └── app.js               # Alpine.js interactions (currently inline in html)
├── tests/
│   ├── test_data_loader.py
│   └── test_load_calc.py
├── SPEC.md
├── PROGRESS.md
└── README.md
```

---

## Data Model

### Faculty
- `name`, `area`, `research_method`, `rank` ("junior" | "senior")
- `can_teach`: `{course_code: bool}` — includes `sci10`, `sci10_health`, `sci10_neuro`, `sci10_earth`
- `prior_teaching_counts`: `{course_code: int}` from `teaching_history.csv` — sci10 history is stored per-flavor (`sci10_health`, `sci10_neuro`, `sci10_earth`); no generic `sci10` key
- `unavailable_semesters`: list of `(year, semester)` tuples (deferred; empty for MVP)

### Course
- `code`, `display_name`
- `category`: `"foundational"` | `"upper_div_lab"` | `"upper_div_lecture"` | `"upper_div_lecture_lab"`
- `is_placeholder`: bool — True for unnamed upper-div slots (solver skips these)
- `sections_per_semester`: `{"fall": int, "spring": int}`
- `flavors`: list — non-empty only for `sci10` (`["health", "neuro", "earth"]`)

### Assignment
- `faculty_name`, `course_code`, `year`, `semester`, `section_number`
- `locked`: bool — if True, solver preserves this assignment
- `manual`: bool — True for user-placed, distinguishes from solver output
- `flavor`: optional string — which sci10 flavor is being taught

### Plan
- `assignments`: list of Assignment
- `year_range`: (start_year, end_year) — default (1, 3)

---

## Courses

**Foundational (weight: 2.0 first 2 times taught, then 1.67):**

| Code   | Display   | Fall sections | Spring sections |
|--------|-----------|---------------|-----------------|
| sci10  | SCI 10    | 8             | 8               |
| sci30a | SCI 30A   | 1             | 3               |
| sci30b | SCI 30B   | 1             | 3               |
| sci31a | SCI 31A   | 3             | 1               |
| sci31b | SCI 31B   | 3             | 1               |
| sci40  | SCI 40    | 2             | 2               |
| sci50  | SCI 50    | 2             | 2               |

**Upper-div lecture + lab (weight: 2.0 always):**

| Code   | Display | Fall | Spring |
|--------|---------|------|--------|
| sci111 | SCI 111 | 1    | 1      |
| sci112 | SCI 112 | 1    | 1      |

**Placeholder upper-div (manually assigned only — solver skips):**

| Code      | Category              | Fall | Spring | Weight |
|-----------|-----------------------|------|--------|--------|
| udl_lab_1 | upper_div_lecture_lab | 1    | 1      | 2.0    |
| udl_lab_2 | upper_div_lecture_lab | 1    | 1      | 2.0    |
| udl_lec_1 | upper_div_lecture     | 1    | 1      | 1.0    |
| udl_lec_2 | upper_div_lecture     | 1    | 1      | 1.0    |

**Total per semester: 22 solver-assigned + 4 manually-assigned = 26 sections.**

### sci10 Flavor Handling
Faculty qualifications differ by flavor (health / neuro / earth). The CSV encodes who can teach which flavor. The solver treats sci10 as 8 generic sections per semester, but:
- Each assignment picks a specific flavor based on faculty qualification
- Soft preference: ≥1 section of each flavor per semester

### CSV Column Mapping
The faculty CSV uses slightly different column names than the internal course codes:

| CSV column      | Internal code |
|-----------------|---------------|
| sci10 health    | sci10_health  |
| sci10 neuro     | sci10_neuro   |
| sci10 earth     | sci10_earth   |
| sci30a chem1    | sci30a        |
| sci30b phys1    | sci30b        |
| sci31a chem2    | sci31a        |
| sci31b bio1     | sci31b        |
| sci40 phys2     | sci40         |
| sci50           | sci50         |
| sci11 organic   | sci111        |
| sci112 biochem  | sci112        |

---

## Constraints

### Hard (inviolable)
- Faculty only assigned to courses where `can_teach[course] == True`
- **Junior faculty:** weighted load ≤ 2.0 per semester, no exceptions
- Locked assignments (including all manual upper-div assignments) are preserved

### Hard-with-flag (solver avoids, warns if violated)
- Senior faculty weighted load > 2.0 per semester → allowed but counted as an objective penalty
- Junior faculty: > 1 new lab prep per academic year

### Soft (objective function, weighted)
- Maximize section coverage (highest weight)
- Minimize total new preps for junior faculty (high weight)
- Balance weighted load across faculty (medium weight)
- sci10 flavor diversity per semester (low weight)
- Prefer senior faculty for first-time lab preps (low weight)
- Minimize senior faculty going over 2.0 (medium weight)

---

## Load Calculation

```python
def section_weight(course, faculty, times_taught_before, cfg):
    bonus_count = cfg["new_prep_bonus_count"]   # default: 2
    if course.category == "foundational":
        return 2.0 if times_taught_before < bonus_count else 1.67
    elif course.category == "upper_div_lecture_lab":
        return 2.0   # always
    elif course.category == "upper_div_lecture":
        return 1.0
    elif course.category == "upper_div_lab":
        return 1.0
```

**Same-course-multiple-sections rule** (configurable via `extra_section_weight_multiplier`):
- `1.0` → each section counts independently at full weight
- `0.5` → 2nd+ sections of the same course in the same semester count at half weight
- Default: `0.5` (reflects shared prep burden)

Cumulative counts carry forward across semesters: a faculty who taught sci10 once in Fall Y1 has `times_taught_before = 1` in Spring Y1, affecting their weight.

**sci10 flavor-specific counting:** Because `prior_teaching_counts` stores per-flavor history, `times_taught_before` for a sci10 assignment is looked up by the assignment's specific flavor key (e.g. `sci10_health`). Teaching sci10 Health counts as a new prep independently of whether the faculty has taught sci10 Neuro or Earth before. The solver aggregates all three flavor counts into a single sci10 total for its pre-count lookup (since it assigns flavor post-hoc).

---

## Configurable Parameters (`data/config.yaml`)

```yaml
junior_faculty_hard_cap: 2.0
senior_faculty_soft_cap: 2.0
junior_new_lab_preps_per_year_max: 1
new_prep_bonus_count: 2
new_prep_weight: 2.0
foundational_experienced_weight: 1.67
extra_section_weight_multiplier: 0.5
target_annual_load: 4.0

objective_weights:
  section_coverage: 1000
  junior_new_preps: 100
  load_balance: 50
  senior_over_cap: 75
  sci10_flavor_diversity: 10
  senior_takes_new_preps: 25
```

These appear as a sidebar in the UI so the user can tweak and re-solve.

---

## UI

### Main View: 6-Semester Grid
- 6 columns: Fall Y1 → Spring Y3 (horizontally scrollable)
- Each column lists all 26 required sections as cards, grouped by course
- Card colour coding by category: indigo (foundational), purple (upper-div+lab), amber (upper-div lec), dashed (manual placeholder)
- Click a slot → dropdown of qualified faculty (greyed if over cap or unqualified)
- Faculty name on card shows their current semester load with colour coding

### Faculty Sidebar
- List of all 20 faculty
- Each shows: rank (J/S), area, annual load
- Click a faculty → highlight all their assignments in the grid
- Colour coding for load status: green (at target), yellow (under or just over), red (significantly over)

### Top Bar
- "Suggest assignments" button (runs solver on non-locked, non-manual slots)
- "Clear solver assignments" (preserves manual + locked)
- "Lock all" / "Unlock all"
- "Export xlsx"
- Config panel toggle

### Diagnostics Panel
- Coverage summary: "X of 26 sections filled per semester"
- Unfilled sections table with reasons
- Faculty load table: who's over, under, at target
- Bottleneck courses: courses where supply/demand ratio is worst
- Junior faculty new-prep counts per year
- Suggestions (e.g. "If Paul takes one more section of sci10, coverage goes from 85% to 92%") — deferred to post-MVP

---

## MVP Build Order

1. ✅ **Data loading:** CSV → Faculty, courses.yaml → Course, teaching_history.csv → prior counts
2. ✅ **Load calculator** with new-prep + extra-section logic, unit-tested
3. ✅ **Static 6-semester grid** rendering (read-only, empty)
4. ✅ **Manual assignment UI:** click slot → pick faculty; upper-div placeholders fillable
5. ✅ **Live load display** per faculty per semester with colour coding
6. ✅ **Constraint validator:** warnings surface in real time
7. ✅ **Diagnostics panel v1:** coverage %, unfilled sections, faculty load table
8. ✅ **OR-Tools solver:** "Suggest" button fills non-locked foundational/sci111/112 slots
9. ✅ **Lock/unlock** + re-run on unlocked subset
10. ✅ **Config panel:** tweakable parameters with "re-solve"
11. ✅ **xlsx export** of final plan + gap report
12. ⬜ *(Deferred)* Sabbatical/availability UI
13. ⬜ *(Deferred)* Edit faculty qualifications in-app

---

## Setup

```bash
# Requires pyenv with pyenv-virtualenv
pyenv virtualenv 3.12.5 cmc-planner
pyenv local cmc-planner          # creates .python-version (gitignored)
pip install flask pandas ortools pyyaml openpyxl pytest

# Copy faculty.csv into data/ (not committed — contains faculty data)
cp faculty.csv data/faculty.csv

python app.py
# → http://localhost:5000
```

Run tests:
```bash
python -m pytest tests/ -v
```
