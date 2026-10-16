import React, { useRef } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { useAppStore } from '../state/useAppStore';

const HINT_COLORS = ['#5EEAD4', '#2DD4BF', '#FBBF24', '#FF6B4A'];

interface LanternProps {
  position: [number, number, number];
  isHintLantern?: boolean;
  hintLevel?: number; // 1 to 4
  baseColor?: string;
}

const SingleLantern: React.FC<LanternProps> = ({
  position,
  isHintLantern = false,
  hintLevel = 1,
  baseColor = '#FF6B4A',
}) => {
  const groupRef = useRef<THREE.Group>(null);
  const lightRef = useRef<THREE.PointLight>(null);
  const meshRef = useRef<THREE.Mesh>(null);

  const reducedMotion = useAppStore((s) => s.reducedMotion);
  const hintsLit = useAppStore((s) => s.hintsLit);
  const sceneMood = useAppStore((s) => s.sceneMood);

  // Determine lit state and color
  const isLit = !isHintLantern || hintsLit >= hintLevel;
  const targetColorHex = isHintLantern
    ? isLit
      ? HINT_COLORS[hintLevel - 1]
      : '#2A3348'
    : baseColor;

  const targetColor = React.useMemo(() => new THREE.Color(targetColorHex), [targetColorHex]);

  useFrame((state) => {
    if (!groupRef.current) return;

    // Gentle sway
    if (!reducedMotion) {
      const time = state.clock.getElapsedTime();
      const swaySpeed = sceneMood === 'running' ? 2.5 : 1.0;
      const swayAmount = 0.04;
      const phase = position[0] * 1.5 + position[2];
      groupRef.current.rotation.z = Math.sin(time * swaySpeed + phase) * swayAmount;
      groupRef.current.rotation.x = Math.cos(time * swaySpeed * 0.8 + phase) * (swayAmount * 0.7);
    } else {
      groupRef.current.rotation.set(0, 0, 0);
    }

    // Flicker & Mood Reactions
    if (lightRef.current) {
      let baseIntensity = isLit ? 1.6 : 0.2;
      let flickerSpeed = sceneMood === 'running' ? 18 : 6;
      let flickerAmp = sceneMood === 'running' ? 0.35 : 0.12;

      if (reducedMotion) {
        flickerAmp = 0;
      }

      if (sceneMood === 'success') {
        baseIntensity = isLit ? 2.8 : 0.8;
      } else if (sceneMood === 'error') {
        baseIntensity = isLit ? 1.1 : 0.15;
      }

      const noise =
        Math.sin(state.clock.getElapsedTime() * flickerSpeed + position[0] * 10) * flickerAmp;
      lightRef.current.intensity = Math.max(0.1, baseIntensity + noise);
    }
  });

  return (
    <group ref={groupRef} position={position}>
      {/* Hanging Cord */}
      <mesh position={[0, 0.7, 0]}>
        <cylinderGeometry args={[0.015, 0.015, 0.8, 8]} />
        <meshBasicMaterial color="#111116" />
      </mesh>

      {/* Top Cap */}
      <mesh position={[0, 0.32, 0]}>
        <cylinderGeometry args={[0.22, 0.22, 0.06, 16]} />
        <meshStandardMaterial color="#1C1816" roughness={0.7} />
      </mesh>

      {/* Main Paper Lantern Body */}
      <mesh ref={meshRef} position={[0, 0, 0]}>
        <cylinderGeometry args={[0.24, 0.28, 0.6, 16]} />
        <meshStandardMaterial
          color={targetColor}
          emissive={targetColor}
          emissiveIntensity={isLit ? (sceneMood === 'success' ? 1.4 : 0.8) : 0.08}
          roughness={0.6}
          transparent
          opacity={isLit ? 0.92 : 0.4}
        />
      </mesh>

      {/* Bottom Cap */}
      <mesh position={[0, -0.32, 0]}>
        <cylinderGeometry args={[0.2, 0.2, 0.06, 16]} />
        <meshStandardMaterial color="#1C1816" roughness={0.7} />
      </mesh>

      {/* Warm Point Light */}
      <pointLight
        ref={lightRef}
        color={targetColor}
        distance={4.5}
        decay={2}
        intensity={isLit ? 1.5 : 0.2}
      />
    </group>
  );
};

export const Lanterns: React.FC = () => {
  return (
    <group>
      {/* Ambient Hall Lanterns (Left Side & Far Background) */}
      <SingleLantern position={[-3.8, 2.8, -2.5]} baseColor="#FF6B4A" />
      <SingleLantern position={[-4.5, 2.5, -5.5]} baseColor="#FF6B4A" />
      <SingleLantern position={[0, 3.4, -7.5]} baseColor="#FF8566" />

      {/* 4 Hint Lanterns (Right Side - Ordered from front to back, lit progressively) */}
      {/* Hint 1: Front */}
      <SingleLantern position={[3.2, 2.3, -1.8]} isHintLantern hintLevel={1} />
      {/* Hint 2: Middle-Front */}
      <SingleLantern position={[3.6, 2.6, -3.2]} isHintLantern hintLevel={2} />
      {/* Hint 3: Middle-Back */}
      <SingleLantern position={[4.1, 2.9, -4.6]} isHintLantern hintLevel={3} />
      {/* Hint 4: Back */}
      <SingleLantern position={[4.6, 3.2, -6.0]} isHintLantern hintLevel={4} />
    </group>
  );
};
