"""Tests for data_loader.py — CSV and YAML parsing."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from data_loader import load_faculty, load_courses


@pytest.fixture(scope="module")
def faculty():
    return load_faculty()


@pytest.fixture(scope="module")
def courses():
    return load_courses()


class TestFacultyLoading:
    def test_count(self, faculty):
        assert len(faculty) == 20

    def test_names(self, faculty):
        names = {f.name for f in faculty}
        assert "Emily KH" in names
        assert "Paul" in names
        assert "Pranav" in names

    def test_rank_values(self, faculty):
        ranks = {f.rank for f in faculty}
        assert ranks == {"junior", "senior"}

    def test_junior_count(self, faculty):
        juniors = [f for f in faculty if f.is_junior()]
        assert len(juniors) == 11

    def test_senior_count(self, faculty):
        seniors = [f for f in faculty if f.is_senior()]
        assert len(seniors) == 9

    def test_sci10_generic_key(self, faculty):
        # Every faculty who can teach any sci10 flavor should have can_teach["sci10"] == True
        for f in faculty:
            any_flavor = any(
                f.can_teach.get(f"sci10_{fl}", False)
                for fl in ("health", "neuro", "earth")
            )
            assert f.can_teach.get("sci10", False) == any_flavor, (
                f"{f.name}: can_teach['sci10'] mismatch"
            )

    def test_paul_qualifications(self, faculty):
        paul = next(f for f in faculty if f.name == "Paul")
        assert paul.can_teach["sci10"] is True
        assert paul.can_teach["sci30a"] is True
        assert paul.can_teach["sci50"] is True
        assert paul.can_teach["sci112"] is True

    def test_diana_limited(self, faculty):
        diana = next(f for f in faculty if f.name == "Diana")
        # Diana can only teach sci10 neuro
        assert diana.can_teach["sci10_neuro"] is True
        assert diana.can_teach.get("sci10_health", False) is False
        assert diana.can_teach.get("sci30a", False) is False

    def test_branwen_only_earth(self, faculty):
        branwen = next(f for f in faculty if f.name == "Branwen")
        assert branwen.can_teach["sci10_earth"] is True
        assert branwen.can_teach.get("sci10_health", False) is False
        assert branwen.can_teach.get("sci10_neuro", False) is False

    def test_sci111_mapping(self, faculty):
        # CSV column "sci11 organic" must map to course code "sci111"
        colin = next(f for f in faculty if f.name == "Colin")
        assert colin.can_teach["sci111"] is True
        will = next(f for f in faculty if f.name == "Will")
        assert will.can_teach["sci111"] is True

    def test_prior_counts_has_expected_keys(self, faculty):
        expected = {"sci10", "sci30a", "sci30b", "sci31a", "sci31b", "sci40", "sci50", "sci111", "sci112"}
        for f in faculty:
            assert expected.issubset(f.prior_teaching_counts.keys()), (
                f"{f.name} missing keys in prior_teaching_counts"
            )


class TestCourseLoading:
    def test_course_count(self, courses):
        assert len(courses) == 13

    def test_sci10_sections(self, courses):
        sci10 = courses["sci10"]
        assert sci10.sections_in("fall") == 8
        assert sci10.sections_in("spring") == 8

    def test_sci30a_sections(self, courses):
        c = courses["sci30a"]
        assert c.sections_in("fall") == 1
        assert c.sections_in("spring") == 3

    def test_sci31a_sections(self, courses):
        c = courses["sci31a"]
        assert c.sections_in("fall") == 3
        assert c.sections_in("spring") == 1

    def test_sci111_category(self, courses):
        assert courses["sci111"].category == "upper_div_lecture_lab"

    def test_placeholder_codes(self, courses):
        placeholders = {code for code, c in courses.items() if c.is_placeholder}
        assert placeholders == {"udl_lab_1", "udl_lab_2", "udl_lec_1", "udl_lec_2"}

    def test_non_placeholders_are_solver_assigned(self, courses):
        for code, c in courses.items():
            if not c.is_placeholder:
                assert c.is_solver_assigned()

    def test_sci10_has_flavors(self, courses):
        assert set(courses["sci10"].flavors) == {"health", "neuro", "earth"}

    def test_fall_sections_total(self, courses):
        total = sum(c.sections_in("fall") for c in courses.values())
        assert total == 26

    def test_spring_sections_total(self, courses):
        total = sum(c.sections_in("spring") for c in courses.values())
        assert total == 26
