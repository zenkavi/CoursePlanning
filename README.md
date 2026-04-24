# CMC Integrated Science Course Planner

A web app for planning faculty assignments across the three-year Integrated Science curriculum at CMC. It tracks weighted teaching loads, flags constraint violations, and (eventually) runs a solver to suggest assignments automatically.

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

**Diagnostics view** (`/diagnostics`) — Read-only summary of the current plan:
- Coverage per semester (filled / 26 sections)
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

1. Add/remove a row in `faculty.csv` with a 1/0 for each course they can teach.
2. Add/remove a corresponding row in `teaching_history.csv` (all zeros for a new hire).
3. Restart the server — faculty data is loaded at startup.

### Changing course section counts

Edit `sections_per_semester` in `data/courses.yaml` and restart the server.

### Tuning load parameters

Edit `data/config.yaml`. Key parameters:

| Parameter | Default | Meaning |
|---|---|---|
| `junior_faculty_hard_cap` | 2.0 | Max load per semester for junior faculty |
| `senior_faculty_soft_cap` | 2.0 | Soft load cap per semester for senior faculty |
| `target_annual_load` | 4.0 | Target total load per year |
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

The app tracks two types of violations shown as warning badges on the faculty sidebar:

- **Hard cap exceeded** (error): a junior faculty member's semester load exceeds `junior_faculty_hard_cap`.
- **Senior soft cap exceeded** (warning): a senior faculty member's semester load exceeds `senior_faculty_soft_cap`.
- **Too many new lab preps** (warning): a junior faculty member has more than one brand-new lab prep in a single academic year.

## Running tests

```bash
pytest
```

45 tests covering data loading and load calculation.

## Project status

Steps completed: 1–7 (data loading, load calc, grid rendering, manual assignment UI, live load display, constraint validator, diagnostics panel). See `PROGRESS.md` for details.
