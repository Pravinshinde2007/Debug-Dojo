import React from 'react';

interface ToggleProps {
  id?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}

export const Toggle: React.FC<ToggleProps> = ({
  id,
  checked,
  onChange,
  label,
  description,
  disabled = false,
}) => {
  const toggleId = id || `toggle-${label.toLowerCase().replace(/\s+/g, '-')}`;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '16px',
        padding: '8px 0',
      }}
    >
      <div>
        <label
          htmlFor={toggleId}
          style={{
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--color-text)',
            cursor: disabled ? 'not-allowed' : 'pointer',
            display: 'block',
          }}
        >
          {label}
        </label>
        {description && (
          <p
            style={{
              fontSize: '0.75rem',
              color: 'var(--color-text-muted)',
              marginTop: '2px',
            }}
          >
            {description}
          </p>
        )}
      </div>

      <button
        id={toggleId}
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        style={{
          position: 'relative',
          width: '44px',
          height: '24px',
          borderRadius: '999px',
          backgroundColor: checked ? 'var(--color-secondary)' : 'var(--color-border)',
          border: 'none',
          cursor: disabled ? 'not-allowed' : 'pointer',
          transition: 'background-color 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          padding: 0,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            position: 'absolute',
            top: '2px',
            left: checked ? '22px' : '2px',
            width: '20px',
            height: '20px',
            borderRadius: '50%',
            backgroundColor: '#FFFFFF',
            boxShadow: 'var(--shadow-sm)',
            transition: 'left 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
        />
      </button>
    </div>
  );
};
