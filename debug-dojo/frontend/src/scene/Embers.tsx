import React, { useRef, useMemo, useEffect } from 'react';
import * as THREE from 'three';
import { useFrame } from '@react-three/fiber';
import { useAppStore } from '../state/useAppStore';

export const Embers: React.FC = () => {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const lowPower = useAppStore((s) => s.lowPower);
  const qualityTier = useAppStore((s) => s.qualityTier);
  const reducedMotion = useAppStore((s) => s.reducedMotion);
  const sceneMood = useAppStore((s) => s.sceneMood);

  const particleCount = lowPower || qualityTier === 'low' ? 45 : 180;

  // Particle simulation state
  const particles = useMemo(() => {
    const data = [];
    for (let i = 0; i < 250; i++) {
      data.push({
        x: (Math.random() - 0.5) * 12,
        y: Math.random() * 5 - 0.5,
        z: (Math.random() - 0.5) * 8 - 4,
        speedY: Math.random() * 0.4 + 0.2,
        driftX: (Math.random() - 0.5) * 0.2,
        driftZ: (Math.random() - 0.5) * 0.2,
        scale: Math.random() * 0.04 + 0.02,
        colorIndex: Math.random() > 0.4 ? 0 : 1, // vermilion or amber
      });
    }
    return data;
  }, []);

  const dummy = useMemo(() => new THREE.Object3D(), []);

  // Initialize colors
  useEffect(() => {
    if (!meshRef.current) return;
    const vermilion = new THREE.Color('#FF6B4A');
    const amber = new THREE.Color('#FBBF24');
    for (let i = 0; i < particleCount; i++) {
      const color = particles[i].colorIndex === 0 ? vermilion : amber;
      meshRef.current.setColorAt(i, color);
    }
    if (meshRef.current.instanceColor) {
      meshRef.current.instanceColor.needsUpdate = true;
    }
  }, [particleCount, particles]);

  useFrame((state, delta) => {
    if (!meshRef.current) return;

    const burstMultiplier =
      sceneMood === 'success' ? 3.5 : sceneMood === 'running' ? 1.6 : 1.0;
    const time = state.clock.getElapsedTime();

    for (let i = 0; i < particleCount; i++) {
      const p = particles[i];

      if (!reducedMotion) {
        p.y += p.speedY * burstMultiplier * delta;
        p.x += Math.sin(time * 0.8 + i) * p.driftX * delta * 2;
        p.z += Math.cos(time * 0.8 + i) * p.driftZ * delta * 2;

        // Reset when reaching top
        if (p.y > 5.5) {
          p.y = -0.5;
          p.x = (Math.random() - 0.5) * 12;
          p.z = (Math.random() - 0.5) * 8 - 4;
        }
      }

      dummy.position.set(p.x, p.y, p.z);
      dummy.scale.setScalar(p.scale * (sceneMood === 'success' ? 1.4 : 1.0));
      dummy.updateMatrix();

      meshRef.current.setMatrixAt(i, dummy.matrix);
    }
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[undefined, undefined, particleCount]}
      frustumCulled={false}
    >
      <sphereGeometry args={[1, 6, 6]} />
      <meshBasicMaterial
        color="#FFA372"
        transparent
        opacity={0.8}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </instancedMesh>
  );
};
