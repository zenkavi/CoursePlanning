import json
import os
from itertools import groupby

from flask import Flask, render_template

from config import load_config
from data_loader import load_courses, load_faculty
from load_calc import all_faculty_loads
from models import Plan

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
    return render_template(
        "planner.html",
        semesters=semesters,
        faculty_list=faculty_list,
        loads=loads,
        cfg=cfg,
    )


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
