---
name: check-coverage
description: Maps SPEC.md sections to their corresponding test files and reports which parts of the spec have test coverage vs which are untested. Invoke with /check-coverage when you want to know whether a feature described in the spec is actually exercised by tests, or to find coverage gaps before committing a step as done.
---

# SPEC → Test Coverage Report

Produce a coverage map showing which parts of `SPEC.md` are backed by tests in `tests/`.

## How to do it

### 1. Extract testable units from SPEC.md

Read `SPEC.md` and list the concrete, testable claims. Focus on these sections:

- **Data Model** — each dataclass and its fields
- **Courses** — the course table (codes, categories, section counts)
- **CSV Column Mapping** — each mapping (e.g. `sci11 organic` → `sci111`)
- **Constraints** — hard, hard-with-flag, and soft
- **Load Calculation** — weight rules, extra-section multiplier, cumulative counts
- **Configurable Parameters** — each config key's effect

Skip sections that aren't testable in isolation (UI layout, setup instructions, build order).

### 2. Walk the test files

Use `Grep` to scan `tests/test_*.py` for test function names and their assertions. Don't just list filenames — read each test function's name and decide what claim it exercises. A test called `test_cumulative_counts_carry_forward` covers the "cumulative counts" invariant; `test_sci11_maps_to_sci111` covers one row of the CSV Column Mapping.

### 3. Map tests to SPEC claims

Build a table. For each SPEC claim, list the covering test(s) or mark it uncovered. Group by SPEC section.

### 4. Report

Format the output as a table, then a gap list. Example:

```
# Coverage Report

## Data Model
| Claim                                | Test(s)                                    |
|--------------------------------------|--------------------------------------------|
| Faculty.can_teach includes sci10     | test_faculty_can_teach_generic_sci10       |
| Faculty.prior_teaching_counts loads  | test_load_teaching_history                 |
| Course.flavors non-empty for sci10   | ⚠ UNCOVERED                                |

## CSV Column Mapping
| Claim                           | Test(s)                            |
|---------------------------------|------------------------------------|
| sci11 organic → sci111          | test_sci11_maps_to_sci111          |
| sci30a chem1 → sci30a           | test_csv_column_stripping          |
| sci10 health → sci10_health     | ⚠ UNCOVERED                        |

## Load Calculation
(...)

## Summary

- 23 SPEC claims covered by tests
- 6 claims UNCOVERED (listed below)
- 4 tests don't clearly map to a SPEC claim — may be implementation details or the SPEC may need updating

### Uncovered claims
1. Course.flavors non-empty only for sci10
2. sci10 health / neuro / earth individual mapping
3. Extra-section multiplier applies per-course-per-semester (only tested for same course)
...

### Tests without clear SPEC backing
1. tests/test_load_calc.py::test_weight_zero_for_unknown_category — SPEC doesn't specify this
...
```

## Guidelines

- **A claim can be covered by multiple tests.** List all of them when that's the case.
- **A test can cover multiple claims.** That's fine; list it under each.
- **"UNCOVERED" is a factual claim.** Don't hedge ("probably not covered", "couldn't find"). If grep didn't find it, say UNCOVERED. If you're genuinely unsure, say so explicitly.
- **Tests without SPEC backing are worth flagging.** They're either testing implementation details (fine) or the SPEC is underspecified (worth noting).
- **Do not propose new tests.** That's the main thread's job. Your job is the map.
- **Do not run the tests.** Coverage here is about "is there a test for this claim," not "does the test pass." `test-runner` handles pass/fail.

## When to use

- Before marking a step complete in `PROGRESS.md`
- When SPEC gets updated and you want to know which new claims need tests
- When onboarding someone new — the gap list tells them where to focus

## Project-specific notes

- The SPEC's "MVP Build Order" lists steps but isn't itself a set of testable claims — skip it.
- `solver.py` doesn't exist yet (Step 8+). The soft constraints and objective weights can't be covered until it does; flag them as "pending implementation" rather than "UNCOVERED".
- Route-level tests don't exist yet either. Flask endpoint behavior is currently only tested implicitly through manual use.