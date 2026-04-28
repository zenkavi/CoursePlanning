---
name: review-test
description: Evaluates the quality of a test file against a rubric of common testing pitfalls. Invoke with `/review-test <test-file-path> [<implementation-file-path>]` to get a report on the test's strengths, weaknesses, and coverage gaps.
---

## Setup

**Input**: `$ARGUMENTS` — a test file path, optionally followed by the implementation file path.

**Step 1 — Read the files.**
- Read the test file at the given path.
- If an implementation path was also given, read it. Otherwise, infer it: strip test-specific suffixes or prefixes from the test filename (e.g., `.spec`, `.test`, `_test`, `test_`, `Test`, `Spec`) and search for a matching source file at the corresponding path depth. Read it if found; proceed without it if not.

**Step 2 — Identify the unit under test.**
Note: what class, function, or module is being tested, and what its core responsibilities are.

**Step 3 — Evaluate.**
Apply every rule in the rubric below. For each finding, record:
- Severity (SEVERE / HIGH / MEDIUM / LOW / INFO)
- A short title
- Which test(s) or section is affected (quote the test name or line reference)
- What the problem is and why it matters
- A concrete suggestion to fix it (prose, not necessarily full rewrite)

**Step 4 — Output the report** in the format shown at the end of this file.

---

## Evaluation Rubric

### Suite-Level Rules (assess the test file as a whole against the implementation)

**[HIGH] Missing error-path coverage**
If the implementation can throw, reject, or return an error state, there must be at least one test exercising that path. Look for: `throw`, `reject`, `catch`, exception handling, error callbacks, non-2xx status handling, error return values. Flag each untested error path.

**[HIGH] Missing branch coverage**
If the implementation has `if/else`, `switch`, ternary, short-circuit operators (`&&`, `||`), or guard clauses, each meaningful branch should be exercised. Identify branches in the implementation that have no corresponding test.

**[MEDIUM] Missing edge cases**
For any function that accepts collections, optional fields, or numeric boundaries: are empty collections, null/absent inputs, zero, or boundary values tested? Flag absent but obvious edge cases.

**Escalation**: After identifying a missing edge case, check whether the current implementation actually has a bug for that input — i.e., if the test were written and run today, it would fail. If so, escalate severity by at least 1 level (MEDIUM → HIGH minimum). If the latent bug has high impact (data loss, silent incorrect output, security implication), escalate to SEVERE. Call out both the missing test and the bug in the finding.

**[MEDIUM] Test-to-behavior alignment**
Do the tests collectively document what the unit *does* (its contract), or do they only happen to exercise some of its code? A reader should be able to understand the unit's behavior from reading only the test names.

---

### Severity Scale
- **SEVERE** — Test is structurally broken: it can pass even when the code under test is wrong. Zero detection value.
- **HIGH** — Test has a meaningful gap: it will miss real regressions or cause false failures due to fragility.
- **MEDIUM** — Test is correct but brittle or unclear: it will create maintenance burden or obscure failure diagnosis.
- **LOW** — Style or preference: test communicates poorly but will still catch the right things.
- **INFO** — Suggestion for improvement, no defect.

---

### Per-Test Rules (evaluate each test case individually)

**[SEVERE] Tautological assertion — test can never fail**
Flag any of:
- Asserting on a mock's or stub's own configured return value without the code under test transforming or validating it. The test exercises the mocking framework, not the unit.
- Asserting on a constant or literal that was hard-coded in the test (e.g., asserting `1 + 1 == 2`).
- Asserting on an object that was constructed in the test itself, where the result under test is that same object reference.

**[SEVERE] Unawaited or unhandled async assertion**
An async test that asserts on a promise or future without properly awaiting or returning the assertion **always passes**, even if the operation resolves incorrectly. The test runner resolves the test function before the assertion runs. Flag any async assertion not properly awaited, returned, or chained to the test's result.

Examples of the pattern across languages:
```js
// JavaScript (Mocha + chai-as-promised) — missing await
it('rejects on error', () => {
  expect(doWork()).to.be.rejectedWith(Error); // always passes — not awaited
});
// Fix: add await or return
```
```python
# Python (pytest-asyncio) — missing await
async def test_raises_on_error():
    with pytest.raises(ValueError):
        doWork()  # coroutine never awaited — pytest.raises block exits immediately
# Fix: await doWork()
```
```java
// Java (JUnit 5) — exception from CompletableFuture not unwrapped
assertThrows(MyException.class, () -> future.get()); // throws ExecutionException, not MyException
// Fix: unwrap or use assertThatThrownBy(...).hasCause(...)
```

**[HIGH] Test verifies implementation, not behavior**
A test's assertions should verify *observable outcomes* — return values, thrown errors, state changes, or externally visible side effects — not internal wiring.

Specifically flag:
- Using spy/mock call-count assertions as the **primary or only** assertion when the test's stated purpose is behavioral (e.g., "Should return cached value" but the only assertion checks whether a method was called once).
- Exception: call-count assertions ARE appropriate when the test is *explicitly about* call frequency — e.g., testing deduplication, idempotency, or guard clauses that skip work.
- Asserting that a private/internal method was called, rather than asserting what effect it caused.

**[HIGH] Shared mutable state without isolation**
Flag any of:
- Variables declared at suite scope that are mutated in setup hooks but also directly mutated inside individual test cases — later tests may inherit dirty state.
- Using a once-per-suite setup hook (e.g., `before`, `setUpClass`, `@BeforeAll`) instead of a per-test hook to initialize stubs or objects that should be fresh per test.
- Any mock, stub, or spy created outside per-test setup without a corresponding teardown that resets it.

