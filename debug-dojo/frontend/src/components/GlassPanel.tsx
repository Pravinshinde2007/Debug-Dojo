import React from 'react';

interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  glow?: 'none' | 'vermilion' | 'teal';
}

export const GlassPanel: React.FC<GlassPanelProps> = ({
  children,
  className = '',
  glow = 'none',
  style,
  ...props
}) => {
  const glowStyle =
    glow === 'vermilion'
      ? { boxShadow: 'var(--shadow-lg), var(--shadow-glow-vermilion)' }
      : glow === 'teal'
      ? { boxShadow: 'var(--shadow-lg), var(--shadow-glow-teal)' }
      : { boxShadow: 'var(--shadow-md)' };

  return (
    <div
      className={`glass-panel ${className}`}
      style={{
        backgroundColor: 'var(--color-surface-translucent)',
        backdropFilter: 'var(--glass-blur)',
        WebkitBackdropFilter: 'var(--glass-blur)',
        border: '1px solid var(--color-border)',
        boxShadow: `${glowStyle.boxShadow}, var(--glass-inner-highlight)`,
        borderRadius: 'var(--radius-lg)',
        color: 'var(--color-text)',
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  );
};
