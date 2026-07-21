# Lesson 43 — Coverage & CI

> **Goal of this lesson:** Measure how much of your code your tests actually exercise with **`pytest-cov`**, understand what coverage does and does **not** prove, and run your tests **automatically on every push** with **GitHub Actions**. This closes Phase 5: you can now write tests, isolate them, measure them, and automate them.
>
> `main.py` has an intentionally-untested branch so the coverage report shows a real gap; `ci.yml` is a working GitHub Actions workflow.

---

## 1. Where We Are

You can write tests (Lesson 40), test protected endpoints (Lesson 41), and isolate database tests (Lesson 42). Two questions remain:

1. **How much** of my code is actually tested? → **coverage**.
2. How do I make sure tests **always run** (not just when I remember)? → **CI**.

---

## 2. What Is Test Coverage?

**Coverage** measures what fraction of your code runs while your tests execute. If a line never runs during any test, it's **uncovered** — nothing verifies it.

```
40 statements, 34 executed by tests  ->  85% coverage
                6 never run          ->  untested (a blind spot)
```

Coverage is a **map of your blind spots**: it points at code no test touches, so you know where bugs can hide unnoticed.

> 🔑 Coverage tells you what your tests **don't** touch. High coverage doesn't prove correctness — but **low** coverage definitely proves you have untested code.

---

## 3. `pytest-cov` — Measuring Coverage

**`pytest-cov`** plugs coverage measurement into pytest. Install it and add `--cov`:

```bash
pip install pytest-cov

pytest --cov=main                    # coverage for the `main` module
pytest --cov=. --cov-report=term-missing   # show which LINES are missing
pytest --cov=. --cov-report=html     # generate a browsable HTML report
```

A `term-missing` report looks like this:

```
Name      Stmts   Miss  Cover   Missing
---------------------------------------
main.py      40      6    85%   52-57
---------------------------------------
TOTAL        40      6    85%
```

- **Stmts** — total statements.
- **Miss** — statements no test ran.
- **Cover** — the percentage.
- **Missing** — the exact line numbers never executed (here, lines 52–57).

That `Missing` column is the gold: it tells you **precisely** which lines to write a test for.

> 🔑 Use **`--cov-report=term-missing`** — the missing line numbers turn "you have a gap" into "write a test for lines 52–57." The HTML report (`--cov-report=html`) is great for browsing a big codebase.

---

## 4. What Coverage Does NOT Tell You

This is the most important part. **100% coverage does not mean bug-free.** Coverage only checks that a line **ran** — not that you **asserted** the right thing about it.

```python
def add(a, b):
    return a - b          # BUG: subtracts instead of adds

def test_add():
    add(2, 2)             # runs the line -> 100% coverage...
    # ...but no assert! The bug sails through.
```

This test gives `add` 100% coverage yet catches nothing, because it never asserts the result. Coverage measures **execution**, not **verification**.

| Coverage tells you | Coverage does NOT tell you |
|---|---|
| Which lines ran during tests | Whether your assertions are meaningful |
| Where the untested gaps are | Whether the code is correct |
| A floor for test quality | That edge cases are handled |

> 🔑 Treat coverage as a **necessary-but-not-sufficient** signal. 100% coverage with weak assertions is worse than 80% with sharp ones. Aim for good coverage **and** real assertions — never game the number.

---

## 5. Line vs Branch Coverage

- **Line (statement) coverage** — did each line run? (the default)
- **Branch coverage** — did each **decision path** run? An `if` with no `else` has two branches; a test that only hits the `True` side leaves the `False` branch uncovered even if every *line* ran.

```bash
pytest --cov=. --cov-branch     # measure branch coverage too
```

Branch coverage is stricter and catches "I tested the happy path but never the error path." Turn it on for a more honest number.

---

## 6. Coverage Targets and `fail_under`

Teams pick a **target** (commonly 80–90%) and let the build **fail** if coverage drops below it:

```bash
pytest --cov=. --cov-fail-under=80     # exit non-zero if under 80%
```

Or configure it once:

```ini
# pyproject.toml or .coveragerc
[tool.coverage.report]
fail_under = 80
```

> 💡 Don't chase **100%** dogmatically — the last few percent (defensive branches, `__repr__`s, unreachable guards) often cost more than they're worth. A pragmatic **80–90%** with strong assertions on critical paths beats a gamed 100%.

### Excluding code

Some lines legitimately shouldn't count (a `__main__` block, an unreachable guard). Mark them:

```python
if __name__ == "__main__":   # pragma: no cover
    uvicorn.run(app)
```

Use `# pragma: no cover` sparingly and honestly — not to hide real gaps.

---

## 7. What Is CI?

**Continuous Integration (CI)** means: every time code is pushed (or a pull request is opened), an automated system **runs your tests** (and linters, coverage, etc.) on a clean machine. If anything fails, you find out **immediately** — before the broken code merges.

```
push / PR  ──►  CI server: fresh machine
                  1. check out the code
                  2. install dependencies
                  3. run pytest (+ coverage)
                  4. ✅ pass -> allow merge   |   ❌ fail -> block, notify
```

Why it matters:

- Tests run **automatically**, not just when someone remembers.
- Runs on a **clean environment** — catches "works on my machine" (missing dependency, wrong Python version).
- A red build **blocks the merge**, keeping the main branch green.

> 🔑 CI turns "I ran the tests locally (I think)" into "the tests provably pass on a clean machine on every change." It's the automation that makes a test suite actually protect the codebase.

---

## 8. GitHub Actions Basics

