import React, { useRef, useMemo } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { useAppStore } from '../state/useAppStore';

const CODE_SNIPPETS = [
  'def solve(nums, k):\n    # boundary guard\n    if not nums: return 0\n    return sum(nums[-k:])',
  '# invariant: i < len(arr)\nwhile i < length:\n    if arr[i] > high:\n        high = arr[i]',
  'def filter_even(xs):\n    return [x for x in xs\n            if x % 2 == 0]',
];

interface FloatingPanelProps {
  position: [number, number, number];
  rotation: [number, number, number];
  snippetIndex: number;
  driftSpeed?: number;
}

const SingleFloatingPanel: React.FC<FloatingPanelProps> = ({
  position,
  rotation,
  snippetIndex,
  driftSpeed = 0.5,
}) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const reducedMotion = useAppStore((s) => s.reducedMotion);

  // Generate a procedural canvas texture with faint code lines
  const codeTexture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 384;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = 'rgba(15, 20, 32, 0.4)';
      ctx.fillRect(0, 0, 512, 384);

      // Draw subtle terminal dots
      ctx.fillStyle = 'rgba(255, 107, 74, 0.4)';
      ctx.beginPath();
      ctx.arc(24, 24, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(251, 191, 36, 0.4)';
      ctx.beginPath();
      ctx.arc(42, 24, 6, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'rgba(45, 212, 191, 0.4)';
      ctx.beginPath();
      ctx.arc(60, 24, 6, 0, Math.PI * 2);
      ctx.fill();

      // Draw faint code lines
      ctx.fillStyle = 'rgba(138, 148, 168, 0.28)';
      ctx.font = '22px monospace';
      const lines = CODE_SNIPPETS[snippetIndex % CODE_SNIPPETS.length].split('\n');
      lines.forEach((line, idx) => {
        ctx.fillText(line, 24, 80 + idx * 36);
      });
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.minFilter = THREE.LinearFilter;
    return texture;
  }, [snippetIndex]);

  useFrame((state) => {
    if (!meshRef.current || reducedMotion) return;
    const t = state.clock.getElapsedTime() * driftSpeed;
    meshRef.current.position.y = position[1] + Math.sin(t + position[0]) * 0.12;
    meshRef.current.rotation.y = rotation[1] + Math.cos(t * 0.8 + position[2]) * 0.05;
  });

  return (
    <mesh ref={meshRef} position={position} rotation={rotation}>
      <planeGeometry args={[2.0, 1.5]} />
      <meshStandardMaterial
        map={codeTexture}
        transparent
        opacity={0.42}
        roughness={0.15}
        metalness={0.1}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
};

export const FloatingPanels: React.FC = () => {
  return (
    <group>
      <SingleFloatingPanel
        position={[-2.4, 2.2, -3.5]}
        rotation={[0.08, 0.25, -0.04]}
        snippetIndex={0}
        driftSpeed={0.4}
      />
      <SingleFloatingPanel
        position={[2.2, 1.8, -4.2]}
        rotation={[-0.05, -0.22, 0.03]}
        snippetIndex={1}
        driftSpeed={0.5}
      />
      <SingleFloatingPanel
        position={[-1.2, 3.2, -5.2]}
        rotation={[0.1, 0.1, -0.02]}
        snippetIndex={2}
        driftSpeed={0.35}
      />
    </group>
  );
};
