import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  icon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  disabled,
  className = '',
  style,
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'primary':
        return {
          backgroundColor: 'var(--color-primary)',
          color: '#FFFFFF',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          boxShadow: 'var(--shadow-glow-vermilion), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
        };
      case 'secondary':
        return {
          backgroundColor: 'transparent',
          color: 'var(--color-secondary)',
          border: '1px solid var(--color-secondary)',
          boxShadow: 'inset 0 0 12px rgba(45, 212, 191, 0.08)',
        };
      case 'danger':
        return {
          backgroundColor: 'rgba(248, 113, 113, 0.15)',
          color: 'var(--color-runtime-error)',
          border: '1px solid var(--color-runtime-error)',
        };
      case 'ghost':
      default:
        return {
          backgroundColor: 'transparent',
          color: 'var(--color-text-muted)',
          border: '1px solid transparent',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return {
          padding: '6px 12px',
          fontSize: '0.8125rem',
          borderRadius: 'var(--radius-sm)',
        };
      case 'lg':
        return {
          padding: '12px 24px',
          fontSize: '1rem',
          borderRadius: 'var(--radius-md)',
        };
      case 'md':
      default:
        return {
          padding: '8px 16px',
          fontSize: '0.875rem',
          borderRadius: 'var(--radius-md)',
        };
    }
  };

  const isDisabled = disabled || loading;

  return (
    <button
      className={`dojo-button ${className}`}
      disabled={isDisabled}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        fontWeight: 600,
        fontFamily: 'var(--font-ui)',
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled ? 0.55 : 1,
        transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        ...getSizeStyles(),
        ...getVariantStyles(),
        ...style,
      }}
      {...props}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : icon}
      <span>{children}</span>
    </button>
  );
};
