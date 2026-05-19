import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { RefObject } from 'react';

const CLAMP_MIN = new THREE.Vector3(0, 0, 0);
const CLAMP_MAX = new THREE.Vector3(1, 1, 1);

interface Props {
  meshRef: RefObject<THREE.Mesh | null>;
}

export function BouncingBall({ meshRef }: Props) {
  const vel = useRef(new THREE.Vector3(0.004, 0.0031, 0.0025));

  useFrame(() => {
    if (!meshRef.current) return;
    const pos = meshRef.current.position;
    pos.add(vel.current);
    if (pos.x <= 0 || pos.x >= 1) vel.current.x *= -1;
    if (pos.y <= 0 || pos.y >= 1) vel.current.y *= -1;
    if (pos.z <= 0 || pos.z >= 1) vel.current.z *= -1;
    pos.clamp(CLAMP_MIN, CLAMP_MAX);
  });

  return (
    <mesh ref={meshRef} position={[0.5, 0.5, 0.5]}>
      <sphereGeometry args={[0.025, 16, 16]} />
      <meshStandardMaterial color="white" emissive="white" emissiveIntensity={0.6} />
    </mesh>
  );
}
