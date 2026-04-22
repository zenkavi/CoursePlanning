from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Faculty:
    name: str
    area: str
    research_method: str
    rank: str  # "junior" | "senior"
    can_teach: dict = field(default_factory=dict)       # course_code -> bool
    prior_teaching_counts: dict = field(default_factory=dict)  # course_code -> int
    unavailable_semesters: list = field(default_factory=list)  # [(year, semester), ...]

    def can_teach_course(self, course_code: str) -> bool:
        return bool(self.can_teach.get(course_code, False))

    def is_junior(self) -> bool:
        return self.rank.lower() == "junior"

    def is_senior(self) -> bool:
        return self.rank.lower() == "senior"


@dataclass
class Course:
    code: str
    display_name: str
    category: str  # foundational | upper_div_lab | upper_div_lecture | upper_div_lecture_lab
    is_placeholder: bool = False
    sections_per_semester: dict = field(default_factory=dict)  # {"fall": int, "spring": int}
    flavors: list = field(default_factory=list)  # non-empty only for sci10

    def sections_in(self, semester: str) -> int:
        return self.sections_per_semester.get(semester.lower(), 0)

    def is_solver_assigned(self) -> bool:
        return not self.is_placeholder


@dataclass
class Assignment:
    faculty_name: str
    course_code: str
    year: int
    semester: str   # "fall" | "spring"
    section_number: int
    locked: bool = False
    manual: bool = False
    flavor: Optional[str] = None  # set for sci10 assignments

    @property
    def slot_id(self) -> str:
        return f"{self.course_code}__{self.year}__{self.semester}__{self.section_number}"

    def to_dict(self) -> dict:
        return {
            "faculty_name": self.faculty_name,
            "course_code": self.course_code,
            "year": self.year,
            "semester": self.semester,
            "section_number": self.section_number,
            "locked": self.locked,
            "manual": self.manual,
            "flavor": self.flavor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Assignment":
        return cls(
            faculty_name=d["faculty_name"],
            course_code=d["course_code"],
            year=d["year"],
            semester=d["semester"],
            section_number=d["section_number"],
            locked=d.get("locked", False),
            manual=d.get("manual", False),
            flavor=d.get("flavor"),
        )


@dataclass
class Plan:
    assignments: list = field(default_factory=list)  # list[Assignment]
    year_range: tuple = (1, 3)

    def get_assignment(self, course_code: str, year: int, semester: str, section_number: int) -> Optional[Assignment]:
        for a in self.assignments:
            if (a.course_code == course_code and a.year == year
                    and a.semester == semester and a.section_number == section_number):
                return a
        return None

    def set_assignment(self, assignment: Assignment):
        self.assignments = [
            a for a in self.assignments
            if not (a.course_code == assignment.course_code
                    and a.year == assignment.year
                    and a.semester == assignment.semester
                    and a.section_number == assignment.section_number)
        ]
        self.assignments.append(assignment)

    def remove_assignment(self, course_code: str, year: int, semester: str, section_number: int):
        self.assignments = [
            a for a in self.assignments
            if not (a.course_code == course_code and a.year == year
                    and a.semester == semester and a.section_number == section_number)
        ]

    def faculty_assignments(self, faculty_name: str) -> list:
        return [a for a in self.assignments if a.faculty_name == faculty_name]

    def semester_assignments(self, year: int, semester: str) -> list:
        return [a for a in self.assignments if a.year == year and a.semester == semester]

    def to_dict(self) -> dict:
        return {
            "assignments": [a.to_dict() for a in self.assignments],
            "year_range": list(self.year_range),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            assignments=[Assignment.from_dict(a) for a in d.get("assignments", [])],
            year_range=tuple(d.get("year_range", [1, 3])),
        )
