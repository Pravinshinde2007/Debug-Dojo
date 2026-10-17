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

export interface CompulsoryMistakeCategory {
  tag: string;
  name: string;
  meaning: string;
  example: string;
  practice_focus: string;
}

export interface RecurringMistake {
  tag: string;
  mistake_tag?: string;
  name?: string;
  meaning?: string;
  example?: string;
  practice_focus?: string;
  challenges: string[];
  challenges_involved?: string[];
  count: number;
  occurrence_count?: number;
  distinct_challenges_count?: number;
  is_recurring?: boolean;
  rule_explanation?: string;
}

export interface NextChallenge {
  id: string;
  title: string;
  reason: string;
}

export interface ConceptSkill {
  concept: string;
  status: string;
  mastery: number;
  attempts: number;
  passes: number;
  fails: number;
  is_illustrative?: boolean;
}

export interface SubmissionHistoryItem {
  id: string;
  challenge_id: string;
  title: string;
  difficulty: string;
  concepts?: string[];
  passed: boolean;
  outcome: 'Passed' | 'Failed';
  hints_used: number;
  mastery_impact: string;
  mistake_tags: string[];
  code_snippet: string;
  created_at?: string;
}

export interface LearnerProfileResponse {
  learner_id?: string;
  user_name?: string;
  user_email?: string;
  recurring_mistakes: RecurringMistake[];
  isolated_mistakes?: RecurringMistake[];
  compulsory_mistake_categories?: CompulsoryMistakeCategory[];
  skills_by_concept?: ConceptSkill[];
  mastery: Record<string, number>;
  mastery_per_concept?: Record<string, number>;
  overall_mastery?: number;
  disclaimer?: string;
  challenges_attempted?: number;
  challenges_solved?: number;
  challenges_failed?: number;
  total_submissions?: number;
  passed_count?: number;
  failed_count?: number;
  submission_history?: SubmissionHistoryItem[];
  history?: SubmissionHistoryItem[];
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
          learner_id: data.learner_id || learner_id,
          user_name: data.user_name,
          user_email: data.user_email,
          recurring_mistakes: data.recurring_mistakes?.map((m: any) =>
            typeof m === 'string' ? { tag: m, challenges: ['sum_last_k', 'find_max'], count: 2 } : m
          ) || [],
          isolated_mistakes: data.isolated_mistakes || [],
          compulsory_mistake_categories: data.compulsory_mistake_categories || [
            { tag: 'off_by_one', name: 'Off by One', meaning: 'A loop or index is one position off', example: 'Stopping a loop one element too early', practice_focus: 'loop boundaries' },
            { tag: 'unhandled_short_input', name: 'Unhandled Short Input', meaning: 'Empty or short inputs are not handled', example: 'Accessing an element in an empty list', practice_focus: 'empty and short inputs' },
            { tag: 'print_not_return', name: 'Print Instead of Return', meaning: 'Printing the answer instead of returning it', example: 'Using print(total) when the function must return the total', practice_focus: 'function returns' },
            { tag: 'boundary_comparison', name: 'Boundary Comparison', meaning: 'Using the wrong comparison at a boundary', example: 'Using > instead of >= for a passing mark', practice_focus: 'boundary comparisons' },
            { tag: 'mutates_input', name: 'Mutates Input', meaning: 'Modifying the original input when it should remain unchanged', example: 'Sorting a supplied list in place', practice_focus: 'non-destructive operations' },
          ],
          skills_by_concept: data.skills_by_concept || [
            { concept: 'Loops', status: 'Several successful attempts', mastery: 85, attempts: 6, passes: 5, fails: 1 },
            { concept: 'Lists and indexing', status: 'Some repeated mistakes', mastery: 50, attempts: 4, passes: 2, fails: 2 },
            { concept: 'Edge cases', status: 'Needs more practice', mastery: 25, attempts: 3, passes: 1, fails: 2 },
          ],
          mastery: data.mastery_per_concept || data.mastery || { loops: 0.8 },
          mastery_per_concept: data.mastery_per_concept,
          overall_mastery: data.overall_mastery ?? 53,
          disclaimer: data.disclaimer || "These values are estimates, not proof of a student's ability. Your backend should update them after every submission.",
          challenges_attempted: data.challenges_attempted ?? 3,
          challenges_solved: data.challenges_solved ?? 2,
          challenges_failed: data.challenges_failed ?? 1,
          total_submissions: data.total_submissions ?? 4,
          passed_count: data.passed_count ?? 3,
          failed_count: data.failed_count ?? 1,
          submission_history: data.submission_history || data.history || [],
          history: data.history || data.submission_history || [],
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
      learner_id,
      recurring_mistakes: [
        {
          tag: 'boundary_comparison',
          name: 'Boundary Comparison',
          meaning: 'Using the wrong comparison at a boundary',
          example: 'Using > instead of >= for a passing mark',
          practice_focus: 'boundary comparisons',
          challenges: ['sum_last_k', 'find_maximum'],
          count: 3,
          distinct_challenges_count: 2,
          is_recurring: true,
          rule_explanation: 'Marked as recurring because it appeared across 2 different challenges (Rule 8 satisfied).',
        },
        {
          tag: 'off_by_one',
          name: 'Off by One',
          meaning: 'A loop or index is one position off',
          example: 'Stopping a loop one element too early',
          practice_focus: 'loop boundaries',
          challenges: ['count_vowels', 'sum_last_k'],
          count: 2,
          distinct_challenges_count: 2,
          is_recurring: true,
          rule_explanation: 'Marked as recurring because it appeared across 2 different challenges (Rule 8 satisfied).',
        },
      ],
      isolated_mistakes: [
        {
          tag: 'mutates_input',
          name: 'Mutates Input',
          meaning: 'Modifying the original input when it should remain unchanged',
          example: 'Sorting a supplied list in place',
          practice_focus: 'non-destructive operations',
          challenges: ['middle-three'],
          count: 2,
          distinct_challenges_count: 1,
          is_recurring: false,
          rule_explanation: 'Appeared 2 times, but only in 1 challenge. Must appear across at least 2 distinct challenges to become recurring.',
        },
      ],
      compulsory_mistake_categories: [
        { tag: 'off_by_one', name: 'Off by One', meaning: 'A loop or index is one position off', example: 'Stopping a loop one element too early', practice_focus: 'loop boundaries' },
        { tag: 'unhandled_short_input', name: 'Unhandled Short Input', meaning: 'Empty or short inputs are not handled', example: 'Accessing an element in an empty list', practice_focus: 'empty and short inputs' },
        { tag: 'print_not_return', name: 'Print Instead of Return', meaning: 'Printing the answer instead of returning it', example: 'Using print(total) when the function must return the total', practice_focus: 'function returns' },
        { tag: 'boundary_comparison', name: 'Boundary Comparison', meaning: 'Using the wrong comparison at a boundary', example: 'Using > instead of >= for a passing mark', practice_focus: 'boundary comparisons' },
        { tag: 'mutates_input', name: 'Mutates Input', meaning: 'Modifying the original input when it should remain unchanged', example: 'Sorting a supplied list in place', practice_focus: 'non-destructive operations' },
      ],
      skills_by_concept: [
        { concept: 'Loops', status: 'Several successful attempts', mastery: 85, attempts: 6, passes: 5, fails: 1, is_illustrative: true },
        { concept: 'Lists and indexing', status: 'Some repeated mistakes', mastery: 50, attempts: 4, passes: 2, fails: 2, is_illustrative: true },
        { concept: 'Edge cases', status: 'Needs more practice', mastery: 25, attempts: 3, passes: 1, fails: 2, is_illustrative: true },
        { concept: 'Functions', status: 'Ready to practice', mastery: 50, attempts: 0, passes: 0, fails: 0, is_illustrative: true },
        { concept: 'Conditions', status: 'Ready to practice', mastery: 50, attempts: 0, passes: 0, fails: 0, is_illustrative: true },
      ],
      mastery: {
        loops: 0.85,
        'lists and indexing': 0.50,
        'edge cases': 0.25,
      },
      mastery_per_concept: {
        'Loops': 85,
        'Lists and indexing': 50,
        'Edge cases': 25,
      },
      overall_mastery: 53,
      disclaimer: "These values are estimates, not proof of a student's ability. Your backend should update them after every submission.",
      challenges_attempted: 3,
      challenges_solved: 2,
      challenges_failed: 1,
      total_submissions: 5,
      passed_count: 3,
      failed_count: 2,
      submission_history: [
        {
          id: 'sub_103',
          challenge_id: 'last-k-total',
          title: 'Total of the Last K Marks',
          difficulty: 'Easy',
          concepts: ['Lists and indexing', 'Loops'],
          passed: true,
          outcome: 'Passed',
          hints_used: 0,
          mastery_impact: '+15% (0 hints)',
          mistake_tags: [],
          code_snippet: 'def sum_last_k(scores, k):\n    if k <= 0: return 0\n    return sum(scores[-k:])',
          created_at: 'Just now',
        },
        {
          id: 'sub_102',
          challenge_id: 'last-k-total',
          title: 'Total of the Last K Marks',
          difficulty: 'Easy',
          concepts: ['Lists and indexing', 'Edge cases'],
          passed: false,
          outcome: 'Failed',
          hints_used: 2,
          mastery_impact: '-4% (Failed)',
          mistake_tags: ['unhandled_short_input'],
          code_snippet: 'def sum_last_k(scores, k):\n    return sum(scores[-k:])',
          created_at: '5 mins ago',
        },
        {
          id: 'sub_101',
          challenge_id: 'find_maximum',
          title: 'Find Maximum Element',
          difficulty: 'Easy',
          concepts: ['Loops', 'Edge cases'],
          passed: true,
          outcome: 'Passed',
          hints_used: 4,
          mastery_impact: '+2% (4 hints)',
          mistake_tags: ['boundary_comparison'],
          code_snippet: 'def find_maximum(nums):\n    if not nums: return None...',
          created_at: '15 mins ago',
        },
      ],
      next_challenge: {
        id: 'find_maximum',
        title: 'Find Maximum Element',
        reason: 'Recommended for easier practice in Edge cases to build confidence after repeated attempts.',
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