**GitHub Actions** is GitHub's built-in CI. You describe a **workflow** in a YAML file at **`.github/workflows/`**. The structure:

```yaml
name: CI                          # workflow name

on: [push, pull_request]          # WHEN it runs: on push and on PRs

jobs:                             # one or more jobs
  test:                           # a job named "test"
    runs-on: ubuntu-latest        # the machine to run on
    steps:                        # ordered steps
      - uses: actions/checkout@v4          # 1. check out your code
      - uses: actions/setup-python@v5      # 2. install Python
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt   # 3. install deps
      - run: pytest --cov=. --cov-report=term-missing --cov-fail-under=80  # 4. test
```

| Key | Meaning |
|---|---|
| `on` | The events that trigger the workflow (`push`, `pull_request`, schedule, …) |
| `jobs` | Independent units of work, run in parallel by default |
| `runs-on` | The runner OS (`ubuntu-latest`, `windows-latest`, …) |
| `steps` | Ordered actions: `uses:` runs a prebuilt action, `run:` runs a shell command |
| `actions/checkout` | The action that clones your repo onto the runner |
| `actions/setup-python` | Installs a specific Python version |

When you push, GitHub spins up a fresh Ubuntu machine, runs these steps, and shows a green check or red X on your commit/PR.

> 🔑 A GitHub Actions workflow is just **"on these events, on this machine, run these steps."** For a FastAPI app the steps are almost always: checkout → setup Python → install deps → run `pytest`.

---

## 9. A Matrix — Testing Multiple Versions

CI can run the same job across several Python versions in parallel with a **matrix**:

```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -r requirements.txt
      - run: pytest
```

This runs your whole suite three times (once per version) simultaneously, catching version-specific breakage.

---

## 10. Real-World Use Case — A Protected Main Branch

Your team's repo requires a **green CI check to merge**. A developer opens a PR that accidentally breaks the auction API's bid validation. Before anyone reviews it:

- GitHub Actions checks out the branch, installs deps, runs `pytest` on a clean Ubuntu machine.
- The bid-validation test fails → the PR shows a **red X** → GitHub **blocks the merge**.
- The developer sees the failure, fixes it, pushes again → CI re-runs → green → merge allowed.

The broken code **never reaches main**. Coverage in the same run flags if the new feature added untested lines. This is how professional teams keep a large codebase from rotting — the machine enforces the test discipline on every change.

---

## 11. Mini Task

This lesson ships an app with a deliberate coverage gap and a CI workflow.

1. Install: `pip install fastapi uvicorn httpx pytest pytest-cov`
2. Run coverage:
   ```bash
   pytest --cov=main --cov-report=term-missing
   ```
   Note the coverage is **below 100%** — read the `Missing` column to see which lines aren't tested (an endpoint the tests skip on purpose).
3. **Close the gap:** add a test for the untested endpoint, re-run, and watch coverage rise (toward 100%).
4. Try branch coverage: `pytest --cov=main --cov-branch --cov-report=term-missing`.
5. Enforce a floor: `pytest --cov=main --cov-fail-under=90` and see it fail (or pass) against the threshold.
6. Read `ci.yml` — the GitHub Actions workflow. In a real repo it lives at `.github/workflows/ci.yml` and runs on every push.
7. **Prove coverage ≠ correctness:** add a test that *calls* an endpoint but asserts nothing; watch coverage go up while the test verifies nothing. Then add real assertions.
8. **Bonus:** Add a `matrix` to `ci.yml` for Python 3.11 and 3.12.

---

## 12. Common Mistakes

| Mistake | Fix |
|---|---|
| Treating 100% coverage as "bug-free" | Coverage measures execution, not correctness; assert meaningfully. |
| Chasing 100% with assertion-free tests | Gaming the number hides risk; write real assertions. |
| Only line coverage | Add `--cov-branch` to catch untested decision paths. |
| Overusing `# pragma: no cover` | Exclude only truly untestable lines, not real gaps. |
| No CI (tests only run locally) | Add a GitHub Actions workflow to run tests on every push. |
| CI passing with no dependencies pinned | Install from a pinned `requirements.txt` for reproducibility. |
| Workflow file in the wrong place | It must live in `.github/workflows/`. |

---

## 13. Key Takeaways

- **Coverage** = the fraction of your code that runs during tests; it maps your **blind spots**.
- **`pytest-cov`**: `pytest --cov=. --cov-report=term-missing`; the **Missing** column names the exact untested lines.
- **Coverage ≠ correctness** — a line can run with no meaningful assertion. Aim for good coverage **and** sharp assertions; never game the number.
- Prefer **branch coverage** (`--cov-branch`) for a stricter, more honest measure.
- Pick a pragmatic target (**80–90%**), enforce with **`--cov-fail-under`**, and exclude only truly untestable lines with `# pragma: no cover`.
- **CI** runs your tests automatically on every push/PR on a clean machine, blocking broken code from merging.
- **GitHub Actions**: a YAML workflow in `.github/workflows/` — `on` events, `jobs`, `runs-on`, `steps` (checkout → setup Python → install → `pytest`). A **matrix** tests multiple versions.

---

## 🎉 Phase 5 Complete

You can now write endpoint and database tests, isolate them with fixtures and overrides, measure them with coverage, and enforce them with CI. Your APIs are no longer "I think it works" — they're provably, automatically verified on every change.

## ➡️ Next Lesson

**Lesson 44 — Project Structure (Production)** (start of Phase 6)
- Organizing a real FastAPI app: `api/`, `core/`, `models/`, `schemas/`, `services/`, `db/`
- Separation of concerns at scale
- The layout production codebases actually use
