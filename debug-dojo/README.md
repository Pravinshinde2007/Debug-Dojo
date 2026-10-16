# Debug Dojo 🥋

> **Safe beginner coding coach for a 24-hour hackathon.**
> Runs learner code safely in isolated child processes, explains failures in plain language, delivers progressive 4-level hints that never leak solutions, tags recurring beginner mistakes, and adapts next challenges to student mastery.

---

## ⛩️ Visual Identity: "Night-Time Dojo"
Debug Dojo features an interactive dark 3D training hall:
- **Atmosphere:** Dark stone floor with wet reflections, timber beam structures, paper lanterns, drifting embers, and subtle volumetric haze.
- **Progressive Hint Lanterns:** The 4 closest lanterns illuminate one-by-one as progressive hints are revealed.
- **Mood Reactions:** The dojo reacts gently to test runs (`running` -> quick flicker, `success` -> warm ember bursts, `error` -> subtle dimming, never jarring red flashes).
- **Accessibility & Performance:** Automatic FPS monitoring with 3 quality tiers (`high`, `medium`, `low`), low-power mode, `prefers-reduced-motion` compliance, and pure CSS/HTML fallback when WebGL is unavailable.

---

## 🛠️ Tech Stack
- **Frontend:** React, Vite, TypeScript, Three.js (`@react-three/fiber`, `@react-three/drei`, `@react-three/postprocessing`), Framer Motion, Monaco Editor, Zustand, Lucide Icons.
- **Backend:** Python 3.11+, FastAPI, Uvicorn, SQLite.
- **Architecture:** Isolated child process worker per test with memory/time/output sandboxing.

---

## 🚀 Quick Start
Run everything with a single command:
```bash
./start.sh
```
Or start individual services:
- **Frontend:** `cd frontend && npm run dev` (starts on `http://localhost:5173`)
- **Backend:** `cd backend && python -m uvicorn app.main:app --port 8000` (starts on `http://localhost:8000`)

---

## 📜 Non-Negotiable Rules
1. **Isolated Execution:** Learner code NEVER runs inside the server process. Always a separate, restricted child process.
2. **Hidden Tests are Secret:** Never reveal a hidden test's input, expected output, program output, or exception message. Explanations only name the *kind* of input.
3. **Deterministic Outcomes:** Every test yields exactly one outcome: `passed`, `wrong_output`, `runtime_error`, or `timeout`.
4. **Leak-Guarded Progressive Hints:** 4 progressive hints per failure. No hint may contain raw code or the full solution.
5. **Mistake Tags:** Tracks `off_by_one`, `unhandled_short_input`, `print_not_return`, `boundary_comparison`, `mutates_input`. Marked "recurring" when appearing in 2+ different challenges.
6. **Concept Mastery:** Passes without hints count more than passes after hints.
7. **LLM Audit Trail:** Every LLM prompt and response is logged to `backend/logs/llm.jsonl`.
8. **Pseudonymous Learners:** Strict student privacy with generated identifiers.
