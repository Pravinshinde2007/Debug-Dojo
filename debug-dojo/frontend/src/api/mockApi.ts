/**
 * Mock API conforming strictly to the Prompt 0 API contract.
 * Also supports transparent fallback if the real backend is running on http://localhost:8000.
 */

export interface VisibleTestResult {
  test: number;
  call: string;
  expected: string;
  got: string;
  outcome: 'passed' | 'wrong_output' | 'runtime_error' | 'timeout';
}

export interface HiddenTestResult {
  test: number;
  outcome: 'passed' | 'wrong_output' | 'runtime_error' | 'timeout';
}

export interface SubmitResponse {
  submission_id: string;
  learner_id: string;
  challenge_id: string;
  visible: VisibleTestResult[];
  hidden: HiddenTestResult[];
  mistake_tags: string[];
  explanation: string;
}

export interface HintResponse {
  submission_id: string;
  level: number;
  total_levels: number;
  hint: string;
}

export interface RecurringMistake {
  tag: string;
  challenges: string[];
  count: number;
}

export interface NextChallenge {
  id: string;
  title: string;
  reason: string;
}

export interface LearnerProfileResponse {
  recurring_mistakes: RecurringMistake[];
  mastery: Record<string, number>;
  next_challenge: NextChallenge;
}

export interface Challenge {
  id: string;
  title: string;
  difficulty: 'beginner' | 'intermediate';
  concepts: string[];
  description: string;
  starter_code: string;
}

const MOCK_CHALLENGES: Challenge[] = [
  {
    id: 'sum_last_k',
    title: 'Total of the Last K Marks',
    difficulty: 'beginner',
    concepts: ['loops', 'lists', 'slicing'],
    description:
      "Rohan's score tracker needs to compute the sum of the last `k` marks in a list of scores.\nIf `k` is larger than the list, sum all available marks. If `k <= 0`, return 0.",
    starter_code:
      'def sum_last_k(scores, k):\n    # Write your solution here\n    if k <= 0:\n        return 0\n    return sum(scores[-k:])\n',
  },
  {
    id: 'count_vowels',
    title: 'Count Vowels',
    difficulty: 'beginner',
    concepts: ['loops', 'strings', 'conditionals'],
    description:
      'Write a function `count_vowels(text)` that returns the count of vowels (a, e, i, o, u, case-insensitive) in the string.',
    starter_code:
      'def count_vowels(text):\n    # Write your solution here\n    vowels = "aeiouAEIOU"\n    count = 0\n    for char in text:\n        if char in vowels:\n            count += 1\n    return count\n',
  },
  {
    id: 'find_maximum',
    title: 'Find Maximum Element',
    difficulty: 'beginner',
    concepts: ['loops', 'lists', 'comparison'],
    description:
      'Write a function `find_maximum(nums)` that finds the maximum value without using built-in `max()`. For an empty list, return None.',
    starter_code:
      'def find_maximum(nums):\n    if not nums:\n        return None\n    highest = nums[0]\n    for n in nums:\n        if n > highest:\n            highest = n\n    return highest\n',
  },
];

const MOCK_HINTS = [
  "Look closely at the case where 'k' exceeds the length of the list.",
  "Consider using slicing with a bound check: what does scores[-k:] evaluate to when k > len(scores)?",
  "Think about clamping k: the maximum number of items you can sum is len(scores).",
  "Ensure you use min(k, len(scores)) before taking the slice from the end.",
];

let mockSubmissionCounter = 100;
let hintLevelTracker: Record<string, number> = {};

/**
 * Resolves the API endpoint URL:
 * 1. Reads bound service environment variable (process.env.BACKEND_URL) if in runtime
 * 2. Reads Vite environment variable (import.meta.env.VITE_BACKEND_URL)
 * 3. Defaults to relative '/api/...' path (routed to backend service via Vercel rewrites)
 * 4. Falls back to 'http://localhost:8000' during standalone local dev on port 5173
 */
function resolveApiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  // 1. Bound service URL from Vercel services binding (runtime injection)
  const proc = (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process;
  if (proc?.env?.BACKEND_URL) {
    try {
      return new URL(cleanEndpoint, proc.env.BACKEND_URL).toString();
    } catch {
      // Fall through if URL parsing fails
    }
  }

  // 2. Client environment variable
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BACKEND_URL) {
    const base = import.meta.env.VITE_BACKEND_URL.replace(/\/$/, '');
    return `${base}${cleanEndpoint}`;
  }

  // 3. Local standalone development fallback
  if (typeof window !== 'undefined' && window.location.port === '5173') {
    return `http://localhost:8000${cleanEndpoint}`;
  }

  // 4. Relative URL on same origin (Vercel public rewrite handles this)
  return cleanEndpoint;
}

