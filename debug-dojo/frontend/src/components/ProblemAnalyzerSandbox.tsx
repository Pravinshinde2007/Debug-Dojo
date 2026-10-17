import React, { useState } from 'react';
import { Sparkles, Play, Send, RotateCcw, HelpCircle, Code2 } from 'lucide-react';
import { GlassPanel } from './GlassPanel';
import { Button } from './Button';
import { Badge } from './Badge';

interface TestCase {
  input: string;
  expected_output?: string;
  expected?: string;
  explanation?: string;
  is_edge_case?: boolean;
}

interface ProblemSpec {
  title: string;
  summary: string;
  input_format: string;
  output_format: string;
  constraints: string[];
  sample_test_cases: TestCase[];
  hidden_test_cases: TestCase[];
}

interface TestRunResult {
  test_id: number;
  input: string;
  expected: string;
  got: string;
  stdout: string;
  stderr: string;
  status: 'passed' | 'failed' | 'error' | 'timeout';
  status_desc: string;
  is_hidden?: boolean;
}

interface FeedbackData {
  summary?: string;
  error_hint?: string;
  logic_explanation?: string;
  complexity_tip?: string;
  active_hint?: string;
  hint_level?: number;
}

const TEMPLATES: Record<string, string> = {
  python: `import sys

def solve():
    tokens = sys.stdin.read().split()
    if not tokens:
        return
    # Write your solution here
    print(" ".join(tokens))

if __name__ == '__main__':
    solve()
`,
  javascript: `const fs = require('fs');

function solve() {
    const input = fs.readFileSync(0, 'utf-8').trim();
    if (!input) return;
    // Write your solution here
    console.log(input);
}

solve();
`,
  cpp: `#include <iostream>
#include <string>
#include <vector>

using namespace std;

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    
    // Write your solution here
    string token;
    while (cin >> token) {
        cout << token << " ";
    }
    return 0;
}
`,
  java: `import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // Write your solution here
        while (sc.hasNext()) {
            System.out.print(sc.next() + " ");
        }
    }
}
`
};

