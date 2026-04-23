import json
import os
from itertools import groupby

from flask import Flask, jsonify, redirect, render_template, request, url_for

from config import load_config
from data_loader import load_courses, load_faculty
from load_calc import all_faculty_loads
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
    return render_template(
        "planner.html",
        semesters=semesters,
        faculty_list=faculty_list,
        loads_by_sem=loads_by_sem,
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


@app.route("/diagnostics")
def diagnostics():
    return render_template("diagnostics.html")


@app.route("/faculty/<name>")
def faculty_detail(name):
    faculty = next((f for f in faculty_list if f.name == name), None)
    if faculty is None:
        return "Faculty not found", 404
    return render_template("faculty_detail.html", faculty=faculty)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
