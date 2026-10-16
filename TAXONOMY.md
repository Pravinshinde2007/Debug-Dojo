# Debug Dojo — Mistake Taxonomy & Detection Specification

Debug Dojo models beginner programming errors through a deterministic, multi-signal taxonomy. Rather than presenting generic stack traces or relying purely on probabilistic LLMs, the platform combines **targeted unit test inputs**, **in-memory AST analysis**, **captured return values vs. standard output**, and **argument mutation tracking**.

---

## 1. The Five Mistake Categories

### 1. `off_by_one`
- **Definition:** The learner's loop range or slice indices are shifted by one position, leading to starting at index 0 instead of 1, missing the final element, or taking the wrong number of elements.
- **Typical Manifestations:**
  - `range(n)` instead of `range(1, n + 1)` in `first_n_squares` (starts with 0, missing $n^2$).
  - `items[mid - 1 : mid + 1]` in `middle_three` (yields 2 elements instead of 3 due to half-open slicing).
  - Slicing `marks[-k:]` with $k = 0$ in `last_k_total`, where `marks[-0:]` evaluates to `marks[0:]` (the whole list).
- **Detection Method:** Detected when the returned list length is off by $\pm 1$, output starts with 0 for positive integer ranges, or slice boundaries omit the target end index.

### 2. `unhandled_short_input`
- **Definition:** The code operates correctly on regular inputs but fails, crashes, or raises unhandled exceptions on small, empty, or boundary collections.
- **Typical Manifestations:**
  - `IndexError` when calculating manual loop ranges `len(marks) - k` when `k > len(marks)`.
  - `ZeroDivisionError` when averaging empty or null-filled reading lists in `safe_average`.
  - Crashing on single-element or 2-element lists in `middle_three`.
- **Detection Method:** Evaluates visible and hidden tests on empty and sub-boundary cases (`[]`, $k > \text{len}$, singletons). If normal cases pass but boundary inputs trigger exceptions or incorrect outputs, the tag is assigned.

### 3. `print_not_return`
- **Definition:** The learner uses `print()` to output values to the console rather than `return` to pass the result back to the caller.
- **Typical Manifestations:**
  - `print(count)` at the end of `count_passes` with no return statement.
- **Detection Method:** The sandbox runner intercepts `sys.stdout` and `sys.stderr` independently from the function's return value. If `printed_output` is non-empty while the function returned `None` for a test expecting non-None, or if AST parsing finds `print()` with no valid `return`, the tag is flagged.

### 4. `boundary_comparison`
- **Definition:** The learner confuses strict inequalities with inclusive inequalities at numerical thresholds.
- **Typical Manifestations:**
  - Using `mark > 40` instead of `mark >= 40` in `count_passes`.
  - Strictly clamping using `>` and `<` in `clamp_score` without handling equal boundaries.
- **Detection Method:** Targeted test case evaluation where an input sits precisely on the boundary threshold (e.g., mark $= 40$). If surrounding cases pass but the exact boundary fails, or AST analysis detects `> 40` without `>= 40`, the tag is assigned.

### 5. `mutates_input`
- **Definition:** The learner modifies the caller's argument in-place when the specification requires returning a new list without side effects.
- **Typical Manifestations:**
  - Using `.pop(0)` or `.pop()` in a `while len(items) > 3:` loop in `middle_three`.
  - Mutating `marks` or `nums` in place using `.remove()`, `.clear()`, or `del`.
- **Detection Method:** The sandbox runner takes a `copy.deepcopy()` of all arguments before calling the learner's function. After execution, the runner checks `args_for_call != args_before`. If the argument was modified, `mutated_input: True` is flagged and the test fails if rules prohibit mutation.

---

## 2. Recurring Mistake Threshold & Mastery Impact

- **Recurring Threshold:** A mistake category is classified as **recurring** if and only if it appears across **at least two different challenges** for the same learner:
  $$\text{Count}(\text{DISTINCT challenge\_id where mistake was detected}) \ge 2$$
- **Mastery Impact:**
  - Independent solution with zero hints: $+10$ points to concept mastery (capped at 100).
  - Solution using hints: $+5$ points.
  - Failure / repeated mistake: $-3$ points (floored at 0).
- **Challenge Recommendation:** The recommendation algorithm heavily weights challenges ($+45$ score boost) that address the learner's recurring mistakes and lowest concept scores, and provides a clear, human-readable justification.
