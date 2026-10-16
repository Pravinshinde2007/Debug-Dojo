import React from 'react';
import { NavLink } from 'react-router-dom';
import { Terminal, Award, User, Flame } from 'lucide-react';
import { SettingsPopover } from './SettingsPopover';
import { useAppStore } from '../state/useAppStore';
import { GlassPanel } from './GlassPanel';

export const Header: React.FC = () => {
  const learnerId = useAppStore((s) => s.learnerId);
  const hintsLit = useAppStore((s) => s.hintsLit);

  return (
    <header
      style={{
        position: 'fixed',
        top: '16px',
        left: '24px',
        right: '24px',
        zIndex: 50,
      }}
    >
      <GlassPanel
        style={{
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        {/* Brand / Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '28px' }}>
          <NavLink
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              textDecoration: 'none',
              color: 'var(--color-text)',
            }}
          >
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(255, 107, 74, 0.15)',
                border: '1px solid var(--color-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Terminal size={18} color="var(--color-primary)" />
            </div>
            <span
              style={{
                fontSize: '1.25rem',
                fontWeight: 800,
                letterSpacing: '-0.02em',
                fontFamily: 'var(--font-ui)',
              }}
            >
              Debug <span style={{ color: 'var(--color-primary)' }}>Dojo</span>
            </span>
          </NavLink>

          {/* Navigation Links */}
          <nav
            style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
            aria-label="Main Navigation"
          >
            <NavLink
              to="/"
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.875rem',
                fontWeight: 600,
                textDecoration: 'none',
                color: isActive ? '#FFFFFF' : 'var(--color-text-muted)',
                backgroundColor: isActive ? 'rgba(45, 212, 191, 0.14)' : 'transparent',
                border: isActive
                  ? '1px solid var(--color-secondary)'
                  : '1px solid transparent',
                transition: 'all 0.15s ease',
              })}
            >
              <Terminal size={15} />
              <span>Practice</span>
            </NavLink>

            <NavLink
              to="/learner"
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.875rem',
                fontWeight: 600,
                textDecoration: 'none',
                color: isActive ? '#FFFFFF' : 'var(--color-text-muted)',
                backgroundColor: isActive ? 'rgba(45, 212, 191, 0.14)' : 'transparent',
                border: isActive
                  ? '1px solid var(--color-secondary)'
                  : '1px solid transparent',
                transition: 'all 0.15s ease',
              })}
            >
              <Award size={15} />
              <span>My Dojo</span>
            </NavLink>
          </nav>
        </div>

        {/* Right Section: Status Indicator, Pseudonym, Settings */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Active Dojo Lanterns Indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'rgba(11, 15, 25, 0.5)',
              border: '1px solid var(--color-border)',
              fontSize: '0.75rem',
              color: 'var(--color-text-muted)',
            }}
            title={`${hintsLit} of 4 hint lanterns glowing in the dojo`}
          >
            <Flame
              size={14}
              color={hintsLit > 0 ? 'var(--color-primary)' : 'var(--color-text-muted)'}
            />
            <span>Lanterns: <strong style={{ color: 'var(--color-text)' }}>{hintsLit}/4</strong></span>
          </div>

          {/* Pseudonymous Learner Tag (Rule 8) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'rgba(45, 212, 191, 0.08)',
              border: '1px solid rgba(45, 212, 191, 0.3)',
              fontSize: '0.75rem',
              fontWeight: 600,
              color: 'var(--color-secondary)',
            }}
            title="Pseudonymous Learner ID (Rule 8)"
          >
            <User size={12} />
            <span>{learnerId}</span>
          </div>

          {/* Settings Popover */}
          <SettingsPopover />
        </div>
      </GlassPanel>
    </header>
  );
};
