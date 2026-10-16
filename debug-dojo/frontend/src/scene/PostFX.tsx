import React from 'react';
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing';
import { useAppStore } from '../state/useAppStore';

export const PostFX: React.FC = () => {
  const lowPower = useAppStore((s) => s.lowPower);
  const qualityTier = useAppStore((s) => s.qualityTier);

  // Disable postprocessing entirely in low tier or low-power mode
  if (lowPower || qualityTier === 'low') {
    return null;
  }

  return (
    <EffectComposer multisampling={qualityTier === 'high' ? 4 : 0}>
      <Bloom
        intensity={0.55}
        luminanceThreshold={0.25}
        luminanceSmoothing={0.8}
        mipmapBlur
      />
      <Vignette eskil={false} offset={0.3} darkness={0.7} />
    </EffectComposer>
  );
};