export const api = {
  async getChallenges(): Promise<Challenge[]> {
    try {
      const res = await fetch(resolveApiUrl('/api/challenges'));
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) return data;
      }
    } catch {
      // Fallback to mock challenges
    }
    return MOCK_CHALLENGES;
  },

  async submit(learner_id: string, challenge_id: string, code: string): Promise<SubmitResponse> {
    try {
      const res = await fetch(resolveApiUrl('/api/submit'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ learner_id, challenge_id, code }),
      });

      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback to mock simulation
    }

    mockSubmissionCounter++;
    const submission_id = `sub_${mockSubmissionCounter}`;

    const isPassing = code.includes('min(k') || code.includes('len(scores)') || code.includes('sum_last_k');
    const hasOffByOne = code.includes('range(len(');

    return {
      submission_id,
      learner_id,
      challenge_id,
      visible: [
        {
          test: 1,
          call: 'sum_last_k([10, 20, 30, 40], 2)',
          expected: '70',
          got: '70',
          outcome: 'passed',
        },
        {
          test: 2,
          call: 'sum_last_k([5, 10, 15], 1)',
          expected: '15',
          got: '15',
          outcome: 'passed',
        },
        {
          test: 3,
          call: 'sum_last_k([12, 18], 0)',
          expected: '0',
          got: '0',
          outcome: 'passed',
        },
      ],
      hidden: [
        {
          test: 4,
          outcome: isPassing ? 'passed' : 'wrong_output',
        },
        {
          test: 5,
          outcome: 'passed',
        },
      ],
      mistake_tags: isPassing ? [] : [hasOffByOne ? 'off_by_one' : 'boundary_comparison'],
      explanation: isPassing
        ? 'All tests passed cleanly! Your boundary logic handled short inputs and edge cases smoothly.'
        : 'Your code handled typical cases well, but did not match expectations on a case where k is larger than the list.',
    };
  },

  async requestHint(submission_id: string): Promise<HintResponse> {
    try {
      const res = await fetch(resolveApiUrl('/api/hint'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ submission_id }),
      });
      if (res.ok) {
        return await res.json();
      }
    } catch {
      // Fallback to mock hint
    }

    const current = hintLevelTracker[submission_id] || 0;
    const nextLevel = Math.min(current + 1, 4);
    hintLevelTracker[submission_id] = nextLevel;

    return {
      submission_id,
      level: nextLevel,
      total_levels: 4,
      hint: MOCK_HINTS[nextLevel - 1],
    };
  },

  async getLearner(learner_id: string): Promise<LearnerProfileResponse> {
    try {
      const res = await fetch(resolveApiUrl(`/api/learner/${learner_id}`));
      if (res.ok) {
        const data = await res.json();
        return {
          recurring_mistakes: data.recurring_mistakes?.map((m: any) =>
            typeof m === 'string' ? { tag: m, challenges: ['sum_last_k', 'find_max'], count: 2 } : m
          ) || [],
          mastery: data.mastery_per_concept || data.mastery || { loops: 0.8 },
          next_challenge: data.next_challenge || {
            id: 'find_maximum',
            title: 'Find Maximum Element',
            reason: data.reason || 'Practice boundary handling',
          },
        };
      }
    } catch {
      // Fallback
    }

    return {
      recurring_mistakes: [
        {
          tag: 'boundary_comparison',
          challenges: ['sum_last_k', 'find_maximum'],
          count: 3,
        },
        {
          tag: 'off_by_one',
          challenges: ['count_vowels', 'sum_last_k'],
          count: 2,
        },
      ],
      mastery: {
        loops: 0.82,
        lists: 0.75,
        slicing: 0.55,
        conditionals: 0.9,
      },
      next_challenge: {
        id: 'find_maximum',
        title: 'Find Maximum Element',
        reason: 'Reinforces boundary checking after recurring boundary_comparison mistakes across 2 challenges',
      },
    };
  },

  async healthCheck(): Promise<{ status: string }> {
    try {
      const res = await fetch(resolveApiUrl('/api/health'));
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
    return { status: 'ok' };
  },
};

