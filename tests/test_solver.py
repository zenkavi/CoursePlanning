"""Tests for the CP-SAT solver using synthetic data (no CSV required)."""
import pytest
from models import Faculty, Course, Assignment, Plan
from solver import solve
from load_calc import all_faculty_loads


def _cfg():
    return {
        "junior_faculty_hard_cap": 2.0,
        "senior_faculty_soft_cap": 2.0,
        "junior_new_lab_preps_per_year_max": 1,
        "new_prep_bonus_count": 2,
        "new_prep_weight": 2.0,
        "foundational_experienced_weight": 1.67,
        "extra_section_weight_multiplier": 0.5,
        "target_annual_load": 4.0,
        "objective_weights": {
            "section_coverage": 1000,
            "junior_new_preps": 100,
            "load_balance": 50,
            "senior_over_cap": 75,
            "sci10_flavor_diversity": 10,
            "senior_takes_new_preps": 25,
        },
    }


def _courses():
    return {
        "sci10": Course(
            code="sci10",
            display_name="SCI 10",
            category="foundational",
            sections_per_semester={"fall": 8, "spring": 8},
            flavors=["health", "neuro", "earth"],
        ),
        "sci30a": Course(
            code="sci30a",
            display_name="SCI 30A",
            category="foundational",
            sections_per_semester={"fall": 1, "spring": 3},
        ),
        "sci111": Course(
            code="sci111",
            display_name="SCI 111",
            category="upper_div_lecture_lab",
            sections_per_semester={"fall": 1, "spring": 1},
        ),
        "udl_lab_1": Course(
            code="udl_lab_1",
            display_name="UDL Lab 1",
            category="upper_div_lecture_lab",
            is_placeholder=True,
            sections_per_semester={"fall": 1, "spring": 1},
        ),
    }


def test_solve_returns_list():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True, "sci30a": True}),
        Faculty(name="Bob", area="chem", research_method="exp", rank="junior",
                can_teach={"sci10": True, "sci10_neuro": True}),
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    assert isinstance(result, list)
    assert all(isinstance(a, Assignment) for a in result)


def test_solve_respects_qualifications():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True}),
        Faculty(name="Bob", area="chem", research_method="exp", rank="senior",
                can_teach={"sci30a": True}),
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    for a in result:
        f = next(f for f in faculty if f.name == a.faculty_name)
        assert f.can_teach_course(a.course_code), \
            f"{a.faculty_name} assigned to {a.course_code} but not qualified"


def test_solve_respects_junior_hard_cap():
    # Junior with experienced weights (1.67) — solver allows 1 section per semester
    junior = Faculty(
        name="Junior", area="bio", research_method="exp", rank="junior",
        can_teach={"sci10": True, "sci10_health": True, "sci30a": True},
        prior_teaching_counts={"sci10": 5, "sci30a": 5},
    )
    result = solve([junior], _courses(), Plan(), _cfg())

    all_assignments = result
    loads = all_faculty_loads([junior], all_assignments, _courses(), _cfg())
    hard_cap = _cfg()["junior_faculty_hard_cap"]
    for (year, sem), data in loads["Junior"].items():
        assert data["total"] <= hard_cap + 0.01, \
            f"Junior exceeded hard cap in Y{year} {sem}: {data['total']}"


def test_solve_skips_placeholders():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True, "udl_lab_1": True}),
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    assert all(a.course_code != "udl_lab_1" for a in result), \
        "Solver should not fill placeholder slots"


def test_solve_skips_filled_slots():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True}),
    ]
    existing = Assignment(
        faculty_name="Alice", course_code="sci10", year=1, semester="fall",
        section_number=1, locked=True, manual=False,
    )
    plan = Plan(assignments=[existing])
    result = solve(faculty, _courses(), plan, _cfg())
    solver_slots = {(a.course_code, a.year, a.semester, a.section_number) for a in result}
    assert ("sci10", 1, "fall", 1) not in solver_slots, \
        "Solver returned an already-filled slot"


def test_solve_no_duplicate_slots():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True}),
        Faculty(name="Bob", area="chem", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_neuro": True}),
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    slot_ids = [(a.course_code, a.year, a.semester, a.section_number) for a in result]
    assert len(slot_ids) == len(set(slot_ids)), "Solver assigned multiple faculty to same slot"


def test_solve_empty_plan_returns_assignments():
    # With enough faculty, solver should fill at least some slots
    faculty = [
        Faculty(name=f"F{i}", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True})
        for i in range(5)
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    assert len(result) > 0, "Solver returned no assignments for an empty plan"


def test_solve_marks_assignments_as_not_manual_not_locked():
    faculty = [
        Faculty(name="Alice", area="bio", research_method="exp", rank="senior",
                can_teach={"sci10": True, "sci10_health": True}),
    ]
    result = solve(faculty, _courses(), Plan(), _cfg())
    for a in result:
        assert not a.manual, "Solver assignments should have manual=False"
        assert not a.locked, "Solver assignments should have locked=False"
