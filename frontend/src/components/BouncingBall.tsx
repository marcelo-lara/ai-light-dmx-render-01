import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { RefObject, MutableRefObject } from 'react';
import type { FixtureLocation } from '../hooks/useFixtures';

interface Props {
  meshRef: RefObject<THREE.Mesh | null>;
  ballPositionRef: MutableRefObject<FixtureLocation>;
}

export function BouncingBall({ meshRef, ballPositionRef }: Props) {
  useFrame(() => {
    if (!meshRef.current) return;
    const { x, y, z } = ballPositionRef.current;
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
