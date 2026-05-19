import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { RefObject } from 'react';
import type { Fixture } from '../hooks/useFixtures';

interface Props {
  fixtureData: Fixture;
  targetRef: RefObject<THREE.Mesh | null>;
  color: string;
}

export function MovingHead({ fixtureData, targetRef, color }: Props) {
  const baseRef = useRef<THREE.Group>(null); // pan  — Y rotation
  const headRef = useRef<THREE.Group>(null); // tilt — X rotation

  useFrame(() => {
    if (!targetRef.current || !baseRef.current || !headRef.current) return;

    const targetPos = targetRef.current.position;
    const dx = targetPos.x - fixtureData.location.x;
    const dy = targetPos.y - fixtureData.location.y;
    const dz = targetPos.z - fixtureData.location.z;

    // Pan: atan2 of X and Z displacement
    // TODO: clamp to physical fixture pan limits once ranges are confirmed
    const panAngle = THREE.MathUtils.clamp(Math.atan2(dx, dz), -Math.PI, Math.PI);
    baseRef.current.rotation.y = panAngle;

    // Tilt: atan2 of Y displacement and 2D Euclidean distance
    // TODO: clamp to physical fixture tilt limits once ranges are confirmed
    const distance2D = Math.hypot(dx, dz);
    const tiltAngle = THREE.MathUtils.clamp(
      Math.atan2(dy, distance2D),
      -Math.PI / 2,
      Math.PI / 2
    );
    headRef.current.rotation.x = -tiltAngle;
  });

  const { x, y, z } = fixtureData.location;

  return (
    <group position={[x, y, z]}>
      {/* Base — pans around Y axis */}
      <group ref={baseRef}>
        <mesh>
          <cylinderGeometry args={[0.04, 0.05, 0.08, 12]} />
          <meshStandardMaterial color="#1e1e2e" />
        </mesh>

        {/* Head — tilts around X axis, nested so it inherits pan */}
        <group ref={headRef} position={[0, 0.09, 0]}>
          <mesh>
            <boxGeometry args={[0.07, 0.12, 0.07]} />
            <meshStandardMaterial color="#2a2a3e" />
          </mesh>

          {/* Beam — thin at source, expands outward */}
          <mesh position={[0, 0.5, 0]}>
            <cylinderGeometry args={[0.05, 0.003, 1, 8]} />
            <meshBasicMaterial color={color} transparent opacity={0.65} />
          </mesh>
        </group>
      </group>
    </group>
  );
}
