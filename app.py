import json
import os
from itertools import groupby

from flask import Flask, jsonify, redirect, render_template, request, url_for

from config import load_config
from data_loader import load_courses, load_faculty
from load_calc import all_faculty_loads, new_preps_in_semester
from models import Assignment, Plan

app = Flask(__name__)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PLAN_FILE = os.path.join(DATA_DIR, "plan.json")

# Load static data once at startup
faculty_list = load_faculty()
courses = load_courses()
cfg = load_config()

COURSE_ORDER = [
    "sci10", "sci30a", "sci30b", "sci31a", "sci31b", "sci40", "sci50",
    "sci111", "sci112", "udl_lab_1", "udl_lab_2", "udl_lec_1", "udl_lec_2",
]


def load_plan() -> Plan:
    try:
        with open(PLAN_FILE) as f:
            return Plan.from_dict(json.load(f))
    except FileNotFoundError:
        return Plan()


def save_plan(plan: Plan):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PLAN_FILE, "w") as f:
        json.dump(plan.to_dict(), f, indent=2)


def compute_violations(faculty_list, loads, plan, courses, cfg) -> dict:
    """Return {faculty_name: {items, has_error, has_warning, count}} for active violations."""
    lab_cats = {"upper_div_lecture_lab", "upper_div_lab"}
    junior_cap = cfg.get("junior_faculty_hard_cap", 2.0)
    senior_cap = cfg.get("senior_faculty_soft_cap", 2.0)

    result = {}
    for faculty in faculty_list:
        fname = faculty.name
        items = []

        # ── Semester load cap violations ──────────────────────────────
        for (y, sem), data in loads.get(fname, {}).items():
            total = data.get("total", 0.0)
            label = f"{'Fall' if sem == 'fall' else 'Spring'} Y{y}"
            if faculty.is_junior() and total > junior_cap:
                items.append({
                    "type": "hard_cap", "severity": "error",
                    "description": f"{label}: load {total:.2f} exceeds junior hard cap ({junior_cap:.1f})",
                })
            elif faculty.is_senior() and total > senior_cap:
                items.append({
                    "type": "soft_cap", "severity": "warning",
                    "description": f"{label}: load {total:.2f} exceeds senior soft cap ({senior_cap:.1f})",
                })

        # ── Junior: > 1 new lab prep per academic year ────────────────
        if faculty.is_junior():
            cumulative = dict(faculty.prior_teaching_counts)
            for year in range(plan.year_range[0], plan.year_range[1] + 1):
                year_new_labs = set()
                for sem in ("fall", "spring"):
                    sem_assigns = [
                        a for a in plan.assignments
                        if a.faculty_name == fname and a.year == year and a.semester == sem
                    ]
                    for a in sem_assigns:
                        course = courses.get(a.course_code)
                        if course and course.category in lab_cats:
                            if cumulative.get(a.course_code, 0) == 0:
                                year_new_labs.add(a.course_code)
                    for a in sem_assigns:
                        cumulative[a.course_code] = cumulative.get(a.course_code, 0) + 1

                if len(year_new_labs) > 1:
                    names = ", ".join(
                        courses[c].display_name if c in courses else c
                        for c in sorted(year_new_labs)
                    )
                    items.append({
                        "type": "new_lab_prep", "severity": "warning",
                        "description": (
                            f"Y{year}: {len(year_new_labs)} new lab preps ({names})"
                            f" — max 1/year for junior faculty"
                        ),
                    })

        result[fname] = {
            "items": items,
            "has_error": any(v["severity"] == "error" for v in items),
            "has_warning": any(v["severity"] == "warning" for v in items),
            "count": len(items),
        }
    return result


def build_grid(plan: Plan, year_range: tuple = (1, 3)) -> list:
    """Return the semester/slot structure the template renders.

    Each semester dict:
      label, year, season, groups: [{course, sections: [{slot_id, section_number, assignment}]}]
    """
    semesters = []
    for year in range(year_range[0], year_range[1] + 1):
        for season in ("fall", "spring"):
            groups = []
            for code in COURSE_ORDER:
                course = courses.get(code)
                if course is None:
                    continue
                n = course.sections_in(season)
                if n == 0:
                    continue
                sections = []
                for sec in range(1, n + 1):
                    sections.append({
                        "slot_id": f"{code}__{year}__{season}__{sec}",
                        "section_number": sec,
                        "assignment": plan.get_assignment(code, year, season, sec),
                    })
                groups.append({"course": course, "sections": sections})
            semesters.append({
                "year": year,
                "season": season,
                "label": f"{'Fall' if season == 'fall' else 'Spring'} Y{year}",
                "groups": groups,
                "total_sections": sum(len(g["sections"]) for g in groups),
            })
    return semesters


