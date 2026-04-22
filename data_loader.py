"""Load faculty, courses, and teaching history from data files."""
import os
import csv
import yaml
from models import Faculty, Course

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Maps CSV column header -> (course_code, flavor_or_None)
_CSV_COLUMN_MAP = {
    "sci10 health":    ("sci10", "health"),
    "sci10 neuro":     ("sci10", "neuro"),
    "sci10 earth":     ("sci10", "earth"),
    "sci30a chem1":    ("sci30a", None),
    "sci30b phys1":    ("sci30b", None),
    "sci31a chem2":    ("sci31a", None),
    "sci31b bio1":     ("sci31b", None),
    "sci40 phys2":     ("sci40", None),
    "sci50":           ("sci50", None),
    "sci11 organic":   ("sci111", None),   # CSV uses "sci11", spec uses "sci111"
    "sci112 biochem":  ("sci112", None),
}


def load_faculty(
    faculty_csv: str = None,
    history_csv: str = None,
) -> list:
    """Return a list of Faculty objects populated from CSV files."""
    if faculty_csv is None:
        faculty_csv = os.path.join(DATA_DIR, "faculty.csv")
    if history_csv is None:
        history_csv = os.path.join(DATA_DIR, "teaching_history.csv")

    prior_counts = _load_teaching_history(history_csv)
    faculty_list = []

    with open(faculty_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["Name"].strip()
            area = row["Area"].strip()
            method = row["Research method"].strip()
            rank = row["Rank"].strip().lower()

            can_teach: dict = {}
            for col, (code, flavor) in _CSV_COLUMN_MAP.items():
                val = int(row.get(col, 0) or 0)
                if flavor:
                    # Flavor-specific key e.g. "sci10_health"
                    can_teach[f"{code}_{flavor}"] = bool(val)
                    # Generic sci10 key is True if any flavor is True
                    can_teach[code] = can_teach.get(code, False) or bool(val)
                else:
                    can_teach[code] = bool(val)

            faculty_list.append(Faculty(
                name=name,
                area=area,
                research_method=method,
                rank=rank,
                can_teach=can_teach,
                prior_teaching_counts=prior_counts.get(name, {}),
            ))

    return faculty_list


def _load_teaching_history(path: str) -> dict:
    """Return {faculty_name: {course_code: count}} from teaching_history.csv."""
    counts: dict = {}
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row["Name"].strip()
                counts[name] = {
                    col: int(val or 0)
                    for col, val in row.items()
                    if col != "Name"
                }
    except FileNotFoundError:
        pass
    return counts


def load_courses(courses_yaml: str = None) -> dict:
    """Return {course_code: Course} from courses.yaml."""
    if courses_yaml is None:
        courses_yaml = os.path.join(DATA_DIR, "courses.yaml")

    with open(courses_yaml) as f:
        data = yaml.safe_load(f)

    courses = {}
    for entry in data.get("courses", []):
        code = entry["code"]
        courses[code] = Course(
            code=code,
            display_name=entry["display_name"],
            category=entry["category"],
            is_placeholder=entry.get("is_placeholder", False),
            sections_per_semester=entry.get("sections_per_semester", {}),
            flavors=entry.get("flavors", []),
        )
    return courses


def faculty_by_name(faculty_list: list) -> dict:
    return {f.name: f for f in faculty_list}
