# Debug Dojo — Implementation Progress 🥋

## System Status: ALL STAGES COMPLETE & PASSING (21/21 Tests Passed) ✅

### 1. Frontend Foundation & Realistic 3D "Night-Time Dojo" UI ✅
- **Design Tokens & Theme (`tokens.css`)**: Dark theme (background `#0F1420`, glass surface `#171E2E`, editor `#0B0F19`, vermilion `#FF6B4A`, teal `#2DD4BF`).
- **Accessible Component Library**: `GlassPanel`, `Button`, `OutcomePill`, `Tag`, `Badge`, `Toggle`, `Tooltip`, `Skeleton`, `ToastContainer`, `SettingsPopover`.
- **Interactive 3D Dojo Scene (`DojoScene.tsx`)**:
  - Wet-stone reflective floor (`MeshReflectorMaterial`).
  - Timber architecture and backlit shoji screens.
  - Swaying, flickering paper lanterns + 4 Progressive Hint Lanterns that ignite as hints unlock.
  - Floating drifting embers & exponential fog (`#0F1420`).
  - Bloom & vignette post-processing with dynamic mood reactions (`running`, `success`, `error`).
- **Performance & A11y**: Auto-FPS adaptation (3 tiers), low-power mode, `prefers-reduced-motion` compliance, WebGL fallback.
- **Production Build**: Verified with `npm run build` (0 TypeScript errors).

---

### 2. Sandboxed Python Runner & Security Hardening (`runner.py`, `worker.py`) ✅
- **Rule 1 (Child Process Isolation)**: Learner code *never* runs inside server process. Executed in isolated child subprocess via `worker.py`.
- **Resource Limits**:
  - Max code size: 16KB limit.
  - Execution timeout: 2.0s per test (kills infinite loops).
  - Stdout capture cap: 4KB limit. Exceeding triggers `runtime_error: Output limit exceeded (max 4KB)`.
- **Security Sandboxing**:
  - Restricts socket connections (`socket.socket = None`), fork/subprocess spawning (`os.fork`, `os.system = None`).
  - Strict audit hooks in Python 3.11+.
  - Input mutation detection via `copy.deepcopy` comparison before and after execution.
- **Rule 2 (Confidential Hidden Tests)**: Hidden test inputs, expected values, learner outputs, and internal traces are strictly stripped from all API outputs.
- **Rule 3 (Strict Outcomes)**: Every test receives exactly one outcome: `passed`, `wrong_output`, `runtime_error`, or `timeout`.

---

### 3. Mistake Taxonomy Engine (`tagger.py`) ✅
- **Deterministic Multi-Signal Detection**:
  - `off_by_one`: Indexing / slicing / range / off-by-one numeric errors.
  - `unhandled_short_input`: Zero/empty/singleton input failures when general cases pass.
  - `print_not_return`: Function calls `print()` and returns `None` when expecting values.
  - `boundary_comparison`: Strict inequality (`>`) where inclusive comparison (`>=`) is required.
  - `mutates_input`: Illegally modifies passed list/dict argument in place (`.pop()`, `.append()`, etc.).
- **AST Code Analysis**: Node visitor inspects AST tree for prints, ranges, comparisons, mutating calls.
- **TAXONOMY.md**: Comprehensive mistake taxonomy guide with signals, triggers, and examples.

---

### 4. Progressive 4-Level Hint Ladder & Leak Guard (`explain.py`, `llm.py`) ✅
- **Four Distinct Hint Levels**:
  - Level 1: "Where to look" (nudge towards concept without mentioning solution).
  - Level 2: "What to question" (directs attention to edge cases or boundary logic).
  - Level 3: "Concrete invariant" (explains rule/invariant to check without code).
  - Level 4: "Structural recipe" (plain language steps, zero solution code).
- **Leak Guard**:
  - Strict regex and AST scanner rejects any generated hint containing function definitions, return statements, variable assignments, list comprehensions, or forbidden code syntax.
  - Automatic fallback to safe, curated progressive hints.
- **Logging**: Every prompt/response logged to `logs/llm.jsonl` (with `/tmp/logs/llm.jsonl` fallback for Vercel).

---

### 5. Learner Tracking & Adaptive Recommendations (`learner.py`, `db.py`) ✅
- **Mastery Calculation**:
  - +10 pts for first-try pass without hints.
  - +5 pts for pass after hints.
  - -3 pts for failed submission.
- **Recurring Mistakes**: Tracks mistakes occurring across $\ge 2$ distinct challenges.
- **Adaptive Recommendations**:
  - Scoring formula prioritizes uncompleted challenges.
  - +45 point bonus for challenges matching learner's recurring mistakes.
  - Explanatory reason provided in API response.
- **Pseudonymous Learner IDs**: Enforces privacy; no PII stored.

---

### 6. Challenge Library & Test Suite ✅
- **10 Core Challenges**:
  - `last-k-total` (Lists, Slicing, Edge cases) - *Mandatory*
  - `count-passes` (Conditionals, Filtering, Boundary) - *Mandatory*
  - `first-n-squares` (Loops, Range, Math) - *Mandatory*
  - `middle-three` (Lists, Indexing, Immutability) - *Mandatory*
  - `safe-average` (Lists, Aggregation, Zero Division)
  - `clamp-list` (Lists, Transformation, Boundaries)
  - `string-shifter` (Strings, Slicing, Modular Arithmetic)
  - `vowel-counter` (Strings, Iteration, Membership)
  - `cumulative-sum` (Lists, State Accumulation)
  - `pair-sum-exists` (Hash Sets, Two-Sum, Searching)
- **Automated Test Suite**:
  - `test_api.py`: 5 tests verifying all API endpoints and response schemas.
  - `test_judge_security.py`: 6 tests verifying sandbox timeout, memory/output caps, and process isolation.
  - `test_mandatory_challenges.py`: 5 tests verifying starter codes and reference implementations.
  - `test_mistake_taxonomy.py`: 5 tests verifying detection of all 5 mistake classes.
  - **Result: 21 passed in 33.88s (100% pass rate)**.

---

### 7. Deployment & One-Command Startup ✅
- **Vercel Multi-Service (`vercel.json`)**:
  - Configured with `services.backend` (`debug-dojo/backend`) and `services.frontend` (`debug-dojo/frontend`).
  - Rewrites `/api/(.*)` to backend service and `/(.*)` to frontend service.
  - Serverless compatibility wrapper in `api/index.py`.
- **One-Command Startup (`start.sh`)**:
  - Installs requirements if needed, detects Python 3.11+ automatically.
  - Concurrently boots FastAPI backend (port 8000) and Vite frontend (port 5173).
  - Clean shutdown handler on Ctrl+C.
