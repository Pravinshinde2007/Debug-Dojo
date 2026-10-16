import React from 'react';

export const SceneFallback: React.FC = () => {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        background:
          'radial-gradient(circle at 50% 30%, #171E2E 0%, #0F1420 70%, #080B12 100%)',
        overflow: 'hidden',
        pointerEvents: 'none',
      }}
    >
      {/* Decorative ambient glowing orbs */}
      <div
        style={{
          position: 'absolute',
          top: '20%',
          left: '25%',
          width: '350px',
          height: '350px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255, 107, 74, 0.08) 0%, transparent 70%)',
          filter: 'blur(40px)',
          animation: 'pulseGlow 6s ease-in-out infinite alternate',
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: '40%',
          right: '20%',
          width: '400px',
          height: '400px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(45, 212, 191, 0.06) 0%, transparent 70%)',
          filter: 'blur(50px)',
          animation: 'pulseGlow 8s ease-in-out infinite alternate-reverse',
        }}
      />
      {/* Subtle floor reflection gradient */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '40%',
          background:
            'linear-gradient(to top, rgba(15, 20, 32, 0.95), transparent)',
          borderTop: '1px solid rgba(42, 51, 72, 0.3)',
        }}
      />
    </div>
  );
};
