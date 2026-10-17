import React, { useEffect, useState } from 'react';
import { Award, AlertOctagon, Target, ArrowRight, ShieldCheck, History, Info, CheckCircle2, XCircle } from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { Button } from '../components/Button';
import { Tag } from '../components/Tag';
import { useAppStore } from '../state/useAppStore';
import { api } from '../api/mockApi';
import type { LearnerProfileResponse, ConceptSkill, SubmissionHistoryItem } from '../api/mockApi';

export const LearnerPage: React.FC = () => {
  const learnerId = useAppStore((s) => s.learnerId);
  const [profile, setProfile] = useState<LearnerProfileResponse | null>(null);

  useEffect(() => {
    api.getLearner(learnerId).then((data) => setProfile(data));
  }, [learnerId]);

  const skills: ConceptSkill[] = profile?.skills_by_concept || [
    { concept: 'Loops', status: 'Several successful attempts', mastery: 85, attempts: 6, passes: 5, fails: 1 },
    { concept: 'Lists and indexing', status: 'Some repeated mistakes', mastery: 50, attempts: 4, passes: 2, fails: 2 },
    { concept: 'Edge cases', status: 'Needs more practice', mastery: 25, attempts: 3, passes: 1, fails: 2 },
  ];

  const historyItems: SubmissionHistoryItem[] = profile?.submission_history || profile?.history || [];

  const getStatusBadgeStyle = (status: string) => {
    if (status === 'Several successful attempts') {
      return {
        bg: 'rgba(34, 197, 94, 0.15)',
        color: '#4ade80',
        border: '1px solid rgba(34, 197, 94, 0.35)',
      };
    }
    if (status === 'Needs more practice') {
      return {
        bg: 'rgba(239, 68, 68, 0.15)',
        color: '#f87171',
        border: '1px solid rgba(239, 68, 68, 0.35)',
      };
    }
    return {
      bg: 'rgba(245, 158, 11, 0.15)',
      color: '#fbbf24',
      border: '1px solid rgba(245, 158, 11, 0.35)',
    };
  };

  const getScoreColor = (score: number) => {
    if (score >= 70) return '#4ade80';
    if (score >= 45) return '#fbbf24';
    return '#f87171';
  };

  return (
    <div
      style={{
        paddingTop: '96px',
        paddingBottom: '48px',
        maxWidth: '1180px',
        margin: '0 auto',
        paddingLeft: '24px',
        paddingRight: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px',
      }}
    >
      {/* Top Banner: Learner Profile Overview */}
      <GlassPanel glow="teal" style={{ padding: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <ShieldCheck size={20} color="var(--color-secondary)" />
              <span
                style={{
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: 'var(--color-secondary)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                Learner Mastery Profile &amp; Performance Audit Log
              </span>
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>
              {profile?.user_name ? `${profile.user_name} (${learnerId})` : learnerId}
            </h1>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '6px' }}>
              {profile?.disclaimer || "These values are estimates, not proof of a student's ability. Updated after every submission."}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '24px', alignItems: 'center' }}>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>Overall Mastery</div>
              <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--color-secondary)' }}>
                {profile?.overall_mastery ?? 53}%
              </div>
            </div>
          </div>
        </div>
      </GlassPanel>

      {/* Two-Column Layout: Skills by Concept & Recurring Mistakes */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.1fr 0.9fr', gap: '24px' }}>
        {/* Skills by Concept (Rule 9) */}
        <GlassPanel style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Award size={20} color="var(--color-secondary)" />
              <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Skills by Concept</h2>
            </div>
            <span
              style={{
                fontSize: '0.75rem',
                padding: '2px 8px',
                borderRadius: '999px',
                background: 'rgba(56, 189, 248, 0.1)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.25)',
              }}
            >
              How platform measures learning
            </span>
          </div>

          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            Maintains a dynamic mastery estimate for every concept practiced.
          </p>

          {/* Scoring Approach Information Box */}
          <div
            style={{
              padding: '12px 14px',
              backgroundColor: 'rgba(15, 23, 42, 0.65)',
              border: '1px solid rgba(56, 189, 248, 0.25)',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.8125rem',
              color: 'var(--color-text-muted)',
              marginBottom: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#38bdf8', fontWeight: 600 }}>
              <Info size={15} />
              <span>Sensible Hint-Weighted Scoring Approach</span>
            </div>
            <div>• <strong>Passing without hints</strong> earns the most credit (+15%).</div>
            <div>• <strong>Passing after hints</strong> earns less credit (+2% to +10% based on hints used).</div>
            <div>• <strong>Failed attempts</strong> do not increase mastery (-4%).</div>
            <div>• <strong>Repeated failures</strong> trigger a recommendation for easier foundational practice.</div>
          </div>

          {/* Skills Breakdown List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {skills.map((item) => {
              const badgeStyle = getStatusBadgeStyle(item.status);
              const scoreColor = getScoreColor(item.mastery);
              return (
                <div
                  key={item.concept}
                  style={{
                    padding: '14px 16px',
                    backgroundColor: 'rgba(11, 15, 25, 0.6)',
                    border: '1px solid var(--color-border)',
                    borderRadius: 'var(--radius-md)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <span style={{ fontWeight: 700, fontSize: '0.9375rem' }}>{item.concept}</span>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          padding: '2px 8px',
                          borderRadius: '999px',
                          backgroundColor: badgeStyle.bg,
                          color: badgeStyle.color,
                          border: badgeStyle.border,
                          fontWeight: 500,
                        }}
                      >
                        {item.status}
                      </span>
                    </div>
                    <span style={{ fontSize: '1rem', fontWeight: 800, color: scoreColor }}>
                      {item.mastery}%
                    </span>
                  </div>

                  {/* Progress Bar Track */}
                  <div
                    style={{
                      width: '100%',
                      height: '7px',
                      backgroundColor: 'rgba(11, 15, 25, 0.9)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                      border: '1px solid rgba(255, 255, 255, 0.08)',
                    }}
                  >
                    <div
                      style={{
                        width: `${item.mastery}%`,
                        height: '100%',
                        backgroundColor: scoreColor,
                        borderRadius: '999px',
                        transition: 'width 0.6s ease',
                      }}
                    />
                  </div>

                  {(item.attempts > 0 || item.is_illustrative) && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)', display: 'flex', gap: '12px' }}>
                      <span>{item.attempts} attempt{item.attempts !== 1 ? 's' : ''}</span>
                      <span>•</span>
                      <span style={{ color: '#4ade80' }}>{item.passes} passed</span>
                      <span>•</span>
                      <span style={{ color: '#f87171' }}>{item.fails} failed</span>
                      {item.is_illustrative && (
                        <>
                          <span>•</span>
                          <span style={{ fontStyle: 'italic', color: '#94a3b8' }}>Illustrative dashboard values</span>
                        </>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </GlassPanel>

        {/* Right Column: Recurring Mistakes & Recommended Next Challenge */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Recurring Mistakes Card (Rule 5) */}
          <GlassPanel style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <AlertOctagon size={20} color="var(--color-primary)" />
              <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Recurring Mistakes</h2>
            </div>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
              A tag is classified as recurring once it appears across at least <strong>2 different challenges</strong>.
            </p>

            {profile?.recurring_mistakes && profile.recurring_mistakes.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {profile.recurring_mistakes.map((m) => (
                  <div
                    key={m.tag}
                    style={{
                      padding: '12px 16px',
                      backgroundColor: 'rgba(11, 15, 25, 0.6)',
                      border: '1px solid var(--color-border)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        marginBottom: '6px',
                      }}
                    >
                      <Tag name={m.tag} isRecurring />
                      <span style={{ fontSize: '0.75rem', color: 'var(--color-primary)', fontWeight: 600 }}>
                        {m.count} occurrences
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                      Seen in: {m.challenges.join(', ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
                No recurring mistakes detected yet! Keep practicing to track patterns.
              </div>
            )}
          </GlassPanel>

          {/* Recommended Next Challenge Card */}
          {profile?.next_challenge && (
            <GlassPanel glow="vermilion" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <Target size={20} color="var(--color-primary)" />
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Recommended Next Challenge</h2>
              </div>
              <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '12px' }}>
                Adaptive recommendation: addresses recurring mistakes or routes to easier practice upon repeated failures.
              </p>
              <div>
                <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--color-text)', marginBottom: '4px' }}>
                  {profile.next_challenge.title}
                </h3>
                <p
                  style={{
                    fontSize: '0.8125rem',
                    color: 'var(--color-text-muted)',
                    marginBottom: '16px',
                    lineHeight: 1.5,
                  }}
                >
                  <strong style={{ color: 'var(--color-secondary)' }}>Reason:</strong> {profile.next_challenge.reason}
                </p>
                <Button
                  variant="primary"
                  icon={<ArrowRight size={16} />}
                  onClick={() => (window.location.href = '/')}
                >
                  Start Challenge
                </Button>
              </div>
            </GlassPanel>
          )}
        </div>
      </div>

      {/* Submission History Section for Judges */}
      <GlassPanel style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <History size={20} color="var(--color-secondary)" />
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Submission &amp; Performance History</h2>
          </div>
          <span
            style={{
              fontSize: '0.75rem',
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'rgba(168, 85, 247, 0.1)',
              color: '#c084fc',
              border: '1px solid rgba(168, 85, 247, 0.25)',
            }}
          >
            Judges' Performance Audit Trail
          </span>
        </div>
        <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
          Inspect how learner performance changes over time and how hint utilization affects mastery credit.
        </p>

        {historyItems.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8125rem', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--color-border)', color: 'var(--color-text-muted)' }}>
                  <th style={{ padding: '10px 12px' }}>Challenge</th>
                  <th style={{ padding: '10px 12px' }}>Outcome</th>
                  <th style={{ padding: '10px 12px' }}>Hints Used</th>
                  <th style={{ padding: '10px 12px' }}>Mastery Impact</th>
                  <th style={{ padding: '10px 12px' }}>Mistake Tags</th>
                  <th style={{ padding: '10px 12px' }}>Code Preview</th>
                  <th style={{ padding: '10px 12px' }}>Time</th>
                </tr>
              </thead>
              <tbody>
                {historyItems.map((h, i) => (
                  <tr
                    key={h.id || i}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                      backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(15, 23, 42, 0.3)',
                    }}
                  >
                    <td style={{ padding: '12px' }}>
                      <div style={{ fontWeight: 600 }}>{h.title}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>{h.difficulty}</div>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          backgroundColor: h.passed ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                          color: h.passed ? '#4ade80' : '#f87171',
                        }}
                      >
                        {h.passed ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
                        {h.outcome || (h.passed ? 'Passed' : 'Failed')}
                      </span>
                    </td>
                    <td style={{ padding: '12px', color: 'var(--color-text)' }}>
                      {h.hints_used != null ? `${h.hints_used} hint${h.hints_used !== 1 ? 's' : ''}` : '0 hints'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span
                        style={{
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          color: h.passed ? '#4ade80' : '#f87171',
                        }}
                      >
                        {h.mastery_impact}
                      </span>
                    </td>
                    <td style={{ padding: '12px' }}>
                      {h.mistake_tags && h.mistake_tags.length > 0 ? (
                        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                          {h.mistake_tags.map((t) => (
                            <Tag key={t} name={t} />
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: 'var(--color-text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <code
                        style={{
                          fontSize: '0.75rem',
                          fontFamily: 'monospace',
                          color: '#38bdf8',
                          background: 'rgba(0,0,0,0.3)',
                          padding: '3px 6px',
                          borderRadius: '4px',
                          maxWidth: '180px',
                          display: 'inline-block',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {h.code_snippet}
                      </code>
                    </td>
                    <td style={{ padding: '12px', color: 'var(--color-text-muted)', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                      {h.created_at || 'Recently'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
            No submissions recorded yet. Submissions will appear here with hint usage and mastery impact.
          </div>
        )}
      </GlassPanel>
    </div>
  );
};

