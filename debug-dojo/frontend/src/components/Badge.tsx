import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'vermilion' | 'teal' | 'muted' | 'amber' | 'cyan';
  size?: 'sm' | 'md';
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
}) => {
  const getStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'amber':
        return {
          backgroundColor: 'rgba(248, 199, 108, 0.15)',
          color: '#f8c76c',
          borderColor: 'rgba(248, 199, 108, 0.4)',
        };
      case 'cyan':
        return {
          backgroundColor: 'rgba(100, 216, 236, 0.15)',
          color: '#64d8ec',
          borderColor: 'rgba(100, 216, 236, 0.4)',
        };
      case 'vermilion':
        return {
          backgroundColor: 'rgba(255, 107, 74, 0.15)',
          color: 'var(--color-primary)',
          borderColor: 'rgba(255, 107, 74, 0.4)',
        };
      case 'teal':
        return {
          backgroundColor: 'rgba(45, 212, 191, 0.12)',
          color: 'var(--color-secondary)',
          borderColor: 'rgba(45, 212, 191, 0.4)',
        };
      case 'muted':
        return {
          backgroundColor: 'rgba(138, 148, 168, 0.1)',
          color: 'var(--color-text-muted)',
          borderColor: 'var(--color-border)',
        };
      case 'default':
      default:
        return {
          backgroundColor: 'rgba(30, 39, 60, 0.6)',
          color: 'var(--color-text)',
          borderColor: 'var(--color-border)',
        };
    }
  };

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: size === 'sm' ? '2px 8px' : '4px 10px',
        fontSize: size === 'sm' ? '0.75rem' : '0.8125rem',
        fontWeight: 500,
        borderRadius: 'var(--radius-sm)',
        border: '1px solid transparent',
        ...getStyles(),
      }}
    >
      {children}
    </span>
  );
};
