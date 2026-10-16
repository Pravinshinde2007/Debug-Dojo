import React, { useMemo } from 'react';
import * as THREE from 'three';
import { MeshReflectorMaterial } from '@react-three/drei';
import { useAppStore } from '../state/useAppStore';

export const Floor: React.FC = () => {
  const qualityTier = useAppStore((s) => s.qualityTier);
  const lowPower = useAppStore((s) => s.lowPower);

  // Generate a procedural noise canvas texture for roughness
  const roughnessMap = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#666666';
      ctx.fillRect(0, 0, 256, 256);
      for (let i = 0; i < 4000; i++) {
        const x = Math.random() * 256;
        const y = Math.random() * 256;
        const radius = Math.random() * 3 + 1;
        const val = Math.floor(Math.random() * 80 + 70);
        ctx.fillStyle = `rgb(${val}, ${val}, ${val})`;
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.repeat.set(12, 12);
    return texture;
  }, []);

  const useReflection = !lowPower && qualityTier !== 'low';

  return (
    <mesh
      rotation={[-Math.PI / 2, 0, 0]}
      position={[0, -0.6, -2]}
      receiveShadow={useReflection}
    >
      <planeGeometry args={[30, 30]} />
      {useReflection ? (
        <MeshReflectorMaterial
          blur={[300, 100]}
          resolution={512}
          mirror={0.4}
          mixBlur={0.8}
          mixStrength={1.2}
          roughness={0.4}
          metalness={0.15}
          color="#151B2B"
          roughnessMap={roughnessMap}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          depthScale={1.2}
          depthToBlurRatioBias={0.25}
        />
      ) : (
        <meshStandardMaterial
          color="#151B2B"
          roughness={0.5}
          metalness={0.1}
          roughnessMap={roughnessMap}
        />
      )}
    </mesh>
  );
};
