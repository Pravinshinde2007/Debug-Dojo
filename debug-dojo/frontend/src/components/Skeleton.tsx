import React from 'react';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  className?: string;
  style?: React.CSSProperties;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width = '100%',
  height = '20px',
  borderRadius = 'var(--radius-sm)',
  className = '',
  style,
}) => {
  return (
    <div
      className={`skeleton-shimmer ${className}`}
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: 'rgba(42, 51, 72, 0.4)',
        background:
          'linear-gradient(90deg, rgba(42,51,72,0.3) 0%, rgba(42,51,72,0.6) 50%, rgba(42,51,72,0.3) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.8s infinite',
        ...style,
      }}
    />
  );
};
