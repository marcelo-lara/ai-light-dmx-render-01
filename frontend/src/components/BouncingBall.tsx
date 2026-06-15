import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { MutableRefObject } from 'react';
import type { FixtureLocation } from '../hooks/useFixtures';

interface Props {
  meshRef: MutableRefObject<THREE.Mesh | null>;
  ballPositionRef: MutableRefObject<FixtureLocation>;
  overridePosition?: FixtureLocation | null;
}

export function BouncingBall({ meshRef, ballPositionRef, overridePosition = null }: Props) {
  useFrame(() => {
    if (!meshRef.current) return;
    const { x, y, z } = overridePosition ?? ballPositionRef.current;
    // Remap room coords → scene coords: room.z (height) → sceneY, room.y (depth) → sceneZ
    meshRef.current.position.set(x, z, y);
  });

  return (
    <mesh ref={meshRef} position={[0.5, 0.5, 0.5]}>
      <sphereGeometry args={[0.025, 16, 16]} />
      <meshStandardMaterial color="white" emissive="white" emissiveIntensity={0.6} />
    </mesh>
  );
}