@app.route("/")
def index():
    plan = load_plan()
    semesters = build_grid(plan)
    loads = all_faculty_loads(faculty_list, plan.assignments, courses, cfg)
    # Flatten loads for Jinja: "year__season" -> {faculty_name: {total, status, ...}}
    loads_by_sem = {}
    for fname, sems in loads.items():
        for (y, sem), data in sems.items():
            loads_by_sem.setdefault(f"{y}__{sem}", {})[fname] = data

    # Annual totals with status: {faculty_name: {year: {total, status}}}
    annual_loads = {}
    faculty_by_name_map = {f.name: f for f in faculty_list}
    for fname, sems in loads.items():
        f = faculty_by_name_map.get(fname)
        annual_loads[fname] = {}
        for year in range(1, 4):
            total = round(
                sems.get((year, "fall"), {}).get("total", 0.0)
                + sems.get((year, "spring"), {}).get("total", 0.0),
                4,
            )
            target = cfg.get("target_annual_load", 4.0)
            hard_cap = cfg.get("junior_faculty_hard_cap", 2.0) * 2
            soft_cap = cfg.get("senior_faculty_soft_cap", 2.0) * 2
            cap = hard_cap if (f and f.is_junior()) else soft_cap
            if total > cap + 1.0:
                status = "red"
            elif total > cap:
                status = "yellow-over"
            elif total >= target - 0.5:
                status = "green"
            elif total > 0:
                status = "yellow-under"
            else:
                status = "empty"
            annual_loads[fname][year] = {"total": total, "status": status}

    violations = compute_violations(faculty_list, loads, plan, courses, cfg)

    return render_template(
        "planner.html",
        semesters=semesters,
        faculty_list=faculty_list,
        loads_by_sem=loads_by_sem,
        annual_loads=annual_loads,
        violations=violations,
        cfg=cfg,
    )


@app.route("/assign", methods=["POST"])
def assign():
    data = request.get_json()
    slot_id = data.get("slot_id", "")
    faculty_name = data.get("faculty_name", "")

    parts = slot_id.split("__")
    if len(parts) != 4:
        return jsonify({"error": "Invalid slot_id"}), 400

    course_code, year, season, section = parts[0], int(parts[1]), parts[2], int(parts[3])

    plan = load_plan()
    existing = plan.get_assignment(course_code, year, season, section)
    if existing and existing.locked:
        return jsonify({"error": "Assignment is locked"}), 403

    faculty = next((f for f in faculty_list if f.name == faculty_name), None)
    if faculty is None:
        return jsonify({"error": "Unknown faculty"}), 400

    course = courses.get(course_code)
    if course is None:
        return jsonify({"error": "Unknown course"}), 400
    if not course.is_placeholder and not faculty.can_teach_course(course_code):
        return jsonify({"error": "Faculty not qualified for this course"}), 400

    flavor = None
    if course_code == "sci10":
        for fl in ("health", "neuro", "earth"):
            if faculty.can_teach.get(f"sci10_{fl}"):
                flavor = fl
                break

    plan.set_assignment(Assignment(
        faculty_name=faculty_name,
        course_code=course_code,
        year=year,
        semester=season,
        section_number=section,
        locked=False,
        manual=True,
        flavor=flavor,
    ))
    save_plan(plan)
    return jsonify({"ok": True})


@app.route("/unassign", methods=["POST"])
def unassign():
    data = request.get_json()
    slot_id = data.get("slot_id", "")

    parts = slot_id.split("__")
    if len(parts) != 4:
        return jsonify({"error": "Invalid slot_id"}), 400

    course_code, year, season, section = parts[0], int(parts[1]), parts[2], int(parts[3])

    plan = load_plan()
    existing = plan.get_assignment(course_code, year, season, section)
    if existing and existing.locked:
        return jsonify({"error": "Assignment is locked"}), 403

    plan.remove_assignment(course_code, year, season, section)
    save_plan(plan)
    return jsonify({"ok": True})


