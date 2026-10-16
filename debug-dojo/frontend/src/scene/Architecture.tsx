import React from 'react';

export const Architecture: React.FC = () => {
  // Beams layout (left pillars, right pillars, top crossbars)
  const timberColor = '#141216';
  const timberRoughness = 0.85;

  return (
    <group position={[0, 0, 0]}>
      {/* Back Wall - Shoji Screen with warm backlighting */}
      <group position={[0, 2.5, -9]}>
        {/* Main back wall frame */}
        <mesh position={[0, 0, -0.1]}>
          <planeGeometry args={[20, 8]} />
          <meshBasicMaterial color="#0A0D15" />
        </mesh>

        {/* Shoji Paper Panels (Emissive warm backlight) */}
        {[-4, -2, 0, 2, 4].map((x) => (
          <group key={x} position={[x, 0, 0]}>
            {/* Paper screen plane */}
            <mesh>
              <planeGeometry args={[1.7, 5]} />
              <meshStandardMaterial
                color="#FDE8D0"
                emissive="#FFAA5A"
                emissiveIntensity={0.06}
                roughness={0.9}
                transparent
                opacity={0.35}
              />
            </mesh>
            {/* Wooden lattice grid (shoji frame) */}
            <mesh position={[0, 0, 0.02]}>
              <boxGeometry args={[1.74, 5.04, 0.04]} />
              <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
            </mesh>
            {/* Horizontal bars inside panel */}
            {[-1.8, -0.9, 0, 0.9, 1.8].map((y) => (
              <mesh key={y} position={[0, y, 0.03]}>
                <boxGeometry args={[1.65, 0.05, 0.03]} />
                <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
              </mesh>
            ))}
          </group>
        ))}
      </group>

      {/* Timber Pillars (Side Columns) */}
      {/* Left Columns */}
      <mesh position={[-4.5, 2.5, -3]}>
        <boxGeometry args={[0.35, 7, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>
      <mesh position={[-5.2, 2.5, -6]}>
        <boxGeometry args={[0.35, 7, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>

      {/* Right Columns */}
      <mesh position={[4.5, 2.5, -3]}>
        <boxGeometry args={[0.35, 7, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>
      <mesh position={[5.2, 2.5, -6]}>
        <boxGeometry args={[0.35, 7, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>

      {/* Overhead Beams (Crossbars) */}
      <mesh position={[0, 4.8, -3]}>
        <boxGeometry args={[11, 0.35, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>
      <mesh position={[0, 4.8, -6]}>
        <boxGeometry args={[12, 0.35, 0.35]} />
        <meshStandardMaterial color={timberColor} roughness={timberRoughness} />
      </mesh>
    </group>
  );
};
