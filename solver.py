"""CP-SAT solver for course assignment suggestions."""
from collections import defaultdict
from ortools.sat.python import cp_model

from load_calc import section_weight
from models import Assignment

WEIGHT_SCALE = 100


def solve(faculty_list, courses, plan, cfg, year_range=(1, 3)):
    """Fill open (non-locked, non-manual, non-placeholder) slots using CP-SAT.

    Returns a list of new Assignment objects placed by the solver.
    Locked and manual assignments in `plan` are preserved but not returned here.
    """
    model = cp_model.CpModel()
    faculty_by_name = {f.name: f for f in faculty_list}

    semesters = [
        (y, sem)
        for y in range(year_range[0], year_range[1] + 1)
        for sem in ("fall", "spring")
    ]

    pre_counts = _build_pre_counts(faculty_list, courses, plan, semesters)

    # Decision variables: (fname, code, year, sem, sec) -> BoolVar
    x = {}
    slot_vars = defaultdict(list)        # slot_key -> [(fname, var)]
    faculty_sem_vars = defaultdict(list)  # (fname, year, sem) -> [(w_int, var)]

    for year, sem in semesters:
        for code, course in courses.items():
            if course.is_placeholder:
                continue
            for sec in range(1, course.sections_in(sem) + 1):
                if plan.get_assignment(code, year, sem, sec) is not None:
                    continue
                slot_key = (code, year, sem, sec)
                for f in faculty_list:
                    if not f.can_teach_course(code):
                        continue
                    v = model.NewBoolVar(f"{f.name}__{code}__{year}__{sem}__{sec}")
                    vk = (f.name, code, year, sem, sec)
                    x[vk] = v
                    slot_vars[slot_key].append((f.name, v))
                    times = pre_counts[(f.name, code, year, sem)]
                    w_int = round(section_weight(course, f, times, cfg) * WEIGHT_SCALE)
                    faculty_sem_vars[(f.name, year, sem)].append((w_int, v))

    if not slot_vars:
        return []

    # Hard constraint: at most one faculty per slot
    for slot_key, fvars in slot_vars.items():
        model.Add(sum(v for _, v in fvars) <= 1)

    # Hard constraint: junior faculty semester load hard cap
    # Uses full weights (no extra_section_weight_multiplier) — conservative but safe.
    junior_cap_int = round(cfg.get("junior_faculty_hard_cap", 2.0) * WEIGHT_SCALE)
    for f in faculty_list:
        if not f.is_junior():
            continue
        for year, sem in semesters:
            existing = _existing_load_int(f, year, sem, plan, courses, pre_counts, cfg)
            svars = faculty_sem_vars.get((f.name, year, sem), [])
            if not svars:
                continue
            model.Add(
                existing + cp_model.LinearExpr.WeightedSum(
                    [v for _, v in svars], [w for w, _ in svars]
                ) <= junior_cap_int
            )

    # Objective terms
    ow = cfg.get("objective_weights", {})
    w_cov = ow.get("section_coverage", 1000)
    w_jr = ow.get("junior_new_preps", 100)
    w_balance = ow.get("load_balance", 50)
    w_sr_cap = ow.get("senior_over_cap", 75)
    w_flavor = ow.get("sci10_flavor_diversity", 10)
    w_sr_newprep = ow.get("senior_takes_new_preps", 25)

    obj_vars = []
    obj_weights = []

    # 1. Coverage: +w_cov per filled slot
    # at-most-one constraint ensures each slot contributes 0 or 1 to the sum
    for fvars in slot_vars.values():
        for _, v in fvars:
            obj_vars.append(v)
            obj_weights.append(w_cov)

    # 2. Penalize junior new preps
    for (fname, code, year, sem, sec), v in x.items():
        f = faculty_by_name.get(fname)
        if f is None or not f.is_junior():
            continue
        if pre_counts[(fname, code, year, sem)] == 0:
            obj_vars.append(v)
            obj_weights.append(-w_jr)

    # 3. Per-semester load penalties: balance (all faculty) + senior over soft cap.
    # One total_var per (faculty, year, sem) so both terms share the same aux variable.
    senior_cap_int = round(cfg.get("senior_faculty_soft_cap", 2.0) * WEIGHT_SCALE)
    target_per_sem_int = round(cfg.get("target_annual_load", 4.0) / 2 * WEIGHT_SCALE)
    for f in faculty_list:
        for year, sem in semesters:
            svars = faculty_sem_vars.get((f.name, year, sem), [])
            if not svars:
                continue
            existing = _existing_load_int(f, year, sem, plan, courses, pre_counts, cfg)
            max_total = existing + sum(w for w, _ in svars)
            need_balance = max_total > target_per_sem_int
            need_sr_cap = f.is_senior() and max_total > senior_cap_int
            if not need_balance and not need_sr_cap:
                continue

            total_var = model.NewIntVar(existing, max_total, f"semload_{f.name}_{year}_{sem}")
            model.Add(
                total_var == existing + cp_model.LinearExpr.WeightedSum(
                    [v for _, v in svars], [w for w, _ in svars]
                )
            )
            if need_balance:
                # over_target = max(0, total - target): penalise overloading any faculty
                over_target = model.NewIntVar(0, max_total, f"over_target_{f.name}_{year}_{sem}")
                model.Add(over_target >= total_var - target_per_sem_int)
                obj_vars.append(over_target)
                obj_weights.append(-w_balance)
            if need_sr_cap:
                # over_cap = max(0, total - senior_cap): additional penalty for seniors
                over_cap = model.NewIntVar(0, max_total, f"over_cap_{f.name}_{year}_{sem}")
                model.Add(over_cap >= total_var - senior_cap_int)
                obj_vars.append(over_cap)
                obj_weights.append(-w_sr_cap)

    # 4. sci10 flavor diversity: bonus for each flavor present per semester
    for year, sem in semesters:
        for flavor in ("health", "neuro", "earth"):
            fvars_fl = [
                v for (fname, code, y2, s2, _sec), v in x.items()
                if code == "sci10" and y2 == year and s2 == sem
                and faculty_by_name.get(fname, {}) != {}
                and faculty_by_name[fname].can_teach.get(f"sci10_{flavor}", False)
            ]
            if not fvars_fl:
                continue
            has_fl = model.NewBoolVar(f"has_{flavor}_{year}_{sem}")
            # has_fl = OR(fvars_fl)
            model.Add(sum(fvars_fl) >= has_fl)
            for v in fvars_fl:
                model.AddImplication(v, has_fl)
            obj_vars.append(has_fl)
            obj_weights.append(w_flavor)

    # 5. Reward senior faculty taking brand-new lab preps
    lab_cats = {"upper_div_lecture_lab", "upper_div_lab"}
    for (fname, code, year, sem, sec), v in x.items():
        f = faculty_by_name.get(fname)
        if f is None or not f.is_senior():
            continue
        course = courses.get(code)
        if course is None or course.category not in lab_cats:
            continue
        if pre_counts[(fname, code, year, sem)] == 0:
            obj_vars.append(v)
            obj_weights.append(w_sr_newprep)

    model.Maximize(cp_model.LinearExpr.WeightedSum(obj_vars, obj_weights))

    cp_solver = cp_model.CpSolver()
    cp_solver.parameters.max_time_in_seconds = 25.0
    status = cp_solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return []

    result = []
    for (fname, code, year, sem, sec), v in x.items():
        if cp_solver.Value(v) != 1:
            continue
        f = faculty_by_name.get(fname)
        flavor = None
        if code == "sci10" and f:
            for fl in ("health", "neuro", "earth"):
                if f.can_teach.get(f"sci10_{fl}"):
                    flavor = fl
                    break
        result.append(Assignment(
            faculty_name=fname,
            course_code=code,
            year=year,
            semester=sem,
            section_number=sec,
            locked=False,
            manual=False,
            flavor=flavor,
        ))

    return result


def _build_pre_counts(faculty_list, courses, plan, semesters):
    """Cumulative counts before each semester: prior history + locked/manual in order."""
    pre = {}
    for f in faculty_list:
        running = dict(f.prior_teaching_counts)
        for year, sem in semesters:
            for code in courses:
                pre[(f.name, code, year, sem)] = running.get(code, 0)
            for a in plan.assignments:
                if a.faculty_name == f.name and a.year == year and a.semester == sem:
                    running[a.course_code] = running.get(a.course_code, 0) + 1
    return pre


def _existing_load_int(faculty, year, sem, plan, courses, pre_counts, cfg):
    """Scaled integer load from locked/manual assignments for this faculty this semester."""
    total = 0
    for a in plan.assignments:
        if a.faculty_name != faculty.name or a.year != year or a.semester != sem:
            continue
        course = courses.get(a.course_code)
        if course is None:
            continue
        times = pre_counts.get((faculty.name, a.course_code, year, sem), 0)
        total += round(section_weight(course, faculty, times, cfg) * WEIGHT_SCALE)
    return total
