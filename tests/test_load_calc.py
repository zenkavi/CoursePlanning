"""Tests for load_calc.py — weighted load with new-prep and extra-section rules."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from models import Faculty, Course, Assignment
from load_calc import section_weight, semester_load, all_faculty_loads, new_preps_in_semester


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg():
    return {
        "junior_faculty_hard_cap": 2.0,
        "senior_faculty_soft_cap": 2.0,
        "new_prep_bonus_count": 2,
        "new_prep_weight": 2.0,
        "foundational_experienced_weight": 1.67,
        "extra_section_weight_multiplier": 0.5,
        "target_annual_load": 4.0,
    }


def make_faculty(name="TestFac", rank="junior", prior=None):
    return Faculty(
        name=name,
        area="Health",
        research_method="Lab",
        rank=rank,
        prior_teaching_counts=prior or {},
    )


def make_course(code="sci10", category="foundational"):
    return Course(code=code, display_name=code.upper(), category=category)


def make_assignment(faculty_name, course_code, year=1, semester="fall", section=1):
    return Assignment(
        faculty_name=faculty_name, course_code=course_code,
        year=year, semester=semester, section_number=section,
    )


# ---------------------------------------------------------------------------
# section_weight
# ---------------------------------------------------------------------------

class TestSectionWeight:
    def test_foundational_new_prep(self, cfg):
        fac = make_faculty(prior={})
        course = make_course("sci10", "foundational")
        assert section_weight(course, fac, 0, cfg) == 2.0

    def test_foundational_one_prior(self, cfg):
        fac = make_faculty(prior={"sci10": 1})
        course = make_course("sci10", "foundational")
        assert section_weight(course, fac, 1, cfg) == 2.0

    def test_foundational_two_prior(self, cfg):
        fac = make_faculty(prior={"sci10": 2})
        course = make_course("sci10", "foundational")
        assert section_weight(course, fac, 2, cfg) == 1.67

    def test_foundational_many_prior(self, cfg):
        course = make_course("sci30a", "foundational")
        fac = make_faculty()
        assert section_weight(course, fac, 10, cfg) == 1.67

    def test_upper_div_lecture_lab(self, cfg):
        fac = make_faculty()
        course = make_course("sci111", "upper_div_lecture_lab")
        assert section_weight(course, fac, 0, cfg) == 2.0
        assert section_weight(course, fac, 5, cfg) == 2.0  # always 2

    def test_upper_div_lecture(self, cfg):
        fac = make_faculty()
        course = make_course("udl_lec_1", "upper_div_lecture")
        assert section_weight(course, fac, 0, cfg) == 1.0

    def test_upper_div_lab(self, cfg):
        fac = make_faculty()
        course = make_course("udl_lab_1", "upper_div_lab")
        assert section_weight(course, fac, 0, cfg) == 1.0


# ---------------------------------------------------------------------------
# semester_load
# ---------------------------------------------------------------------------

class TestSemesterLoad:
    def test_single_new_prep(self, cfg):
        fac = make_faculty("Alice")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [make_assignment("Alice", "sci10", section=1)]
        result = semester_load(fac, assignments, courses, {}, cfg)
        assert result["total"] == 2.0
        assert len(result["items"]) == 1

    def test_single_experienced(self, cfg):
        fac = make_faculty("Alice", prior={"sci10": 5})
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [make_assignment("Alice", "sci10", section=1)]
        cumulative = {"sci10": 5}
        result = semester_load(fac, assignments, courses, cumulative, cfg)
        assert result["total"] == 1.67

    def test_two_sections_same_course_extra_weight(self, cfg):
        # cfg.extra_section_weight_multiplier = 0.5
        # First section: 2.0, second section: 2.0 * 0.5 = 1.0 → total 3.0
        fac = make_faculty("Alice")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [
            make_assignment("Alice", "sci10", section=1),
            make_assignment("Alice", "sci10", section=2),
        ]
        result = semester_load(fac, assignments, courses, {}, cfg)
        assert result["total"] == pytest.approx(3.0)
        assert len(result["items"]) == 2

    def test_two_sections_no_extra_discount(self, cfg):
        cfg2 = {**cfg, "extra_section_weight_multiplier": 1.0}
        fac = make_faculty("Alice")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [
            make_assignment("Alice", "sci10", section=1),
            make_assignment("Alice", "sci10", section=2),
        ]
        result = semester_load(fac, assignments, courses, {}, cfg2)
        assert result["total"] == pytest.approx(4.0)

    def test_two_different_courses(self, cfg):
        fac = make_faculty("Alice")
        courses = {
            "sci10": make_course("sci10", "foundational"),
            "sci30a": make_course("sci30a", "foundational"),
        }
        assignments = [
            make_assignment("Alice", "sci10"),
            make_assignment("Alice", "sci30a"),
        ]
        result = semester_load(fac, assignments, courses, {}, cfg)
        # Both new preps → 2.0 + 2.0 = 4.0
        assert result["total"] == pytest.approx(4.0)

    def test_upper_div_plus_foundational(self, cfg):
        fac = make_faculty("Alice", prior={"sci10": 3})
        courses = {
            "sci10": make_course("sci10", "foundational"),
            "sci111": make_course("sci111", "upper_div_lecture_lab"),
        }
        assignments = [
            make_assignment("Alice", "sci10"),
            make_assignment("Alice", "sci111"),
        ]
        result = semester_load(fac, assignments, courses, {"sci10": 3}, cfg)
        # sci10 experienced → 1.67, sci111 → 2.0
        assert result["total"] == pytest.approx(1.67 + 2.0)

    def test_empty_assignments(self, cfg):
        fac = make_faculty("Alice")
        result = semester_load(fac, [], {}, {}, cfg)
        assert result["total"] == 0.0
        assert result["items"] == []

    def test_three_sections_same_course(self, cfg):
        # First: 2.0, second: 1.0, third: 1.0 → 4.0
        fac = make_faculty("Alice")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [make_assignment("Alice", "sci10", section=i) for i in range(3)]
        result = semester_load(fac, assignments, courses, {}, cfg)
        assert result["total"] == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# all_faculty_loads (integration)
# ---------------------------------------------------------------------------

class TestAllFacultyLoads:
    def test_cumulative_count_updates_across_semesters(self, cfg):
        """Faculty who taught sci10 in fall Y1 should get experienced weight in spring Y1."""
        fac = make_faculty("Alice", prior={"sci10": 1})  # 1 prior → still new in fall
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [
            make_assignment("Alice", "sci10", year=1, semester="fall", section=1),
            make_assignment("Alice", "sci10", year=1, semester="spring", section=1),
        ]
        loads = all_faculty_loads([fac], assignments, courses, cfg)
        fall_load = loads["Alice"][(1, "fall")]["total"]
        spring_load = loads["Alice"][(1, "spring")]["total"]
        # Fall: prior=1 → still < 2 → weight 2.0
        assert fall_load == pytest.approx(2.0)
        # Spring: cumulative now 2 (1 prior + 1 from fall) → experienced → 1.67
        assert spring_load == pytest.approx(1.67)

    def test_annual_total(self, cfg):
        fac = make_faculty("Alice")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [
            make_assignment("Alice", "sci10", year=1, semester="fall"),
            make_assignment("Alice", "sci10", year=1, semester="spring"),
        ]
        loads = all_faculty_loads([fac], assignments, courses, cfg)
        assert loads["Alice"][(1, "fall")]["annual"] == pytest.approx(4.0)
        assert loads["Alice"][(1, "spring")]["annual"] == pytest.approx(4.0)

    def test_unassigned_faculty_zero_load(self, cfg):
        fac = make_faculty("Bob")
        courses = {"sci10": make_course("sci10", "foundational")}
        loads = all_faculty_loads([fac], [], courses, cfg)
        for key, val in loads["Bob"].items():
            assert val["total"] == 0.0

    def test_multiple_faculty_independent(self, cfg):
        alice = make_faculty("Alice")
        bob = make_faculty("Bob")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [
            make_assignment("Alice", "sci10", year=1, semester="fall"),
        ]
        loads = all_faculty_loads([alice, bob], assignments, courses, cfg)
        assert loads["Alice"][(1, "fall")]["total"] == pytest.approx(2.0)
        assert loads["Bob"][(1, "fall")]["total"] == pytest.approx(0.0)

    def test_load_status_green(self, cfg):
        fac = make_faculty("Alice", rank="junior")
        courses = {"sci10": make_course("sci10", "foundational")}
        assignments = [make_assignment("Alice", "sci10", year=1, semester="fall")]
        loads = all_faculty_loads([fac], assignments, courses, cfg)
        # 2.0 load for junior with hard cap 2.0 → green
        assert loads["Alice"][(1, "fall")]["status"] == "green"

    def test_load_status_over_cap(self, cfg):
        fac = make_faculty("Alice", rank="junior")
        courses = {
            "sci10": make_course("sci10", "foundational"),
            "sci30a": make_course("sci30a", "foundational"),
        }
        assignments = [
            make_assignment("Alice", "sci10", year=1, semester="fall"),
            make_assignment("Alice", "sci30a", year=1, semester="fall"),
        ]
        loads = all_faculty_loads([fac], assignments, courses, cfg)
        # 2.0 + 2.0 = 4.0 → red (well over cap)
        assert loads["Alice"][(1, "fall")]["status"] == "red"


# ---------------------------------------------------------------------------
# new_preps_in_semester
# ---------------------------------------------------------------------------

class TestNewPreps:
    def test_new_prep_detected(self, cfg):
        fac = make_faculty("Alice", prior={"sci10": 0})
        assignments = [make_assignment("Alice", "sci10")]
        result = new_preps_in_semester(fac, assignments, {}, cfg)
        assert "sci10" in result

    def test_experienced_not_new_prep(self, cfg):
        fac = make_faculty("Alice", prior={"sci10": 2})
        assignments = [make_assignment("Alice", "sci10")]
        result = new_preps_in_semester(fac, assignments, {"sci10": 2}, cfg)
        assert result == []

    def test_multiple_courses_mixed(self, cfg):
        fac = make_faculty("Alice")
        assignments = [
            make_assignment("Alice", "sci10"),
            make_assignment("Alice", "sci30a"),
        ]
        cumulative = {"sci10": 3, "sci30a": 0}
        result = new_preps_in_semester(fac, assignments, cumulative, cfg)
        assert "sci10" not in result
        assert "sci30a" in result
