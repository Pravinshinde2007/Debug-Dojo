import React from 'react';
import { Tag as TagIcon } from 'lucide-react';

interface TagProps {
  name: string;
  count?: number;
  isRecurring?: boolean;
}

const TAG_LABELS: Record<string, string> = {
  off_by_one: 'Off-by-One',
  unhandled_short_input: 'Unhandled Short Input',
  print_not_return: 'Print Instead of Return',
  boundary_comparison: 'Boundary Comparison',
  mutates_input: 'Mutates Input Parameter',
};

export const Tag: React.FC<TagProps> = ({ name, count, isRecurring = false }) => {
  const label = TAG_LABELS[name] || name.replace(/_/g, ' ');

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '3px 10px',
        fontSize: '0.8125rem',
        borderRadius: 'var(--radius-sm)',
        backgroundColor: isRecurring ? 'rgba(255, 107, 74, 0.15)' : 'rgba(42, 51, 72, 0.5)',
        color: isRecurring ? 'var(--color-primary)' : 'var(--color-text)',
        border: `1px solid ${isRecurring ? 'var(--color-primary)' : 'var(--color-border)'}`,
        fontWeight: 500,
        fontFamily: 'var(--font-ui)',
      }}
      title={isRecurring ? 'Recurring mistake across 2+ challenges' : 'Observed mistake tag'}
    >
      <TagIcon size={12} color={isRecurring ? 'var(--color-primary)' : 'var(--color-text-muted)'} />
      <span>{label}</span>
      {count !== undefined && (
        <span
          style={{
            backgroundColor: isRecurring ? 'var(--color-primary)' : 'var(--color-border)',
            color: isRecurring ? '#fff' : 'var(--color-text-muted)',
            borderRadius: '999px',
            fontSize: '0.7rem',
            padding: '0 6px',
            lineHeight: 1.4,
            fontWeight: 700,
          }}
        >
          {count}
        </span>
      )}
    </span>
  );
};