**[HIGH] Missing mock/stub teardown**
If mocks, stubs, or spies are set up anywhere in the file, there must be a corresponding teardown after each test (e.g., in `afterEach`, `tearDown`, `@AfterEach`). If teardown is missing or only present in some suites but not all that need it, flag it. Without teardown, mocks from one test bleed into subsequent tests and cause unpredictable failures.

This applies to any mocking approach: manual monkey-patching, test doubles, spy libraries, or framework-level mocking utilities. Each requires cleanup appropriate to how it was set up.

**[MEDIUM] Vague test name**
A test name should describe two things: (1) the scenario or precondition, and (2) the expected outcome. Names like "Should work", "Should handle error", "Should return data", "Should process correctly" fail this.

Better: "Should return null when item is not found in cache", "Should throw an error with status 500 when upstream returns 500".

Flag names that omit the condition, the outcome, or both.

**[MEDIUM] Too many unrelated concerns in one test**
A test that verifies the return value AND validates multiple call arguments AND checks a side effect is covering multiple concerns. If a future refactor changes one of those, the test failure is harder to diagnose. Flag tests asserting more than one logical concern — unless those concerns are inherently coupled (e.g., verifying the URL passed to an HTTP call IS the behavior for a URL-construction function).

**[MEDIUM] Brittle over-specification**
Flag tests that will fail on a refactor that doesn't change observable behavior:
- Asserting exact argument shapes of internal calls when the test's contract is about the output.
- Asserting call order when order is not part of the contract.
- Hard-coding implementation details (specific internal paths, private method names) in assertions.

**[MEDIUM] Overly broad equality assertion on the entire result**
Asserting deep equality on an entire response object when the test is only verifying one or two properties ties the test to the complete shape of the response. Adding any new field to that object — even for an unrelated feature — will break this test.

Prefer partial/subset assertions when the test is only about a subset of the result's properties. Reserve full equality assertions for cases where the complete shape is the contract — for example, a data mapper that must produce exactly a specific structure, or a serializer where extra fields would be a bug.

```js
// JavaScript — fragile
expect(response).to.deep.equal({ uri: testUri, hash: expectedHash, bytes: 26 });
// resilient
expect(response).to.deep.include({ hash: expectedHash, bytes: 26 });
```
```python
# Python — fragile
assert response == {"uri": test_uri, "hash": expected_hash, "bytes": 26}
# resilient
assert response["hash"] == expected_hash
assert response["bytes"] == 26
# or with pytest: assert {"hash": expected_hash} <= response  (subset check)
```
```java
// Java (AssertJ) — fragile
assertThat(response).isEqualTo(new Response(testUri, expectedHash, 26));
// resilient
assertThat(response).extracting("hash", "bytes").containsExactly(expectedHash, 26);
```

**[LOW] Weak assertion specificity**
Prefer the most specific assertion that meaningfully exercises the behavior: exact values over truthiness, typed matchers over existence checks, specific error classes over generic exception types. Flag tests where a stronger assertion is clearly possible and would catch more regressions.

```js
// JavaScript — weak → strong
expect(result).to.be.ok          // → expect(result).to.equal(true)
expect(result).to.exist          // → expect(result).to.deep.include({ id: 42 })
```
```python
# Python — weak → strong
assert result                    # → assert result is True
assert result is not None        # → assert result == {"id": 42}
```
```java
// Java (AssertJ) — weak → strong
assertThat(result).isNotNull();          // → assertThat(result).isEqualTo(expected)
assertThat(flag).isTrue();               // fine — but prefer assertThat(result.getId()).isEqualTo(42)
```

**[LOW] Overly broad exception catch in test**
Using a try/catch (or equivalent) in a test that catches all exceptions and then asserts on `message` — if the code throws for the wrong reason, the test still passes. Prefer the assertion utilities provided by your testing framework that assert both exception type and message.

```js
// JavaScript (chai-as-promised)
await expect(doWork()).to.be.rejectedWith(MyError, 'expected message');
```
```python
# Python (pytest)
with pytest.raises(MyError, match="expected message"):
    do_work()
```
```java
// Java (JUnit 5)
assertThrows(MyException.class, () -> doWork(), "expected message");
// or with AssertJ:
assertThatThrownBy(() -> doWork()).isInstanceOf(MyException.class).hasMessageContaining("expected");
```

**[INFO] Suggestion for additional test**
Note any non-obvious scenario that the tests don't cover but would meaningfully increase confidence (not just coverage for its own sake).

---

## Output Format

```
## Test Quality Report: <filename>

### Unit Under Test
<One sentence: what this module/class does>

### Overall Assessment
<2–3 sentences: quality level, most significant gaps, what the tests do well>

---

### Findings

#### [SEVERITY] <Short title>
**Affects**: `<test name>` / suite-level
**Problem**: <What is wrong and why it matters>
**Suggestion**: <What to do instead>

[repeat for each finding, ordered by severity then by position in file]

---

### Coverage Assessment
**Covered scenarios**: <brief list>
**Missing scenarios**: <list of untested paths, branches, or edge cases>
```

Omit sections with no findings. If there are no findings at a severity level, don't include a placeholder — just list only what you found. If the test file is high quality, say so clearly and explain why.
