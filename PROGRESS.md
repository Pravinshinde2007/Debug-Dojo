# Debug Dojo — Implementation Progress 🥋

## Stage 1: Frontend Foundation & Realistic 3D "Night-Time Dojo" UI

### Status: COMPLETED ✅

### Done
- [x] **Project Structure Setup**: Created root `debug-dojo/` with `frontend/`, `backend/`, `docs/`, `README.md`, `start.sh`, `PROGRESS.md`.
- [x] **Design Tokens & Theme (`tokens.css`)**:
  - Full dark theme token set: background `#0F1420`, surface `#171E2E` (70% translucent glass), editor `#0B0F19`, border `#2A3348`, text `#E6EAF2`, muted `#8A94A8`.
  - Brand accents: vermilion `#FF6B4A`, secondary teal `#2DD4BF`.
  - Outcome colors: `passed` `#34D399`, `wrong_output` `#FBBF24`, `runtime_error` `#F87171`, `timeout` `#A78BFA`.
  - Accessible focus rings (2px teal) and WCAG AA contrast.
- [x] **Accessible UI Component Library (`src/components`)**:
  - `GlassPanel`: Translucent surface with backdrop blur, 1px border, inner top highlight, and soft shadows.
  - `Button`: Primary vermilion with subtle glow, secondary teal outline, ghost, loading/disabled states.
  - `OutcomePill`: Distinct icon + text label + color for all 4 test outcomes (check, not-equal, exclamation, clock).
  - `Tag`: Mistake tags (`off_by_one`, `unhandled_short_input`, `boundary_comparison`, etc.) with recurring indicators.
  - `Badge`: For difficulty levels and concepts.
  - `Toggle`: Keyboard-accessible switch for settings.
  - `Tooltip`: Accessible hover/focus tooltips.
  - `Skeleton`: Shimmer loading placeholder.
  - `ToastContainer`: Non-intrusive feedback toasts.
  - `SettingsPopover`: Accessible popover for graphics tier, low power, reduced motion, and audio mute.
- [x] **Global Application State (`useAppStore.ts`)**:
  - Zustand store managing `lowPower`, `reducedMotion`, `qualityTier`, `fps`, `sceneMood`, `hintsLit`, `learnerId`.
- [x] **Interactive 3D Dojo Scene (`DojoScene.tsx`)**:
  - Perspective camera with gentle idle sine drift and mouse parallax (max 0.3 units).
  - Wet-stone reflective floor using procedural roughness texture and `MeshReflectorMaterial` (with fallback for low tier).
  - Japanese timber beam architecture and back wall with backlit shoji screens.
  - 7 paper lanterns with subtle sway animation and flickering point lights.
  - 4 Progressive Hint Lanterns that light up sequentially (`#5EEAD4`, `#2DD4BF`, `#FBBF24`, `#FF6B4A`) as hints are unlocked.
  - Floating transparent glass panels drifting with faint code lines.
  - Instanced warm embers (180 particles in high tier, 45 in low power).
  - Exponential dark fog (`#0F1420`), volumetric light haze, and ACES filmic tone mapping.
  - Post-processing: Bloom & Vignette via `@react-three/postprocessing`.
  - Mood reactions: `running` (faster flicker), `success` (ember burst + brightening), `error` (gentle cooling/dimming).
- [x] **Performance & Accessibility Fallbacks**:
  - Auto-FPS measurement during initial 3 seconds; drops quality tier if FPS < 40.
  - Automatic frame pausing when tab is hidden (`visibilitychange`).
  - DPR clamping (`[1, 1.5]`).
  - Full static CSS/HTML gradient fallback if WebGL is unavailable or fails.
  - Full `prefers-reduced-motion` compliance.
- [x] **Mock API & App Shell**:
  - Conforms strictly to Prompt 0 contracts (`/api/submit`, `/api/hint`, `/api/learner/{id}`, `/api/challenges`).
  - Practice workbench route (`/`) and Learner profile route (`/learner`).
  - Production build verified: 0 TypeScript errors.

---

### In Progress
- [ ] Stage 2 / Backend execution engine integration.

---

### Next Steps
- Implement Stage 2: Sandboxed Python child process runner (`runner.py` -> `worker.py`) with memory/time/output limits and resource attribution.
- Integrate AST mistake tagger for the 5 required mistake types.
- Add progressive 4-tier hint generation engine with leak guard.

---

### Known Issues / Observations
- None. The frontend compiles cleanly, runs at 60 FPS, and gracefully degrades on low-power devices.