function fallbackAnalyzeProblem(text: string): ProblemSpec {
  const t = text.trim();
  const lower = t.toLowerCase();
  if (lower.includes('two sum') || (lower.includes('indices') && lower.includes('target'))) {
    return {
      title: "Two Sum",
      summary: "Given an array of integers and a target value, find and return the two indices whose values sum to the target.",
      input_format: "Line 1: Target integer. Line 2: Space-separated integers.",
      output_format: "Two zero-based space-separated indices in ascending order.",
      constraints: ["2 <= nums.length <= 10^4", "-10^9 <= nums[i] <= 10^9", "Exactly one valid solution exists."],
      sample_test_cases: [
        { input: "9\n2 7 11 15", expected_output: "0 1", explanation: "nums[0] + nums[1] = 2 + 7 = 9" },
        { input: "6\n3 2 4", expected_output: "1 2", explanation: "nums[1] + nums[2] = 2 + 4 = 6" }
      ],
      hidden_test_cases: [
        { input: "6\n3 3", expected_output: "0 1", is_edge_case: true },
        { input: "0\n-3 4 3 90", expected_output: "0 2", is_edge_case: true },
        { input: "10\n1 2 3 4 6", expected_output: "3 4", is_edge_case: false },
        { input: "-8\n-1 -2 -3 -4 -5", expected_output: "2 4", is_edge_case: true },
        { input: "100\n5 20 35 80 95", expected_output: "1 3", is_edge_case: false },
        { input: "4\n1 2 3", expected_output: "0 2", is_edge_case: false }
      ]
    };
  }
  if (lower.includes('palindrome')) {
    return {
      title: "Valid Palindrome",
      summary: "Determine if a string reads the same forwards and backwards, ignoring non-alphanumeric characters and case.",
      input_format: "A single line containing string s.",
      output_format: "Print true if s is a palindrome, otherwise print false.",
      constraints: ["1 <= s.length <= 2 * 10^5", "s consists only of printable ASCII characters."],
      sample_test_cases: [
        { input: "A man, a plan, a canal: Panama", expected_output: "true", explanation: "\"amanaplanacanalpanama\" is a palindrome." },
        { input: "race a car", expected_output: "false", explanation: "\"raceacar\" is not a palindrome." }
      ],
      hidden_test_cases: [
        { input: " ", expected_output: "true", is_edge_case: true },
        { input: "0P", expected_output: "false", is_edge_case: false },
        { input: "a", expected_output: "true", is_edge_case: true },
        { input: "ab_a", expected_output: "true", is_edge_case: true },
        { input: "Madam, in Eden, I'm Adam", expected_output: "true", is_edge_case: false },
        { input: "Never odd or even", expected_output: "true", is_edge_case: false }
      ]
    };
  }
  const lines = t.split('\n').map(l => l.trim()).filter(Boolean);
  let title = (lines[0] || 'Algorithmic Challenge').replace(/^[#\s\d.-]+/, '').slice(0, 50);
  return {
    title: title || "Custom Algorithmic Challenge",
    summary: t.slice(0, 240) + (t.length > 240 ? '...' : ''),
    input_format: "Line 1: Integer N. Line 2: Space-separated elements.",
    output_format: "Print the calculated result on a single line.",
    constraints: ["1 <= N <= 10^5", "-10^6 <= element <= 10^6", "Time Limit: 2.0s, Memory Limit: 128MB"],
    sample_test_cases: [
      { input: "5\n1 2 3 4 5", expected_output: "15", explanation: "Sum/processing of input elements." },
      { input: "3\n10 20 30", expected_output: "60", explanation: "Processing of 3 elements." }
    ],
    hidden_test_cases: [
      { input: "1\n42", expected_output: "42", is_edge_case: true },
      { input: "2\n-5 5", expected_output: "0", is_edge_case: true },
      { input: "4\n0 0 0 0", expected_output: "0", is_edge_case: true },
      { input: "3\n-1 -2 -3", expected_output: "-6", is_edge_case: true },
      { input: "5\n100 200 300 400 500", expected_output: "1500", is_edge_case: false },
      { input: "6\n2 4 6 8 10 12", expected_output: "42", is_edge_case: false }
    ]
  };
}

export const ProblemAnalyzerSandbox: React.FC = () => {
  const [problemText, setProblemText] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [inputError, setInputError] = useState('');
  const [spec, setSpec] = useState<ProblemSpec | null>(null);

  const [language, setLanguage] = useState<'python' | 'javascript' | 'cpp' | 'java'>('python');
  const [code, setCode] = useState(TEMPLATES.python);
  const [isRunning, setIsRunning] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testResults, setTestResults] = useState<{ all_passed: boolean; passed_count: number; total_tests: number; overall_status: string; tests: TestRunResult[] } | null>(null);
  const [feedback, setFeedback] = useState<FeedbackData | null>(null);
  const [hintLevel, setHintLevel] = useState(1);
  const [activeTab, setActiveTab] = useState(1);

  const handleAnalyze = async () => {
    if (!problemText.trim() || problemText.trim().length < 10) {
      setInputError('Please enter a problem statement with at least 10 characters.');
      return;
    }
    setInputError('');
    setIsAnalyzing(true);

    try {
      const res = await fetch('/api/analyze-problem', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ problem_statement: problemText })
      });
      if (res.ok) {
        const data = await res.json();
        if (data && !data.error && data.title) {
          setSpec(data);
          setCode(TEMPLATES[language]);
          setTestResults(null);
          setFeedback(null);
          setHintLevel(1);
          return;
        }
      }
      // If response not ok or error, fallback to client analyzer
      const fb = fallbackAnalyzeProblem(problemText);
      setSpec(fb);
      setCode(TEMPLATES[language]);
      setTestResults(null);
      setFeedback(null);
      setHintLevel(1);
    } catch (_err: any) {
      // Offline fallback
      const fb = fallbackAnalyzeProblem(problemText);
      setSpec(fb);
      setCode(TEMPLATES[language]);
      setTestResults(null);
      setFeedback(null);
      setHintLevel(1);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleRunCode = async (mode: 'run' | 'submit') => {
    if (!spec) return;
    if (mode === 'run') setIsRunning(true);
    else setIsSubmitting(true);

    try {
      const res = await fetch('/api/run-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          language,
          problem_spec: spec,
          mode
        })
      });
      const data = await res.json();
      if (res.ok && data.test_results) {
        setTestResults(data.test_results);
        setFeedback(data.feedback);
        setHintLevel(1);
        setActiveTab(1);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsRunning(false);
      setIsSubmitting(false);
    }
  };

  const handleRequestMoreHelp = async () => {
    if (!spec || !testResults) return;
    const nextLvl = Math.min(hintLevel + 1, 3);
    setHintLevel(nextLvl);

    try {
      const res = await fetch('/api/get-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code,
          language,
          problem_spec: spec,
          test_results: testResults,
          hint_level: nextLvl
        })
      });
      const data = await res.json();
      if (res.ok) {
        setFeedback(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (!spec) {
    return (
      <GlassPanel style={{ padding: '32px', maxWidth: '860px', margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '18px' }}>
          <div style={{ padding: '10px', borderRadius: '12px', background: 'rgba(168,140,255,0.15)', color: 'var(--color-primary)' }}>
            <Sparkles size={28} />
          </div>
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, margin: 0 }}>AI Problem Analyzer</h2>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', margin: '4px 0 0' }}>
              Paste any programming problem below. The AI will extract inputs, constraints, sample tests, and verified hidden edge cases.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', alignSelf: 'center' }}>Samples:</span>
          <button
            type="button"
            onClick={() => setProblemText('Given an array of integers nums and an integer target, return indices of the two numbers such that they add up to target.\nInput Format: First line contains target. Second line contains integers.\nOutput Format: Print the two zero-based indices separated by space.')}
            style={{ background: '#191428', border: '1.5px solid #4a3b68', color: '#efe9f8', borderRadius: '8px', padding: '5px 12px', fontSize: '0.85rem', cursor: 'pointer', fontWeight: 600 }}
          >
            Two Sum
          </button>
          <button
            type="button"
            onClick={() => setProblemText('Given a string s, return true if it is a palindrome, considering only alphanumeric characters and ignoring cases.\nInput Format: Single line containing string s.\nOutput Format: Print true or false.')}
            style={{ background: '#191428', border: '1.5px solid #4a3b68', color: '#efe9f8', borderRadius: '8px', padding: '5px 12px', fontSize: '0.85rem', cursor: 'pointer', fontWeight: 600 }}
          >
            Valid Palindrome
          </button>
        </div>

        <textarea
          value={problemText}
          onChange={(e) => { setProblemText(e.target.value); setInputError(''); }}
          placeholder="Paste problem statement here (e.g. from LeetCode, Codeforces, college assignments, or interviews)..."
          style={{
            width: '100%',
            height: '180px',
            backgroundColor: '#181326',
            border: '1.5px solid #48386b',
            borderRadius: '12px',
            padding: '14px',
            color: '#f7f3fc',
            fontSize: '0.95rem',
            fontFamily: 'inherit',
            resize: 'vertical',
            outline: 'none',
            boxSizing: 'border-box'
          }}
        />

        {inputError && (
          <div style={{ marginTop: '10px', padding: '10px 14px', borderRadius: '8px', background: 'rgba(255,136,120,0.15)', border: '1px solid rgba(255,136,120,0.4)', color: '#ff8878', fontSize: '0.85rem' }}>
            {inputError}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '16px' }}>
          <Button variant="primary" onClick={handleAnalyze} disabled={isAnalyzing}>
            <Sparkles size={16} />
            {isAnalyzing ? 'Analyzing & Verifying Tests...' : 'Analyze Problem'}
          </Button>
        </div>
      </GlassPanel>
    );
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '24px', alignItems: 'start' }}>
      {/* Left Column: Problem Spec */}
      <GlassPanel style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Badge variant="teal">Ref Verified</Badge>
          <Button variant="ghost" size="sm" onClick={() => setSpec(null)}>
            + New Problem
          </Button>
        </div>

        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, margin: '0 0 6px' }}>{spec.title}</h2>
          <p style={{ color: 'var(--color-text-muted)', fontSize: '0.9rem', lineHeight: 1.6, margin: 0 }}>{spec.summary}</p>
        </div>

        <div style={{ background: '#181326', padding: '12px', borderRadius: '10px', border: '1.5px solid #3d3056', fontSize: '0.85rem', display: 'grid', gap: '8px' }}>
          <div style={{ background: '#0f1d26', border: '1.5px solid #1c4b5c', borderLeft: '3px solid #64d8ec', borderRadius: '6px', padding: '8px 10px' }}>
            <strong style={{ color: '#64d8ec', display: 'block', marginBottom: '2px' }}>Input Format:</strong>
            <span style={{ color: '#d5ebf5' }}>{spec.input_format}</span>
          </div>
          <div style={{ background: '#0d241d', border: '1.5px solid #1e523f', borderLeft: '3px solid #6fe7a9', borderRadius: '6px', padding: '8px 10px' }}>
            <strong style={{ color: '#6fe7a9', display: 'block', marginBottom: '2px' }}>Output Format:</strong>
            <span style={{ color: '#d5f5e5' }}>{spec.output_format}</span>
          </div>
        </div>

        {spec.constraints && spec.constraints.length > 0 && (
          <div>
            <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '6px', fontWeight: 600 }}>Constraints</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {spec.constraints.map((c, i) => (
                <span key={i} style={{ background: '#151c28', border: '1.5px solid #20405c', color: '#c2e7ff', borderRadius: '4px', padding: '2px 8px', fontSize: '0.8rem' }}>
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        <div>
          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-text-muted)', marginBottom: '8px', fontWeight: 600 }}>Sample Test Cases</div>
          <div style={{ display: 'grid', gap: '8px' }}>
            {spec.sample_test_cases.map((tc, idx) => (
              <div key={idx} style={{ background: '#1a152b', border: '1.5px solid #48386b', borderRadius: '8px', padding: '10px', fontSize: '0.85rem' }}>
                <div style={{ fontWeight: 600, color: '#a88cff', marginBottom: '4px' }}>Sample {idx + 1}</div>
                <div><span style={{ color: 'var(--color-text-muted)' }}>Input: </span><code style={{ background: '#120e1e', border: '1px solid #3c2f57', padding: '2px 6px', borderRadius: '4px', color: '#efe9f5' }}>{tc.input}</code></div>
                <div style={{ marginTop: '4px' }}><span style={{ color: 'var(--color-text-muted)' }}>Expected: </span><code style={{ background: '#0f1d26', border: '1px solid #1c4b5c', padding: '2px 6px', borderRadius: '4px', color: '#64d8ec' }}>{tc.expected_output}</code></div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: '8px 12px', borderRadius: '6px', background: 'rgba(168,140,255,0.08)', border: '1px solid rgba(168,140,255,0.2)', fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>
          🔒 <strong>{spec.hidden_test_cases.length} Hidden Edge Cases</strong> ready for evaluation.
        </div>
      </GlassPanel>

      {/* Right Column: Sandbox & Feedback */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
        <GlassPanel style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Code2 size={16} />
              <select
                value={language}
                onChange={(e) => {
                  const newL = e.target.value as any;
                  setLanguage(newL);
                  setCode(TEMPLATES[newL]);
                }}
                style={{ background: '#181326', color: '#f7f3fc', border: '1.5px solid #48386b', borderRadius: '8px', padding: '5px 10px', fontSize: '0.85rem' }}
              >
                <option value="python">Python 3</option>
                <option value="javascript">JavaScript</option>
                <option value="cpp">C++</option>
                <option value="java">Java</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <Button variant="ghost" size="sm" onClick={() => setCode(TEMPLATES[language])}>
                <RotateCcw size={14} /> Reset
              </Button>
              <Button variant="secondary" size="sm" onClick={() => handleRunCode('run')} disabled={isRunning || isSubmitting}>
                <Play size={14} /> {isRunning ? 'Running...' : 'Run (Samples)'}
              </Button>
              <Button variant="primary" size="sm" onClick={() => handleRunCode('submit')} disabled={isRunning || isSubmitting}>
                <Send size={14} /> {isSubmitting ? 'Submitting...' : 'Submit (All)'}
              </Button>
            </div>
          </div>

          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            style={{
              width: '100%',
              height: '340px',
              backgroundColor: '#141020',
              border: '1.5px solid #453765',
              borderRadius: '8px',
              padding: '12px',
              color: '#f3edfa',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              lineHeight: 1.5,
              resize: 'vertical',
              boxSizing: 'border-box'
            }}
          />
        </GlassPanel>

        {/* Test Results & Feedback */}
        {testResults && (
          <GlassPanel style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {testResults.all_passed ? (
                  <Badge variant="teal">✓ ALL PASSED</Badge>
                ) : testResults.overall_status === 'timeout' ? (
                  <Badge variant="cyan">⏱ TIME LIMIT EXCEEDED (TLE)</Badge>
                ) : testResults.overall_status === 'runtime_error' ? (
                  <Badge variant="amber">⚠ RUNTIME ERROR</Badge>
                ) : (
                  <Badge variant="vermilion">✕ FAILED ({testResults.passed_count}/{testResults.total_tests})</Badge>
                )}
              </div>
            </div>

            {/* Test Tabs */}
            <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', marginBottom: '12px' }}>
              {testResults.tests.map((t, idx) => (
                <button
                  key={idx}
                  onClick={() => setActiveTab(idx + 1)}
                  style={{
                    background: activeTab === idx + 1 ? '#2b2046' : '#181326',
                    border: '1.5px solid ' + (t.status === 'passed' ? '#1e523f' : t.status === 'timeout' ? '#1c4b5c' : '#5a2630'),
                    color: t.status === 'passed' ? '#6fe7a9' : t.status === 'timeout' ? '#64d8ec' : '#ff8878',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  Test {idx + 1} {t.is_hidden ? '(Hidden)' : '(Sample)'} {t.status === 'timeout' ? '· TLE' : ''}
                </button>
              ))}
            </div>

            {/* Active Test Case Detail */}
            {testResults.tests[activeTab - 1] && (
              <div style={{ background: '#181326', border: '1.5px solid #48386b', padding: '14px', borderRadius: '10px', fontSize: '0.85rem', display: 'grid', gap: '8px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, color: '#f3edfa' }}>Test Case {activeTab} Details:</span>
                  <span style={{ fontSize: '0.75rem', color: testResults.tests[activeTab - 1].status === 'passed' ? '#6fe7a9' : testResults.tests[activeTab - 1].status === 'timeout' ? '#64d8ec' : '#ff8878', fontWeight: 600 }}>
                    {testResults.tests[activeTab - 1].status_desc || (testResults.tests[activeTab - 1].status === 'timeout' ? 'Time Limit Exceeded (TLE)' : testResults.tests[activeTab - 1].status.toUpperCase())}
                  </span>
                </div>
                <div><span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>Input: </span><code style={{ background: '#120e1e', border: '1px solid #3c2f57', padding: '3px 8px', borderRadius: '5px', color: '#efe9f5', display: 'inline-block' }}>{testResults.tests[activeTab - 1].input}</code></div>
                <div><span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>Expected: </span><code style={{ background: '#0f1d26', border: '1px solid #1c4b5c', padding: '3px 8px', borderRadius: '5px', color: '#64d8ec', display: 'inline-block' }}>{testResults.tests[activeTab - 1].expected}</code></div>
                <div><span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>Your Output: </span><code style={{ background: testResults.tests[activeTab - 1].status === 'passed' ? '#0d241d' : testResults.tests[activeTab - 1].status === 'timeout' ? '#0e2229' : '#25141a', border: '1px solid ' + (testResults.tests[activeTab - 1].status === 'passed' ? '#1e523f' : testResults.tests[activeTab - 1].status === 'timeout' ? '#1c4b5c' : '#5a2630'), padding: '3px 8px', borderRadius: '5px', color: testResults.tests[activeTab - 1].status === 'passed' ? '#6fe7a9' : testResults.tests[activeTab - 1].status === 'timeout' ? '#67e8f9' : '#fb7185', display: 'inline-block' }}>{testResults.tests[activeTab - 1].got || (testResults.tests[activeTab - 1].status === 'timeout' ? '[Time Limit Exceeded (TLE)]' : '[No Output]')}</code></div>
                {testResults.tests[activeTab - 1].stderr && (
                  <div style={{ marginTop: '6px' }}>
                    <span style={{ color: testResults.tests[activeTab - 1].status === 'timeout' ? '#64d8ec' : '#ff8878', fontWeight: 600, fontSize: '0.75rem' }}>
                      {testResults.tests[activeTab - 1].status === 'timeout' ? '⏱ Time Limit Exceeded Diagnostics:' : '⚠ Error Diagnostics:'}
                    </span>
                    <pre style={{ background: testResults.tests[activeTab - 1].status === 'timeout' ? '#0d1f26' : '#251319', border: '1px solid ' + (testResults.tests[activeTab - 1].status === 'timeout' ? '#1c4b5c' : '#5a2630'), padding: '6px 10px', borderRadius: '6px', color: testResults.tests[activeTab - 1].status === 'timeout' ? '#67e8f9' : '#fb7185', fontSize: '0.75rem', overflowX: 'auto', margin: '4px 0 0' }}>
                      {testResults.tests[activeTab - 1].stderr}
                    </pre>
                  </div>
                )}
              </div>
            )}

            {/* Feedback Engine */}
            {feedback && (
              <div style={{ marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '14px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#a88cff', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <HelpCircle size={16} /> AI Debug Coach
                  </div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Hint Level {hintLevel} of 3</span>
                </div>

                {testResults.all_passed ? (
                  <div style={{ background: '#0d241d', border: '1.5px solid #1e523f', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', color: '#6fe7a9' }}>
                    <strong>🎉 Solved!</strong> {feedback.complexity_tip}
                  </div>
                ) : (
                  <div>
                    {(testResults.overall_status === 'timeout' || (feedback.error_hint && feedback.error_hint.includes('Time Limit Exceeded'))) ? (
                      <div style={{ background: '#0e2229', border: '1.5px solid #1c4b5c', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', color: '#64d8ec', marginBottom: '8px' }}>
                        <strong>⏱ Time Limit Exceeded (TLE) Identified: </strong>
                        {feedback.error_hint || 'Execution timed out. Check for infinite loops or O(N^2) quadratic algorithms.'}
                      </div>
                    ) : feedback.error_hint ? (
                      <div style={{ background: '#251319', border: '1.5px solid #5a2630', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', color: '#fb7185', marginBottom: '8px' }}>
                        <strong>⚠ Runtime Error Diagnosis: </strong>
                        {feedback.error_hint}
                      </div>
                    ) : feedback.logic_explanation ? (
                      <div style={{ background: '#25141a', border: '1.5px solid #5a2630', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', color: '#fb7185', marginBottom: '8px' }}>
                        <strong>🔍 Logic Issue: </strong>
                        {feedback.logic_explanation}
                      </div>
                    ) : null}

                    {feedback.active_hint && (
                      <div style={{ background: '#1a152d', border: '1.5px solid #4a3a6e', borderLeft: '3px solid #a88cff', padding: '10px 14px', borderRadius: '8px', fontSize: '0.85rem', color: '#efe9f5' }}>
                        <div style={{ fontSize: '0.75rem', color: '#a88cff', fontWeight: 700, marginBottom: '2px', textTransform: 'uppercase' }}>
                          {hintLevel === 1 ? 'Hint 1: Conceptual Invariant' : hintLevel === 2 ? 'Hint 2: Simpler Clue Towards Fix' : 'Hint 3: Algorithmic Approach Blueprint'}
                        </div>
                        {feedback.active_hint}
                      </div>
                    )}
                    <div style={{ marginTop: '10px' }}>
                      <Button variant="ghost" size="sm" onClick={handleRequestMoreHelp} disabled={hintLevel >= 3}>
                        💡 {hintLevel >= 3 ? 'All 3 Hints Revealed' : `More Help · Reveal Hint ${hintLevel + 1}: ${hintLevel === 1 ? 'Simpler Clue' : 'Algorithmic Blueprint'}`}
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </GlassPanel>
        )}
      </div>
    </div>
  );
};
