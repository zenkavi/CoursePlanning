"""Weighted load calculation per faculty per semester."""
from collections import defaultdict
from models import Faculty, Course, Assignment


def section_weight(
    course: Course,
    faculty: Faculty,
    times_taught_before: int,
    cfg: dict,
) -> float:
    """Return the weight of a single section for this faculty.

    times_taught_before counts how many times this faculty has taught this
    specific course prior to this assignment (history + earlier semesters).
    """
    bonus_count = cfg.get("new_prep_bonus_count", 2)
    new_weight = cfg.get("new_prep_weight", 2.0)
    exp_weight = cfg.get("foundational_experienced_weight", 1.67)

    cat = course.category
    if cat == "foundational":
        return new_weight if times_taught_before < bonus_count else exp_weight
    elif cat == "upper_div_lecture_lab":
        return 2.0
    elif cat == "upper_div_lecture":
        return 1.0
    elif cat == "upper_div_lab":
        return 1.0
    return 1.0


def semester_load(
    faculty: Faculty,
    assignments: list,       # all Assignment objects for this faculty in ONE semester
    courses: dict,           # {code: Course}
    cumulative_counts: dict, # {course_code: times_taught_before_this_semester}
    cfg: dict,
) -> dict:
    """Return a detailed load breakdown for one faculty in one semester.

    Returns:
        {
          'total': float,
          'items': [{'course_code', 'section_number', 'base_weight', 'actual_weight', 'times_before'}]
        }
    """
    extra_mult = cfg.get("extra_section_weight_multiplier", 0.5)

    # Group by course_code to apply extra_section_weight_multiplier
    course_groups: dict = defaultdict(list)
    for a in assignments:
        course_groups[a.course_code].append(a)

    total = 0.0
    items = []
    for code, group in course_groups.items():
        course = courses.get(code)
        if course is None:
            continue
        times_before = cumulative_counts.get(code, 0)
        base_w = section_weight(course, faculty, times_before, cfg)

        for idx, a in enumerate(group):
            multiplier = 1.0 if idx == 0 else extra_mult
            actual_w = round(base_w * multiplier, 4)
            total += actual_w
            items.append({
                "course_code": code,
                "section_number": a.section_number,
                "base_weight": base_w,
                "actual_weight": actual_w,
                "times_before": times_before,
            })

    return {"total": round(total, 4), "items": items}


def all_faculty_loads(
    faculty_list: list,
    all_assignments: list,
    courses: dict,
    cfg: dict,
    year_range: tuple = (1, 3),
) -> dict:
    """Compute weighted load for every faculty in every semester.

    Returns:
        {faculty_name: {(year, semester): {'total', 'items', 'status', 'annual': {year: float}}}}
    """
    semesters = [
        (y, sem)
        for y in range(year_range[0], year_range[1] + 1)
        for sem in ("fall", "spring")
    ]

    result: dict = {}

    for faculty in faculty_list:
        name = faculty.name
        # Running tally of how many times faculty has taught each course
        cumulative: dict = dict(faculty.prior_teaching_counts)

        faculty_result: dict = {}
        for year, semester in semesters:
            sem_assignments = [
                a for a in all_assignments
                if a.faculty_name == name and a.year == year and a.semester == semester
            ]
            detail = semester_load(faculty, sem_assignments, courses, cumulative, cfg)
            status = _load_status(detail["total"], faculty, cfg)
            faculty_result[(year, semester)] = {
                **detail,
                "status": status,
            }
            # Update cumulative counts with this semester's assignments
            for a in sem_assignments:
                cumulative[a.course_code] = cumulative.get(a.course_code, 0) + 1

        # Attach annual totals
        for year in range(year_range[0], year_range[1] + 1):
            annual = (
                faculty_result.get((year, "fall"), {}).get("total", 0.0)
                + faculty_result.get((year, "spring"), {}).get("total", 0.0)
            )
            for sem in ("fall", "spring"):
                if (year, sem) in faculty_result:
                    faculty_result[(year, sem)]["annual"] = round(annual, 4)

        result[name] = faculty_result

    return result


def new_preps_in_semester(
    faculty: Faculty,
    assignments: list,         # assignments for this faculty in this semester
    cumulative_before: dict,   # {course_code: count} before this semester
    cfg: dict,
) -> list:
    """Return list of course codes that are new preps in this semester."""
    bonus_count = cfg.get("new_prep_bonus_count", 2)
    new = []
    for a in assignments:
        if cumulative_before.get(a.course_code, 0) < bonus_count:
            new.append(a.course_code)
    return new


def _load_status(total: float, faculty: Faculty, cfg: dict) -> str:
    hard_cap = cfg.get("junior_faculty_hard_cap", 2.0)
    soft_cap = cfg.get("senior_faculty_soft_cap", 2.0)
    target = cfg.get("target_annual_load", 4.0) / 2  # per semester

    cap = hard_cap if faculty.is_junior() else soft_cap

    if total > cap + 0.5:
        return "red"
    if total > cap:
        return "yellow-over"
    if total >= target - 0.25:
        return "green"
    if total > 0:
        return "yellow-under"
    return "empty"
