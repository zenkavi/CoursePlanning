# CMC Integrated Science Course Planner

A web app for planning faculty assignments across the three-year Integrated Science curriculum at CMC. It tracks weighted teaching loads, flags constraint violations, and runs a solver to suggest assignments automatically.

## Quick start

**First-time setup** (requires Python 3.12+):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Run the app:**

```bash
python app.py
```

Open http://127.0.0.1:5000. Stop the server with Ctrl+C.

**Reset to a blank plan:**
```bash
rm data/plan.json
```

## What it does

**Grid view** (`/`) — A 6-column schedule (Fall Y1 through Spring Y3) with every course section as a slot. Click a slot to assign a faculty member from the dropdown. The faculty sidebar shows annual load badges (Y1/Y2/Y3) colour-coded by status; click a faculty name to highlight all their assignments in the grid. Warning badges appear on faculty with constraint violations.

- **Lock/unlock** individual assignments (or all at once) to pin them before running the solver.
- **Sci10 section count** — use the `+`/`−` buttons on the SCI 10 group header in any semester to add or remove sections (default 10 per semester, adjustable per semester up to 20).
- **Sci10 flavor** — each Sci10 section can be tagged health/neuro/earth from the assignment dropdown.
- **Solver** — the "Solve" button auto-fills remaining unfilled slots using a constraint solver; locked and manually-placed assignments are preserved.
- **Config panel** — edit load parameters (caps, weights) from the UI and re-solve without touching `config.yaml`.
- **Export** — download the current plan and a gap report as an xlsx file.

**Diagnostics view** (`/diagnostics`) — Read-only summary of the current plan:
- Coverage per semester (filled / total sections; total reflects any sci10 count adjustments)
- All unfilled slots
- Course supply/demand ratios (which courses have the fewest qualified faculty relative to section count)
- Faculty load table with fall/spring/annual breakdown
- Junior faculty new-prep counts per year

## Data files

All editable data lives in `data/`:

| File | Purpose |
|---|---|
| `faculty.csv` | One row per faculty. Columns: Name, Area, Research method, Rank (Junior/Senior), then one column per course (1 = can teach, 0 = cannot). |
| `teaching_history.csv` | Prior teaching counts by course code, used to determine new-prep status. One row per faculty. |
| `courses.yaml` | Course definitions: code, display name, category, sections per semester. |
| `config.yaml` | Tunable parameters (load caps, weights). |
| `plan.json` | Auto-generated. Stores the current assignment state. Delete to start fresh. |

### Adding or removing a faculty member

1. Add/remove a row in `faculty.csv` with a 1/0 for each course they can teach. Valid values for the `Rank` column: `junior`, `senior`, `visiting`, `lab director`.
2. Add/remove a corresponding row in `teaching_history.csv` (all zeros for a new hire).
3. Restart the server — faculty data is loaded at startup.

### Changing course section counts

For **SCI 10**, use the `+`/`−` buttons on the SCI 10 group header in each semester column — no restart needed, counts are saved per semester in `plan.json`.

For all other courses, edit `sections_per_semester` in `data/courses.yaml` and restart the server.

### Tuning load parameters

Edit `data/config.yaml`. Key parameters:

| Parameter | Default | Meaning |
|---|---|---|
| `junior_faculty_hard_cap` | 2.0 | Max load per semester for junior faculty (hard) |
| `senior_faculty_soft_cap` | 2.0 | Soft load cap per semester for senior faculty |
| `visiting_faculty_soft_cap` | 2.5 | Soft load cap per semester for visiting faculty |
| `visiting_faculty_target_annual` | 5.0 | Target annual load for visiting faculty |
| `lab_director_soft_cap` | 1.67 | Soft load cap per semester for lab directors |
| `lab_director_target_annual` | 3.33 | Target annual load for lab directors |
| `junior_new_lab_preps_per_year_max` | 1 | Max new lab preps per year for junior faculty |
| `target_annual_load` | 4.0 | Target annual load for junior and senior faculty |
| `new_prep_weight` | 2.0 | Load weight for a course taught fewer than `new_prep_bonus_count` times |
| `new_prep_bonus_count` | 2 | Number of times a course must be taught before it drops to experienced weight |
| `foundational_experienced_weight` | 1.67 | Load weight for an experienced foundational course section |
| `extra_section_weight_multiplier` | 0.5 | Multiplier applied to a second section of the same course in the same semester |

## Load calculation

Each assigned section has a weight:

- **Foundational course, new prep** (taught < `new_prep_bonus_count` times): 2.0
- **Foundational course, experienced**: 1.67
- **Upper-div lecture/lab combined**: 2.0
- **Upper-div lecture only or lab only**: 1.0

If a faculty member teaches two sections of the same course in the same semester, the second section is multiplied by `extra_section_weight_multiplier` (default 0.5).

## Constraint violations

The app tracks three types of violations shown as warning badges on the faculty sidebar:

- **Hard cap exceeded** (error): a junior faculty member's semester load exceeds `junior_faculty_hard_cap`.
- **Soft cap exceeded** (warning): a senior, visiting, or lab director faculty member's semester load exceeds their rank-specific soft cap.
- **Too many new lab preps** (warning): a junior faculty member has more than `junior_new_lab_preps_per_year_max` new lab preps in a single academic year.

## Running tests

```bash
pytest
```

54 tests covering data loading, load calculation, and the solver.

## Project status

MVP complete (steps 1–11). Post-MVP: dynamic SCI 10 section count, unlock button bug fix. See `PROGRESS.md` for details.
