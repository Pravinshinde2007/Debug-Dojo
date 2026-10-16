import { create } from 'zustand';

export type SceneMood = 'idle' | 'running' | 'success' | 'error';
export type QualityTier = 'high' | 'medium' | 'low';

export interface AppState {
  // 3D Scene & Performance Settings
  lowPower: boolean;
  reducedMotion: boolean;
  soundMuted: boolean;
  qualityTier: QualityTier;
  fps: number;

  // Scene Reactive State
  sceneMood: SceneMood;
  hintsLit: number; // 0 to 4

  // Learner Pseudonym (Rule 8)
  learnerId: string;

  // Actions
  setLowPower: (enabled: boolean) => void;
  setReducedMotion: (enabled: boolean) => void;
  setSoundMuted: (muted: boolean) => void;
  setQualityTier: (tier: QualityTier) => void;
  setFps: (fps: number) => void;
  setSceneMood: (mood: SceneMood) => void;
  setHintsLit: (count: number) => void;
  setLearnerId: (id: string) => void;
  triggerSuccess: () => void;
  triggerError: () => void;
}

// Check initial prefers-reduced-motion
const initialReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export const useAppStore = create<AppState>((set) => ({
  lowPower: false,
  reducedMotion: initialReducedMotion,
  soundMuted: true,
  qualityTier: 'high',
  fps: 60,

  sceneMood: 'idle',
  hintsLit: 0,
  learnerId: 'learner_dojo_master',

  setLowPower: (enabled) =>
    set({
      lowPower: enabled,
      qualityTier: enabled ? 'low' : 'high',
    }),
  setReducedMotion: (enabled) => set({ reducedMotion: enabled }),
  setSoundMuted: (muted) => set({ soundMuted: muted }),
  setQualityTier: (tier) =>
    set({
      qualityTier: tier,
      lowPower: tier === 'low',
    }),
  setFps: (fps) => set({ fps }),
  setSceneMood: (mood) => set({ sceneMood: mood }),
  setHintsLit: (count) => set({ hintsLit: Math.max(0, Math.min(4, count)) }),
  setLearnerId: (id) => set({ learnerId: id }),

  triggerSuccess: () => {
    set({ sceneMood: 'success' });
    setTimeout(() => {
      set((state) => (state.sceneMood === 'success' ? { sceneMood: 'idle' } : {}));
    }, 2500);
  },

  triggerError: () => {
    set({ sceneMood: 'error' });
    setTimeout(() => {
      set((state) => (state.sceneMood === 'error' ? { sceneMood: 'idle' } : {}));
    }, 2500);
  },
}));