def build_diagnostics(plan: Plan) -> dict:
    loads = all_faculty_loads(faculty_list, plan.assignments, courses, cfg)
    semesters = build_grid(plan)

    # 1. Coverage per semester
    coverage = []
    for sem in semesters:
        total = sem["total_sections"]
        filled = sum(
            1 for g in sem["groups"]
            for s in g["sections"]
            if s["assignment"] is not None
        )
        coverage.append({
            "label": sem["label"],
            "filled": filled,
            "total": total,
            "pct": round(filled / total * 100) if total else 0,
        })

    # 2. Unfilled sections
    unfilled = []
    for sem in semesters:
        for g in sem["groups"]:
            for s in g["sections"]:
                if s["assignment"] is None:
                    unfilled.append({
                        "semester_label": sem["label"],
                        "course_name": g["course"].display_name,
                        "section": s["section_number"],
                        "is_placeholder": g["course"].is_placeholder,
                    })

    # 3. Faculty load table — sorted juniors first then seniors, alphabetical within
    target = cfg.get("target_annual_load", 4.0)
    hard_cap = cfg.get("junior_faculty_hard_cap", 2.0) * 2
    soft_cap = cfg.get("senior_faculty_soft_cap", 2.0) * 2

    faculty_loads_table = []
    for f in sorted(faculty_list, key=lambda x: (x.rank, x.name)):
        row = {"name": f.name, "rank": "J" if f.is_junior() else "S", "area": f.area, "years": {}}
        cap = hard_cap if f.is_junior() else soft_cap
        for year in range(1, 4):
            fall_t = loads.get(f.name, {}).get((year, "fall"), {}).get("total", 0.0)
            spring_t = loads.get(f.name, {}).get((year, "spring"), {}).get("total", 0.0)
            annual = round(fall_t + spring_t, 2)
            if annual > cap + 1.0:
                status = "red"
            elif annual > cap:
                status = "yellow-over"
            elif annual >= target - 0.5:
                status = "green"
            elif annual > 0:
                status = "yellow-under"
            else:
                status = "empty"
            row["years"][year] = {
                "fall": round(fall_t, 2),
                "spring": round(spring_t, 2),
                "annual": annual,
                "status": status,
            }
        faculty_loads_table.append(row)

    # 4. Bottleneck courses (non-placeholder only), sorted by sections/faculty ratio desc
    bottlenecks = []
    for code, course in courses.items():
        if course.is_placeholder:
            continue
        qualified = sum(1 for f in faculty_list if f.can_teach_course(code))
        total_sections = (
            course.sections_per_semester.get("fall", 0)
            + course.sections_per_semester.get("spring", 0)
        ) * 3
        ratio = round(total_sections / qualified, 2) if qualified else None
        bottlenecks.append({
            "name": course.display_name,
            "qualified": qualified,
            "total_sections": total_sections,
            "ratio": ratio,
        })
    bottlenecks.sort(key=lambda x: (x["ratio"] is None, -(x["ratio"] or 0)))

    # 5. Junior new-prep counts per year (brand-new = zero prior history, matching constraint logic)
    junior_preps = []
    for f in faculty_list:
        if not f.is_junior():
            continue
        cumulative = dict(f.prior_teaching_counts)
        years_data = {}
        for year in range(1, 4):
            year_new = set()
            for sem in ("fall", "spring"):
                sem_assigns = [
                    a for a in plan.assignments
                    if a.faculty_name == f.name and a.year == year and a.semester == sem
                ]
                for a in sem_assigns:
                    if cumulative.get(a.course_code, 0) == 0:
                        year_new.add(a.course_code)
                    cumulative[a.course_code] = cumulative.get(a.course_code, 0) + 1
            years_data[year] = {
                "count": len(year_new),
                "names": [courses[c].display_name for c in year_new if c in courses],
            }
        junior_preps.append({"name": f.name, "years": years_data})

    return {
        "coverage": coverage,
        "unfilled": unfilled,
        "faculty_loads_table": faculty_loads_table,
        "bottlenecks": bottlenecks,
        "junior_preps": junior_preps,
    }


@app.route("/diagnostics")
def diagnostics():
    plan = load_plan()
    data = build_diagnostics(plan)
    return render_template("diagnostics.html", **data)


@app.route("/faculty/<name>")
def faculty_detail(name):
    faculty = next((f for f in faculty_list if f.name == name), None)
    if faculty is None:
        return "Faculty not found", 404
    return render_template("faculty_detail.html", faculty=faculty)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
