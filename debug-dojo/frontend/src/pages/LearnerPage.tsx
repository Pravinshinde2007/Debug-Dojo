import React, { useEffect, useState } from 'react';
import { Award, AlertOctagon, Target, ArrowRight, ShieldCheck } from 'lucide-react';
import { GlassPanel } from '../components/GlassPanel';
import { Button } from '../components/Button';
import { Tag } from '../components/Tag';
import { useAppStore } from '../state/useAppStore';
import { api } from '../api/mockApi';
import type { LearnerProfileResponse } from '../api/mockApi';

export const LearnerPage: React.FC = () => {
  const learnerId = useAppStore((s) => s.learnerId);
  const [profile, setProfile] = useState<LearnerProfileResponse | null>(null);

  useEffect(() => {
    api.getLearner(learnerId).then((data) => setProfile(data));
  }, [learnerId]);

  return (
    <div
      style={{
        paddingTop: '96px',
        paddingBottom: '48px',
        maxWidth: '1100px',
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
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
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
                Pseudonymous Learner Profile (Rule 8)
              </span>
            </div>
            <h1 style={{ fontSize: '1.75rem', fontWeight: 800 }}>{learnerId}</h1>
            <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '4px' }}>
              Concept mastery is weighted by hint usage: passes without hints yield higher mastery.
            </p>
          </div>
        </div>
      </GlassPanel>

      {/* Two-Column Layout: Recurring Mistakes & Concept Mastery */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Recurring Mistakes Card (Rule 5: appears in 2+ different challenges) */}
        <GlassPanel style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <AlertOctagon size={20} color="var(--color-primary)" />
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Recurring Mistakes</h2>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            A tag is classified as "recurring" once it appears in at least <strong>2 different challenges</strong>.
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
                    Seen in challenges: {m.challenges.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
              No recurring mistakes detected yet! Keep solving challenges.
            </div>
          )}
        </GlassPanel>

        {/* Concept Mastery Card (Rule 6) */}
        <GlassPanel style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Award size={20} color="var(--color-secondary)" />
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Concept Mastery</h2>
          </div>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-text-muted)', marginBottom: '16px' }}>
            Estimated mastery scale (0 to 100%) computed dynamically from solution efficiency.
          </p>

          {profile?.mastery ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {Object.entries(profile.mastery).map(([concept, score]) => (
                <div key={concept}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '0.8125rem',
                      fontWeight: 600,
                      marginBottom: '6px',
                      textTransform: 'capitalize',
                    }}
                  >
                    <span>{concept}</span>
                    <span style={{ color: 'var(--color-secondary)' }}>
                      {Math.round(score * 100)}%
                    </span>
                  </div>
                  {/* Progress Bar Track */}
                  <div
                    style={{
                      width: '100%',
                      height: '8px',
                      backgroundColor: 'rgba(11, 15, 25, 0.8)',
                      borderRadius: '999px',
                      overflow: 'hidden',
                      border: '1px solid var(--color-border)',
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.round(score * 100)}%`,
                        height: '100%',
                        backgroundColor:
                          score >= 0.8
                            ? 'var(--color-passed)'
                            : score >= 0.6
                            ? 'var(--color-secondary)'
                            : 'var(--color-wrong-output)',
                        borderRadius: '999px',
                        transition: 'width 0.6s ease',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem' }}>
              Calculating concept mastery...
            </div>
          )}
        </GlassPanel>
      </div>

      {/* Recommended Next Challenge Card */}
      {profile?.next_challenge && (
        <GlassPanel glow="vermilion" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Target size={20} color="var(--color-primary)" />
            <h2 style={{ fontSize: '1.125rem', fontWeight: 700 }}>Recommended Next Challenge</h2>
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text)' }}>
                {profile.next_challenge.title}
              </h3>
              <p
                style={{
                  fontSize: '0.875rem',
                  color: 'var(--color-text-muted)',
                  marginTop: '4px',
                  maxWidth: '700px',
                }}
              >
                <strong>Reason:</strong> {profile.next_challenge.reason}
              </p>
            </div>
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
  );
};
