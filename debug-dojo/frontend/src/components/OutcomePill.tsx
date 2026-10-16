import React from 'react';
import { Check, EqualNot, AlertCircle, Clock } from 'lucide-react';

export type OutcomeType = 'passed' | 'wrong_output' | 'runtime_error' | 'timeout';

interface OutcomePillProps {
  outcome: OutcomeType;
  label?: string;
  size?: 'sm' | 'md';
}

const OUTCOME_CONFIG: Record<
  OutcomeType,
  { label: string; color: string; bg: string; icon: React.ComponentType<{ size: number }> }
> = {
  passed: {
    label: 'Passed',
    color: 'var(--color-passed)',
    bg: 'var(--color-passed-bg)',
    icon: Check,
  },
  wrong_output: {
    label: 'Wrong Output',
    color: 'var(--color-wrong-output)',
    bg: 'var(--color-wrong-output-bg)',
    icon: EqualNot,
  },
  runtime_error: {
    label: 'Runtime Error',
    color: 'var(--color-runtime-error)',
    bg: 'var(--color-runtime-error-bg)',
    icon: AlertCircle,
  },
  timeout: {
    label: 'Timeout',
    color: 'var(--color-timeout)',
    bg: 'var(--color-timeout-bg)',
    icon: Clock,
  },
};

export const OutcomePill: React.FC<OutcomePillProps> = ({ outcome, label, size = 'md' }) => {
  const config = OUTCOME_CONFIG[outcome] || OUTCOME_CONFIG.passed;
  const Icon = config.icon;
  const displayLabel = label || config.label;

  const isSmall = size === 'sm';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: isSmall ? '4px' : '6px',
        padding: isSmall ? '2px 8px' : '4px 10px',
        borderRadius: 'var(--radius-full)',
        backgroundColor: config.bg,
        color: config.color,
        border: `1px solid ${config.color}`,
        fontSize: isSmall ? '0.75rem' : '0.8125rem',
        fontWeight: 600,
        fontFamily: 'var(--font-ui)',
        lineHeight: 1.2,
      }}
      aria-label={`Test outcome: ${displayLabel}`}
    >
      <Icon size={isSmall ? 12 : 14} />
      <span>{displayLabel}</span>
    </span>
  );
};
