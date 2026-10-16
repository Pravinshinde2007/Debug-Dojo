import React, { useRef, useEffect, useState, Component } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { useAppStore } from '../state/useAppStore';
import { Floor } from './Floor';
import { Architecture } from './Architecture';
import { Lanterns } from './Lanterns';
import { FloatingPanels } from './FloatingPanels';
import { Embers } from './Embers';
import { PostFX } from './PostFX';
import { SceneFallback } from './SceneFallback';

// Error Boundary for WebGL failures
interface ErrorBoundaryState {
  hasError: boolean;
}

class WebGLErrorBoundary extends Component<{ children: React.ReactNode }, ErrorBoundaryState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn('WebGL Rendering Error caught by DojoScene boundary:', error);
  }

  render() {
    if (this.state.hasError) {
      return <SceneFallback />;
    }
    return this.props.children;
  }
}

// Camera Rig with Parallax, Sine Drift, and FPS monitoring
const CameraRig: React.FC = () => {
  const reducedMotion = useAppStore((s) => s.reducedMotion);
  const setFps = useAppStore((s) => s.setFps);
  const setQualityTier = useAppStore((s) => s.setQualityTier);
  const qualityTier = useAppStore((s) => s.qualityTier);

  const mousePos = useRef({ x: 0, y: 0 });
  const frameCount = useRef(0);
  const startTime = useRef(performance.now());
  const evaluatedFps = useRef(false);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (reducedMotion) return;
      const x = (e.clientX / window.innerWidth) * 2 - 1;
      const y = -(e.clientY / window.innerHeight) * 2 + 1;
      mousePos.current = { x, y };
    };

    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [reducedMotion]);

  useFrame((state) => {
    // 1. Measure FPS for first 3 seconds
    if (!evaluatedFps.current) {
      frameCount.current++;
      const elapsed = performance.now() - startTime.current;
      if (elapsed > 3000) {
        evaluatedFps.current = true;
        const measuredFps = Math.round((frameCount.current / elapsed) * 1000);
        setFps(measuredFps);
        if (measuredFps < 40 && qualityTier === 'high') {
          console.info(`Measured ${measuredFps} FPS. Automatically dropping to medium tier.`);
          setQualityTier('medium');
        }
      }
    }

    // 2. Camera drift and parallax
    const camera = state.camera;
    const time = state.clock.getElapsedTime();

    if (!reducedMotion) {
      // Gentle sine drift
      const driftX = Math.sin(time * 0.25) * 0.15;
      const driftY = Math.cos(time * 0.35) * 0.08;

      // Mouse parallax (clamped to max 0.3 units)
      const targetX = driftX + mousePos.current.x * 0.28;
      const targetY = 1.4 + driftY + mousePos.current.y * 0.18;
      const targetZ = 3.6;

      camera.position.x = THREE.MathUtils.lerp(camera.position.x, targetX, 0.05);
      camera.position.y = THREE.MathUtils.lerp(camera.position.y, targetY, 0.05);
      camera.position.z = THREE.MathUtils.lerp(camera.position.z, targetZ, 0.05);

      camera.lookAt(0, 1.2, -4);
    } else {
      camera.position.set(0, 1.4, 3.6);
      camera.lookAt(0, 1.2, -4);
    }
  });

  return null;
};

// Soft Volumetric Haze Planes
const VolumetricHaze: React.FC = () => {
  return (
    <group position={[0, 2, -3]}>
      <mesh position={[-2, 0, 0]}>
        <planeGeometry args={[6, 4]} />
        <meshBasicMaterial
          color="#FF8266"
          transparent
          opacity={0.035}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh position={[2, 0.5, -1]}>
        <planeGeometry args={[6, 4]} />
        <meshBasicMaterial
          color="#2DD4BF"
          transparent
          opacity={0.025}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
};

export const DojoScene: React.FC = () => {
  const lowPower = useAppStore((s) => s.lowPower);
  const qualityTier = useAppStore((s) => s.qualityTier);
  const [isTabVisible, setIsTabVisible] = useState(!document.hidden);
  const [isWebGLSupported, setIsWebGLSupported] = useState(true);

  // Check WebGL availability
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas');
      const gl =
        canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) {
        setIsWebGLSupported(false);
      }
    } catch {
      setIsWebGLSupported(false);
    }

    const handleVisibilityChange = () => {
      setIsTabVisible(!document.hidden);
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  if (!isWebGLSupported) {
    return <SceneFallback />;
  }

  // DPR clamp: [1, 1.5] for high/med, 1 for low
  const dpr = lowPower || qualityTier === 'low' ? 1 : Math.min(window.devicePixelRatio || 1, 1.5);

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 0,
        pointerEvents: 'none', // UI above stays fully clickable
        backgroundColor: '#0F1420',
      }}
      aria-hidden="true"
    >
      <WebGLErrorBoundary>
        <Canvas
          camera={{ position: [0, 1.4, 3.6], fov: 45 }}
          dpr={dpr}
          gl={{
            antialias: !lowPower,
            toneMapping: THREE.ACESFilmicToneMapping,
            toneMappingExposure: 0.9,
            powerPreference: lowPower ? 'low-power' : 'high-performance',
          }}
          frameloop={isTabVisible ? 'always' : 'never'}
        >
          {/* Exponential Dark Fog */}
          <fogExp2 attach="fog" args={['#0F1420', 0.045]} />

          {/* Ambient Lighting */}
          <ambientLight intensity={0.22} color="#151A28" />

          {/* Key Moonlight Directional */}
          <directionalLight
            position={[5, 8, 3]}
            intensity={0.4}
            color="#9CB3DB"
            castShadow={!lowPower && qualityTier === 'high'}
          />

          {/* Camera Rig & Parallax */}
          <CameraRig />

          {/* 3D Scene Layers */}
          <Floor />
          <Architecture />
          <Lanterns />
          <FloatingPanels />
          <Embers />
          <VolumetricHaze />

          {/* Post Processing */}
          <PostFX />
        </Canvas>
      </WebGLErrorBoundary>
    </div>
  );
};
