import React, { useState, useEffect } from 'react';
import { Play, Sparkles, HelpCircle, Code2 } from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { Button } from '../components/Button';
import { OutcomePill } from '../components/OutcomePill';
import { Tag } from '../components/Tag';
import { Badge } from '../components/Badge';
import { ProblemAnalyzerSandbox } from '../components/ProblemAnalyzerSandbox';
import { useAppStore } from '../state/useAppStore';
import { api } from '../api/mockApi';
import type { Challenge, SubmitResponse, HintResponse } from '../api/mockApi';

export const PracticePage: React.FC = () => {
  const [activeMode, setActiveMode] = useState<'curated' | 'analyzer'>('curated');
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [code, setCode] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [submission, setSubmission] = useState<SubmitResponse | null>(null);
  const [hintData, setHintData] = useState<HintResponse | null>(null);
  const [isHintLoading, setIsHintLoading] = useState(false);

  const setSceneMood = useAppStore((s) => s.setSceneMood);
  const triggerSuccess = useAppStore((s) => s.triggerSuccess);
  const triggerError = useAppStore((s) => s.triggerError);
  const setHintsLit = useAppStore((s) => s.setHintsLit);
  const learnerId = useAppStore((s) => s.learnerId);

  useEffect(() => {
    api.getChallenges().then((challenges) => {
      if (challenges.length > 0) {
        setChallenge(challenges[0]);
        setCode(challenges[0].starter_code);
      }
    });
  }, []);

  const handleRunCode = async () => {
    if (!challenge) return;
    setIsRunning(true);
    setSceneMood('running');

    try {
      const res = await api.submit(learnerId, challenge.id, code);
      setSubmission(res);

      const allPassed =
        res.visible.every((t) => t.outcome === 'passed') &&
        res.hidden.every((t) => t.outcome === 'passed');

      if (allPassed) {
        triggerSuccess();
      } else {
        triggerError();
      }
    } finally {
      setIsRunning(false);
    }
  };

  const handleRequestHint = async () => {
    if (!submission) return;
    setIsHintLoading(true);
    try {
      const failedTest = submission.visible?.find((t: any) => t.outcome !== 'passed');
      const res = await api.requestHint(submission.submission_id, {
        challenge_id: challenge?.id,
        code,
        hint_level: (hintData?.level || 0) + 1,
        error_type: failedTest?.outcome === 'runtime_error' ? 'RuntimeError' : 'Wrong Output',
        error_msg: submission.explanation || '',
        failed_call: failedTest?.call,
        expected: failedTest?.expected,
        got: failedTest?.got
      });
      setHintData(res);
      // Light up hint lanterns in 3D Dojo
      setHintsLit(res.level);
    } finally {
      setIsHintLoading(false);
    }
  };

  return (
    <div
      style={{
        paddingTop: '96px',
        paddingBottom: '48px',
        maxWidth: '1440px',
        margin: '0 auto',
        paddingLeft: '24px',
        paddingRight: '24px',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '24px',
        minHeight: 'calc(100vh - 96px)',
      }}
    >
      {/* Top Practice Mode Switcher */}
      <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.08)', paddingBottom: '12px', alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => setActiveMode('curated')}
          style={{
            background: activeMode === 'curated' ? 'rgba(45, 212, 191, 0.15)' : 'transparent',
            border: activeMode === 'curated' ? '1px solid var(--color-secondary)' : '1px solid transparent',
            color: activeMode === 'curated' ? '#fff' : 'var(--color-text-muted)',
            padding: '6px 14px',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          🥋 Curated Dojo Challenges
        </button>
        <button
          type="button"
          onClick={() => setActiveMode('analyzer')}
          style={{
            background: activeMode === 'analyzer' ? 'rgba(168, 140, 255, 0.15)' : 'transparent',
            border: activeMode === 'analyzer' ? '1px solid var(--color-primary)' : '1px solid transparent',
            color: activeMode === 'analyzer' ? '#fff' : 'var(--color-text-muted)',
            padding: '6px 14px',
            borderRadius: 'var(--radius-sm)',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          ✨ AI Problem Analyzer &amp; Sandbox
        </button>
      </div>

      {activeMode === 'analyzer' ? (
        <div style={{ gridColumn: '1 / -1' }}>
          <ProblemAnalyzerSandbox />
        </div>
      ) : (
        <>
          {/* Left Column: Challenge Description, Instructions, Hints */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <GlassPanel style={{ padding: '24px' }}>
          {challenge ? (
            <>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Badge variant="vermilion">Beginner</Badge>
                  {challenge.concepts.map((c) => (
                    <Badge key={c} variant="teal">
                      {c}
                    </Badge>
                  ))}
                </div>
              </div>

              <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '12px' }}>
                {challenge.title}
              </h1>

              <div
                style={{
                  fontSize: '0.9375rem',
                  lineHeight: 1.6,
                  color: 'var(--color-text-muted)',
                  whiteSpace: 'pre-line',
                  marginBottom: '20px',
                }}
              >
                {challenge.description}
              </div>

              {/* Story Context Callout */}
              <div
                style={{
                  padding: '12px 16px',
                  backgroundColor: 'rgba(45, 212, 191, 0.08)',
                  border: '1px solid rgba(45, 212, 191, 0.25)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.8125rem',
                  color: 'var(--color-text)',
                  display: 'flex',
                  gap: '10px',
                }}
              >
                <HelpCircle size={18} color="var(--color-secondary)" style={{ flexShrink: 0 }} />
                <span>
                  <strong>Dojo Story:</strong> Rohan's function passes his 3 visible examples, but
                  fails a hidden edge case. Observe how the 4 hint lanterns guide him without
                  revealing the answer!
                </span>
              </div>
            </>
          ) : (
            <div style={{ color: 'var(--color-text-muted)' }}>Loading challenge...</div>
          )}
        </GlassPanel>

        {/* Progressive Hints Section */}
        {submission && (
          <GlassPanel glow={hintData ? 'vermilion' : 'none'} style={{ padding: '24px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '14px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Sparkles size={18} color="var(--color-primary)" />
                <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Progressive Hints</h3>
                <span
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-muted)',
                    marginLeft: '4px',
                  }}
                >
                  (Level {hintData ? hintData.level : 0} of 4)
                </span>
              </div>

              <Button
                size="sm"
                variant="secondary"
                onClick={handleRequestHint}
                loading={isHintLoading}
                disabled={Boolean(hintData && hintData.level >= 4)}
              >
                {hintData ? 'Next Specific Hint' : 'Get First Hint'}
              </Button>
            </div>

            {hintData ? (
              <div
                style={{
                  padding: '14px',
                  backgroundColor: 'rgba(11, 15, 25, 0.7)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.875rem',
                  lineHeight: 1.5,
                  color: 'var(--color-text)',
                  borderLeft: '4px solid var(--color-primary)',
                }}
              >
                <div style={{ fontWeight: 600, color: 'var(--color-primary)', marginBottom: '4px' }}>
                  Hint #{hintData.level}:
                </div>
                {hintData.hint}
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--color-text-dim)',
                    marginTop: '8px',
                  }}
                >
                  Notice: Lantern #{hintData.level} has lit up in the Dojo on your right!
                </div>
              </div>
            ) : (
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)' }}>
                Stuck? Request progressive hints that guide your thought process without ever
                revealing code or the complete solution.
              </p>
            )}
          </GlassPanel>
        )}
      </div>

      {/* Right Column: Code Editor & Test Outcomes */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Editor Glass Panel */}
        <GlassPanel style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Code2 size={18} color="var(--color-secondary)" />
              <span style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Python Solution</span>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                variant="primary"
                onClick={handleRunCode}
                loading={isRunning}
                icon={<Play size={16} />}
              >
                Run Code
              </Button>
            </div>
          </div>

          {/* Simple Code Area for Stage 1 (Monaco or textarea fallback) */}
          <textarea
            value={code}
            onChange={(e) => setCode(e.target.value)}
            spellCheck={false}
            style={{
              flex: 1,
              minHeight: '260px',
              backgroundColor: 'var(--color-editor)',
              color: 'var(--color-text)',
              fontFamily: 'var(--font-code)',
              fontSize: '0.875rem',
              padding: '16px',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md)',
              resize: 'vertical',
              outline: 'none',
              lineHeight: 1.5,
            }}
            aria-label="Python code input"
          />
        </GlassPanel>

        {/* Test Outcomes & Diagnostics Panel */}
        {submission && (
          <GlassPanel style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '14px' }}>
              Test Suite Results
            </h3>

            {/* Explanation */}
            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(23, 30, 46, 0.8)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                marginBottom: '16px',
                fontSize: '0.875rem',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 600, color: 'var(--color-text)', marginBottom: '4px' }}>
                Dojo Feedback:
              </div>
              <div style={{ color: 'var(--color-text-muted)' }}>{submission.explanation}</div>
            </div>

            {/* Mistake Tags */}
            {submission.mistake_tags.length > 0 && (
              <div style={{ marginBottom: '16px' }}>
                <span style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginRight: '8px' }}>
                  Mistake Tags:
                </span>
                <div style={{ display: 'inline-flex', gap: '6px', flexWrap: 'wrap' }}>
                  {submission.mistake_tags.map((tag) => (
                    <Tag key={tag} name={tag} />
                  ))}
                </div>
              </div>
            )}

            {/* Visible Tests List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '12px' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Visible Examples (3)
              </span>
              {submission.visible.map((vt) => (
                <div
                  key={vt.test}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    backgroundColor: 'rgba(11, 15, 25, 0.5)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8125rem',
                    fontFamily: 'var(--font-code)',
                  }}
                >
                  <span style={{ color: 'var(--color-text)' }}>{vt.call}</span>
                  <OutcomePill outcome={vt.outcome} size="sm" />
                </div>
              ))}
            </div>

            {/* Hidden Tests (Rule 2: Never reveal input, expected, or output) */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--color-text-muted)' }}>
                Hidden Verification Tests (2)
              </span>
              {submission.hidden.map((ht) => (
                <div
                  key={ht.test}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    backgroundColor: 'rgba(11, 15, 25, 0.5)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-sm)',
                    fontSize: '0.8125rem',
                  }}
                >
                  <span style={{ color: 'var(--color-text-muted)' }}>
                    Hidden Case #{ht.test} (Secret input/output per Rule 2)
                  </span>
                  <OutcomePill outcome={ht.outcome} size="sm" />
                </div>
              ))}
            </div>
          </GlassPanel>
        )}
      </div>
     </>
    )}
  </div>
  );
};
