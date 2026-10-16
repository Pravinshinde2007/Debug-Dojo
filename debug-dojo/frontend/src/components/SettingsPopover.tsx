import React, { useState, useRef, useEffect } from 'react';
import { Settings, X, Activity } from 'lucide-react';
import { useAppStore } from '../state/useAppStore';
import { GlassPanel } from './GlassPanel';
import { Toggle } from './Toggle';
import { Button } from './Button';

export const SettingsPopover: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  const lowPower = useAppStore((s) => s.lowPower);
  const setLowPower = useAppStore((s) => s.setLowPower);
  const reducedMotion = useAppStore((s) => s.reducedMotion);
  const setReducedMotion = useAppStore((s) => s.setReducedMotion);
  const soundMuted = useAppStore((s) => s.soundMuted);
  const setSoundMuted = useAppStore((s) => s.setSoundMuted);
  const qualityTier = useAppStore((s) => s.qualityTier);
  const setQualityTier = useAppStore((s) => s.setQualityTier);
  const fps = useAppStore((s) => s.fps);

  // Close on outside click or escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  return (
    <div style={{ position: 'relative' }} ref={popoverRef}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Open Display and Accessibility Settings"
        aria-expanded={isOpen}
        icon={<Settings size={18} />}
        style={{
          border: '1px solid var(--color-border)',
          backgroundColor: isOpen ? 'var(--color-surface-hover)' : 'rgba(23, 30, 46, 0.6)',
        }}
      >
        Settings
      </Button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 12px)',
            right: 0,
            width: '320px',
            zIndex: 1000,
          }}
        >
          <GlassPanel
            glow="teal"
            style={{
              padding: '20px',
              border: '1px solid var(--color-border)',
            }}
          >
            {/* Popover Header */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '16px',
                borderBottom: '1px solid var(--color-border)',
                paddingBottom: '10px',
              }}
            >
              <h3 style={{ fontSize: '0.9375rem', fontWeight: 600, color: 'var(--color-text)' }}>
                Dojo Settings
              </h3>
              <button
                onClick={() => setIsOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-text-muted)',
                  cursor: 'pointer',
                  padding: '4px',
                }}
                aria-label="Close settings"
              >
                <X size={16} />
              </button>
            </div>

            {/* Performance Status */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                backgroundColor: 'rgba(11, 15, 25, 0.6)',
                borderRadius: 'var(--radius-sm)',
                marginBottom: '14px',
                fontSize: '0.75rem',
                color: 'var(--color-text-muted)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Activity size={14} color="var(--color-secondary)" />
                <span>FPS: <strong style={{ color: 'var(--color-text)' }}>{fps}</strong></span>
              </div>
              <div>
                <span>Tier: <strong style={{ color: 'var(--color-secondary)', textTransform: 'capitalize' }}>{qualityTier}</strong></span>
              </div>
            </div>

            {/* Settings Toggles */}
            <Toggle
              label="Low Power Mode"
              description="Disables post-processing, reflections and reduces particles"
              checked={lowPower}
              onChange={(val) => setLowPower(val)}
            />

            <Toggle
              label="Reduced Motion"
              description="Disables parallax, swaying lanterns and ember bursts"
              checked={reducedMotion}
              onChange={(val) => setReducedMotion(val)}
            />

            <Toggle
              label="Mute Audio"
              description="Keep ambient sounds and audio muted"
              checked={soundMuted}
              onChange={(val) => setSoundMuted(val)}
            />

            {/* Quality Tier Selector */}
            <div style={{ marginTop: '16px', borderTop: '1px solid var(--color-border)', paddingTop: '12px' }}>
              <label
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--color-text-muted)',
                  display: 'block',
                  marginBottom: '8px',
                  fontWeight: 500,
                }}
              >
                Graphics Quality Tier
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                {(['high', 'medium', 'low'] as const).map((tier) => (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => setQualityTier(tier)}
                    style={{
                      padding: '6px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor:
                        qualityTier === tier ? 'var(--color-surface-hover)' : 'transparent',
                      color:
                        qualityTier === tier ? 'var(--color-secondary)' : 'var(--color-text-muted)',
                      border: `1px solid ${
                        qualityTier === tier ? 'var(--color-secondary)' : 'var(--color-border)'
                      }`,
                      cursor: 'pointer',
                      textTransform: 'capitalize',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {tier}
                  </button>
                ))}
              </div>
            </div>
          </GlassPanel>
        </div>
      )}
    </div>
  );
};
